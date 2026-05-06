from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import cases, auth, training, dashboard, knowledge, student
import database, models

# 不在启动时强制初始化，因为已经有 init_db.py
# models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI虚拟警情模拟训练平台 - API", version="1.0.0")


def ensure_default_users():
    db = database.SessionLocal()
    try:
        existing_count = db.query(models.User).count()
        if existing_count > 0:
            return

        db.add_all(
            [
                models.User(username="admin", hashed_password="123456", role="admin"),
                models.User(username="student001", hashed_password="123456", role="student"),
            ]
        )
        db.commit()
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 部署云服务器时允许所有跨域请求，或指定真实域名
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


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Serve static assets from the frontend/dist folder
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(os.path.join(frontend_dist, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # Optional: serve root icon files if needed (favicon, etc)
    @app.get("/favicon.svg")
    def serve_favicon():
        return FileResponse(os.path.join(frontend_dist, "favicon.svg"))
        
    @app.get("/icons.svg")
    def serve_icons():
        return FileResponse(os.path.join(frontend_dist, "icons.svg"))

@app.on_event("startup")
def on_startup():
    ensure_default_users()

# Catch-all route to serve the Vue SPA (Single Page Application)
@app.get("/{catchall:path}")
def serve_vue_app(catchall: str):
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI虚拟警情模拟训练平台 - 核心引擎已启动 (Frontend not built)"}
