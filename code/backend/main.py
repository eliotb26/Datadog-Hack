"""
SIGNAL Backend — FastAPI app entry point (company profile + brand intake).
Run from repo root with PYTHONPATH=code:  uvicorn backend.main:app --reload --port 8000
Or from code/backend with PYTHONPATH=code:  python -m uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import company

app = FastAPI(
    title="SIGNAL API",
    description="Brand intake, trend signals, and campaign generation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(company.router)
# If you use the lightdash router, add:  app.include_router(lightdash.router)
# (Run from code/backend with PYTHONPATH=code/backend so 'integrations' resolves, or fix lightdash imports to backend.integrations.)


@app.get("/")
async def root():
    return {"service": "SIGNAL", "docs": "/docs"}
