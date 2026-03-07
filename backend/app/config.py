from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    collection_name: str = "photos"
    photos_dir: str = "/photos"
    clip_model_name: str = "clip-ViT-B-32"
    embedding_dim: int = 512
    index_batch_size: int = 32
    search_default_limit: int = 20

    model_config = {"env_prefix": "FAMILYLENS_"}


settings = Settings()
