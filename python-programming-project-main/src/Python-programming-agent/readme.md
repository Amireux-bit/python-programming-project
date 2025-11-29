# 🛠️ Project B: 基础设施与工具层 (Tools & Infra)

大家好，这是我负责的**工具层**实现。我已经搭好了 Agent 所需的底层框架，保证了工具调用的**稳定性、安全性**以及**可追溯性**。

## 1\. 我完成了什么？

目前实现了以下核心功能（已满足作业 KPI）：

  * **基础工具集**：
      * `CalculatorTool`: 支持数学计算，带防注入安全检查。
      * `SearchTool`: 联网搜索（DuckDuckGo），带超时重试机制。
  * **工程化保障**：
      * **自动日志 (Auditable)**：所有工具调用都会自动记录到 `logs/tool_metrics.csv`，方便调试和写报告。
      * **缓存加速 (Caching)**：对重复的搜索/计算请求，直接从内存返回结果，延迟为 0ms。
      * **输入校验 (Safety)**：使用 `Pydantic` 严格校验参数格式，防止 LLM 乱传参导致程序崩坏。

## 2\. 你们怎么用？(Quick Start)

### 第一步：安装依赖

请确保环境里安装了我的依赖包：

```bash
pip install -r requirements.txt
```

### 第二步：在 Agent 代码里调用

你们写 Agent 逻辑时，直接 import 我的类就行，不用管底层的重试和日志逻辑，我都封装好了。

**示例代码：**

```python
from tools.calculator import CalculatorTool
from tools.search import SearchTool
import json

# 1. 初始化工具
calc = CalculatorTool()
search = SearchTool()

# 2. 获取给 LLM 看的 Prompt 描述 (JSON Schema)
# 直接把这个塞给 System Prompt
print(json.dumps(calc.get_spec(), indent=2))
print(json.dumps(search.get_spec(), indent=2))

# 3. 执行工具 (Agent 决定调用时)
# 搜索
result_search = search.run(query="Singpore weather")
print(result_search) 

# 计算
result_calc = calc.run(expression="25 * 4") 
print(result_calc)
```

## 3\. 项目结构说明

```text
project_b_agent/
├── tools/
│   ├── calculator.py   # 计算器实现
│   ├── search.py       # 搜索实现
│   └── base.py         # 工具基类
├── logs/
│   └── tool_metrics.csv # 自动生成的运行日志 (不要删，用来分析性能)
├── utils.py            # 监控装饰器代码
└── main.py             # 测试脚本 (想看工具怎么跑的，可以直接运行这个)
```

## 4\. 注意事项

  * **日志文件**：`logs/tool_metrics.csv` 会自动生成，如果你们发现调用变慢或者报错，先去看看这个文件里的 Error Log。
  * **扩展工具**：如果需要加新工具，请告诉我，我按照目前的架构（继承 `BaseTool`）来添加，以保证日志和缓存功能生效。
