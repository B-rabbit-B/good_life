from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.config import get_settings
from app.disclaimer.router import router as disclaimer_router
from app.errors import register_error_handlers
from app.profile.router import router as profile_router


def create_app() -> FastAPI:
    get_settings()  # 配置或密钥不合法时启动即失败
    app = FastAPI(title="good-life API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(disclaimer_router)
    app.include_router(profile_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
