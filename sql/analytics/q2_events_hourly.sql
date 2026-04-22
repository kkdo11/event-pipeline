-- 시간대별 이벤트 추이 (최근 24시간, event_type별 분류)
SELECT
    date_trunc('hour', occurred_at)  AS hour,
    event_type,
    COUNT(*)                         AS total
FROM events
WHERE occurred_at >= now() - INTERVAL '24 hours'
GROUP BY hour, event_type
ORDER BY hour ASC, total DESC;
