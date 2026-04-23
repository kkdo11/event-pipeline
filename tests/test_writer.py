"""writer 통합 테스트 (실행 DB 필요 — docker compose 또는 로컬 postgres)."""
from __future__ import annotations

import json
import os
import pytest
import psycopg

from src.generator.factory import SessionPool
from src.generator.writer import get_dsn, insert_users, insert_sessions, insert_events, insert_broken, ingest_raw

NEEDS_DB = pytest.mark.skipif(
    os.getenv("POSTGRES_HOST") is None,
    reason="POSTGRES_HOST 환경변수 없음 — DB 연결 불가",
)


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(get_dsn()) as c:
        yield c


@pytest.fixture(scope="module")
def pool(conn):
    p = SessionPool(user_count=5, sessions_per_user=2)
    insert_users(conn, p.users)
    insert_sessions(conn, p.sessions)
    return p


@NEEDS_DB
def test_insert_events_count(conn, pool):
    from src.generator.factory import random_event
    events = [random_event(pool.random_session()) for _ in range(10)]
    inserted = insert_events(conn, events)
    assert inserted == 10


@NEEDS_DB
@pytest.mark.parametrize(
    "bad_payload,reason",
    [
        ({"event_type": "purchase", "amount": -999}, "필수 필드 누락 + 음수 amount"),
        ({"event_type": "purchase"}, "purchase 필수 필드(amount, currency) 누락"),
        ({"event_type": "unknown_type"}, "허용되지 않은 event_type"),
        ({}, "event_type 자체 누락"),
        ({"event_type": "click", "session_id": "not-a-uuid"}, "UUID 형식 위반"),
    ],
)
def test_dlq_on_validation_failure(conn, bad_payload, reason):
    """깨진 payload 5종 → broken_events 적재 확인."""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM broken_events")
        before = cur.fetchone()[0]

    result = ingest_raw(conn, bad_payload)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM broken_events WHERE raw_json = %s::jsonb", (json.dumps(bad_payload),))
        matched = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM broken_events")
        after = cur.fetchone()[0]

    assert result is False, f"ingest_raw should return False for: {reason}"
    assert after == before + 1, f"broken_events +1 expected for: {reason}"
    assert matched >= 1, f"raw_json row should be persisted for: {reason}"
