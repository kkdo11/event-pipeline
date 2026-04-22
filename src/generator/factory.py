"""Faker 기반 이벤트 랜덤 생성.

SessionPool: 유저/세션을 메모리에 유지 → FK 제약 충족
random_event(): 풀에서 랜덤 세션 선택 → 가중 랜덤 이벤트 반환
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from faker import Faker

from .models import (
    AnyEvent,
    ClickEvent,
    ErrorEvent,
    PageViewEvent,
    PurchaseEvent,
    SignupEvent,
    EVENT_TYPES,
    EVENT_WEIGHTS,
)

fake = Faker("ko_KR")

_PAGES     = ["/", "/home", "/products", "/cart", "/checkout", "/profile", "/search"]
_PRODUCTS  = [f"P{i:03d}" for i in range(1, 51)]
_ERROR_CODES = ["400", "401", "403", "404", "500", "502", "503"]
_ELEMENTS  = ["btn-buy", "btn-add-cart", "nav-home", "search-bar", "product-card", "footer-link"]
_METHODS   = ["email", "google", "kakao"]
_PLATFORMS = ["web", "mobile", "api"]
_COUNTRIES = ["KR", "KR", "KR", "US", "JP"]  # KR 가중


@dataclass(frozen=True)
class UserRecord:
    user_id:    UUID
    country:    str
    platform:   str
    created_at: datetime


@dataclass(frozen=True)
class SessionRecord:
    session_id: UUID
    user_id:    UUID
    started_at: datetime
    user_agent: str


class SessionPool:
    """유저/세션 풀 — 이벤트 FK 충족을 위해 먼저 DB에 삽입 후 사용."""

    def __init__(self, user_count: int = 50, sessions_per_user: int = 3) -> None:
        self.users:    list[UserRecord]    = []
        self.sessions: list[SessionRecord] = []
        self._build(user_count, sessions_per_user)

    def _build(self, user_count: int, sessions_per_user: int) -> None:
        for _ in range(user_count):
            user = UserRecord(
                user_id=uuid4(),
                country=random.choice(_COUNTRIES),
                platform=random.choice(_PLATFORMS),
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 365)),
            )
            self.users.append(user)
            for _ in range(sessions_per_user):
                self.sessions.append(SessionRecord(
                    session_id=uuid4(),
                    user_id=user.user_id,
                    started_at=datetime.now(timezone.utc) - timedelta(minutes=random.randint(0, 60)),
                    user_agent=fake.user_agent(),
                ))

    def random_session(self) -> SessionRecord:
        return random.choice(self.sessions)


def random_event(session: SessionRecord, occurred_at: datetime | None = None) -> AnyEvent:
    """가중 분포 기반 랜덤 이벤트 생성. occurred_at 미지정 시 현재 시각."""
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)

    event_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]
    base = dict(session_id=session.session_id, user_id=session.user_id, occurred_at=occurred_at)

    match event_type:
        case "page_view":
            return PageViewEvent(
                **base,
                url=random.choice(_PAGES),
                referrer=random.choice(_PAGES + [None, None]),  # None 확률 높임
                duration_ms=random.randint(300, 30_000),
            )
        case "click":
            return ClickEvent(
                **base,
                element_id=random.choice(_ELEMENTS),
                page_url=random.choice(_PAGES),
            )
        case "purchase":
            return PurchaseEvent(
                **base,
                product_id=random.choice(_PRODUCTS),
                amount=round(random.uniform(1_000, 500_000), -2),  # 100원 단위
                currency="KRW",
            )
        case "signup":
            return SignupEvent(**base, method=random.choice(_METHODS))
        case "error":
            return ErrorEvent(
                **base,
                error_code=random.choice(_ERROR_CODES),
                page_url=random.choice(_PAGES),
                message=fake.sentence(nb_words=6),
            )
        case _:
            raise ValueError(f"Unknown event_type: {event_type}")


def make_past_events(pool: SessionPool, total: int) -> list[AnyEvent]:
    """seed-heavy 시딩용: 과거 날짜로 분산된 이벤트 N건 생성."""
    events = []
    for _ in range(total):
        session = pool.random_session()
        # 최근 90일 내 랜덤 타임스탬프
        occurred_at = datetime.now(timezone.utc) - timedelta(
            seconds=random.randint(0, 90 * 24 * 3600)
        )
        events.append(random_event(session, occurred_at))
    return events
