import sys
from pathlib import Path

# 将 src 目录添加到 Python 路径
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

from agent.controller import TravelAssistantController
import yaml
from tools.calculator import CalculatorTool
from tools.search import SmartSearchTool
from agent.llm import QwenLLM

if __name__ == "__main__":
    # 使用相对于脚本的路径（跨平台通用）
    config_path = src_dir / "agent" / "configs" / "baseline.yaml"
    config = yaml.safe_load(open(config_path, "r", encoding="utf-8"))
    
    cal = CalculatorTool()
    search = SmartSearchTool()

    controller = TravelAssistantController(
        llm=QwenLLM(api_key="sk-KnnTjVEys05BmjMCD100AcD4B72849Ab9628979d64D35b05"),
        cal_tool=cal,
        search_tool=search,
        config=config
    )

    user_query = "请帮我规划一个从上海到巴黎的五天旅行行程。"

    result = controller.run(user_query)

    print("状态:", result["status"])
    print("\n" + "="*50)
    print("答案:")
    print("="*50)
    # 直接打印，不要和其他字符串拼接
    print(result["answer"])
    print("="*50)
    print("\nTrace:", result["trace"])