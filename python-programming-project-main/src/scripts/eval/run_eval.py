import sys
import json
import time
from pathlib import Path

import yaml

# --------- 路径设置：把 src 加到 sys.path 里 ---------
# 当前文件：src/scripts/eval/run_eval.py
# parent        -> src/scripts/eval
# parent.parent -> src/scripts
# parent.parent.parent -> src
SRC_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SRC_DIR))

# 现在可以安全地 import 项目里的模块
from agent.controller import TravelAssistantController
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from agent.llm import QwenLLM


def build_controller():
    """创建和 main.py 类似的 TravelAssistantController 实例。"""
    # 读取配置文件：src/agent/configs/baseline.yaml
    config_path = SRC_DIR / "agent" / "configs" / "baseline.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cal = CalculatorTool()
    search = SearchTool()
    llm = QwenLLM()

    controller = TravelAssistantController(
        cal_tool=cal,
        search_tool=search,
        config=config,
        llm=llm,
        debug_mode=True,
    )
    return controller


def main():
    # eval_querier.json 就在当前目录：src/scripts/eval
    eval_dir = Path(__file__).resolve().parent
    queries_path = eval_dir / "eval_querier_small.json"
    results_path = eval_dir / "eval_results_step9.json"

    # 读取评测集
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    controller = build_controller()
    all_results = []

    for item in queries:
        qid = item.get("id", "unknown")
        user_query = item["user_query"]
        difficulty = item.get("difficulty", "")
        scenario = item.get("scenario", "")

        print(f"\n=== Running {qid} ({difficulty}/{scenario}) ===")
        print(f"User query: {user_query}")

        t0 = time.time()
        out = controller.run(user_query,run_id=qid)
        t1 = time.time()

        result = {
            "id": qid,
            "user_query": user_query,
            "difficulty": difficulty,
            "scenario": scenario,
            "status": out.get("status", ""),
            "answer": out.get("answer", ""),
            "latency_sec": round(t1 - t0, 3),
            "trace": out.get("trace", {}),
        }
        all_results.append(result)

        print(f" -> status: {result['status']}, latency: {result['latency_sec']}s")

    # 保存所有评测结果
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ All eval queries finished. Results saved to: {results_path}")


if __name__ == "__main__":
    main()
