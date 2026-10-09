from fastapi import FastAPI

from app.agent.router import router as agent_router
from app.agent_grants.router import router as agent_grants_router
from app.auth.router import router as auth_router
from app.common.body_limit import EvidenceBodyLimitMiddleware
from app.config import get_settings
from app.cycle.router import router as cycle_router
from app.disclaimer.router import router as disclaimer_router
from app.errors import register_error_handlers
from app.fitness.router import router as fitness_router
from app.llm.router import router as llm_router
from app.medical.router import router as medical_router
from app.nutrition.router import router as nutrition_router
from app.profile.router import router as profile_router


def create_app() -> FastAPI:
    get_settings()  # 配置或密钥不合法时启动即失败
    app = FastAPI(title="good-life API", version="0.1.0")
    register_error_handlers(app)
    app.add_middleware(EvidenceBodyLimitMiddleware)
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

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
