-- ============================================================
-- event-pipeline 스키마
-- ============================================================

-- 유저 테이블
CREATE TABLE IF NOT EXISTS users (
    user_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    country     TEXT        NOT NULL DEFAULT 'KR',
    platform    TEXT        NOT NULL CHECK (platform IN ('web', 'mobile', 'api'))
);

-- 세션 테이블
CREATE TABLE IF NOT EXISTS sessions (
    session_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(user_id),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent  TEXT
);

-- 이벤트 테이블 (PARTITION BY RANGE, 월별)
-- 공통 필드는 컬럼, 이벤트별 가변 필드는 properties JSONB
CREATE TABLE IF NOT EXISTS events (
    event_id    UUID        NOT NULL DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL REFERENCES sessions(session_id),
    user_id     UUID        NOT NULL REFERENCES users(user_id),
    event_type  TEXT        NOT NULL CHECK (
                    event_type IN ('page_view', 'click', 'purchase', 'signup', 'error')
                ),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    properties  JSONB       NOT NULL DEFAULT '{}'::JSONB,
    PRIMARY KEY (event_id, occurred_at)
) PARTITION BY RANGE (occurred_at);

-- 파티션 선제 생성 (2026-04, 2026-05)
CREATE TABLE IF NOT EXISTS events_2026_04 PARTITION OF events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE IF NOT EXISTS events_2026_05 PARTITION OF events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- Dead Letter 테이블: Pydantic validation 실패 이벤트
CREATE TABLE IF NOT EXISTS broken_events (
    id              BIGSERIAL   PRIMARY KEY,
    raw_json        JSONB       NOT NULL,
    error_message   TEXT        NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
