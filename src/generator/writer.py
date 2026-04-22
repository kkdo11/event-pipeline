"""psycopg3 bulk insert + Dead Letter Queue.

원칙:
- executemany로 bulk insert (N+1 금지)
- Pydantic validation 실패 → broken_events (파이프라인 중단 X)
- 커넥션/커서는 항상 context manager 사용
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence

import psycopg

from .factory import SessionRecord, UserRecord
from .models import AnyEvent, BaseEvent, event_to_properties

logger = logging.getLogger(__name__)


def get_dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'events')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'postgres')}"
    )


def insert_users(conn: psycopg.Connection, users: Sequence[UserRecord]) -> None:
    rows = [(str(u.user_id), u.country, u.platform, u.created_at) for u in users]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO users (user_id, country, platform, created_at) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            rows,
        )
    conn.commit()


def insert_sessions(conn: psycopg.Connection, sessions: Sequence[SessionRecord]) -> None:
    rows = [(str(s.session_id), str(s.user_id), s.started_at, s.user_agent) for s in sessions]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO sessions (session_id, user_id, started_at, user_agent) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            rows,
        )
    conn.commit()


def insert_events(conn: psycopg.Connection, events: Sequence[BaseEvent]) -> int:
    """이벤트 bulk insert. 성공 건수 반환."""
    rows = [
        (
            str(e.event_id),
            str(e.session_id),
            str(e.user_id),
            e.event_type,
            e.occurred_at,
            json.dumps(event_to_properties(e)),
        )
        for e in events
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO events "
            "(event_id, session_id, user_id, event_type, occurred_at, properties) "
            "VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
            rows,
        )
    conn.commit()
    return len(rows)


def insert_broken(conn: psycopg.Connection, raw_json: dict, error_message: str) -> None:
    """validation 실패 이벤트 → broken_events (DLQ)."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO broken_events (raw_json, error_message) VALUES (%s::jsonb, %s)",
            (json.dumps(raw_json), error_message),
        )
    conn.commit()
    logger.warning("DLQ: %s", error_message[:120])


def ingest_raw(conn: psycopg.Connection, raw: dict) -> bool:
    """raw dict → Pydantic 파싱 → insert. 실패 시 DLQ. True=성공."""
    from pydantic import ValidationError
    from .models import parse_event

    try:
        event = parse_event(raw)
        insert_events(conn, [event])
        return True
    except ValidationError as e:
        insert_broken(conn, raw, str(e))
        return False
