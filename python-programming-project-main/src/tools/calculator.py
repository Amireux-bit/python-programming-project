from pydantic import BaseModel, Field
from tools.base import BaseTool
from .utils import monitor_execution
from functools import lru_cache
import json
import re  # 引入正则模块

class CalculatorArgs(BaseModel):
    expression: str = Field(..., description="The mathematical expression to evaluate.")

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Useful for performing mathematical calculations. Handles basic arithmetic (+, -, *, /, %, **, (, ))."
    args_schema = CalculatorArgs

    @monitor_execution(tool_name="calculator")
    @lru_cache(maxsize=128)
    def run(self, expression: str) -> str:
        try:
            # 1. 数据清洗 (Sanitization) - 你的核心需求
            # 只保留：数字(0-9)、小数点(.)、运算符(+-*/%^)、括号()
            # [^...] 表示匹配“除了这些字符以外的所有字符”
            # 我们把这些“杂质”全部替换为空字符串
            cleaned_expression = re.sub(r'[^0-9\.\+\-\*\/\%\(\)\s]', '', expression)
            
            # 如果清洗完是空的（比如 LLM 传了个 "Hello"），直接报错
            if not cleaned_expression.strip():
                return json.dumps({"status": "ERROR", "message": "No valid math expression found"})

            # 2. 安全检查 (Safety)
            # 虽然已经清洗过，但为了防止类似 "9**999999" 这种 DoS 攻击，可以限制长度
            if len(cleaned_expression) > 100:
                return json.dumps({"status": "ERROR", "message": "Expression too long"})

            # 3. 执行计算
            # 这里的 eval 相对安全，因为恶意字符（如 a-z, import, os）已经在第1步被清洗掉了
            result = eval(cleaned_expression)
            
            # 4. 格式化输出
            return json.dumps({
                "status": "SUCCESS", 
                "original_input": expression,
                "cleaned_input": cleaned_expression, # 方便调试看清洗效果
                "result": str(result)
            })

        except ZeroDivisionError:
            return json.dumps({"status": "ERROR", "message": "Division by zero"})
        except SyntaxError:
            return json.dumps({"status": "ERROR", "message": f"Invalid syntax in: {cleaned_expression}"})
        except Exception as e:
            return json.dumps({"status": "ERROR", "message": str(e)})