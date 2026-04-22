"""Pydantic 이벤트 모델 단위 테스트."""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.generator.models import (
    ClickEvent,
    ErrorEvent,
    PageViewEvent,
    PurchaseEvent,
    SignupEvent,
    event_to_properties,
    parse_event,
)

SESSION_ID = uuid4()
USER_ID    = uuid4()


# ── 유효한 이벤트 파싱 ──────────────────────────────────────

def test_parse_page_view():
    e = parse_event({"event_type": "page_view", "session_id": str(SESSION_ID),
                     "user_id": str(USER_ID), "url": "https://example.com"})
    assert isinstance(e, PageViewEvent)
    assert e.referrer is None


def test_parse_purchase():
    e = parse_event({"event_type": "purchase", "session_id": str(SESSION_ID),
                     "user_id": str(USER_ID), "product_id": "P1", "amount": 9900.0})
    assert isinstance(e, PurchaseEvent)
    assert e.currency == "KRW"


def test_parse_error_event():
    e = parse_event({"event_type": "error", "session_id": str(SESSION_ID),
                     "user_id": str(USER_ID), "error_code": "500",
                     "page_url": "/checkout"})
    assert isinstance(e, ErrorEvent)


# ── validation 실패 케이스 ─────────────────────────────────

def test_purchase_rejects_zero_amount():
    with pytest.raises(ValidationError):
        parse_event({"event_type": "purchase", "session_id": str(SESSION_ID),
                     "user_id": str(USER_ID), "product_id": "P1", "amount": 0})


def test_purchase_rejects_negative_amount():
    with pytest.raises(ValidationError):
        PurchaseEvent(session_id=SESSION_ID, user_id=USER_ID,
                      product_id="P1", amount=-100)


def test_unknown_event_type_rejected():
    with pytest.raises(ValidationError):
        parse_event({"event_type": "unknown", "session_id": str(SESSION_ID),
                     "user_id": str(USER_ID)})


def test_missing_required_field():
    # ClickEvent는 element_id, page_url 필수
    with pytest.raises(ValidationError):
        parse_event({"event_type": "click", "session_id": str(SESSION_ID),
                     "user_id": str(USER_ID)})


# ── properties 직렬화 ──────────────────────────────────────

def test_event_to_properties_excludes_base_fields():
    e = PurchaseEvent(session_id=SESSION_ID, user_id=USER_ID,
                      product_id="P42", amount=19900.0)
    props = event_to_properties(e)
    assert "product_id" in props
    assert "amount" in props
    assert "event_id" not in props     # 공통 필드 제외
    assert "session_id" not in props


def test_page_view_none_fields_excluded():
    e = PageViewEvent(session_id=SESSION_ID, user_id=USER_ID, url="/home")
    props = event_to_properties(e)
    assert "referrer" not in props     # None 필드 제외
    assert "url" in props
