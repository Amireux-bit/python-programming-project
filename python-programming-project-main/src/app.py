import streamlit as st
import time
import sys
import os
import yaml
import json
import pandas as pd
from pathlib import Path
import traceback

# --------- 1. 路径设置 (更稳健的写法) ---------
# 假设 app.py 位于项目根目录
# 目录结构:
# project_root/
#   ├── app.py
#   ├── src/
#   │   ├── agent/
#   │   └── tools/
#   ├── logs/
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR

# 将 src 加入系统路径，这样才能 import agent 和 tools
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# --------- 导入自定义模块 ---------
try:
    from agent.controller import TravelAssistantController
    from tools.calculator import CalculatorTool
    # 注意：这里直接导入 SearchTool，因为文件名是 search.py
    from tools.search import SmartSearchTool
    from agent.llm import QwenLLM
except ImportError as e:
    st.error(f"❌ 模块导入失败: {e}")
    st.info("请检查 src/ 目录下的文件结构是否正确。")
    st.stop()

# --------- 2. 初始化资源 (带缓存，只跑一次) ---------
@st.cache_resource
def get_controller():
    """
    初始化 Controller。
    使用 cache_resource 装饰器，确保 LLM 和向量库只加载一次，
    不会因为页面刷新或新对话而重复加载。
    """
    print("🔄 [System] Initializing Agent Controller...")
    
    # 自动寻找配置文件
    config_path = SRC_DIR / "agent" / "configs" / "baseline.yaml"
    
    if not config_path.exists():
        st.error(f"❌ 找不到配置文件: {config_path}")
        st.stop()
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 初始化工具
    cal = CalculatorTool()
    search = SmartSearchTool()
    llm = QwenLLM()

    # 初始化控制器
    controller = TravelAssistantController(
        cal_tool=cal,
        search_tool=search,
        config=config,
        llm=llm,
        debug_mode=True,
    )
    print("✅ [System] Agent Controller Ready.")
    return controller

# === 3. 页面配置 ===
st.set_page_config(page_title="Agent Chat", page_icon="🤖", layout="wide")
st.title("🤖 Project B: Intelligent Travel Agent")
st.caption("Powered by Hybrid RAG (Local Knowledge + Google Search) & ReAct Pattern")

# === 4. 侧边栏：实时监控面板 ===
st.sidebar.title("📊 System Monitor")
log_file = ROOT_DIR / "logs" / "tool_metrics.csv" 

# 自动刷新日志显示
if log_file.exists():
    try:
        # 读取 CSV
        df = pd.read_csv(log_file)
        st.sidebar.success(f"Log Found: {len(df)} records")
        
        # 显示最新的 5 条日志
        st.sidebar.subheader("Recent Tool Usage")
        # 只显示关键列
        if all(col in df.columns for col in ["Timestamp", "Tool_Name", "Status", "Latency"]):
            st.sidebar.dataframe(df.tail(5)[["Timestamp", "Tool_Name", "Status", "Latency"]])
        else:
            st.sidebar.dataframe(df.tail(5))
        
        # 画一个简单的耗时统计图
        if "Latency" in df.columns:
            # 清洗数据：去掉 'ms' 单位转成数字
            df["Latency_Val"] = df["Latency"].astype(str).str.replace("ms", "", regex=False)
            df["Latency_Val"] = pd.to_numeric(df["Latency_Val"], errors='coerce').fillna(0)
            
            st.sidebar.subheader("Latency Trend (ms)")
            st.sidebar.line_chart(df["Latency_Val"])
    except Exception as e:
        st.sidebar.error(f"Error reading logs: {e}")
else:
    st.sidebar.warning("No logs found yet. Try running a query.")


# === 5. 聊天主逻辑 ===

# 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 处理用户输入
if prompt := st.chat_input("Ask me about travel (e.g. Paris, Singapore) or general questions..."):
    # 显示用户问题
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 调用 Agent
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        with st.spinner("🧠 Thinking & Searching..."):
            try:
                # 获取缓存的控制器
                controller = get_controller()
                
                # 运行 Agent
                raw_response = controller.run(prompt)
                
                # --- 核心数据清洗：处理字典类型 ---
                final_text = ""
                if isinstance(raw_response, dict):
                    # 尝试提取常见的 key
                    if "output" in raw_response:
                        final_text = raw_response["output"]
                    elif "result" in raw_response:
                        final_text = raw_response["result"]
                    elif "answer" in raw_response:
                        final_text = raw_response["answer"]
                    else:
                        # 兜底：转 JSON 字符串
                        final_text = json.dumps(raw_response, ensure_ascii=False, indent=2)
                else:
                    # 如果本来就是字符串
                    final_text = str(raw_response)
                
                # 🔴 FIX 1: 防止 LaTeX 数学公式误伤 (解决斜体粘连问题)
                # 将所有的 $ 符号转义为 \$，这样 Streamlit 就不会把它当成公式渲染了
                final_text = final_text.replace("$", "\$")
                
                # 🔴 FIX 2: 预处理换行符 (解决分点空行问题)
                # Markdown 需要两个空格+换行，或者双换行才能正确显示分段
                final_text = final_text.replace("\n", "  \n")

                # --- 打字机效果 (使用切片，不要用 split) ---
                step = 3  # 每次显示字符数
                for i in range(0, len(final_text), step):
                    # 按字符切片，完美保留空格和换行
                    chunk = final_text[i:i+step]
                    full_response += chunk
                    
                    # 刷新显示
                    message_placeholder.markdown(full_response + "▌")
                    time.sleep(0.01) 
                
                # 最后移除光标
                message_placeholder.markdown(full_response)
                
                # 记录助手回复
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"❌ Agent Runtime Error: {e}")
                traceback.print_exc()