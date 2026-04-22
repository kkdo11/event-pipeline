-- ============================================================
-- 인덱스 (001_schema.sql 실행 후 적용)
-- ============================================================

-- 이벤트 타입별 집계 쿼리용
CREATE INDEX IF NOT EXISTS idx_events_event_type   ON events (event_type);

-- 시간대별 집계 쿼리용 (파티션 프루닝과 별도로 범위 내 정렬 최적화)
CREATE INDEX IF NOT EXISTS idx_events_occurred_at  ON events (occurred_at DESC);

-- 유저별 이벤트 집계 쿼리용
CREATE INDEX IF NOT EXISTS idx_events_user_id      ON events (user_id);

-- JSONB 속성 조회 최적화 (GIN)
CREATE INDEX IF NOT EXISTS idx_events_properties   ON events USING GIN (properties);

-- broken_events 시간 조회용
CREATE INDEX IF NOT EXISTS idx_broken_received_at  ON broken_events (received_at DESC);
