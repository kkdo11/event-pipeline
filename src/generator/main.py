"""이벤트 생성기 CLI."""
from __future__ import annotations

import argparse
import logging
import time

import psycopg

from .factory import SessionPool, make_past_events, random_event
from .writer import get_dsn, insert_events, insert_sessions, insert_users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Event log generator")
    parser.add_argument("--rate",       type=int, default=50,  help="초당 생성 이벤트 수 (기본: 50)")
    parser.add_argument("--duration",   type=int, default=60,  help="실행 시간 초 (0=무한, 기본: 60)")
    parser.add_argument("--total",      type=int, default=0,   help="총 생성 건수 (0=제한 없음)")
    parser.add_argument("--seed-heavy", type=int, default=0, metavar="N",
                        help="N건 과거 날짜 분산 시딩 (파티셔닝 벤치용)")
    parser.add_argument("--batch-size", type=int, default=100, help="bulk insert 단위 (기본: 100)")
    return parser.parse_args()


def run_seed_heavy(conn: psycopg.Connection, pool: SessionPool, n: int, batch_size: int) -> None:
    logger.info("seed-heavy: %d건 시딩 시작", n)
    events = make_past_events(pool, n)
    total = 0
    for i in range(0, len(events), batch_size):
        total += insert_events(conn, events[i : i + batch_size])
        if total % 100_000 == 0:
            logger.info("  시딩 진행: %d / %d", total, n)
    logger.info("seed-heavy 완료: %d건", total)


def run_daemon(conn: psycopg.Connection, pool: SessionPool,
               rate: int, duration: int, total_limit: int, batch_size: int) -> None:
    logger.info("daemon 시작: rate=%d/s duration=%ds", rate, duration)
    interval  = 1.0 / rate
    inserted  = 0
    start     = time.monotonic()
    batch: list = []

    while True:
        elapsed = time.monotonic() - start
        if duration > 0 and elapsed >= duration:
            break
        if total_limit > 0 and inserted >= total_limit:
            break

        session = pool.random_session()
        batch.append(random_event(session))

        if len(batch) >= batch_size:
            inserted += insert_events(conn, batch)
            logger.info("inserted %d (total %d)", len(batch), inserted)
            batch.clear()

        time.sleep(interval)

    if batch:
        inserted += insert_events(conn, batch)

    logger.info("완료: 총 %d건 적재", inserted)


def main() -> None:
    args = parse_args()

    logger.info("DB 연결 중...")
    with psycopg.connect(get_dsn()) as conn:
        logger.info("유저/세션 풀 초기화 (user=50, session/user=3)")
        pool = SessionPool(user_count=50, sessions_per_user=3)
        insert_users(conn, pool.users)
        insert_sessions(conn, pool.sessions)
        logger.info("풀 준비 완료: user=%d session=%d", len(pool.users), len(pool.sessions))

        if args.seed_heavy > 0:
            run_seed_heavy(conn, pool, args.seed_heavy, args.batch_size)
        else:
            run_daemon(conn, pool, args.rate, args.duration, args.total, args.batch_size)


if __name__ == "__main__":
    main()
