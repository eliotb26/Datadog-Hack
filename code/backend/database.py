"""
onlyGen — SQLite Database Setup
Uses aiosqlite for async access. No ORM — raw SQL per design decision.
"""
import asyncio
import json
import os
import aiosqlite
from pathlib import Path

DB_PATH = Path(os.getenv("DATABASE_PATH", str(Path(__file__).parent / "data" / "onlygen.db")))
_INIT_LOCK = asyncio.Lock()
_INITIALIZED_DBS: set[Path] = set()

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
    confidence_score REAL,
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

CREATE TABLE IF NOT EXISTS content_strategies (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    company_id TEXT REFERENCES companies(id),
    content_type TEXT NOT NULL,
    reasoning TEXT,
    target_length TEXT,
    tone_direction TEXT,
    structure_outline TEXT,
    priority_score REAL DEFAULT 0.5,
    visual_needed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS content_pieces (
    id TEXT PRIMARY KEY,
    strategy_id TEXT REFERENCES content_strategies(id),
    campaign_id TEXT REFERENCES campaigns(id),
    company_id TEXT REFERENCES companies(id),
    content_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    summary TEXT,
    word_count INTEGER DEFAULT 0,
    visual_prompt TEXT,
    visual_asset_url TEXT,
    quality_score REAL DEFAULT 0.0,
    brand_alignment REAL DEFAULT 0.0,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trend_signals_surfaced_at
ON trend_signals(surfaced_at DESC);

CREATE INDEX IF NOT EXISTS idx_trend_signals_category_surfaced
ON trend_signals(category, surfaced_at DESC);

CREATE INDEX IF NOT EXISTS idx_campaigns_created_at
ON campaigns(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_campaigns_company_status_created
ON campaigns(company_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_campaign_metrics_campaign_measured
ON campaign_metrics(campaign_id, measured_at DESC);
"""


async def init_db(db_path: Path = DB_PATH) -> None:
    """Create schema once per DB path and run lightweight migrations."""
    resolved_path = db_path.resolve()
    if resolved_path in _INITIALIZED_DBS:
        return
    async with _INIT_LOCK:
        if resolved_path in _INITIALIZED_DBS:
            return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(CREATE_TABLES_SQL)
        # Migration: add website column if missing (existing DBs)
        cursor = await db.execute("PRAGMA table_info(companies)")
        rows = await cursor.fetchall()
        has_website = any(r[1] == "website" for r in rows)
        if not has_website:
            await db.execute("ALTER TABLE companies ADD COLUMN website TEXT")
        cursor = await db.execute("PRAGMA table_info(trend_signals)")
        signal_rows = await cursor.fetchall()
        signal_cols = {r[1] for r in signal_rows}
        if "confidence_score" not in signal_cols:
            await db.execute("ALTER TABLE trend_signals ADD COLUMN confidence_score REAL")
        await db.commit()
    _INITIALIZED_DBS.add(resolved_path)


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


# ---------------------------------------------------------------------------
# Company helpers
# ---------------------------------------------------------------------------

async def list_companies(db_path: Path = DB_PATH) -> list[dict]:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM companies ORDER BY updated_at DESC")
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

async def list_signals(
    db_path: Path = DB_PATH,
    company_id: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        clauses, params = [], []
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor = await conn.execute(
            f"SELECT * FROM trend_signals {where} ORDER BY surfaced_at DESC LIMIT ?",
            params + [limit],
        )
        rows = await cursor.fetchall()
    parsed_rows = [dict(r) for r in rows]
    if not company_id:
        return parsed_rows

    # trend_signals is global; when company_id is provided, return only signals
    # that include a relevance score for that company.
    filtered: list[dict] = []
    for row in parsed_rows:
        rel = row.get("relevance_scores") or "{}"
        if isinstance(rel, str):
            try:
                rel = json.loads(rel)
            except Exception:
                rel = {}
        if isinstance(rel, dict) and company_id in rel:
            filtered.append(row)
    return filtered


async def get_signal_by_id(signal_id: str, db_path: Path = DB_PATH) -> dict | None:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM trend_signals WHERE id = ?", (signal_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def insert_signal(row: dict, db_path: Path = DB_PATH) -> None:
    """Insert or replace a signal row into trend_signals."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO trend_signals
                (id, polymarket_market_id, title, category,
                 probability, probability_momentum, volume, volume_velocity,
                 relevance_scores, confidence_score, surfaced_at, expires_at)
            VALUES
                (:id, :polymarket_market_id, :title, :category,
                 :probability, :probability_momentum, :volume, :volume_velocity,
                 :relevance_scores, :confidence_score, :surfaced_at, :expires_at)
            """,
            {
                **row,
                "confidence_score": row.get("confidence_score"),
            },
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Campaign helpers
# ---------------------------------------------------------------------------

async def list_campaigns(
    db_path: Path = DB_PATH,
    company_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        clauses, params = [], []
        if company_id:
            clauses.append("company_id = ?")
            params.append(company_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor = await conn.execute(
            f"SELECT * FROM campaigns {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def count_campaigns(
    db_path: Path = DB_PATH,
    company_id: str | None = None,
) -> int:
    """Return total campaign count, optionally scoped to a company."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        if company_id:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS cnt FROM campaigns WHERE company_id = ?",
                (company_id,),
            )
        else:
            cursor = await conn.execute("SELECT COUNT(*) AS cnt FROM campaigns")
        row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def get_campaign_by_id(campaign_id: str, db_path: Path = DB_PATH) -> dict | None:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def update_campaign_status(
    campaign_id: str, new_status: str, db_path: Path = DB_PATH
) -> None:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE campaigns SET status = ? WHERE id = ?", (new_status, campaign_id)
        )
        await conn.commit()


async def update_campaign_distribution(
    campaign_id: str,
    channel_recommendation: str,
    channel_reasoning: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    """Persist Agent 4 routing fields for a campaign."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        if channel_reasoning is None:
            await conn.execute(
                """
                UPDATE campaigns
                SET channel_recommendation = ?
                WHERE id = ?
                """,
                (channel_recommendation, campaign_id),
            )
        else:
            await conn.execute(
                """
                UPDATE campaigns
                SET channel_recommendation = ?, channel_reasoning = ?
                WHERE id = ?
                """,
                (channel_recommendation, channel_reasoning, campaign_id),
            )
        await conn.commit()


async def insert_campaign_metrics(row: dict, db_path: Path = DB_PATH) -> None:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO campaign_metrics
                (id, campaign_id, channel, impressions, clicks,
                 engagement_rate, sentiment_score, measured_at)
            VALUES
                (:id, :campaign_id, :channel, :impressions, :clicks,
                 :engagement_rate, :sentiment_score, :measured_at)
            """,
            row,
        )
        await conn.commit()


async def get_campaign_metrics(
    campaign_id: str, db_path: Path = DB_PATH
) -> list[dict]:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM campaign_metrics WHERE campaign_id = ? ORDER BY measured_at DESC",
            (campaign_id,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Agent trace helpers
# ---------------------------------------------------------------------------

async def insert_agent_trace(row: dict, db_path: Path = DB_PATH) -> None:
    """Insert one agent run trace row into agent_traces."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO agent_traces
                (id, agent_name, braintrust_trace_id, company_id,
                 input_summary, output_summary, quality_score,
                 tokens_used, latency_ms, created_at)
            VALUES
                (:id, :agent_name, :braintrust_trace_id, :company_id,
                 :input_summary, :output_summary, :quality_score,
                 :tokens_used, :latency_ms, :created_at)
            """,
            row,
        )
        await conn.commit()


async def list_agent_traces(
    db_path: Path = DB_PATH,
    agent_name: str | None = None,
    company_id: str | None = None,
    campaign_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List agent traces with optional filters.

    campaign_id is matched against output_summary text, where campaign ids are embedded.
    """
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        clauses, params = [], []
        if agent_name:
            clauses.append("agent_name = ?")
            params.append(agent_name)
        if company_id:
            clauses.append("company_id = ?")
            params.append(company_id)
        if campaign_id:
            clauses.append("output_summary LIKE ?")
            params.append(f"%campaign_id={campaign_id}%")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor = await conn.execute(
            f"SELECT * FROM agent_traces {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Feedback loop read helpers
# ---------------------------------------------------------------------------

async def get_prompt_weights(
    company_id: str,
    agent_name: str = "campaign_gen",
    db_path: Path = DB_PATH,
) -> dict[str, float]:
    """Return prompt weights for a company/agent keyed by weight_key."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT weight_key, weight_value
            FROM prompt_weights
            WHERE company_id = ? AND agent_name = ?
            ORDER BY updated_at DESC
            """,
            (company_id, agent_name),
        )
        rows = await cursor.fetchall()
    return {str(r["weight_key"]): float(r["weight_value"] or 1.0) for r in rows}


async def get_shared_patterns(
    db_path: Path = DB_PATH,
    pattern_type: str | None = None,
    min_confidence: float = 0.0,
    industry: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return shared patterns with optional type/industry filtering."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        clauses = ["confidence >= ?"]
        params: list = [min_confidence]
        if pattern_type:
            clauses.append("pattern_type = ?")
            params.append(pattern_type)
        where = " AND ".join(clauses)
        cursor = await conn.execute(
            f"""
            SELECT *
            FROM shared_patterns
            WHERE {where}
            ORDER BY confidence DESC, discovered_at DESC
            LIMIT ?
            """,
            params + [limit],
        )
        rows = [dict(r) for r in await cursor.fetchall()]

    parsed: list[dict] = []
    for row in rows:
        try:
            cond = json.loads(row.get("conditions") or "{}")
        except Exception:
            cond = {}
        try:
            eff = json.loads(row.get("effect") or "{}")
        except Exception:
            eff = {}
        row["conditions"] = cond
        row["effect"] = eff
        parsed.append(row)

    if not industry:
        return parsed

    needle = industry.strip().lower()
    filtered: list[dict] = []
    for row in parsed:
        cond_industry = str((row.get("conditions") or {}).get("industry", "")).strip().lower()
        if not cond_industry:
            filtered.append(row)
            continue
        if cond_industry == needle:
            filtered.append(row)
    return filtered


async def get_signal_calibration(
    db_path: Path = DB_PATH,
    company_type: str | None = None,
    signal_category: str | None = None,
    min_accuracy: float = 0.0,
    limit: int = 100,
) -> list[dict]:
    """Return signal calibration rows, newest first, with optional filters."""
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        clauses = ["accuracy_score >= ?"]
        params: list = [min_accuracy]
        if company_type:
            clauses.append("company_type = ?")
            params.append(company_type)
        if signal_category:
            clauses.append("signal_category = ?")
            params.append(signal_category)
        where = " AND ".join(clauses)
        cursor = await conn.execute(
            f"""
            SELECT *
            FROM signal_calibration
            WHERE {where}
            ORDER BY calibrated_at DESC
            LIMIT ?
            """,
            params + [limit],
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Content strategy helpers
# ---------------------------------------------------------------------------

async def list_content_strategies(
    db_path: Path = DB_PATH,
    campaign_id: str | None = None,
    company_id: str | None = None,
) -> list[dict]:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        clauses, params = [], []
        if campaign_id:
            clauses.append("campaign_id = ?")
            params.append(campaign_id)
        if company_id:
            clauses.append("company_id = ?")
            params.append(company_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor = await conn.execute(
            f"SELECT * FROM content_strategies {where} ORDER BY created_at DESC",
            params,
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_content_strategy_by_id(
    strategy_id: str, db_path: Path = DB_PATH
) -> dict | None:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM content_strategies WHERE id = ?", (strategy_id,)
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Content piece helpers
# ---------------------------------------------------------------------------

async def list_content_pieces(
    db_path: Path = DB_PATH,
    strategy_id: str | None = None,
    campaign_id: str | None = None,
    company_id: str | None = None,
) -> list[dict]:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        clauses, params = [], []
        if strategy_id:
            clauses.append("strategy_id = ?")
            params.append(strategy_id)
        if campaign_id:
            clauses.append("campaign_id = ?")
            params.append(campaign_id)
        if company_id:
            clauses.append("company_id = ?")
            params.append(company_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor = await conn.execute(
            f"SELECT * FROM content_pieces {where} ORDER BY created_at DESC",
            params,
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_content_piece_by_id(
    piece_id: str, db_path: Path = DB_PATH
) -> dict | None:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM content_pieces WHERE id = ?", (piece_id,)
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def update_content_piece_status(
    piece_id: str, new_status: str, db_path: Path = DB_PATH
) -> None:
    await init_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE content_pieces SET status = ? WHERE id = ?", (new_status, piece_id)
        )
        await conn.commit()


if __name__ == "__main__":
    asyncio.run(init_db())
    print(f"Database initialized at {DB_PATH}")
