from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gcp_project: str
    gcp_location: str = "us-central1"
    vertex_ai_credentials_file: str = "app/config/vertex-ai.json"

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()

