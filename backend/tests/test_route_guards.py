from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from app.cycle.deps import require_cycle_user
from app.disclaimer.deps import require_disclaimer_user
from app.main import create_app

# 不需要免责声明门槛的 /api 接口：健康检查、账号接口、免责声明本身。
ALLOWED_PREFIXES = ("/api/auth/", "/api/disclaimer/")
ALLOWED_PATHS = {"/api/health", "/api/disclaimer"}


def _dependency_calls(dependant: Dependant) -> set:
    calls = set()
    for sub in dependant.dependencies:
        calls.add(sub.call)
        calls |= _dependency_calls(sub)
    return calls


def _api_routes(app: FastAPI) -> list:
    # FastAPI 0.142 起 app.routes 里 include_router 进来的路由被包在内部对象里，
    # 必须用 iter_route_contexts 展开，才能看到每条接口的完整路径和依赖。
    return [
        ctx
        for ctx in iter_route_contexts(app.routes)
        if isinstance(ctx.original_route, APIRoute) and ctx.path.startswith("/api/")
    ]


def _unguarded_api_paths(app: FastAPI) -> list[str]:
    unguarded = []
    for ctx in _api_routes(app):
        if ctx.path in ALLOWED_PATHS or ctx.path.startswith(ALLOWED_PREFIXES):
            continue
        if require_disclaimer_user not in _dependency_calls(ctx.dependant):
            unguarded.append(f"{sorted(ctx.methods)} {ctx.path}")
    return unguarded


def test_route_walk_sees_included_routers():
    paths = {ctx.path for ctx in _api_routes(create_app())}
    assert {"/api/health", "/api/auth/login", "/api/disclaimer", "/api/profile", "/api/me/capabilities"} <= paths


def test_every_business_route_requires_disclaimer():
    assert _unguarded_api_paths(create_app()) == []


def test_guard_check_detects_unguarded_route():
    app = create_app()
    router = APIRouter(prefix="/api/_test")

    @router.get("/unguarded")
    def unguarded() -> dict[str, str]:
        return {}

    app.include_router(router)
    assert _unguarded_api_paths(app) == ["['GET'] /api/_test/unguarded"]


def test_every_cycle_route_requires_cycle_user():
    cycle_routes = [ctx for ctx in _api_routes(create_app()) if ctx.path.startswith("/api/cycle/")]
    assert len(cycle_routes) >= 10
    unguarded = [ctx.path for ctx in cycle_routes if require_cycle_user not in _dependency_calls(ctx.dependant)]
    assert unguarded == []


def test_every_medical_route_requires_medical_user():
    from app.medical.deps import require_medical_user

    routes = [ctx for ctx in _api_routes(create_app()) if ctx.path.startswith("/api/medical/")]
    assert len(routes) >= 18
    missing = [ctx.path for ctx in routes if require_medical_user not in _dependency_calls(ctx.dependant)]
    assert missing == []
