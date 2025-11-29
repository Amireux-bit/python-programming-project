# 安全模块（检测 + 生成拒绝回答）

# src/agent/safety.py

from typing import Dict, Tuple


# 一些简单的关键词规则（可以在报告里说是“rule-based safety module”）
PROMPT_LEAK_KEYWORDS = [
    "system prompt", "hidden system message", "隐藏的系统提示",
    "你是一位旅行助手", "强制执行的搜索顺序"
]

INJECTION_KEYWORDS = [
    "ignore all previous instructions",
    "ignore previous instructions",
    "override all previous rules",
    "越狱", "解除所有限制", "忽略以上所有规则"
]

SQL_KEYWORDS = [
    "drop table", "delete from", "truncate table",
    "sql injection", "sql 注入"
]

SECRET_KEYWORDS = [
    "api key", "token", "secret", "password",
    "密钥", "口令", "密码"
]

ILLEGAL_KEYWORDS = [
    "illegal", "违法", "犯罪", "exploit vulnerabilities",
    "hack", "黑客攻击", "欺诈", "fraud"
]


def analyze_query_for_risk(user_query: str) -> Dict[str, bool]:
    """
    输入用户的原始问题，输出各类风险的布尔值。
    这里只做非常简单的关键词匹配，方便在报告里解释。
    """
    text = user_query.lower()

    def contains_any(text: str, keywords):
        return any(k.lower() in text for k in keywords)

    risk = {
        "prompt_leak": contains_any(text, PROMPT_LEAK_KEYWORDS),
        "injection": contains_any(text, INJECTION_KEYWORDS),
        "sql": contains_any(text, SQL_KEYWORDS),
        "secret": contains_any(text, SECRET_KEYWORDS),
        "illegal": contains_any(text, ILLEGAL_KEYWORDS),
    }
    risk["has_risk"] = any(risk.values())
    return risk


def safety_guard(user_query: str) -> Tuple[bool, str]:

    """
    安全总控函数：
    - 返回 (should_block, safe_answer)
    - should_block = True 表示直接拦截，不让 Agent 继续调用工具/LLM
    """
    risk = analyze_query_for_risk(user_query)

    if not risk["has_risk"]:
        return False, ""

    # 根据不同风险类型给出稍微不一样的拒绝话术
    if risk["prompt_leak"]:
        reason = "系统提示与内部指令是保密内容，不能直接展示。"
    elif risk["sql"]:
        reason = "不能提供删除数据库或破坏系统的 SQL 指令。"
    elif risk["secret"]:
        reason = "不能访问或泄露任何 API 密钥、密码或隐私数据。"
    elif risk["illegal"]:
        reason = "不能提供违法或具有欺诈性质的操作建议。"
    else:
        reason = "该请求可能存在安全风险，无法直接执行。"

    safe_answer = (
        "出于安全考虑，我不能按照你的这个请求去执行或给出具体操作。"
        f"{reason}\n\n"
        "如果你有正常的旅行规划、预算或行程相关的问题，我很乐意帮你。"
    )
    return True, safe_answer
