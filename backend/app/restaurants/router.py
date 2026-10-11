from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.llm.service import AdapterFactory, get_adapter_factory
from app.nutrition.deps import require_nutrition_user
from app.restaurants import service
from app.restaurants.amap import AmapClient, get_amap_client
from app.restaurants.models import RestaurantSettings
from app.restaurants.needs import load_needs
from app.restaurants.schemas import ConsentIn, NeedOut, SearchIn, SearchOut, SettingsOut

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])

RestaurantUser = Annotated[User, Depends(require_nutrition_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]


def _settings_out(settings: RestaurantSettings) -> SettingsOut:
    """只有从未询问过时才提示前端询问定位；拒绝之后一直为假，直到用户自己改回授权。"""
    area = settings.area
    return SettingsOut(
        location_consent=settings.location_consent,
        should_ask_location=settings.location_consent == service.NOT_ASKED,
        area={"name": area["name"], "saved_at": settings.area_saved_at} if area else None,
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings(user: RestaurantUser, db: DbSession) -> SettingsOut:
    return _settings_out(service.get_settings(db, user.id))


@router.put("/settings/consent", response_model=SettingsOut)
def set_consent(body: ConsentIn, user: RestaurantUser, db: DbSession) -> SettingsOut:
    return _settings_out(service.set_consent(db, user.id, body.consent))


@router.delete("/settings/area", status_code=204)
def clear_area(user: RestaurantUser, db: DbSession) -> Response:
    service.clear_area(db, user.id)
    return Response(status_code=204)


@router.get("/needs", response_model=list[NeedOut])
def list_needs(user: RestaurantUser) -> list[NeedOut]:
    return [NeedOut(key=need.key, name=need.name, description=need.description) for need in load_needs()]


@router.post("/search", response_model=SearchOut)
def search(
    body: SearchIn,
    user: RestaurantUser,
    db: DbSession,
    today: Today,
    client: Annotated[AmapClient, Depends(get_amap_client)],
    factory: Annotated[AdapterFactory, Depends(get_adapter_factory)],
) -> SearchOut:
    return SearchOut(**service.search(db, user.id, body, today, client=client, factory=factory))
