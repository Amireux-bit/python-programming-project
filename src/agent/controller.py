import uuid
import time
import json
from agent.prompts import build_initial_prompt, final_answer_prompt
from agent.evidence_gate import evidence_sufficient, format_evidence_for_prompt
from agent.trace import TraceLogger
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from agent.llm import QwenLLM
from pathlib import Path

class TravelAssistantController:
    def __init__(self, cal_tool, search_tool, config, llm=None):
        """
        cal_tool: 计算器工具实例
        search_tool: 搜索工具实例
        config: dict 配置
        llm: 可选的 LLM 实例，默认创建 QwenLLM
        """
        self.llm = llm if llm is not None else QwenLLM()
        self.cal_tool = cal_tool
        self.search_tool = search_tool
        self.config = config
        self.trace = TraceLogger()

    def run(self, user_query: str) -> dict:
        """
        主运行方法：输入用户查询，返回答案与 Trace
        """
        context = self._init_context(user_query)
        min_steps = self.config.get("min_steps", 3)  # 新增

        for step_id in range(1, self.config.get("max_steps", 6) + 1):
            thought = self._generate_thought(context)
            tool_name, params = self._decide_action(thought)
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

            # 证据门控判断（增加最小步数限制）
            if step_id == self.config.get("max_steps", 6):
                if evidence_sufficient(context["evidence"], self.config, context["used_tools"]):
                   final_answer = self._final_answer(context)
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
        组合初始Prompt和上下文
        """
        prompt = build_initial_prompt(self.config, user_query)
        return {
            "system_prompt": prompt,
            "user_query": user_query,
            "observations": [],
            "evidence": [],
            "scores": [],  
            "used_tools": []
        }

    def _generate_thought(self, context: dict) -> str:
        """
        LLM生成下一步思路（Thought→Action）
        """
        obs_text = "\n".join(
            [f"Step {i+1}: {o}" for i, o in enumerate(context["observations"])]
        ) if context["observations"] else "暂无观察结果"
        
        used_tools_text = ", ".join(context["used_tools"]) if context["used_tools"] else "无"
        
        prompt = (
        f"{context['system_prompt']}\n\n"
        f"用户的问题: {context['user_query']}\n\n"
        f"目前已知信息:\n{obs_text}\n\n"
        f"已调用过的工具: {used_tools_text}\n\n"
        "**重要**：如果当前信息中缺少具体的价格数据（如住宿、交通、餐饮费用），\n"
        "你必须继续调用 Search 工具获取详细价格，不能编造数字。\n\n"
        "现在请输出下一步工具调用（只输出一行，严格按格式）：\n"
        "工具名: JSON参数"
    )
        
        llm_output = self.llm.generate(
            prompt, 
            temperature=self.config.get("temperature", 0.1)  # 降低温度
        )
        return llm_output.strip()

    def _decide_action(self, thought: str):
        """
        从Thought解析工具名和参数（JSON）
        """
        try:
            # 只取第一行并清理
            first_line = thought.split('\n')[0].strip()
            
            # 移除可能的markdown代码块标记
            first_line = first_line.replace('```', '').replace('json', '')
            
            if ':' not in first_line:
                print(f"[警告] 格式错误，缺少冒号: {first_line}")
                raise ValueError("格式错误")
            
            parts = first_line.split(":", 1)
            tool_name = parts[0].strip()
            params_str = parts[1].strip()
            
            params_dict = json.loads(params_str)
            
            if tool_name == "Search":
                params = params_dict.get("query", "")
            elif tool_name == "Calculator":
                params = params_dict.get("expression", "")
            else:
                params = params_dict
            
            print(f"[调试] 解析成功: {tool_name} -> {params}")
                
        except Exception as e:
            print(f"[错误] 解析失败: {e}")
            print(f"[原始输出]: {thought[:300]}")
            tool_name, params = "UnknownTool", {}
            
        return tool_name, params

    def _execute_tool(self, tool_name: str, params: dict):
        """
        调用工具并返回观察结果和证据
        """
        if tool_name == "Calculator":
            tool = self.cal_tool
        elif tool_name == "Search":
            tool = self.search_tool
        else:
            return f"Tool {tool_name} not found.", [], []
        
        try:
            # 执行工具
            if isinstance(tool, CalculatorTool):
                raw_result = tool.run(expression=params)
                result_dict = json.loads(raw_result)
                
                if result_dict.get("status") == "SUCCESS":
                    return result_dict.get("result", "计算失败"), [], []
                else:
                    return f"计算错误: {result_dict.get('error', '未知错误')}", [], []
                    
            elif isinstance(tool, SearchTool):
                raw_result = tool.run(query=params)
                print(f"[调试] Search 原始结果: {raw_result}") 
                result_dict = json.loads(raw_result)
                print(f"[DEBUG] Search工具解析后:\n{json.dumps(result_dict, ensure_ascii=False, indent=2)}\n")
                if result_dict.get("status") == "SUCCESS":
                    results = result_dict.get("results", [])
                    
                    # 直接使用content作为observation
                    observation = "\n".join([f"- {r.get('content', '')}" for r in results])
                    
                    # source作为证据，同时包含score
                    evidence = [
                        {
                            "content": r.get("content", ""), 
                            "source": r.get("source", ""),
                            "score": r.get("score", 0.0)  # 添加这一行
                        } 
                        for r in results
                    ]
                    
                    # score直接传入
                    scores = [r.get("score", 0.0) for r in results]
                    
                    return observation, evidence, scores
                else:
                    return f"搜索失败: {result_dict.get('error', '未知错误')}", [], []
            else:
                return f"Unknown tool type: {tool_name}", [], []
                
        except json.JSONDecodeError as e:
            return f"工具返回JSON解析失败: {str(e)}", [], []
        except Exception as e:
            return f"工具执行错误: {str(e)}", [], []
            

    def _final_answer(self, context: dict) -> str:
        """
        根据证据生成最终答案（带引用）
        """
        evidence_str = format_evidence_for_prompt(context["evidence"])
        prompt = final_answer_prompt(evidence_str, context["user_query"])  
        return self.llm.generate(prompt, temperature=0.2)

    def _fail_answer(self) -> str:

        return "抱歉，我无法提供高可信度的旅行建议，因为当前证据不足。"
