# DB/AGENTS.md

## 역할
DB 공통 규칙을 관리한다.

```text
DB/
├─ Supabase/
└─ PostgreSQL/
```

SQLite 로컬 DB는 사용하지 않는다.

역할:
- `Supabase/` → 연결, Realtime, RLS, 권한, Key 사용
- `PostgreSQL/` → 중앙 DB 구조, 테이블/컬럼/제약조건

현재 중앙 테이블:

```text
raw_data
processed_features
ml_results
collection_sessions
process_orders
process_judgments
```

`collection_sessions`는 `session_id`별 `collection_mode`, `dataset_type`, 검증된 Ground Truth와 실험 정보를 관리한다. `raw_data.session_id`와 `processed_features.session_id`는 이 테이블을 참조하며 Raw Row에 데이터 분류값을 반복 저장하지 않는다.

## 중복 규칙

- `raw_data`: `cylinder_id + session_id + sequence_id`가 MQTT 메시지 중복 키다.
- `processed_features`: `cylinder_id + cycle_id`가 Cycle 결과 upsert 키다.
- `ml_results`: `cylinder_id + cycle_id`가 Cycle 판정 upsert 키다.
- `collection_sessions`: `session_id`가 Primary Key이며 같은 session을 중복 생성하지 않는다.
- `process_orders`: `order_id`가 주문과 `PROCESS_START` 이벤트의 고유 식별값이다.
- `process_judgments`: `order_id`가 Unique Foreign Key이며 주문당 최종 판단 1건만 저장한다.

`raw_data.cycle_id`는 NULL을 허용한다. `processed_features`와 `ml_results`의 `cycle_id`는 NULL을 허용하지 않으며, `ml_results(cylinder_id, cycle_id)`는 `processed_features(cylinder_id, cycle_id)`를 참조한다.

Backend upsert는 기존 `created_at`을 유지하고 `updated_at`만 갱신한다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\DB"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- SQLite 추가 금지
- 테이블/컬럼/타입/제약조건 임의 변경 금지
- RLS/권한 임의 변경 금지
- 민감정보 평문 저장 금지
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(db): <변경 내용>`

Supabase와 PostgreSQL 역할을 분리하고 기존 데이터 구조를 유지해야 완료다.
