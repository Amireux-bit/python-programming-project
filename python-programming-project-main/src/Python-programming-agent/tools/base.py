from pydantic import BaseModel
from typing import Dict, Any

class BaseTool:
    name: str = "base_tool"
    description: str = "Base tool description"
    args_schema: type[BaseModel] = None # 这里稍后用来做输入验证

    def get_spec(self) -> Dict[str, Any]:
        """
        生成给 LLM 看的'说明书' (JSON Schema)
        对应图片里的: spec.json
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_schema.model_json_schema() if self.args_schema else {}
        }

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        这里是实际执行逻辑，留给子类去实现
        """
        raise NotImplementedError("Subclasses must implement run()")