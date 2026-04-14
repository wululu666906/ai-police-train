from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import cases, auth, prompts, training, dashboard
import database, models

# 不在启动时强制初始化，因为已经有 init_db.py
# models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI虚拟警情模拟训练平台 - API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(prompts.router)
app.include_router(training.router)
app.include_router(dashboard.router)

@app.get("/")
def read_root():
    return {"message": "AI虚拟警情模拟训练平台 - 核心引擎已启动"}
