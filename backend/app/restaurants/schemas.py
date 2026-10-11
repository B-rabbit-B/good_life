import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.nutrition.schemas import Conclusion, ReasonOut
from app.restaurants.needs import MAX_NEEDS

LocationConsent = Literal["not_asked", "granted", "denied"]


class Coordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lng: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
    lat: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    coord_type: Literal["gps", "gcj02"] = "gps"


class SearchIn(BaseModel):
    """地点三选一：坐标（要求已授权定位）、手动地点（可加城市）、已保存的大致区域。一种都没给时由服务报错。"""

    model_config = ConfigDict(extra="forbid")

    location: Coordinate | None = None
    place: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None = None
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)] | None = None
    use_saved_area: bool = False
    need: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    needs: Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=32)]], Field(max_length=MAX_NEEDS)
    ] = []
    radius: Annotated[int, Field(ge=500, le=5000)] = 2000
    remember_area: bool = False

    @model_validator(mode="after")
    def _one_location(self) -> "SearchIn":
        given = sum([self.location is not None, self.place is not None, self.use_saved_area])
        if given > 1:
            raise ValueError("地点只能三选一：坐标、手动地点或已保存的大致区域")
        if self.city is not None and self.place is None:
            raise ValueError("city 只能和 place 一起使用")
        return self


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent: Literal["granted", "denied"]


class AreaOut(BaseModel):
    name: str
    saved_at: dt.datetime | None


class SettingsOut(BaseModel):
    location_consent: LocationConsent
    should_ask_location: bool
    area: AreaOut | None


class NeedOut(BaseModel):
    key: str
    name: str
    description: str


class CenterOut(BaseModel):
    name: str
    source: Literal["gps", "place", "saved_area"]


class NeedsUsedOut(BaseModel):
    keys: list[str]
    names: list[str]
    source: Literal["rules", "model", "none"]


class RestaurantOut(BaseModel):
    id: str
    name: str
    type_key: str | None
    type_name: str | None
    distance_m: int | None
    rating: float | None
    address: str
    conclusion: Literal["suitable", "caution", "unchecked"]
    nav_url: str
    tip: str | None


class DishReasonOut(ReasonOut):
    """引擎给出的原因，连同给出这条原因的代表菜。"""

    food_name: str


class TypeAdviceOut(BaseModel):
    type_key: str
    type_name: str
    conclusion: Conclusion
    order: list[str]
    moderate: list[str]
    avoid: list[str]
    reasons: list[DishReasonOut]


class AvoidedTypeOut(BaseModel):
    type_key: str
    type_name: str
    reasons: list[DishReasonOut]
    restaurants: list[str]


class SearchOut(BaseModel):
    center: CenterOut
    needs: NeedsUsedOut
    restaurants: list[RestaurantOut]
    type_advice: list[TypeAdviceOut]
    avoided_types: list[AvoidedTypeOut]
    notice: str
    disclaimer: str
