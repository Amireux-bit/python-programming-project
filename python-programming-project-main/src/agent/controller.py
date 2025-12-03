import uuid
import time
import json
import re
from agent.prompts import build_initial_prompt, final_answer_prompt, format_output
from agent.evidence_gate import evidence_sufficient, format_evidence_for_prompt
from agent.trace import TraceLogger
from agent.safety import safety_guard
from tools.calculator import CalculatorTool
from tools.search import SmartSearchTool
from agent.llm import QwenLLM
from pathlib import Path


class TravelAssistantController:
    def __init__(self, cal_tool, search_tool, config, llm=None, debug_mode: bool = False):
        """
        cal_tool: 计算器工具实例
        search_tool: 搜索工具实例
        config: dict 配置
        llm: 可选的 LLM 实例，默认创建 QwenLLM
        debug_mode: 若为 True，批量运行时每个 query 单独一个 trace 文件
        """
        self.llm = llm if llm is not None else QwenLLM()
        self.cal_tool = cal_tool
        self.search_tool = search_tool
        self.config = config
        self.debug_mode = debug_mode
        self.enable_safety = bool(config.get("enable_safety", True))
        self.trace = None
        
        # Action 解析重试配置
        self.max_parse_retries = config.get("max_parse_retries", 2)

    def run(self, user_query: str, run_id: str | None = None) -> dict:
        """
        主运行方法：输入用户查询，返回答案与 Trace
        """
        # ===== 1. 安全模块入口拦截 =====
        if self.enable_safety:
            should_block, safe_answer = safety_guard(user_query)
            if should_block:
                trace = {
                    "steps": [{
                        "step_id": 0,
                        "thought": "Safety module blocked the request.",
                        "action": {"tool_name": "SafetyGuard", "params": ""},
                        "observation": "Blocked by safety module.",
                        "evidence": []
                    }],
                    "final": {"answer": safe_answer, "status": "blocked_by_safety"}
                }
                return {
                    "id": str(uuid.uuid4()),
                    "user_query": user_query,
                    "status": "blocked",
                    "answer": safe_answer,
                    "latency_sec": 0.0,
                    "trace": trace
                }

        # 初始化 TraceLogger
        if self.debug_mode:
            tag = run_id or "run"
            self.trace = TraceLogger(debug_mode=True, run_tag=tag)
        else:
            if self.trace is None:
                self.trace = TraceLogger()

        context = self._init_context(user_query)

        for step_id in range(1, self.config.get("max_steps", 6) + 1):
            # 使用 Dynamic Injection 生成 thought 并解析 action
            thought, tool_name, params, parse_error = self._generate_and_parse_action(context)
            
            # 如果解析失败且重试后仍失败，记录错误并继续
            if parse_error:
                observation = f"Action 解析失败: {parse_error}"
                evidence_items = []
                scores = []
            else:
                observation, evidence_items, scores = self._execute_tool(tool_name, params)

            context["used_tools"].append(tool_name)
            context["observations"].append(observation)
            context["evidence"].extend(evidence_items)
            context["scores"].extend(scores)

            self.trace.log_step(
                step_id=step_id,
                thought=thought,
                tool_name=tool_name,
                params=params,
                observation=observation,
                evidence=evidence_items
            )

            # 证据门控判断
            max_steps = self.config.get("max_steps", 6)
            use_evidence_gate = self.config.get("use_evidence_gate", True)

            if step_id == max_steps:
                if not use_evidence_gate:
                    final_answer = self._final_answer(context)
                    self.trace.log_final(final_answer)
                    return {
                        "status": "success",
                        "answer": final_answer,
                        "trace": self.trace.get_trace()
                    }

                if evidence_sufficient(context["evidence"], self.config, context["used_tools"]):
                    final_answer = self._final_answer(context)
                    final_answer = format_output(final_answer)
                    self.trace.log_final(final_answer)
                    return {
                        "status": "success",
                        "answer": final_answer,
                        "trace": self.trace.get_trace()
                    }
                else:
                    fail_answer = self._fail_answer()
                    self.trace.log_final(fail_answer)
                    return {
                        "status": "failed",
                        "answer": fail_answer,
                        "trace": self.trace.get_trace()
                    }

    # ---------------- 内部方法 ----------------

    def _init_context(self, user_query: str) -> dict:
        """
        组合初始 Prompt 和上下文
        """
        prompt = build_initial_prompt(self.config, user_query)
        return {
            "system_prompt": prompt,
            "user_query": user_query,
            "observations": [],
            "evidence": [],
            "scores": [],
            "used_tools": [],
            "parse_errors": []  
        }

    def _generate_and_parse_action(self, context: dict) -> tuple:
        error_feedback = None
        
        for attempt in range(self.max_parse_retries + 1):
            thought = self._generate_thought(context, error_feedback)
            
            tool_name, params, parse_error = self._extract_action(thought)
            
            if parse_error is None:
                return thought, tool_name, params, None
            
            print(f"[重试 {attempt + 1}/{self.max_parse_retries}] 解析失败: {parse_error}")
            error_feedback = parse_error
            context["parse_errors"].append(parse_error)
        
        return thought, "UnknownTool", {}, parse_error

    def _generate_thought(self, context: dict, error_feedback: str = None) -> str:
        obs_text = "\n".join(
            [f"Step {i+1}: {o[:200]}..." if len(o) > 200 else f"Step {i+1}: {o}" 
             for i, o in enumerate(context["observations"])]
        ) if context["observations"] else "No observations yet"
        
        used_tools_text = ", ".join(context["used_tools"]) if context["used_tools"] else "None"
        
        prompt = (
            f"{context['system_prompt']}\n\n"
            f"User question: {context['user_query']}\n\n"
            f"Observations so far:\n{obs_text}\n\n"
            f"Tools already used: {used_tools_text}\n\n"
        )
        
        if error_feedback:
            prompt += (
                "=== ERROR FEEDBACK ===\n"
                f"Your previous output could not be parsed. Error: {error_feedback}\n\n"
                "Please fix the format and try again. Remember:\n"
                "- Output EXACTLY ONE LINE\n"
                "- Format: Search: {\"query\": \"...\"} or Calculator: {\"expression\": \"...\"}\n"
                "- Use straight double quotes (\"), not curly quotes\n"
                "- JSON must be valid and complete\n\n"
            )
        
        prompt += (
            "=== OUTPUT CONTRACT ===\n"
            "Please output your reasoning followed by the action:\n"
            "Thought: ...\n"
            "Action: Search: {...} OR Calculator: {...}\n\n"
            "Your response:"
        )
        
        llm_output = self.llm.generate(
            prompt,
            temperature=self.config.get("temperature", 0.1)
        )
        return llm_output.strip()

    def _extract_action(self, thought: str) -> tuple:
        thought = thought.strip()
        
        # 1. 优先寻找 "Action:" 标记
        action_match = re.search(r'Action:\s*(.*)', thought, re.DOTALL | re.IGNORECASE)
        if action_match:
            action_line = action_match.group(1).strip()
        else:
            # 2. 如果没有 Action 标记，尝试取最后一行（兼容旧模式）
            lines = thought.strip().split('\n')
            action_line = lines[-1].strip()

        # 定义工具调用的正则模式 (针对 action_line)
        patterns = [
            r'^(Search|Calculator)\s*:\s*(\{.*\})\s*$',
            r'(Search|Calculator)\s*:\s*(\{[^}]+\})'
        ]
        
        lines = thought.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            line = self._clean_line(line)
            
            for pattern in patterns:
                match = re.search(pattern, action_line, re.IGNORECASE)
                if match:
                    tool_name = match.group(1).strip()
                    json_str = match.group(2).strip()
                    
                    tool_name = self._normalize_tool_name(tool_name)
                    
                    try:
                        params_dict = json.loads(json_str)
                        if tool_name == "Search":
                           params = params_dict.get("query", "")
                        elif tool_name == "Calculator":
                           params = params_dict.get("expression", "")
                        else:
                           params = params_dict
                        return tool_name, params, None
                        
                    except json.JSONDecodeError as e:
                        fixed_json = self._try_fix_json(json_str)
                        if fixed_json:
                            try:
                                params_dict = json.loads(fixed_json)
                                if tool_name == "Search":
                                    params = params_dict.get("query", "")
                                elif tool_name == "Calculator":
                                    params = params_dict.get("expression", "")
                                else:
                                    params = params_dict
                                print(f"[解析成功-修复后] {tool_name}: {params}")
                                return tool_name, params, None
                            except:
                                pass
                        
                        return None, None, f"JSON 解析失败: {str(e)}. 原始内容: {json_str[:100]}"
        
        return None, None, f"未找到有效的工具调用格式. 原始输出: {thought[:200]}"

    def _clean_line(self, line: str) -> str:
        line = re.sub(r'```\w*', '', line)
        line = line.replace('```', '')
        
        line = line.replace('：', ':')
        
        line = line.replace('"', '"').replace('"', '"')
        line = line.replace(''', "'").replace(''', "'")
        
        line = line.replace('｛', '{').replace('｝', '}')
        
        return line.strip()

    def _normalize_tool_name(self, tool_name: str) -> str:
        tool_name = tool_name.strip().lower()
        
        if tool_name in ['search', 'searchl', '搜索']:
            return 'Search'
        elif tool_name in ['calculator', 'calc', 'calculate', '计算器', '计算']:
            return 'Calculator'
        else:
            return tool_name.capitalize()

    def _try_fix_json(self, json_str: str) -> str:
        """
        尝试修复常见的 JSON 格式问题
        """
        original = json_str
        
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
        
        json_str = re.sub(r'{\s*(\w+)\s*:', r'{"\1":', json_str)
        json_str = re.sub(r',\s*(\w+)\s*:', r', "\1":', json_str)
        
        if json_str != original:
            print(f"[JSON修复] {original} -> {json_str}")
        
        return json_str

    def _execute_tool(self, tool_name: str, params) -> tuple:
        if tool_name == "Calculator":
            tool = self.cal_tool
        elif tool_name == "Search":
            tool = self.search_tool
        else:
            return f"Tool '{tool_name}' not found. Available tools: Search, Calculator", [], []

        try:
            if isinstance(tool, SmartSearchTool) and not self.config.get("enable_search", True):
                msg = "当前配置禁止使用 Search，请根据已有证据回答。"
                return msg, [], []

            if isinstance(tool, CalculatorTool):
                raw_result = tool.run(expression=params)
                result_dict = json.loads(raw_result)

                if result_dict.get("status") == "SUCCESS":
                    return result_dict.get("result", "计算失败"), [], []
                else:
                    return f"计算错误: {result_dict.get('error', '未知错误')}", [], []

            elif isinstance(tool, SmartSearchTool):
                raw_result = tool.run(query=params)
                print(f"[调试] Search 原始结果: {raw_result[:500]}...")
                result_dict = json.loads(raw_result)

                if result_dict.get("status") == "SUCCESS":
                    results = result_dict.get("results", [])
                    observation = "\n".join([f"- {r.get('content', '')}" for r in results])
                    evidence = [{
                        "content": r.get("content", ""),
                        "source": r.get("source", ""),
                        "score": r.get("score", 0.0)
                    } for r in results]
                    scores = [r.get("score", 0.0) for r in results]
                    return observation, evidence, scores
                else:
                    return f"搜索失败: {result_dict.get('error', '未知错误')}", [], []
            else:
                return f"Unknown tool type: {tool_name}", [], []

        except json.JSONDecodeError as e:
            return f"工具返回 JSON 解析失败: {str(e)}", [], []
        except Exception as e:
            return f"工具执行错误: {str(e)}", [], []

    def _final_answer(self, context: dict) -> str:
        evidence_str = format_evidence_for_prompt(context["evidence"])
        prompt = final_answer_prompt(evidence_str, context["user_query"])
        return self.llm.generate(prompt, temperature=0.2)

    def _fail_answer(self) -> str:
        return "抱歉，我无法提供高可信度的回答，因为当前证据不足。"