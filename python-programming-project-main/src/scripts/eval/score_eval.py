# src/eval/score_eval.py

import sys
import json
import argparse
import statistics
from pathlib import Path
from collections import Counter, defaultdict
import re

# ---- 确保可以 import 到 agent 里的工具函数 ----
src_dir = Path(__file__).parent.parent  # 指向 src 目录
sys.path.insert(0, str(src_dir))

try:
    from agent.evidence_gate import has_price_information
except Exception:
    # 如果导入失败，就在本脚本里写一个兜底版本
    def has_price_information(evidence_list):
        price_keywords = [
            '$', '€', '¥', '元', 'yuan', 'rmb', 'cny',
            'price', 'cost', 'budget', 'fee', 'fare',
            'per night', 'per day', '/night', '/day',
            'starting at', 'from'
        ]
        combined_text = " ".join([e.get("content", "").lower() for e in evidence_list])
        matches = sum(1 for kw in price_keywords if kw.lower() in combined_text)
        return matches >= 3


# ---------------- 文本匹配指标：EM / F1 ----------------

def _normalize_text(s: str) -> str:
    """简单清洗：小写、去标点、去多余空格"""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff\s]", " ", s)  # 保留英文数字和中文
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compute_em_f1(pred: str, gold: str):
    """返回 (EM, F1)。如果没有 gold，就返回 (None, None)。"""
    if gold is None or gold == "":
        return None, None

    norm_pred = _normalize_text(pred)
    norm_gold = _normalize_text(gold)

    # EM
    em = 1.0 if norm_pred == norm_gold else 0.0

    # F1
    pred_tokens = norm_pred.split()
    gold_tokens = norm_gold.split()
    if not pred_tokens or not gold_tokens:
        return em, 0.0

    common = 0
    gold_counts = Counter(gold_tokens)
    for t in pred_tokens:
        if gold_counts[t] > 0:
            common += 1
            gold_counts[t] -= 1

    precision = common / len(pred_tokens)
    recall = common / len(gold_tokens)
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return em, f1


# ---------------- 安全 / 注入 检测（简单版） ----------------

SUSPICIOUS_PATTERNS = [
    "ignore previous", "ignore all previous", "system prompt",
    "override instructions", "sudo", "drop table", "delete from",
    "union select", "shutdown", "format c:", "--", "#!", ";--"
]

