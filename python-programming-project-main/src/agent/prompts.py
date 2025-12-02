import re

def format_output(text: str) -> str:
    """
    将 Markdown 格式的文本转换为干净的纯文本
    """
    # 移除 Markdown 标题符号 (###, ##, #)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    
    # 移除加粗符号 (**text** 或 __text__)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    
    # 移除斜体符号 (*text* 或 _text_)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', text)
    
    # 移除分隔线 (---, ***, ___)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # 移除列表符号 (- 或 * 开头)，替换为 • 
    text = re.sub(r'^\s*[-*]\s+', '• ', text, flags=re.MULTILINE)
    
    # 移除数字列表符号 (1. 2. 等)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # 移除代码块标记 (```)
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # 移除行内代码标记 (`code`)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 移除链接格式 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # 将多个换行符替换为两个换行符
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 移除空白行
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '\n'.join(lines)
    
    return text.strip()



def build_initial_prompt(config: dict, user_query: str) -> str:
    """
    组合初始Prompt（系统规则 + 工具说明 + 用户问题）
    """
    return "\n".join([
        system_prompt(),
        developer_prompt(),
        f"用户问题: {user_query}"
    ])


def system_prompt() -> str:
    return (
        "You are a general-purpose assistant capable of solving complex, multi-domain tasks "
        "(travel, technology, education, business, etc.). "
        "Your reasoning must begin by breaking down the user's overall request into clear, ordered, non-overlapping substeps, "
        "and then completing them with multi-step tool calls.\n"

        "Core workflow:\n"
        "1. Analyze the user query and determine the essential substeps required.\n"
        "2. Keep track of which substeps are finished and which are still missing.\n"
        "3. Execute substeps in order without skipping or redoing completed ones.\n"
        "4. Use Search to gather facts and numeric values. If evidence contains irrelevant or unrelated data, "
        "explicitly discard it and focus only on the parts relevant to the current substep.\n"
        "5. Use Calculator strictly for numeric arithmetic when ALL required numeric inputs are present.\n"
        "6. After all substeps are complete, synthesize a concise final answer.\n"

        "Strict rules:\n"
        "- Do not repeat identical or semantically equivalent searches more than once per substep.\n"
        "- If the current substep cannot yield relevant results after two reformulations, switch to the next incomplete substep.\n"
        "- Never fabricate data; all numbers must come directly from Search evidence.\n"
        "- Calculator expressions must contain ONLY digits and +-*/(), with no variables or currency symbols.\n"
        "- If the evidence includes unrelated locations/topics, filter them out and use only relevant portions.\n"
        "- The final answer must cite at least one real source (URL or named source) consistent with the evidence.\n"
        "- If no high-confidence evidence (score >= 0.8 or configured threshold) exists for a required fact, "
        "explicitly state the limitation instead of guessing.\n"

        "Travel example (other tasks should create their own substeps):\n"
        "1. Search: hotel price per night (city-specific)\n"
        "2. Search: attractions ticket prices (city-specific)\n"
        "3. Search: daily food budget (city-specific)\n"
        "4. Calculator: compute total budget based only on numeric evidence"
        "5. Final synthesis with citations"
    )

def developer_prompt() -> str:
    return (
        "Available tools:\n"
        "- Search: {\"query\": \"precise and relevant search keywords\"}\n"
        "- Calculator: {\"expression\": \"numeric expression with only digits and +-*/()\"}\n"

        "Output format (MUST be exactly one single line with no extra text):\n"
        "Search: {\"query\": \"...\"}\n"
        "Calculator: {\"expression\": \"120*5 + 150 + 60*5\"}\n"

        "Additional guidance:\n"
        "- Before using Search, confirm the current substep still lacks required facts; if it is already completed, move to the next substep.\n"
        "- Use Search to obtain numeric data; if irrelevant or unrelated details appear, discard them in your reasoning and focus only on what matters.\n"
        "- Only call Calculator after ALL required numeric inputs are explicitly extracted from relevant evidence.\n"
        "- After using Calculator, do not call Search again—proceed directly to the final answer.\n"
        "- For non-travel tasks, plan your own sensible substeps while following the same tool and output rules.\n"
        "- If evidence confidence is low or unrelated to the query target, reformulate the query and retry; "
        "after two failed attempts, switch to the next substep.\n"
    )

def final_answer_prompt(evidence_text: str, user_query: str) -> str:
    return (
        "You are a general-purpose assistant. All necessary information has been collected. "
        "Write the final answer strictly grounded in the evidence provided below.\n"
        f"User query:\n{user_query}\n"
        f"Evidence:\n{evidence_text}\n"
        "Requirements:\n"
        "- Use ONLY the evidence that is relevant to the current task/topic; explicitly ignore or omit unrelated parts.\n"
        "- Cite at least one real source (URL or named source) inline or at the end.\n"
        "- Do not fabricate numbers; all figures must come directly from the relevant evidence. "
        "If Calculator was used, reuse its exact result for totals.\n"
        "- Keep the answer concise and directly address the user's goals.\n"
        "- If the task involves costs, provide a clear breakdown (e.g., hotel per night * nights, attractions, food per day * days) and the total.\n"
        "- If evidence confidence is insufficient, state the limitation openly.\n"
    )
