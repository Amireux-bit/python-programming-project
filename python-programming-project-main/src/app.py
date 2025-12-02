from agent.controller import TravelAssistantController
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from agent.llm import QwenLLM
import streamlit as st
import time
import sys
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

def build_controller():
    """创建和 main.py 类似的 TravelAssistantController 实例。"""
    # 读取配置文件：src/agent/configs/baseline.yaml
    config_path = SRC_DIR / "python-programming-project-main" / "src" / "agent" / "configs" / "baseline.yaml"
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



# === 1. 页面配置 ===
st.set_page_config(page_title="Agent Chat", page_icon="🤖", layout="wide")
st.title("🤖 Project B: Intelligent Agent")
st.caption("Powered by ReAct Pattern & Custom Tools")

# === 2. 初始化聊天记录 (Session State) ===
# Streamlit 每次交互都会重跑代码，所以需要用 Session State 记住之前的聊天
if "messages" not in st.session_state:
    st.session_state.messages = []

# === 3. 显示之前的聊天记录 ===
for msg in st.session_state.messages:
    # msg["role"] 是 "user" 或 "assistant"
    # st.chat_message 会自动显示对应的头像
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# === 4. 处理用户输入 ===
if prompt := st.chat_input("What is your question?"):
    # 4.1 显示用户的问题
    with st.chat_message("user"):
        st.markdown(prompt)
    # 记录到历史
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 4.2 调用 Agent (核心部分)
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # --- 🔴 关键：这里接入队友的 Agent ---
        # 假设队友的入口函数是 run_agent(query)
        # 目前先用模拟代码代替
        with st.spinner("Thinking & Using Tools..."):
            try:
                # 🔴 真实调用
                response_text = build_controller().run(prompt)
                
                st.markdown(response_text)
                
                # 记录
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                
            except Exception as e:
                st.error(f"Agent Error: {e}")

        # --- 模拟打字机效果 (可选，看起来更像 ChatGPT) ---
        for chunk in response_text.split():
            full_response += chunk + " "
            time.sleep(0.05)
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)
    
    # 记录 Agent 回复到历史
    st.session_state.messages.append({"role": "assistant", "content": full_response})

import pandas as pd
import os

# === 侧边栏：实时监控面板 ===
st.sidebar.title("📊 System Monitor")

log_file = "logs/tool_metrics.csv" # 确保路径对

if st.sidebar.button("Refresh Logs"):
    if os.path.exists(log_file):
        # 读取 CSV
        df = pd.read_csv(log_file)
        # 显示最新的 5 条日志
        st.sidebar.subheader("Recent Tool Usage")
        st.sidebar.dataframe(df.tail(5))
        
        # 画一个简单的耗时统计图
        if "Latency" in df.columns:
            # 去掉 'ms' 单位转成数字
            df["Latency_Val"] = df["Latency"].str.replace("ms", "").astype(float)
            st.sidebar.subheader("Latency Chart")
            st.sidebar.line_chart(df["Latency_Val"])
    else:
        st.sidebar.warning("No logs found yet.")