def detect_prompt_injection(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(pat in t for pat in SUSPICIOUS_PATTERNS)


# ---------------- 评分主逻辑 ----------------

def load_results(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_gold(path: Path | None):
    """gold 文件可选。如果存在，构建 id -> gold 的字典"""
    if path is None:
        return {}

    with open(path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    gold_map = {}
    for item in gold_data:
        qid = item.get("id")
        if qid is None:
            continue
        gold_map[qid] = {
            "gold_answer": item.get("gold_answer"),
            "gold_sources": item.get("gold_sources", [])
        }
    return gold_map


def compute_per_query_score(record, gold_item=None, latency_threshold=240.0):
    """
    设计一个 0-100 的综合分：
    - 40% 成功与否（status）
    - 30% 证据质量（来源数、score、是否含价格）
    - 20% 工具使用合理性（Search 足够 + Calculator 至少一次，无 UnknownTool）
    - 10% 延迟（是否低于阈值）
    """
    qid = record.get("id")
    status = record.get("status")
    success = 1 if status == "success" else 0

    trace = record.get("trace", {})
    steps = trace.get("steps", [])
    tools = [s.get("action", {}).get("tool_name", "") for s in steps]

    # 工具使用
    used_search = tools.count("Search")
    used_calc = tools.count("Calculator")
    tool_ok = 1 if used_search >= 3 and used_calc >= 1 and "UnknownTool" not in tools else 0

    # 证据统计
    all_evidence = []
    for s in steps:
        all_evidence.extend(s.get("evidence", []))

    unique_sources = len({e.get("source") for e in all_evidence if e.get("source")})
    max_score = max([e.get("score", 0.0) for e in all_evidence], default=0.0)
    price_ok = 1 if has_price_information(all_evidence) else 0
    evidence_ok = 1 if (unique_sources >= 2 and max_score >= 0.7 and price_ok) else 0

    # 延迟
    latency = record.get("latency_sec", 0.0)
    latency_ok = 1 if latency <= latency_threshold else 0

    # 文本匹配（可选，用于分析，不直接进综合分）
    em, f1 = None, None
    if gold_item is not None:
        em, f1 = compute_em_f1(
            record.get("answer", ""),
            gold_item.get("gold_answer", "")
        )

    # 简单综合分
    total_score = 100 * (0.4 * success + 0.3 * evidence_ok + 0.2 * tool_ok + 0.1 * latency_ok)

    # 注入检测
    answer = record.get("answer", "")
    user_query = record.get("user_query", "")
    injection_flag = detect_prompt_injection(answer) or detect_prompt_injection(user_query)

    return {
        "id": qid,
        "success": success,
        "evidence_ok": evidence_ok,
        "tool_ok": tool_ok,
        "latency_ok": latency_ok,
        "latency_sec": latency,
        "unique_sources": unique_sources,
        "max_evidence_score": max_score,
        "has_price_info": price_ok,
        "em": em,
        "f1": f1,
        "total_score": total_score,
        "possible_injection": injection_flag,
        "difficulty": record.get("difficulty", "unknown"),
        "scenario": record.get("scenario", "unknown"),
        "n_steps": len(steps),
        "tool_list": tools,
    }


def aggregate_stats(per_query_stats):
    n = len(per_query_stats)
    if n == 0:
        return {}

    # 整体指标
    success_rate = sum(x["success"] for x in per_query_stats) / n
    avg_score = statistics.mean(x["total_score"] for x in per_query_stats)
    avg_latency = statistics.mean(x["latency_sec"] for x in per_query_stats)
    median_latency = statistics.median(x["latency_sec"] for x in per_query_stats)
    p95_latency = sorted(x["latency_sec"] for x in per_query_stats)[int(0.95 * n) - 1]

    # 工具使用统计
    tool_counter = Counter()
    steps_list = []
    for x in per_query_stats:
        tool_counter.update(x["tool_list"])
        steps_list.append(x["n_steps"])

    # 证据统计
    avg_unique_sources = statistics.mean(x["unique_sources"] for x in per_query_stats)
    price_coverage = sum(1 for x in per_query_stats if x["has_price_info"]) / n

    # 文本匹配
    f1_values = [x["f1"] for x in per_query_stats if x["f1"] is not None]
    em_values = [x["em"] for x in per_query_stats if x["em"] is not None]
    avg_f1 = statistics.mean(f1_values) if f1_values else None
    avg_em = statistics.mean(em_values) if em_values else None

    # 难度分层
    by_difficulty = defaultdict(list)
    for x in per_query_stats:
        by_difficulty[x["difficulty"]].append(x)

    diff_summary = {}
    for diff, items in by_difficulty.items():
        m = len(items)
        diff_success = sum(i["success"] for i in items) / m
        diff_latency = statistics.mean(i["latency_sec"] for i in items)
        diff_summary[diff] = {
            "count": m,
            "success_rate": diff_success,
            "avg_latency": diff_latency,
            "avg_score": statistics.mean(i["total_score"] for i in items),
        }

    # 注入
    injection_cases = [x["id"] for x in per_query_stats if x["possible_injection"]]

    return {
        "n_samples": n,
        "overall": {
            "success_rate": success_rate,
            "avg_total_score": avg_score,
            "avg_latency": avg_latency,
            "median_latency": median_latency,
            "p95_latency": p95_latency,
            "avg_steps": statistics.mean(steps_list),
            "tool_usage": dict(tool_counter),
            "avg_unique_sources": avg_unique_sources,
            "price_coverage": price_coverage,
            "avg_f1": avg_f1,
            "avg_em": avg_em,
        },
        "by_difficulty": diff_summary,
        "possible_injection_cases": injection_cases,
    }


def main():
    parser = argparse.ArgumentParser(description="Score eval_results.json for the travel agent.")
    parser.add_argument(
        "--results_path",
        type=str,
        required=True,
        help="Path to eval_results.json (模型运行结果)"
    )
    parser.add_argument(
        "--gold_path",
        type=str,
        default=None,
        help="(可选) gold 标注文件路径，包含 gold_answer 和 gold_sources"
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default=None,
        help="(可选) 将打分结果保存为 JSON 文件的路径"
    )
    parser.add_argument(
        "--latency_threshold",
        type=float,
        default=240.0,
        help="延迟合格阈值（秒），用于计算 latency_ok 指标"
    )

    args = parser.parse_args()

    results_path = Path(args.results_path)
    gold_path = Path(args.gold_path) if args.gold_path else None
    output_path = Path(args.output_path) if args.output_path else None

    results = load_results(results_path)
    gold_map = load_gold(gold_path)

    per_query_stats = []
    for record in results:
        qid = record.get("id")
        gold_item = gold_map.get(qid)
        stat = compute_per_query_score(record, gold_item, latency_threshold=args.latency_threshold)
        per_query_stats.append(stat)

    summary = aggregate_stats(per_query_stats)

    # -------- 控制台打印（报告形式） --------
    print("=" * 60)
    print(f"[总体] 样本数: {summary['n_samples']}")
    print(f"[总体] 成功率: {summary['overall']['success_rate']:.2%}")
    print(f"[总体] 平均综合得分: {summary['overall']['avg_total_score']:.2f} / 100")
    print(f"[总体] 平均延迟: {summary['overall']['avg_latency']:.2f}s "
          f"(median={summary['overall']['median_latency']:.2f}s, "
          f"p95={summary['overall']['p95_latency']:.2f}s)")
    print(f"[总体] 平均步骤数: {summary['overall']['avg_steps']:.2f}")
    print(f"[总体] 工具使用统计: {summary['overall']['tool_usage']}")
    print(f"[总体] 平均独立来源数: {summary['overall']['avg_unique_sources']:.2f}")
    print(f"[总体] 含价格信息的比例: {summary['overall']['price_coverage']:.2%}")

    if summary["overall"]["avg_f1"] is not None:
        print(f"[文本匹配] 平均 F1: {summary['overall']['avg_f1']:.3f}")
        print(f"[文本匹配] 平均 EM: {summary['overall']['avg_em']:.3f}")

    print("\n[按难度分组]:")
    for diff, stats in summary["by_difficulty"].items():
        print(f"  - {diff}: count={stats['count']}, "
              f"success_rate={stats['success_rate']:.2%}, "
              f"avg_latency={stats['avg_latency']:.2f}s, "
              f"avg_score={stats['avg_score']:.2f}")

    if summary["possible_injection_cases"]:
        print("\n[安全提示] 检测到可能存在提示注入风险的问题 ID:")
        print("  ", ", ".join(summary["possible_injection_cases"]))
    else:
        print("\n[安全提示] 本次评测中未检测到明显的提示注入模式。")

    # -------- 保存到文件（可选） --------
    if output_path is not None:
        output_data = {
            "summary": summary,
            "per_query": per_query_stats
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n已将详细打分结果保存到: {output_path}")


if __name__ == "__main__":
    main()
