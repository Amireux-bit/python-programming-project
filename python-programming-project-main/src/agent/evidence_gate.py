def evidence_sufficient(evidence_list: list, config: dict, used_tools: list) -> bool:
    """
    证据充足性判定：
    1. 来源数量 >= min_sources
    2. 最高相关性 >= relevance_threshold
    3. 包含价格信息（新增）
    """
    high_quality_evidence = [e for e in evidence_list if e.get("score", 0) > 0.7]
    # 只用了 Calculator，直接通过
    if all(tool == "Calculator" for tool in used_tools):
        return True
    
    # 过滤 Search 证据
    search_evidence = [e for e in high_quality_evidence if e.get("source")]
    
    if not search_evidence:
        return False

    # 检查来源数量
    unique_sources = set(e.get("source") for e in search_evidence)
    if len(unique_sources) < config.get("min_sources", 0):
        print(f"[证据门控] ❌ 来源不足: {len(unique_sources)}/{config.get('min_sources', 2)}")
        return False

    # 检查相关性
    max_rel = max(e.get("score", 0.0) for e in search_evidence)
    if max_rel < config.get("relevance_threshold", 0.8):
        print(f"[证据门控] ❌ 相关性不足: {max_rel}/{config.get('relevance_threshold', 0.8)}")
        return False

    print(f"[证据门控] ✅ 通过检查")
    return True


def has_price_information(evidence_list: list) -> bool:
    """
    检查证据中是否包含价格信息
    """
    price_keywords = [
        '$', '€', '¥', '元', 'yuan', 'rmb', 'CNY',
        'price', 'cost', 'budget', 'fee', 'fare',
        'per night', 'per day', '/night', '/day',
        'starting at', 'from'
    ]
    
    combined_text = " ".join([e.get("content", "").lower() for e in evidence_list])
    
    # 至少匹配 3 个价格关键词
    matches = sum(1 for keyword in price_keywords if keyword.lower() in combined_text)
    has_price = matches >= 3
    
    print(f"[价格检测] 关键词匹配数: {matches}/3")
    return has_price


def format_evidence_for_prompt(evidence_list: list) -> str:
    """
    格式化证据供 Prompt 使用
    """
    result = []
    for i, e in enumerate(evidence_list, 1):
        result.append(f"[证据{i}] {e.get('content', '')} (来源: {e.get('source', 'Unknown')})")
    return "\n".join(result)