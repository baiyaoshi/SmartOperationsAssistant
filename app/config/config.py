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

    # Milvus
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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

# 创建全局单例
settings = Settings()