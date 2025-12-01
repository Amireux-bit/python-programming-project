import json
from pathlib import Path
from datetime import datetime

class TraceLogger:
    def __init__(self, log_dir=None, debug_mode: bool = False, run_tag: str | None = None):
        """
        debug_mode=False: 保持原来行为
        debug_mode=True: 允许通过 run_tag 为每次运行生成独立的 trace 文件名
        """
        self.trace = {
            "steps": [],
            "final": None
        }
        
        # 如果没有指定 log_dir，默认使用 src/logs
        if log_dir is None:
            # 使用 src 目录下的 logs 文件夹
            src_root = Path(__file__).parent.parent  # src/agent -> src
            self.log_dir = src_root / "logs"
        else:
            log_path = Path(log_dir)
            if not log_path.is_absolute():
                # 相对路径转绝对路径
                project_root = Path(__file__).parent.parent.parent
                self.log_dir = project_root / log_dir
            else:
                self.log_dir = log_path
        
        # 创建目录
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] 日志目录: {self.log_dir.absolute()}")
        except Exception as e:
            print(f"[ERROR] 无法创建日志目录: {e}")
            raise
        
        # 生成日志文件名
        if debug_mode and run_tag:
            # 调试模式：文件名里带上 run_tag，方便区分每个 query
            filename = f"trace_{run_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            # 默认行为：跟以前一样，用时间戳
            filename = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        self.log_file = self.log_dir / filename
        print(f"[INFO] 日志文件: {self.log_file.absolute()}")
    
    def log_step(self, step_id:int, thought:str, tool_name:str, params:dict, observation:str, evidence:list):
        step_data = {
            "step_id": step_id,
            "thought": thought,
            "action": {
                "tool_name": tool_name,
                "params": params
            },
            "observation": observation,
            "evidence": evidence
        }
        self.trace["steps"].append(step_data)
        self._write_to_file()
    
    def log_final(self, final_answer:str):
        self.trace["final"] = final_answer
        self._write_to_file()
    
    def get_trace(self):
        return self.trace
    
    def _write_to_file(self):
        """将当前trace写入JSON文件"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.trace, f, ensure_ascii=False, indent=2)
            
            # 验证文件写入
            if self.log_file.exists():
                file_size = self.log_file.stat().st_size
                print(f"[DEBUG] ✅ 日志已写入: {self.log_file.name} ({file_size} 字节)")
            else:
                print(f"[ERROR] ❌ 文件写入后消失！")
                
        except Exception as e:
            print(f"[ERROR] ❌ 写入失败: {e}")
            import traceback
            traceback.print_exc()
