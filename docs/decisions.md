# 설계 결정 기록 (Architecture Decision Records)

> 평가자용 축약본. 각 결정은 "무엇을 선택했는가 / 왜 / 트레이드오프"로 구성.

---

## ADR-1 · 언어: Python 3.11+

- **선택**: Python 3.11+ (`uv` 패키지 매니저)
- **대안**: Java(Spring), Go
- **이유**: 데이터 엔지니어링 직무 표준, `Faker/Pydantic/matplotlib/psycopg3` 네이티브 → 3일 내 완성 리스크 최소
- **포기한 것**: Spring Boot 엔지니어링 깊이 어필

## ADR-2 · 저장소: PostgreSQL 15+

- **선택**: PostgreSQL 15 (alpine)
- **대안**: SQLite, ClickHouse, MongoDB
- **이유**:
  - 과제 요구("필드 구분 저장")와 정합
  - **파티셔닝·JSONB·윈도우 함수**가 모두 네이티브 → 차별화 포인트 확보 가능
  - 평가자 친숙도 가장 높음
- **포기한 것**: SQLite의 "세팅 제로" 단순성, MongoDB의 스키마 유연성

## ADR-3 · 스키마: 3-테이블 정규화 + 시간 기반 RANGE 파티셔닝 + DLQ

- **선택**: `users / sessions / events` 분리 + `events`를 `occurred_at` 기준 월별 RANGE 파티션 + Pydantic 실패 이벤트는 `broken_events` (DLQ)
- **대안**: 단일 `events` 테이블에 user/session 정보 denormalized
- **이유**:
  - 이벤트는 고카디널리티/시계열 → **파티션 드롭으로 보존기간 관리**가 `DELETE`보다 O(1)
  - JSONB는 **공통 필드 + 가변 properties** 하이브리드 (purchase.amount, page_view.url 등)
  - DLQ 분리 → 단일 불량 이벤트가 파이프라인을 중단시키지 않음
- **트레이드오프**:
  - PARTITION BY RANGE 필수 조건 → 기본키가 `(event_id, occurred_at)` 복합키로 강제됨
  - 월별 파티션 자동 생성 스크립트 필요 (과제 범위 외, `pg_partman` 대체)

## ADR-4 · 생성기: Continuous Daemon + Seed-heavy 옵션

- **선택**: `--rate N --duration S` 초당 N건, `--seed-heavy M`로 과거 90일 분산 M건 백필
- **대안**: one-shot 스크립트
- **이유**:
  - 데몬 구조는 실무 이벤트 파이프라인과 동형
  - seed-heavy로 **파티션 prune 벤치마크용 대규모 과거 데이터** 생성 가능

## ADR-5 · 시각화: matplotlib PNG + `psycopg3 cursor → pandas DataFrame`

- **선택**: matplotlib (headless `Agg` 백엔드), psycopg3 커서 결과를 `pd.DataFrame(rows, columns=cols)`로 수동 변환
- **대안**: Grafana/Metabase 대시보드, `pd.read_sql(sqlalchemy_engine)`
- **이유**:
  - PNG 3장을 저장소에 커밋 → 평가자는 클론/실행 없이 **README에서 바로 확인 가능**
  - `pd.read_sql`는 SQLAlchemy Connectable이 아니면 경고 발생 → cursor 우회
- **포기한 것**: 인터랙티브 탐색 (과제 스코프 외)

## ADR-6 · 선택 과제: Kubernetes manifest 4종 (AWS 아님)

- **선택**: `Deployment / ConfigMap / Secret / CronJob` manifest 작성 + `kubectl apply --dry-run=client` 검증
- **대안**: AWS 아키텍처 다이어그램
- **이유**:
  - K8s manifest는 **실제 코드**로 남음 → AWS 다이어그램보다 엔지니어링 신호 강함
  - 실 클러스터 배포는 과제 요구 아님

## ADR-7 · 차별화: 파티셔닝 EXPLAIN ANALYZE + Pydantic DLQ

두 가지 실측 가능한 차별화 포인트를 우선순위로 배치.

### ① 파티셔닝 prune 벤치마크 (아래 **벤치마크** 섹션 참조)

