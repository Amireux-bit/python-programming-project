# ...existing code...
import os
from typing import List, Dict, Optional, Union
from openai import OpenAI

class QwenLLM:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-r1-distill-qwen-32b",  # 修改默认模型
        base_url: str = "https://vip.yi-zhan.top/v1",
        default_system: str = "You are a helpful assistant.",
        temperature: float = 0.7,
        env_var: str = "SUANLI_API_KEY",    # 使用新的环境变量名
    ):
        self.api_key = api_key or os.getenv(env_var)
        if not self.api_key:
            raise ValueError(f"缺少 API Key。请设置环境变量 {env_var} 或传入 api_key。")
        self.model = model
        self.base_url = base_url
        self.default_system = default_system
        self.temperature = temperature
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        return_raw: bool = False,
        model: Optional[str] = None,  # 可动态覆盖模型
    ) -> Union[str, Dict]:
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt or self.default_system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        resp = self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
        )
        return resp.model_dump() if return_raw else resp.choices[0].message.content

    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ):
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt or self.default_system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        for chunk in self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            stream=True,
        ):
            part = chunk.choices[0].delta.content
            if part:
                yield part

