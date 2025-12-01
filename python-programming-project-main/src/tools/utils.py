# utils.py
import time
import csv
import os
from functools import wraps

# 定义日志文件的位置
LOG_FILE = "tool_metrics.csv"

def monitor_execution(tool_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "SUCCESS"
            error_msg = ""
            result = None
            
            try:
                # 1. 尝试执行工具原本的逻辑
                result = func(*args, **kwargs)
            except Exception as e:
                # 2. 如果出错了，记录错误
                status = "ERROR"
                error_msg = str(e)
                raise e # 继续抛出异常，让外层知道
            finally:
                # 3. 无论成功失败，都记录数据 (Finally 块)
                end_time = time.time()
                latency = round((end_time - start_time) * 1000, 2) # 毫秒
                
                # 准备要写入的一行数据
                # 图片要求: 开始/结束、耗时、字节数、错误码
                log_entry = [
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                    tool_name,
                    status,
                    f"{latency}ms",
                    error_msg
                ]
                
                # 写入 CSV 文件
                file_exists = os.path.isfile(LOG_FILE)
                with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # 如果文件是新的，先写表头
                    if not file_exists:
                        writer.writerow(["Timestamp", "Tool_Name", "Status", "Latency", "Error_Log"])
                    writer.writerow(log_entry)
                    
            return result
        return wrapper
    return decorator