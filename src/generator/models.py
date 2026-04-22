"""이벤트 Pydantic 스키마 5종.

공통 필드는 컬럼 → BaseEvent
이벤트별 가변 필드는 각 서브클래스 → DB의 properties JSONB에 매핑
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# 이벤트 타입별 가중치 (합 = 100)
# 현실 웹 서비스 로그 분포 반영: page_view 대량, 구매/에러 소량
WEIGHTS: dict[str, int] = {
    "page_view": 60,
    "click":     25,
    "purchase":   5,
    "signup":     5,
    "error":      5,
}

EVENT_TYPES = list(WEIGHTS.keys())
EVENT_WEIGHTS = list(WEIGHTS.values())


class BaseEvent(BaseModel):
    event_id:    UUID     = Field(default_factory=uuid4)
    session_id:  UUID
    user_id:     UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type:  str


class PageViewEvent(BaseEvent):
    event_type:  Literal["page_view"] = "page_view"
    url:         str
    referrer:    str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class ClickEvent(BaseEvent):
    event_type: Literal["click"] = "click"
    element_id: str
    page_url:   str


class PurchaseEvent(BaseEvent):
    event_type: Literal["purchase"] = "purchase"
    product_id: str
    amount:     float = Field(gt=0)   # 음수·0 금지
    currency:   str   = "KRW"


class SignupEvent(BaseEvent):
    event_type: Literal["signup"] = "signup"
    method:     Literal["email", "google", "kakao"] = "email"


class ErrorEvent(BaseEvent):
    event_type: Literal["error"] = "error"
    error_code: str
    page_url:   str
    message:    str | None = None


# 판별자(discriminator) 기반 유니온 — parse_event()에서 event_type으로 자동 분기
AnyEvent = Annotated[
    Union[PageViewEvent, ClickEvent, PurchaseEvent, SignupEvent, ErrorEvent],
    Field(discriminator="event_type"),
]


def parse_event(data: dict) -> AnyEvent:
    """dict → 타입별 이벤트 모델로 파싱. 실패 시 ValidationError raise."""
    from pydantic import TypeAdapter
    return TypeAdapter(AnyEvent).validate_python(data)


def event_to_properties(event: BaseEvent) -> dict:
    """이벤트 서브클래스 필드를 JSONB properties dict로 직렬화."""
    excluded = {"event_id", "session_id", "user_id", "occurred_at", "event_type"}
    return {k: v for k, v in event.model_dump().items() if k not in excluded and v is not None}
