from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ConsentKind = Literal["cycle", "medical"]


class ConsentOut(BaseModel):
    kind: ConsentKind
    title: str
    text: str
    current_version: str
    granted: bool  # 有同意记录且没有撤回
    granted_at: datetime | None
    granted_version: str | None
    withdrawn_at: datetime | None


class ConsentGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
