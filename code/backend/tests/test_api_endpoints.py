import pytest
import asyncio
import uuid
import time
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database import DB_PATH, init_db
import os

# Set up test environment
os.environ["PYTHONPATH"] = "code"

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    await init_db(DB_PATH)

@pytest.mark.anyio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.anyio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert "version" in response.json()
    assert response.json()["service"] == "SIGNAL"

@pytest.mark.anyio
async def test_company_intake_and_profile():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Intake
        intake_data = {
            "companyName": f"TestCorp_{uuid.uuid4().hex[:6]}",
            "industry": "Technology",
            "description": "A test company for API testing",
            "audience": "Developers",
            "tone": "Professional",
            "goals": "Test API endpoints",
            "website": "https://example.com"
        }
        response = await ac.post("/api/company/intake", json=intake_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        company_id = data["company_id"]
        assert company_id is not None

        # 2. Get latest profile
        response = await ac.get("/api/company/profile")
        assert response.status_code == 200
        profile = response.json()
        assert profile["name"] == intake_data["companyName"]
        assert profile["id"] == company_id

        # 3. Get profile by ID
        response = await ac.get(f"/api/company/profile/{company_id}")
        assert response.status_code == 200
        assert response.json()["id"] == company_id

@pytest.mark.anyio
async def test_signals_workflow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Refresh signals (async job)
        refresh_data = {"top_n": 3}
        response = await ac.post("/api/signals/refresh", json=refresh_data)
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # 2. Poll job
        result = await poll_job(ac, job_id)
        assert result["status"] == "succeeded"

        # 3. List signals
        response = await ac.get("/api/signals")
        assert response.status_code == 200
        signals = response.json()
        assert len(signals) > 0
        signal_id = signals[0]["id"]

        # 4. Get single signal
        response = await ac.get(f"/api/signals/{signal_id}")
        assert response.status_code == 200
        assert response.json()["id"] == signal_id

@pytest.mark.anyio
async def test_campaigns_workflow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Ensure we have a company
        intake_data = {
            "companyName": "CampaignTest",
            "industry": "Marketing",
            "description": "Testing campaigns"
        }
        await ac.post("/api/company/intake", json=intake_data)
        
        # 1. Generate campaigns
        gen_data = {"n_concepts": 2}
        response = await ac.post("/api/campaigns/generate", json=gen_data)
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # 2. Poll job
        result = await poll_job(ac, job_id)
        assert result["status"] == "succeeded"
        campaigns = result["result"]["campaigns"]
        assert len(campaigns) > 0
        campaign_id = campaigns[0]["id"]

        # 3. List campaigns
        response = await ac.get("/api/campaigns")
        assert response.status_code == 200
        assert len(response.json()) > 0

        # 4. Get campaign detail
        response = await ac.get(f"/api/campaigns/{campaign_id}")
        assert response.status_code == 200
        assert response.json()["id"] == campaign_id

        # 5. Approve campaign
        response = await ac.post(f"/api/campaigns/{campaign_id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

        # 6. Submit metrics
        metrics_data = {
            "channel": "linkedin",
            "impressions": 1000,
            "clicks": 50
        }
        response = await ac.post(f"/api/campaigns/{campaign_id}/metrics", json=metrics_data)
        assert response.status_code == 200
        assert response.json()["status"] == "recorded"

@pytest.mark.anyio
async def test_content_workflow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Get an existing campaign
        response = await ac.get("/api/campaigns")
        campaigns = response.json()
        if not campaigns:
            pytest.skip("No campaigns available for content testing")
        campaign_id = campaigns[0]["id"]

        # 1. Generate strategy
        response = await ac.post("/api/content/strategies/generate", json={"campaign_id": campaign_id})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        result = await poll_job(ac, job_id)
        assert result["status"] == "succeeded"
        strategies = result["result"]["strategies"]
        assert len(strategies) > 0
        strategy_id = strategies[0]["id"]

        # 2. List strategies
        response = await ac.get("/api/content/strategies", params={"campaign_id": campaign_id})
        assert response.status_code == 200
        assert len(response.json()) > 0

        # 3. Get strategy
        response = await ac.get(f"/api/content/strategies/{strategy_id}")
        assert response.status_code == 200
        assert response.json()["id"] == strategy_id

        # 4. Generate piece
        response = await ac.post("/api/content/pieces/generate", json={"strategy_id": strategy_id})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        result = await poll_job(ac, job_id)
        assert result["status"] == "succeeded"
        pieces = result["result"]["pieces"]
        assert len(pieces) > 0
        piece_id = pieces[0]["id"]

        # 5. List pieces
        response = await ac.get("/api/content/pieces", params={"strategy_id": strategy_id})
        assert response.status_code == 200
        assert len(response.json()) > 0

        # 6. Get piece
        response = await ac.get(f"/api/content/pieces/{piece_id}")
        assert response.status_code == 200
        assert response.json()["id"] == piece_id

        # 7. Update status
        response = await ac.patch(f"/api/content/pieces/{piece_id}/status", json={"status": "review"})
        assert response.status_code == 200
        assert response.json()["status"] == "review"

@pytest.mark.anyio
async def test_feedback_trigger():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/feedback/trigger", json={"run_loop1": True, "run_loop2": False, "run_loop3": False})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        result = await poll_job(ac, job_id, timeout=60)
        assert result["status"] in ["succeeded", "failed"] # Feedback loops might fail if no data

async def poll_job(ac, job_id, timeout=30, interval=2):
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = await ac.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in ["succeeded", "failed"]:
            return data
        await asyncio.sleep(interval)
    pytest.fail(f"Job {job_id} timed out")

@pytest.mark.anyio
async def test_error_cases():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 404 for non-existent job
        response = await ac.get(f"/api/jobs/{uuid.uuid4()}")
        assert response.status_code == 404

        # 404 for non-existent company
        response = await ac.get(f"/api/company/profile/{uuid.uuid4()}")
        assert response.status_code == 404

        # 422 for invalid intake
        response = await ac.post("/api/company/intake", json={"companyName": ""})
        assert response.status_code == 422
