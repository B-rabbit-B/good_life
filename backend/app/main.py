from fastapi import FastAPI

from app.agent.router import router as agent_router
from app.agent_grants.router import router as agent_grants_router
from app.auth.router import router as auth_router
from app.common.body_limit import UploadBodyLimitMiddleware
from app.config import get_settings
from app.cycle.router import router as cycle_router
from app.disclaimer.router import router as disclaimer_router
from app.errors import register_error_handlers
from app.fitness.router import router as fitness_router
from app.frontend_static import DEFAULT_DIST, mount_frontend
from app.llm.router import router as llm_router
from app.medical.router import router as medical_router
from app.nutrition.router import router as nutrition_router
from app.photos.router import router as photos_router
from app.profile.router import router as profile_router
from app.restaurants.router import router as restaurants_router


def create_app(*, serve_frontend: bool = True) -> FastAPI:
    settings = get_settings()  # 配置或密钥不合法时启动即失败
    app = FastAPI(title="good-life API", version="0.1.0")
    register_error_handlers(app)
    app.add_middleware(UploadBodyLimitMiddleware)
    app.include_router(auth_router)
    app.include_router(disclaimer_router)
    app.include_router(profile_router)
    app.include_router(cycle_router)
    app.include_router(medical_router)
    app.include_router(nutrition_router)
    app.include_router(fitness_router)
    app.include_router(agent_grants_router)
    app.include_router(llm_router)
    app.include_router(agent_router)
    app.include_router(photos_router)
    app.include_router(restaurants_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if serve_frontend:
        mount_frontend(app, settings.frontend_dist_dir or DEFAULT_DIST)
    return app


app = create_app()
