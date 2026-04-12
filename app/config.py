from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    db_name: str = "voice_cloning"

    # Storage paths (relative to project root)
    checkpoints_dir: str = "checkpoints"
    outputs_dir: str = "outputs"

    # TTS model identifier
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"

    # Audio settings
    sample_rate: int = 24000

    # Security & Rate Limiting
    api_key: str = "change-me-in-production"  # MUST be set via environment
    rate_limit_requests: int = 10  # requests per minute per IP
    rate_limit_window: int = 60  # seconds

    # Request constraints
    max_file_size_mb: int = 50  # Max upload size (50 MB)
    max_text_length: int = 4096  # Max synthesis text length
    request_timeout_seconds: int = 300  # 5 minutes for inference

    # Deployment mode
    debug: bool = False
    workers: int = 1  # Keep at 1 to prevent GPU memory duplication

    # Ignore unknown keys (e.g. COQUI_TOS_AGREED) so they can pass through to os.environ
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def validate_security_settings(self) -> None:
        """Ensure production-critical settings are configured."""
        if self.debug:
            raise RuntimeError("DEBUG mode is enabled! Disable in production.")
        if self.api_key == "change-me-in-production":
            raise RuntimeError(
                "API_KEY not configured! Set a strong API_KEY environment variable."
            )


settings = Settings()
