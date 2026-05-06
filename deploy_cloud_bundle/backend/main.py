import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers import auth, cases, dashboard, knowledge, student, training


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"


def get_allowed_origins() -> list[str]:
    origins = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if origins:
        return origins
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


app = FastAPI(title="AI虚拟警情处置模拟训练平台 - API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(training.router)
app.include_router(dashboard.router)
app.include_router(knowledge.router)
app.include_router(student.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    if not FRONTEND_INDEX.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend build not found. Run `npm run build` in the frontend directory first."
        )

    requested_path = (FRONTEND_DIST_DIR / full_path).resolve()
    if full_path and requested_path.is_file() and FRONTEND_DIST_DIR in requested_path.parents:
        return FileResponse(requested_path)

    return FileResponse(FRONTEND_INDEX)
