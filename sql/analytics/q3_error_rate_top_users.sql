-- 유저별 총 이벤트 수 · 에러 수 · 에러율 TOP 10
-- 에러 이벤트 비율이 높은 유저 탐지 (이상 유저 모니터링 용도)
SELECT
    u.user_id,
    u.country,
    u.platform,
    COUNT(e.event_id)                                              AS total_events,
    COUNT(e.event_id) FILTER (WHERE e.event_type = 'error')        AS error_count,
    ROUND(
        COUNT(e.event_id) FILTER (WHERE e.event_type = 'error')
        * 100.0 / NULLIF(COUNT(e.event_id), 0),
        1
    )                                                              AS error_rate_pct
FROM users u
JOIN sessions s ON s.user_id = u.user_id
JOIN events  e ON e.session_id = s.session_id
GROUP BY u.user_id, u.country, u.platform
HAVING COUNT(e.event_id) > 0
ORDER BY error_rate_pct DESC, total_events DESC
LIMIT 10;
