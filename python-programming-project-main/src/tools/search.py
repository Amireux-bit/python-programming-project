from pydantic import BaseModel, Field
from tools.base import BaseTool
from .utils import monitor_execution
from functools import lru_cache
import json
import requests
import re
import os
import numpy as np

# === 尝试导入 AI 库 (如果没有安装，代码会自动降级为纯 Google 搜索) ===
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    HAS_LOCAL_SEARCH = True
except ImportError:
    HAS_LOCAL_SEARCH = False
    print("⚠️ Warning: sentence-transformers or faiss not installed. Local search disabled.")


# === 1. 本地知识库单例 (支持持久化缓存) ===
class LocalKnowledgeBase:
    _instance = None

    def __new__(cls, doc_dir="data/docs"):
        if cls._instance is None:
            cls._instance = super(LocalKnowledgeBase, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def init_kb(self, doc_dir="data/docs"):
        if self.initialized or not HAS_LOCAL_SEARCH: return
        
        # 定义缓存文件路径
        cache_dir = "data/cache"
        if not os.path.exists(cache_dir): os.makedirs(cache_dir)
        
        index_path = os.path.join(cache_dir, "faiss_index.bin")
        docs_path = os.path.join(cache_dir, "documents.json")

        # 🟢 策略 A: 尝试从缓存加载 (极速模式)
        if os.path.exists(index_path) and os.path.exists(docs_path):
            print("🚀 [SmartSearch] Found cache! Loading from disk...")
            try:
                # 1. 加载 FAISS 索引
                self.index = faiss.read_index(index_path)
                # 2. 加载文本数据
                with open(docs_path, 'r', encoding='utf-8') as f:
                    self.documents = json.load(f)
                
                # 3. 必须加载模型以便后续把 Query 转向量 (但不需要重新 Embed 文档了)
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                
                print(f"✅ [SmartSearch] Cache loaded. Ready with {len(self.documents)} documents.")
                self.initialized = True
                return
            except Exception as e:
                print(f"⚠️ [SmartSearch] Cache corrupted ({e}), rebuilding...")

        # 🟠 策略 B: 缓存不存在，重新构建 (慢速模式)
        print("📥 [SmartSearch] Building Knowledge Base from scratch...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.documents = []
        
        if not os.path.exists(doc_dir):
            os.makedirs(doc_dir)
            with open(f"{doc_dir}/readme.txt", "w") as f: 
                f.write("Place your txt files here.")

        for filename in os.listdir(doc_dir):
            if filename.endswith(".txt"):
                file_path = os.path.join(doc_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        chunks = [c.strip() for c in content.split('\n\n') if len(c.strip()) > 30]
                        self.documents.extend([(c, filename) for c in chunks])
                except Exception as e:
                    print(f"Error reading {filename}: {e}")

        if self.documents:
            # 向量化
            texts = [doc[0] for doc in self.documents]
            print(f"⏳ Embedding {len(texts)} snippets... (This may take a while)")
            embeddings = self.model.encode(texts)
            
            # 建索引
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dimension)
            self.index.add(np.array(embeddings).astype('float32'))
            
            # 💾 保存缓存 (关键步骤)
            print("💾 Saving cache to disk...")
            faiss.write_index(self.index, index_path)
            with open(docs_path, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f)
                
            print(f"✅ [SmartSearch] Built and saved {len(self.documents)} snippets.")
        else:
            print("⚠️ [SmartSearch] No documents found.")
        
        self.initialized = True

    # ... (search 方法保持不变) ...
    def search(self, query, top_k=2):
        # 保持原样
        if not self.initialized or not self.documents: return [], []
        query_vec = self.model.encode([query])
        distances, indices = self.index.search(np.array(query_vec).astype('float32'), top_k)
        results = []
        scores = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                results.append(self.documents[idx])
                scores.append(distances[0][i])
        return results, scores
    
    
# 初始化全局 KB 实例
kb = LocalKnowledgeBase()
# 建议在 main.py 启动时调用 kb.init_kb()，但这里为了鲁棒性，会在 run 里懒加载

# === 2. 混合搜索工具 ===
class SearchArgs(BaseModel):
    query: str = Field(..., description="The query string to search for.")

class SmartSearchTool(BaseTool):
    name = "search" # 保持名字叫 search，这样队友的 prompt 不用改
    description = (
        "Intelligent Search Tool. "
        "First checks the local verified knowledge base (policies, guides). "
        "If no match found, searches the live internet using Google. "
        "Returns structured data with confidence scores."
    )
    args_schema = SearchArgs
    
    # 你的 API Key
    api_key: str = "8c5a260710c9c2aceda64505b3a551d88a7a14b6" 

    def _calculate_google_confidence(self, query: str, snippet: str, rank: int) -> float:
        """
        你的混合置信度算法 (保留原样)
        """
        rank_score = max(0.5, 0.9 - (rank * 0.05))
        q_tokens = set(re.findall(r'\w+', query.lower()))
        s_tokens = set(re.findall(r'\w+', snippet.lower()))
        if not q_tokens: return rank_score
        overlap = len(q_tokens.intersection(s_tokens))
        match_ratio = overlap / len(q_tokens)
        final_score = (rank_score * 0.7) + (match_ratio * 0.3)
        return round(final_score, 2)

    def _search_google(self, query: str) -> list:
        """
        纯 Google 搜索逻辑
        """
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 5})
        headers = {'X-API-KEY': self.api_key, 'Content-Type': 'application/json'}

        results = []
        try:
            response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "organic" in data:
                    for index, item in enumerate(data["organic"]):
                        snippet = item.get("snippet", "")
                        # 调用你的算法
                        confidence = self._calculate_google_confidence(query, snippet, index)
                        results.append({
                            "content": snippet,
                            "source": item.get("link", ""),
                            "title": item.get("title", ""),
                            "score": confidence,
                            "type": "internet" # 标记来源
                        })
        except Exception as e:
            print(f"Google Search Error: {e}")
        return results

    @monitor_execution(tool_name="smart_search")
    @lru_cache(maxsize=50) 
    def run(self, query: str) -> str:
        kb.init_kb()
        final_results = []
        
        # 阈值保持不变
        LOCAL_THRESHOLD = 0.95 
        
        # 🔴 改进点 1: 获取更多候选 (比如 Top 3)
        local_docs, local_dists = kb.search(query, top_k=3)
        
        found_local_match = False
        valid_local_snippets = [] # 用来存所有合格的片段
        
        if local_docs:
            # 只要第一条合格，我们就认为命中了本地
            if local_dists[0] < LOCAL_THRESHOLD:
                found_local_match = True
                
                # 🔴 改进点 2: 把所有合格的片段都收集起来
                for (doc_content, filename), dist in zip(local_docs, local_dists):
                    if dist < LOCAL_THRESHOLD:
                        valid_local_snippets.append(f"--- (Source: {filename}) ---\n{doc_content}")

        # 如果命中了本地，把收集到的片段拼成一个大结果返回
        if found_local_match:
            # 用换行符拼接
            combined_content = "\n\n".join(valid_local_snippets)
            final_results.append({
                "content": f"[Verified Local Guide]:\n{combined_content}",
                "source": "Local DB (Multiple Hits)", 
                "title": "Local Knowledge Base Match",
                "score": 1.0, 
                "type": "local"
            })

        # 联网部分保持不变
        if not found_local_match:
            google_results = self._search_google(query)
            final_results.extend(google_results)
            
        final_results.sort(key=lambda x: x["score"], reverse=True)
        
        if not final_results:
            return json.dumps({"status": "EMPTY", "results": []})

        return json.dumps({
            "status": "SUCCESS", 
            "results": final_results
        })