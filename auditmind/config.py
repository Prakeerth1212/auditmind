from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str
    llm_model: str = "gemini-1.5-flash"      
    llm_model_pro: str = "gemini-1.5-pro"     
    database_url: str = "postgresql+asyncpg://auditmind:auditmind@localhost:5432/auditmind"
    redis_url: str = "redis://localhost:6379/0"
    github_token: str = ""
    report_output_dir: str = "/tmp/auditmind_reports"
    mlflow_tracking_uri: str = "http://localhost:5000"

    class Config:
        env_file = ".env"

settings = Settings()
