# src/scripts/eval/run_attack_eval.py

import sys
import json
import time
from pathlib import Path

# 加载 src 路径
SRC_DIR = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(SRC_DIR))

from agent.controller import TravelAssistantController
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from agent.llm import QwenLLM
import yaml


def load_config(config_path: Path):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_queries(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[3]
    config_no_safety = project_root / "src" / "agent" / "configs" / "baseline_no_safety.yaml"
    config_with_safety = project_root / "src" / "agent" / "configs" / "baseline.yaml"

    attack_queries_path = project_root / "src" / "scripts" / "eval" / "attack_querier.json"

    # 1) 先跑“关闭安全”的情况
    for mode, cfg_path, output_name in [
        ("no_safety", config_no_safety, "attack_results_no_safety.json"),
        ("with_safety", config_with_safety, "attack_results_with_safety.json"),
    ]:
        print(f"\n========== Running attack eval: {mode} ==========")
        config = load_config(cfg_path)

        cal = CalculatorTool()
        search = SearchTool()
        llm = QwenLLM()

        controller = TravelAssistantController(cal_tool=cal, search_tool=search, config=config, llm=llm ,debug_mode=True,)

        queries = load_queries(attack_queries_path)

        results = []
        for q in queries:
            user_query = q["user_query"]
            qid = q["id"]
            print(f"\n[ATTACK] {mode} - {qid}: {user_query[:60]}...")

            start = time.time()
            result = controller.run(user_query)
            end = time.time()

            result_record = {
                "id": qid,
                "user_query": user_query,
                "attack_type": q.get("attack_type", ""),
                "difficulty": q.get("difficulty", ""),
                "scenario": q.get("scenario", ""),
                "status": result.get("status"),
                "answer": result.get("answer"),
                "latency_sec": end - start,
                "trace": result.get("trace"),
            }
            results.append(result_record)

        output_path = project_root / "src" / "scripts" / "eval" / output_name
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Attack eval ({mode}) saved to: {output_path}")
