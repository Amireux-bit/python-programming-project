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
        "**强制执行的搜索顺序**（每步只调用一次，关键词必须精确）：\n"
        "1. Search: 航班信息\n"
        "   例如：'Paris flight price' 或 'Paris airfare cost'\n"
        "2. Search: 酒店信息\n"
        "   例如：'paris hotel'\n"
        "3. Search: 景点\n"
        "   例如：'what attractions in Paris' 或 'Paris sightseeing spots'\n"
        "4. Search: 餐饮\n"
        "   例如：'paris food' 或 'paris restaurants'\n"
        "5. Calculator: 计算总预算\n"
        "   表达式示例：'2000 + 250 + 1000 + 430'\n\n"
        "请保证calculator的调用在得到了航班酒店景点餐饮信息之后立刻进行。calculator的调用是为了计算最后的总预算，请保证总预算的估计是由calculator计算的。\n"
        "不要进行重复的信息的搜索"
        "**严格规则**：\n"
        "- 禁止搜索 'itinerary'、'travel guide'、'trip' 等泛化词汇\n"
        "- 每次搜索必须针对一个具体类别（住宿/交通/餐饮/景点）\n"
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
        "- 不要编造数字，所有价格必须基于证据，你的证据需要把来源提供出来，而不是简单的说基于证据2这样，应该是直接给出具体的来源URL\n"
        "- 答案必须简洁明了，直接回应用户问题\n"
        "如果提到酒店，需要给出酒店名字\n"
        "需要非常详细的行程安排，还有预算。"
    )