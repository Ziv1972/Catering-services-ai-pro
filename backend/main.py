"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.api import auth, meetings, chat, dashboard, complaints
from backend.api import menu_compliance, proformas, historical, anomalies, webhooks, suppliers

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(meetings.router, prefix="/api/meetings", tags=["Meetings"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(complaints.router, prefix="/api/complaints", tags=["Complaints"])
app.include_router(menu_compliance.router, prefix="/api/menu-compliance", tags=["Menu Compliance"])
app.include_router(proformas.router, prefix="/api/proformas", tags=["Proformas"])
app.include_router(historical.router, prefix="/api/historical", tags=["Historical"])
app.include_router(anomalies.router, prefix="/api/anomalies", tags=["Anomalies"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Suppliers"])


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
