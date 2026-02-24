"""
onlyGen - Application Configuration
Loads all environment variables from .env and exposes them as typed settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the repo root (two levels up from this file)
_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Settings:
    # LLM provider credentials
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # Google DeepMind / Gemini (fallback compatibility)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_GENAI_USE_VERTEXAI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").upper() == "TRUE"
    GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    GEMINI_VIDEO_MODEL: str = os.getenv("GEMINI_VIDEO_MODEL", "veo-3.1-fast-generate-preview")
    GEMINI_MEDIA_TIMEOUT_S: int = int(os.getenv("GEMINI_MEDIA_TIMEOUT_S", "45"))
    ENABLE_GEMINI_MEDIA: bool = os.getenv("ENABLE_GEMINI_MEDIA", "TRUE").upper() == "TRUE"
    ENABLE_VIDEO_GEN: bool = os.getenv("ENABLE_VIDEO_GEN", "FALSE").upper() == "TRUE"

    # Braintrust
    BRAINTRUST_API_KEY: str = os.getenv("BRAINTRUST_API_KEY", "")
    BRAINTRUST_PROJECT: str = os.getenv("BRAINTRUST_PROJECT", "onlygen")

    # Airia - Enterprise Orchestration & AI Gateway
    AIRIA_API_KEY: str = os.getenv("AIRIA_API_KEY", "")
    AIRIA_PIPELINE_URL: str = os.getenv("AIRIA_PIPELINE_URL", "")
    # Per-agent pipeline GUIDs (set after creating agents in Airia Studio)
    AIRIA_PIPELINE_BRAND_INTAKE: str = os.getenv("AIRIA_PIPELINE_BRAND_INTAKE", "")
    AIRIA_PIPELINE_TREND_INTEL: str = os.getenv("AIRIA_PIPELINE_TREND_INTEL", "")
    AIRIA_PIPELINE_CAMPAIGN_GEN: str = os.getenv("AIRIA_PIPELINE_CAMPAIGN_GEN", "")
    AIRIA_PIPELINE_DISTRIBUTION: str = os.getenv("AIRIA_PIPELINE_DISTRIBUTION", "")
    AIRIA_PIPELINE_FEEDBACK_LOOP: str = os.getenv("AIRIA_PIPELINE_FEEDBACK_LOOP", "")

    # Datadog
    DD_API_KEY: str = os.getenv("DD_API_KEY", "")
    DD_APP_KEY: str = os.getenv("DD_APP_KEY", "")
    DD_SITE: str = os.getenv("DD_SITE", "datadoghq.com")
    DD_SERVICE: str = os.getenv("DD_SERVICE", "onlygen-backend")
    DD_ENV: str = os.getenv("DD_ENV", "hackathon")

    # Application
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/onlygen.db")
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH",
        DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", ""),
    )
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CAMPAIGNS_PER_CYCLE: int = int(os.getenv("CAMPAIGNS_PER_CYCLE", "3"))
    SAFETY_THRESHOLD: float = float(os.getenv("SAFETY_THRESHOLD", "0.3"))
    FEEDBACK_SCHEDULER_ENABLED: bool = os.getenv("FEEDBACK_SCHEDULER_ENABLED", "TRUE").upper() == "TRUE"
    FEEDBACK_SCHEDULER_INTERVAL_S: int = int(os.getenv("FEEDBACK_SCHEDULER_INTERVAL_S", "900"))
    FEEDBACK_SCHEDULER_RUN_ON_START: bool = os.getenv("FEEDBACK_SCHEDULER_RUN_ON_START", "FALSE").upper() == "TRUE"
    FEEDBACK_SCHEDULER_RUN_LOOP1: bool = os.getenv("FEEDBACK_SCHEDULER_RUN_LOOP1", "TRUE").upper() == "TRUE"
    FEEDBACK_SCHEDULER_RUN_LOOP2: bool = os.getenv("FEEDBACK_SCHEDULER_RUN_LOOP2", "TRUE").upper() == "TRUE"
    FEEDBACK_SCHEDULER_RUN_LOOP3: bool = os.getenv("FEEDBACK_SCHEDULER_RUN_LOOP3", "TRUE").upper() == "TRUE"

    # Polymarket
    POLYMARKET_BASE_URL: str = os.getenv("POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")
    POLYMARKET_VOLUME_THRESHOLD: float = float(os.getenv("POLYMARKET_VOLUME_THRESHOLD", "10000"))
    POLYMARKET_VOLUME_VELOCITY_THRESHOLD: float = float(
        os.getenv("POLYMARKET_VOLUME_VELOCITY_THRESHOLD", "0.0")
    )

    # Modulate AI - voice intelligence + content safety
    # Key obtained from Carter on hackathon Discord (#modulate-ai)
    MODULATE_API_KEY: str = os.getenv("MODULATE_API_KEY", "")
    MODULATE_VELMA_BASE_URL: str = os.getenv(
        "MODULATE_VELMA_BASE_URL", "https://modulate-prototype-apis.com"
    )

    @property
    def modulate_configured(self) -> bool:
        """True when a real (non-placeholder) Modulate API key is set."""
        placeholders = {"", "your_modulate_api_key_here", "your_modulate_toxmod_api_key_here"}
        return self.MODULATE_API_KEY not in placeholders

    @property
    def airia_configured(self) -> bool:
        """True when AIRIA_API_KEY is set and non-placeholder."""
        placeholders = {"", "your_airia_api_key_here", "ak-your_key_here"}
        return self.AIRIA_API_KEY not in placeholders

    @property
    def gemini_api_key_set(self) -> bool:
        return self.llm_api_key_set

    @property
    def llm_api_key(self) -> str:
        """Primary runtime API key: OpenRouter first, then Gemini fallback."""
        return self.OPENROUTER_API_KEY or self.GEMINI_API_KEY

    @property
    def llm_api_key_set(self) -> bool:
        placeholders = {
            "",
            "your_openrouter_api_key_here",
            "your_gemini_api_key_here",
        }
        return self.llm_api_key not in placeholders


settings = Settings()
