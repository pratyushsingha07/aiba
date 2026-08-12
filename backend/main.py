"""
main.py
────────
FastAPI application entrypoint for the BI Dashboard SaaS API.

Start the server:
  uvicorn main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import upload, confirm_mapping, dashboard, export, audit, insights, ask

app = FastAPI(
    title="BI Dashboard SaaS API",
    version="2.0.0",
    description=(
        "REST API for the BI Dashboard. Exposes upload, confirm-mapping, "
        "dashboard, export, audit, insights, and ask endpoints backed by Supabase."
    ),
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Adjust allowed_origins for production — do not use '*' with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload.router,          prefix="/api/v1")
app.include_router(confirm_mapping.router, prefix="/api/v1")
app.include_router(dashboard.router,       prefix="/api/v1")
app.include_router(export.router,          prefix="/api/v1")
app.include_router(audit.router,           prefix="/api/v1")
app.include_router(insights.router,        prefix="/api/v1")
app.include_router(ask.router,             prefix="/api/v1")



# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "BI Dashboard API", "version": "2.0.0"}
