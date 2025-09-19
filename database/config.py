
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    class Config:
        env_file = ".env"

settings = Settings()
