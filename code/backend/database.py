"""
onlyGen — SQLite Database Setup
Uses aiosqlite for async access. No ORM — raw SQL per design decision.
"""
import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "onlygen.db"

CREATE_TABLES_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    website TEXT,
    tone_of_voice TEXT,
    target_audience TEXT,
    campaign_goals TEXT,
    competitors TEXT,
    content_history TEXT,
    visual_style TEXT,
    safety_threshold REAL DEFAULT 0.7,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trend_signals (
    id TEXT PRIMARY KEY,
    polymarket_market_id TEXT,
    title TEXT NOT NULL,
    category TEXT,
    probability REAL,
    probability_momentum REAL,
    volume REAL,
    volume_velocity REAL,
    relevance_scores TEXT,
    surfaced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id),
    trend_signal_id TEXT REFERENCES trend_signals(id),
    headline TEXT NOT NULL,
    body_copy TEXT NOT NULL,
    visual_direction TEXT,
    visual_asset_url TEXT,
    confidence_score REAL,
    channel_recommendation TEXT,
    channel_reasoning TEXT,
    safety_score REAL,
    safety_passed BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_metrics (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    channel TEXT,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    engagement_rate REAL DEFAULT 0.0,
    sentiment_score REAL,
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prompt_weights (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id),
    agent_name TEXT NOT NULL,
    weight_key TEXT NOT NULL,
    weight_value REAL DEFAULT 1.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, agent_name, weight_key)
);

CREATE TABLE IF NOT EXISTS shared_patterns (
    id TEXT PRIMARY KEY,
    pattern_type TEXT,
    description TEXT,
    conditions TEXT,
    effect TEXT,
    confidence REAL,
    sample_size INTEGER,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signal_calibration (
    id TEXT PRIMARY KEY,
    signal_category TEXT,
    probability_threshold REAL,
    volume_velocity_threshold REAL,
    predicted_engagement REAL,
    actual_engagement REAL,
    accuracy_score REAL,
    company_type TEXT,
    calibrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_traces (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    braintrust_trace_id TEXT,
    company_id TEXT REFERENCES companies(id),
    input_summary TEXT,
    output_summary TEXT,
    quality_score REAL,
    tokens_used INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db(db_path: Path = DB_PATH) -> None:
    """Create all tables if they don't exist. Add missing columns for existing DBs."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(CREATE_TABLES_SQL)
        # Migration: add website column if missing (existing DBs)
        cursor = await db.execute("PRAGMA table_info(companies)")
        rows = await cursor.fetchall()
        has_website = any(r[1] == "website" for r in rows)
        if not has_website:
            await db.execute("ALTER TABLE companies ADD COLUMN website TEXT")
        await db.commit()


async def get_company_by_id(company_id: str, db_path: Path = DB_PATH) -> dict | None:
    """Load a single company row by id. Returns dict suitable for CompanyProfile.from_db_row, or None."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def get_latest_company_row(db_path: Path = DB_PATH) -> dict | None:
    """Load the most recently updated company row. Returns dict suitable for CompanyProfile.from_db_row, or None."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM companies ORDER BY updated_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def get_db(db_path: Path = DB_PATH):
    """Async context manager for database connections."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db


if __name__ == "__main__":
    asyncio.run(init_db())
    print(f"Database initialized at {DB_PATH}")
