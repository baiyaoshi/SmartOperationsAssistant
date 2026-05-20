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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

# 创建全局单例
settings = Settings()