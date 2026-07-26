from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    gemini_api_key: str
    llm_model: str = "gemini-1.5-flash"        # fast + cheap for agents
    llm_model_pro: str = "gemini-1.5-pro"      # for executive summary only

    # Database
    database_url: str = "postgresql+asyncpg://auditmind:auditmind@localhost:5432/auditmind"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # GitHub
    github_token: str = ""

    # Reports
    report_output_dir: str = "/tmp/auditmind_reports"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"

    class Config:
        env_file = ".env"

settings = Settings()