### ② Pydantic → DLQ 통합 테스트

- **검증**: `pytest tests/test_writer.py::test_dlq_on_validation_failure`
- **커버 케이스 5종**: 필수 필드 누락, 음수 amount, 허용되지 않은 event_type, event_type 자체 누락, UUID 형식 위반
- 모두 `broken_events` 테이블에 `raw_json + error_message`로 적재되어 파이프라인 정지 없이 회수 가능

---

## 벤치마크 — 파티션 prune 실측

### 환경

- PostgreSQL 15-alpine (docker compose)
- 이벤트 총 **1,005,944건** — `--seed-heavy 1000000` 최근 90일 분산 + 데몬 잔여
- 파티션 5개: `events_2026_01 ~ events_2026_05` 월별 RANGE

```text
events_2026_01: 102,799건   (2026-01-23~31, 부분)
events_2026_02: 311,119건   (full month)
events_2026_03: 344,411건   (full month)
events_2026_04: 247,615건   (2026-04-01~22, 부분)
events_2026_05:       0건   (future)
```

### 측정 결과 — 실측 (ANALYZE 후 `EXPLAIN (ANALYZE, BUFFERS)` 1회 실행)

| 시나리오 | 실행 시간 | Partitions Scanned | Subplans Removed | Buffers (hit + read) |
|---|---:|---:|---:|---:|
| **A. 좁은 범위 (24h)** `WHERE occurred_at >= now() - '24h'` | **20.52 ms** | 1 (events_2026_04) | **4** (prune 적용) | 218+4,406 |
| **B. 넓은 범위 (90d)** `WHERE occurred_at >= now() - '90d'` | 87.48 ms | 4 | 1 (미래 파티션만 prune) | 3,931+16,639 |
| **C. 필터 없음** (full scan) | 60.27 ms | 5 (전체) | 0 | 6,143+14,427 |

> 예상: 파티션 prune 적용 시 10x~100x — **실측은 ~3x** (A vs C: 60.27/20.52 = 2.94x)
>
> **실측이 예상보다 작은 이유**: 모든 파티션에 `occurred_at` btree 인덱스가 있어 인덱스 스캔이 많은 작업을 흡수. 파티션 prune의 실질적 효과는 wall-clock보다 **I/O (Buffers)와 planning time**에 더 크게 나타남:
> - Buffers: A는 ~4.6K, C는 ~20.6K → **4.5x I/O 감소**
> - 파티션 수가 늘어나면 planning 오버헤드가 선형 증가 (본 측정 환경은 5개라 미미)

### EXPLAIN 발췌 — 좁은 범위 쿼리

```text
Append  (cost=0.30..6013.14 rows=17500 ...) (actual time=1.156..19.028 rows=17066 loops=1)
  Subplans Removed: 4        ← 5개 파티션 중 4개 제거됨
  -> Bitmap Heap Scan on events_2026_04 events_1
       Recheck Cond: ((occurred_at >= (now() - '24:00:00'::interval)) AND (occurred_at < now()))
       -> Bitmap Index Scan on events_2026_04_occurred_at_idx
```

### 해석 — 왜 이 구조인가

1. **파티션 prune의 진짜 이점은 wall-clock 외 3가지**:
   - 구형 데이터 삭제를 `DROP PARTITION`으로 O(1) 처리 (DELETE 대비 WAL·vacuum 비용 없음)
   - 인덱스가 파티션별로 분리되어 **한 파티션의 bloat이 다른 파티션에 영향 없음**
   - 집계 쿼리의 planner cost가 파티션 수와 선형 비례 → 30~60개 파티션 환경에서 planning time 차이가 크게 벌어짐
2. **현재 데이터량 (1M)에서는 CPU보다 I/O에서 이득이 더 크다** — Buffers 4.5x 감소가 wall-clock 3x 감소로 이어짐
3. **확장**: 실무에서는 `pg_partman`으로 월별 파티션 자동 생성·보존기간 관리. 본 과제는 수동으로 5개월 선제 생성

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-04-23 | 초기 작성 — ADR 1~7 + 파티션 prune 벤치 실측 | Step 2.4 완료 |
