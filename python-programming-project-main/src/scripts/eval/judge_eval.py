# src/scripts/eval/judge_eval.py

import json
from pathlib import Path
from collections import defaultdict
import argparse
import sys

# ---------- 路径设置 ----------
ROOT = Path(__file__).resolve().parents[3]   # 项目根目录 python-programming-project-main
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

# 这里不再从 agent 导入，直接定义一个本地版本的 has_price_information
def has_price_information(evidence_list):
    """
    简单判断证据中是否包含足够多的价格相关信息：
    - 把所有 evidence 的 content 拼成一个字符串
    - 统计若干价格相关关键词是否出现
    - 命中关键词数 >= 3 就认为“有价格信息”
    """
    price_keywords = [
        "$", "€", "¥", "元", "yuan", "rmb", "cny",
        "price", "cost", "budget", "fee", "fare",
        "per night", "per day", "/night", "/day",
        "starting at", "from"
    ]
    texts = []
    for e in evidence_list:
        content = e.get("content", "")
        if isinstance(content, str):
            texts.append(content.lower())
    combined_text = " ".join(texts)

    matches = 0
    for kw in price_keywords:
        if kw.lower() in combined_text:
            matches += 1
    return matches >= 3



# ---------- 工具函数 ----------

def load_results(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_human_labels(path: Path):
    """
    human_labels.json 结构示例：
    [
      {
        "id": "q01",
        "difficulty": "medium",
        "scenario": "xxx",
        "human_label": {
          "overall_score": 95,
          "correctness": "correct",          # 或 partially_correct
          ...
        }
      },
      ...
    ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    label_map = {}
    for item in data:
        qid = item.get("id")
        if not qid:
            continue
        label_map[qid] = item
    return label_map


def compute_auto_judge(record: dict, latency_threshold: float = 240.0):
    """
    这里实现一个“规则版 Judge”：
    - success: status == "success"
    - evidence_ok: 来源数 >= 2 且 max_score >= 0.7 且 有价格信息
    - tool_ok: Search 次数 >= 3 且 至少 1 次 Calculator 且没 UnknownTool
    - latency_ok: 延迟 <= latency_threshold
    综合得分:
        score = 0.4*success + 0.3*evidence_ok + 0.2*tool_ok + 0.1*latency_ok
    最终判定:
        judge_pred = 1 if score >= 0.8 else 0
    """
    status = record.get("status", "")
    success = 1 if status == "success" else 0

    trace = record.get("trace", {})
    steps = trace.get("steps", [])
    tools = [s.get("action", {}).get("tool_name", "") for s in steps]

    used_search = tools.count("Search")
    used_calc = tools.count("Calculator")
    tool_ok = 1 if (used_search >= 3 and used_calc >= 1 and "UnknownTool" not in tools) else 0

    # 汇总证据
    all_evidence = []
    for s in steps:
        all_evidence.extend(s.get("evidence", []))

    unique_sources = len({e.get("source") for e in all_evidence if e.get("source")})
    max_score = max([e.get("score", 0.0) for e in all_evidence], default=0.0)
    price_ok = 1 if has_price_information(all_evidence) else 0

    evidence_ok = 1 if (unique_sources >= 2 and max_score >= 0.7 and price_ok) else 0

    latency = float(record.get("latency_sec", 0.0))
    latency_ok = 1 if latency <= latency_threshold else 0

    score = 0.4 * success + 0.3 * evidence_ok + 0.2 * tool_ok + 0.1 * latency_ok
    judge_pred = 1 if score >= 0.8 else 0

    return {
        "judge_score": score,
        "judge_pred": judge_pred,
        "success": success,
        "evidence_ok": evidence_ok,
        "tool_ok": tool_ok,
        "latency_ok": latency_ok,
        "unique_sources": unique_sources,
        "max_score": max_score,
        "has_price_info": price_ok,
        "latency_sec": latency,
        "n_steps": len(steps),
        "used_search": used_search,
        "used_calculator": used_calc,
        "tools": tools,
    }


def binarize_human_label(human_item: dict):
    """
    把 human_labels.json 里的人工标注，转成 0/1 标签：
    - label = 1: correctness == "correct" 且 overall_score >= 90
    - label = 0: 其他情况（包括 partially_correct 或 分数 < 90）
    方便和自动 Judge 对齐。
    """
    h = human_item.get("human_label", {})
    correctness = h.get("correctness", "correct")
    score = h.get("overall_score", 0)

    if correctness == "correct" and score >= 90:
        return 1
    else:
        return 0


def compute_metrics(y_true, y_pred):
    """
    简单实现 accuracy / precision / recall / F1。
    y_true, y_pred 都是 0/1 列表。
    """
    assert len(y_true) == len(y_pred)
    n = len(y_true)
    if n == 0:
        return dict(accuracy=0, precision=0, recall=0, f1=0,
                    tp=0, tn=0, fp=0, fn=0)

    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    accuracy = (tp + tn) / n
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return dict(
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        tp=tp, tn=tn, fp=fp, fn=fn
    )


# ---------- 主函数 ----------

def main():
    parser = argparse.ArgumentParser(description="Evaluate rule-based Judge vs human labels.")
    parser.add_argument(
        "--results_path",
        type=str,
        default="src/scripts/eval/eval_results.json",
        help="eval_results.json 路径"
    )
    parser.add_argument(
        "--labels_path",
        type=str,
        default="src/scripts/eval/human_labels.json",
        help="human_labels.json 路径"
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default="src/scripts/eval/judge_eval_detail.json",
        help="保存每条样本 Judge 结果的 JSON 路径"
    )
    parser.add_argument(
        "--latency_threshold",
        type=float,
        default=240.0,
        help="延迟阈值，超过算 latency_not_ok（默认 240 秒）"
    )
    args = parser.parse_args()

    results_path = ROOT / args.results_path
    labels_path = ROOT / args.labels_path
    output_path = ROOT / args.output_path

    print(f"[INFO] 读取模型结果: {results_path}")
    print(f"[INFO] 读取人工标注: {labels_path}")

    results = load_results(results_path)
    human_map = load_human_labels(labels_path)

    per_case = []
    y_true = []
    y_pred = []
    by_diff_true = defaultdict(list)
    by_diff_pred = defaultdict(list)

    for r in results:
        qid = r.get("id")
        if qid not in human_map:
            continue

        human_item = human_map[qid]
        diff = human_item.get("difficulty", "unknown")

        human_bin = binarize_human_label(human_item)
        judge_info = compute_auto_judge(r, latency_threshold=args.latency_threshold)
        judge_bin = judge_info["judge_pred"]

        y_true.append(human_bin)
        y_pred.append(judge_bin)
        by_diff_true[diff].append(human_bin)
        by_diff_pred[diff].append(judge_bin)

        per_case.append({
            "id": qid,
            "difficulty": diff,
            "scenario": human_item.get("scenario", ""),
            "human_label_bin": human_bin,
            "human_overall_score": human_item.get("human_label", {}).get("overall_score"),
            "human_correctness": human_item.get("human_label", {}).get("correctness"),
            **judge_info
        })

    # 整体指标
    overall_metrics = compute_metrics(y_true, y_pred)

    # 按难度分组指标
    difficulty_metrics = {}
    for diff in by_diff_true:
        m = compute_metrics(by_diff_true[diff], by_diff_pred[diff])
        difficulty_metrics[diff] = m

    # ----- 控制台输出 -----
    print("\n================ Rule-based Judge vs Human ================")
    n = len(y_true)
    print(f"样本数: {n}")
    print(f"整体 Accuracy: {overall_metrics['accuracy']:.3f}")
    print(f"整体 Precision: {overall_metrics['precision']:.3f}")
    print(f"整体 Recall: {overall_metrics['recall']:.3f}")
    print(f"整体 F1: {overall_metrics['f1']:.3f}")
    print(f"混淆矩阵: TP={overall_metrics['tp']}, TN={overall_metrics['tn']}, FP={overall_metrics['fp']}, FN={overall_metrics['fn']}")

    print("\n按难度分组:")
    for diff, m in difficulty_metrics.items():
        print(f"  - {diff}: acc={m['accuracy']:.3f}, prec={m['precision']:.3f}, "
              f"recall={m['recall']:.3f}, f1={m['f1']:.3f}, "
              f"TP={m['tp']}, TN={m['tn']}, FP={m['fp']}, FN={m['fn']}")

    # ----- 保存详细结果 -----
    output_data = {
        "overall_metrics": overall_metrics,
        "by_difficulty": difficulty_metrics,
        "per_case": per_case
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n[INFO] 详细 Judge 评估结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
