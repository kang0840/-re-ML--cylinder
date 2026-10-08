# PostgreSQL/AGENTS.md

## 역할
Supabase가 사용하는 PostgreSQL의 **데이터 구조**를 관리한다.

현재 테이블:

```text
raw_data
processed_features
ml_results
```

중복 기준:

```text
raw_data:           cylinder_id + session_id + sequence_id
processed_features: cylinder_id + cycle_id
ml_results:         cylinder_id + cycle_id
```

`raw_data`는 MQTT 메시지 단위이며 `cycle_id`는 NULL을 허용한다. 분석 결과 테이블은 Cycle 단위이고 `cycle_id`를 필수로 사용한다. `ml_results(cylinder_id, cycle_id)`는 `processed_features(cylinder_id, cycle_id)`에 복합 Foreign Key로 연결된다.

같은 각 테이블의 중복 키가 재수신되면 새 행을 만들지 않고 기존 값을 갱신한다. `created_at`은 최초 INSERT 값을 유지하고 `updated_at`은 Backend 저장 시 갱신한다.

## SQL 사용 규칙
현재 프로젝트에서는 별도의 `.sql` 파일이나 수동 SQL 스크립트 중심 구조를 사용하지 않는다.

PostgreSQL 폴더는 테이블, 컬럼, 데이터 타입, 제약조건 등 **DB 구조 규칙**을 관리하며 실제 서비스 접근은 Supabase 계층을 따른다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\DB\PostgreSQL"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- `schema.sql`, migration SQL 등을 사용자 승인 없이 만들지 않는다.
- 테이블/컬럼/타입/KEY/UNIQUE 규칙 임의 변경 금지
- 전체 데이터 삭제/초기화 금지
- Supabase Realtime/RLS/Key 관리는 `../Supabase/`에서 처리

## 커밋 / PR
`<type>(postgresql): <변경 내용>`

현재 DB 구조와 중복 처리 규칙을 유지해야 완료다.
