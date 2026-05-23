from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM 配置
    llm_api_key: str = ""      # 对应 .env 里的 LLM_API_KEY
    llm_base_url: str = ""     # 对应 .env 里的 LLM_BASE_URL
    llm_model_name: str = "qwen-plus"

    # Redis 配置
    redis_url: str = "redis://localhost:6379"
    chat_memory_enabled: bool = True
    chat_memory_ttl_sec: int = 86400         # 记忆过期时间 (24小时)
    chat_max_messages: int = 20             # 最大消息条数

    # DashScope (Embedding + Reranker)
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_embedding_model: str = "text-embedding-v3"
    dashscope_embedding_dim: int = 1024

    # milvus
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_collection: str = "knowledge_base"

    # RAG 相关
    rag_top_k: int = 3
    rag_retrieve_k: int = 20
    rag_hybrid_enabled: bool = True
    rag_rerank_enabled: bool = True
    rag_rerank_model: str = "gte-rerank-v2"
    rag_rerank_timeout_sec: int = 30
    rag_chunk_size: int = 800                     # 文档分块大小 (字符)
    rag_chunk_overlap: int = 100                  # 分块重叠大小 (字符)
    rag_hybrid_bm25_weight: float = 0.4           # Hybrid 中 BM25 的权重

    # 联网搜索
    web_search_provider: str = "open_websearch"             # open_websearch / mock
    open_websearch_base_url: str = "http://127.0.0.1:3210"
    open_websearch_engine: str = "bing"
    open_websearch_search_mode: str = "auto"
    open_websearch_timeout_sec: float = 15.0

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

# 创建全局单例
settings = Settings()
