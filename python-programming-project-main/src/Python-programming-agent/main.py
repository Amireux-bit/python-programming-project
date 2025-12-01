from tools.calculator import CalculatorTool
from tools.search import SearchTool
import json

def main():
    print("=== 1. 初始化工具 ===")
    calc_tool = CalculatorTool()
    search_tool = SearchTool()

    print("\n=== 2. 检查给 LLM 看的说明书 (Spec) ===")
    # 对应图片任务：tools/... 目录下每个工具提供 spec.json
    print("Calculator Spec:", json.dumps(calc_tool.get_spec(), indent=2))

    print("\n=== 3. 测试计算器 (正常情况) ===")
    # 模拟 LLM 传进来的参数
    result = calc_tool.run(expression="10 * 5 + 2")
    print("Output:", result)

    print("\n=== 4. 测试计算器 (非法输入 - 安全测试) ===")
    # 图片任务：安全审计，防注入
    result = calc_tool.run(expression="import os; os.system('rm -rf')")
    print("Output:", result)

    print("\n=== 5. 测试搜索工具 (实际联网) ===")
    result = search_tool.run(query="Capital of France")
    print("Output:", result)

    print("\n=== 6. 测试旅行查询场景 (模拟机票/高铁) ===")
    # 模拟用户询问明天的机票
    queries = [
        "flight price from Shanghai to Beijing tomorrow",
        "high speed train ticket price Shanghai to Beijing",
        "Singapore to Tokyo flight duration"
    ]

    for q in queries:
        print(f"\n[Query]: {q}")
        # 调用你的工具
        result = search_tool.run(query=q)
        print(f"[Result]: {result}")

    print("\n=== 改进版计算器测试 ===")
    
    # 测试 1: 带有文字干扰的输入 (以前会挂，现在能跑)
    print("Test 1 (Dirty Input):", 
          calc_tool.run(expression="The price is 100 * 0.8 dollars"))
    
    # 测试 2: 带有货币符号的输入
    print("Test 2 (Currency):", 
          calc_tool.run(expression="$50 + $20"))
          
    # 测试 3: 纯文本 (应该报错 No valid math)
    print("Test 3 (Text only):", 
          calc_tool.run(expression="Hello World"))

if __name__ == "__main__":
    main()