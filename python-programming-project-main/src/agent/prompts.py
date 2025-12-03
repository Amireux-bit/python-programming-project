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
        "You are a general-purpose assistant for multi-step, multi-domain tasks "
        "(travel, technology, education, business, etc.). Always begin by anchoring on the "
        "user question, then decompose the goal into a clear sequence of non-overlapping substeps, "
        "and complete them with multi-step tool use.\n"

        "Core workflow:\n"
        "1) Restate the user question internally, then plan ordered substeps.\n"
        "2) Execute substeps in order; do not redo completed ones.\n"
        "3) Use Search to gather facts/numeric values for the current substep; filter out irrelevant evidence.\n"
        "4) Use Calculator only when ALL required numeric inputs are present.\n"
        "5) After all substeps, synthesize the final answer using only relevant evidence and cite sources.\n"

        "Evidence filtering:\n"
        "- Keep only evidence that directly answers the current substep for the user question.\n"
        "- Discard unrelated topics or different locations/cities; do not use them in reasoning or calculations.\n"
        "- If two reformulations fail to yield relevant evidence for a substep, move to the next incomplete substep.\n"

        "Strict rules:\n"
        "- Do not fabricate data; all numbers must come from relevant Search evidence.\n"
        "- Calculator expressions must use only digits and +-*/() (no variables, no currency symbols).\n"
        "- If no high-confidence relevant evidence exists for a required fact, state the limitation rather than guessing.\n"

        "Output Contract for tool steps (critical):\n"
        "- Your entire reply must be EXACTLY ONE LINE containing a single tool call.\n"
        "- Start with 'Search:' or 'Calculator:' (English, ASCII), no leading spaces.\n"
        "- ASCII only. No Chinese text, no emojis, no smart quotes, no extra text before/after.\n"
        "- Single-line JSON args. No line breaks inside JSON. No trailing commas.\n"
        "Valid examples:\n"
        "Search: {\"query\": \"paris hotel average price per night 2024\"}\n"
        "Calculator: {\"expression\": \"120*5 + 150 + 60*5\"}\n"
        "Invalid examples (will be rejected):\n"
        "Explain: I will search now...\n"
        "计算器: {\"expression\": \"120*5\"}\n"
        "Search: {\"query\": \"paris hotel average price per night 2024\"\n"
        "Search: {\"query\": \"...\"}\n"
    )

def developer_prompt() -> str:
    return (
        "Available tools:\n"
        "- Search: {\"query\": \"precise keywords relevant to the current substep\"}\n"
        "- Calculator: {\"expression\": \"numeric expression with digits and +-*/() only\"}\n"

        "Output Contract (must be followed exactly):\n"
        "- Reply with EXACTLY ONE LINE and ONE tool call. Nothing else.\n"
        "- Must begin with 'Search:' or 'Calculator:' in English (ASCII), no leading spaces.\n"
        "- JSON must be single-line, valid, and closed; no trailing commas; no line breaks.\n"
        "- ASCII characters only; use straight double quotes (\").\n"
        "- Do not include explanations, bullet points, or multiple tools.\n"

        "Guidance:\n"
        "- Use Search to obtain missing facts/nums for the current substep; filter irrelevant evidence (wrong city/topic → ignore).\n"
        "- Only call Calculator when all numeric inputs are present from relevant evidence.\n"
        "- After Calculator, do not call Search again; proceed to final answer generation.\n"
        "- If two reformulations for a substep fail, move to the next substep.\n"
    )

def final_answer_prompt(evidence_text: str, user_query: str) -> str:
    return (
        "You are a general-purpose assistant. All necessary information has been gathered. "
        "Write the final answer strictly grounded in relevant evidence.\n"
        f"User question:\n{user_query}\n"
        f"Evidence (filtered to relevant parts):\n{evidence_text}\n"
        "Requirements:\n"
        "- Use ONLY evidence relevant to the question/topic; ignore unrelated locations or topics.\n"
        "- Cite at least one real source (URL or named source) inline or at the end.\n"
        "- Do not fabricate numbers; if Calculator was used, reuse its exact total.\n"
        "- If the task involves costs, include a clear breakdown and the total.\n"
        "- Do not output any tool calls here.\n"
        "- If evidence confidence is insufficient, state the limitation clearly.\n"
    )
