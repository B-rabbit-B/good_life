from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.disclaimer.router import router as disclaimer_router
from app.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="good-life API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(disclaimer_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
