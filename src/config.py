from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):

    HOST: str = Field(
            default="0.0.0.0",
            description="Server host address"
        )
    PORT: int = Field(
            default=8000,
            description="Server port"
        )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode flag"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()