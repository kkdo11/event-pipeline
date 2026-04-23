-- ============================================================
-- 파티션 prune 벤치마크 — 좁은 범위 vs 넓은 범위
-- ============================================================
-- 실행 방법:
--   docker exec event-pipeline-postgres-1 psql -U postgres -d events \
--       -f /sql/bench/explain_partition_prune.sql
--
-- 해석 포인트:
--   - 좁은 범위: Append 노드 아래 단일 파티션만 scan → prune 성공
--   - 넓은 범위: 여러 파티션 동시 scan → prune 미적용
-- ============================================================

\timing on

-- ── Query A: 좁은 범위 (1 파티션으로 prune 예상) ──────────────
-- 최근 24시간만 조회 → events_2026_04 단일 파티션
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_type, COUNT(*)
FROM events
WHERE occurred_at >= now() - INTERVAL '24 hours'
  AND occurred_at <  now()
GROUP BY event_type
ORDER BY COUNT(*) DESC;

-- ── Query B: 넓은 범위 (다수 파티션 scan 예상) ────────────────
-- 최근 90일 전체 → events_2026_01 ~ events_2026_04 전부 scan
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_type, COUNT(*)
FROM events
WHERE occurred_at >= now() - INTERVAL '90 days'
  AND occurred_at <  now()
GROUP BY event_type
ORDER BY COUNT(*) DESC;

-- ── Query C (참고): 전체 스캔 ─────────────────────────────────
-- WHERE 절 없이 모든 파티션 scan
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_type, COUNT(*)
FROM events
GROUP BY event_type
ORDER BY COUNT(*) DESC;
