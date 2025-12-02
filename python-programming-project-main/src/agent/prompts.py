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
        "你是一位旅行助手，必须通过多步工具调用收集完整信息。\n\n"
        "**强制执行的搜索顺序**（请记住每步只调用一次，关键词必须精确）：\n"
        "1. Search: 酒店信息\n"
        "   例如：'paris hotel'\n"
        "2. Search: 景点\n"
        "   例如：'what attractions in Paris' 或 'Paris sightseeing spots'\n"
        "3. Search: 餐饮\n"
        "   例如：'paris food' 或 'paris restaurants'\n"
        "4. Calculator: 计算总预算\n"
        "   表达式示例：'2000 + 250 + 1000 + 430'\n\n"
        "请保证calculator的调用在得到了酒店景点餐饮信息之后立刻进行。calculator的调用是为了计算最后的总预算，请保证总预算的估计是由calculator计算的。\n"
        "一定一定要遵守不要进行重复的信息的搜索，在你得到了酒店景点餐饮信息之后，不要再搜索酒店景点餐饮信息相关的信息。\n\n"
        "**严格规则**：\n"
        "- 禁止搜索 'itinerary'、'travel guide'、'trip' 等泛化词汇\n"
        "- 每次搜索必须针对一个具体类别（住宿/餐饮/景点）\n"
        "- 最终答案必须引用至少一个来源 URL\n"
        "- 所有价格必须基于搜索结果，禁止编造数字，最后的总预算结果必须来源于calculator的计算。\n"
    )


def developer_prompt() -> str:
    """
    开发者提示：工具使用说明
    """
    return (
        "可用工具及调用格式（严格遵守）：\n"
        "1. Search: {\"query\": \"搜索内容\"}\n"
        "2. Calculator: {\"expression\": \"数学表达式\"}\n\n"
        "输出格式要求（必须严格遵守）：\n"
        "- 第一行：工具名: JSON参数\n"
        "- 不要添加任何额外说明或步骤编号\n\n"
        "正确示例：\n"
        "Search: {\"query\": \"hotels in Paris budget\"}\n"
        "Calculator: {\"expression\": \"5000 - 2000\"}\n\n"
        "但是你不要完全仿照示例，因为示例只是一个简单的参考，真实情况中你需要提一个具体的搜索内容。\n"
        "错误示例（不要这样）：\n"
        "❌ Step 1: Search: {\"query\": \"...\"}\n"
        "❌ 我需要搜索...\n"
        "❌ 使用Search工具查找...\n\n"
        "注意：Calculator 不提供证据，Search 提供 content、source 和 score。"
    )


def final_answer_prompt(evidence_text: str, user_query: str) -> str:
    """
    生成最终答案的Prompt（不包含工具调用说明）
    """
    return (
        "你是一位旅行助手。现在所有信息已收集完毕，请基于以下证据生成最终的旅行建议。\n\n"
        f"用户问题: {user_query}\n\n"
        f"已收集的证据：\n{evidence_text}\n\n"
        "引用至少一个真实来源(URL)\n\n"
        "注意：\n"
        "- 不要输出任何工具调用格式\n"
        "- 不要编造数字，所有价格必须基于证据\n"
        "- 答案必须简洁明了，直接回应用户问题\n"
        "需要非常详细的行程安排，还有预算。"
    )