"""
SIGNAL — Application Configuration
Loads all environment variables from .env and exposes them as typed settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the repo root (two levels up from this file)
_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Settings:
    # Google DeepMind / Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_GENAI_USE_VERTEXAI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").upper() == "TRUE"

    # Braintrust
    BRAINTRUST_API_KEY: str = os.getenv("BRAINTRUST_API_KEY", "")
    BRAINTRUST_PROJECT: str = os.getenv("BRAINTRUST_PROJECT", "signal")

    # Datadog
    DD_API_KEY: str = os.getenv("DD_API_KEY", "")
    DD_APP_KEY: str = os.getenv("DD_APP_KEY", "")
    DD_SITE: str = os.getenv("DD_SITE", "datadoghq.com")
    DD_SERVICE: str = os.getenv("DD_SERVICE", "signal-backend")
    DD_ENV: str = os.getenv("DD_ENV", "hackathon")

    # Application
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/signal.db")
    DATABASE_PATH: str = os.getenv("DATABASE_URL", "sqlite:///./data/signal.db").replace(
        "sqlite+aiosqlite:///", ""
    )
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CAMPAIGNS_PER_CYCLE: int = int(os.getenv("CAMPAIGNS_PER_CYCLE", "3"))
    SAFETY_THRESHOLD: float = float(os.getenv("SAFETY_THRESHOLD", "0.3"))

    # Polymarket
    POLYMARKET_BASE_URL: str = os.getenv("POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")
    POLYMARKET_VOLUME_THRESHOLD: float = float(os.getenv("POLYMARKET_VOLUME_THRESHOLD", "10000"))

    # Lightdash — self-hosted BI dashboard
    # LIGHTDASH_URL:          Base URL of the self-hosted Lightdash instance
    #                         e.g. "http://localhost:8080"
    # LIGHTDASH_API_KEY:      Personal API token from Lightdash user settings
    # LIGHTDASH_PROJECT_UUID: UUID of the SIGNAL project in Lightdash
    # LIGHTDASH_SECRET:       Internal server secret (set when running Lightdash itself,
    #                         NOT used for API calls)
    LIGHTDASH_URL: str = os.getenv("LIGHTDASH_URL", "")
    LIGHTDASH_API_KEY: str = os.getenv("LIGHTDASH_API_KEY", "")
    LIGHTDASH_PROJECT_UUID: str = os.getenv("LIGHTDASH_PROJECT_UUID", "")
    LIGHTDASH_SECRET: str = os.getenv("LIGHTDASH_SECRET", "")

    # Per-dashboard UUIDs (set after creating dashboards in Lightdash)
    LIGHTDASH_DASHBOARD_CAMPAIGN_PERF_UUID: str = os.getenv(
        "LIGHTDASH_DASHBOARD_CAMPAIGN_PERF_UUID", ""
    )
    LIGHTDASH_DASHBOARD_LEARNING_CURVE_UUID: str = os.getenv(
        "LIGHTDASH_DASHBOARD_LEARNING_CURVE_UUID", ""
    )
    LIGHTDASH_DASHBOARD_CALIBRATION_UUID: str = os.getenv(
        "LIGHTDASH_DASHBOARD_CALIBRATION_UUID", ""
    )
    LIGHTDASH_DASHBOARD_CHANNEL_PERF_UUID: str = os.getenv(
        "LIGHTDASH_DASHBOARD_CHANNEL_PERF_UUID", ""
    )
    LIGHTDASH_DASHBOARD_PATTERNS_UUID: str = os.getenv(
        "LIGHTDASH_DASHBOARD_PATTERNS_UUID", ""
    )
    LIGHTDASH_DASHBOARD_SAFETY_UUID: str = os.getenv(
        "LIGHTDASH_DASHBOARD_SAFETY_UUID", ""
    )

    @property
    def gemini_api_key_set(self) -> bool:
        return bool(self.GEMINI_API_KEY) and self.GEMINI_API_KEY != "your_gemini_api_key_here"

    @property
    def lightdash_configured(self) -> bool:
        """True when both LIGHTDASH_URL and LIGHTDASH_API_KEY are present."""
        return bool(self.LIGHTDASH_URL and self.LIGHTDASH_API_KEY)


settings = Settings()
