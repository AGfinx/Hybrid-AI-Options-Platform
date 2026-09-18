import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from db.database import init_db
from db.seed import seed_database
from services.api.routes import (
    market, forecasts, recommendations, mandates, risk, paper, reports
)

app = FastAPI(
    title="Hybrid AI Options Platform API",
    version="1.0.0",
    description="Human-in-the-loop crypto options analytics, risk-management, recommendation, and paper-trading platform.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID & Audit Correlation Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:8]}")
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

# Register API v1 routes
app.include_router(market.router, prefix="/api/v1")
app.include_router(forecasts.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(mandates.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(paper.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")

@app.on_event("startup")
def startup_event():
    init_db()
    seed_database()

@app.get("/")
def root():
    return {
        "platform": "Hybrid AI Options Platform",
        "status": "operational",
        "version": "1.0.0",
        "mode": "recommendation",
        "live_trading_enabled": False,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.api.main:app", host="0.0.0.0", port=8000, reload=True)
