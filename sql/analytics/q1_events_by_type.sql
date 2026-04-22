-- 이벤트 타입별 발생 횟수 및 비율
SELECT
    event_type,
    COUNT(*)                                          AS total,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM events
GROUP BY event_type
ORDER BY total DESC;
