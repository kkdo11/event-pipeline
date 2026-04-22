"""writer 통합 테스트 (실행 DB 필요 — docker compose 또는 로컬 postgres)."""
from __future__ import annotations

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
def test_dlq_on_validation_failure(conn):
    """잘못된 payload → broken_events 적재 확인."""
    bad_payload = {"event_type": "purchase", "amount": -999}  # 필수 필드 누락 + 음수
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM broken_events")
        before = cur.fetchone()[0]

    result = ingest_raw(conn, bad_payload)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM broken_events")
        after = cur.fetchone()[0]

    assert result is False
    assert after == before + 1
