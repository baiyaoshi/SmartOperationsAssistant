from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM 配置
    llm_api_key: str = ""      # 对应 .env 里的 LLM_API_KEY
    llm_base_url: str = ""     # 对应 .env 里的 LLM_BASE_URL
    llm_model_name: str = "qwen-plus"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

# 创建全局单例
settings = Settings()