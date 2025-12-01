from pydantic import BaseModel, Field
from tools.base import BaseTool
from utils import monitor_execution
from functools import lru_cache
import json
import requests
import re

class SearchArgs(BaseModel):
    query: str = Field(..., description="The query string to search for.")

class SearchTool(BaseTool):
    name = "search"
    description = (
        "Useful for searching information. "
        "Returns structured data with confidence scores and sources for citations."
    )
    args_schema = SearchArgs
    
    # 依然建议使用 Google Serper，因为它稳定且包含 link
    api_key: str = "8c5a260710c9c2aceda64505b3a551d88a7a14b6" 

    def _calculate_confidence(self, query: str, snippet: str, rank: int) -> float:
        """
        计算置信度的私有方法：混合了排名衰减和文本相似度
        """
        # 1. 排名基础分 (Base Score from Rank)
        # Rank 0 (第1名) = 0.9, Rank 1 = 0.85, ... 最低 0.5
        rank_score = max(0.5, 0.9 - (rank * 0.05))
        
        # 2. 文本匹配分 (Text Match Score) - 简单的关键词重合度
        # 把 query 和 snippet 拆成单词集合 (set)
        q_tokens = set(re.findall(r'\w+', query.lower()))
        s_tokens = set(re.findall(r'\w+', snippet.lower()))
        
        if not q_tokens:
            return rank_score
            
        # 计算交集：snippet 里包含了多少 query 的词？
        overlap = len(q_tokens.intersection(s_tokens))
        match_ratio = overlap / len(q_tokens) # 0.0 到 1.0
        
        # 3. 最终加权：70%看排名，30%看匹配度
        final_score = (rank_score * 0.7) + (match_ratio * 0.3)
        
        return round(final_score, 2)

    @monitor_execution(tool_name="search")
    @lru_cache(maxsize=50) 
    def run(self, query: str) -> str:
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 5}) # 多抓几条，比如5条
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        try:
            response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
            if response.status_code != 200:
                return json.dumps({"status": "ERROR", "message": "API Error"})
            
            data = response.json()
            if "organic" not in data:
                return json.dumps({"status": "EMPTY", "results": []})
            
            # === 核心逻辑升级：结构化数据 + 置信度计算 ===
            structured_results = []
            if "organic" in data:
                for index, item in enumerate(data["organic"]):
                    snippet = item.get("snippet", "")
                    
                    # === 调用刚才写的算法计算分数 ===
                    confidence = self._calculate_confidence(query, snippet, index)
                    
                    entry = {
                        "content": snippet,
                        "source": item.get("link", ""),
                        "title": item.get("title", ""),
                        "score": confidence  # 现在这是一个经过计算的“真实”分数了
                    }
                    structured_results.append(entry)
            
            return json.dumps({
                "status": "SUCCESS", 
                "results": structured_results
            })

        except Exception as e:
            return json.dumps({"status": "ERROR", "message": str(e)})