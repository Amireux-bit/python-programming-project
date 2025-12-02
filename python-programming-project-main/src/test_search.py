from tools.search import SmartSearchTool
import json
import time

# 修改 test_hybrid.py 中的 run_query 函数
def run_query(tool, query, scene_name):
    print(f"\n{'='*50}")
    print(f"🧪 测试场景: {scene_name}")
    print(f"🧐 查询: {query}")
    print(f"{'='*50}")
    
    start_time = time.time()
    result = tool.run(query)
    end_time = time.time()
    
    data = json.loads(result)
    print(f"⏱️ 耗时: {end_time - start_time:.4f}秒")
    
    if data['results']:
        top = data['results'][0]
        source_type = top.get('type', 'unknown')
        score = top.get('score', 0)
        content = top.get('content', '') # 🔴 删掉了 [:100]
        
        print(f"🏆 命中类型: 【{source_type.upper()}】")
        print(f"💯 置信度分: {score}")
        print(f"📄 完整内容:\n{'-'*20}\n{content}\n{'-'*20}") # 🔴 完整打印
        
        if source_type == 'local':
            print("✅ 命中本地")
        else:
            print("🌐 命中网络")
    else:
        print("❌ 未找到任何结果")
        
def test():
    print("=== 正在初始化 Smart Search 工具 (加载 8000+ 片段请稍候) ===")
    tool = SmartSearchTool()
    
    # --- Case 1: 语义测试 (不出现 'Food' 关键词) ---
    # 假设你的库里有 Paris.txt
    run_query(tool, 
              "Where can I find romantic dinner places in Paris?", 
              "语义匹配 - 巴黎餐厅")

    # --- Case 2: 细节规则测试 ---
    # 假设你的库里有 Singapore.txt 或相关安全文档
    run_query(tool, 
              "Is it illegal to chew gum in Singapore?", 
              "细节规则 - 新加坡口香糖")

    # --- Case 3: 干扰测试 (本地没有的城市) ---
    # 假设你的库里只有几十个大城市，应该没有 "Gotham City" (哥谭市)
    run_query(tool, 
              "How to get to Gotham City police station?", 
              "不存在的城市 - 哥谭市")

if __name__ == "__main__":
    test()