# Supabase/AGENTS.md

## 역할
Supabase PostgreSQL 중앙 데이터 저장소의 연결, Realtime, RLS, 권한과 Key 사용 규칙을 담당한다. Collection session, Raw 데이터, processed feature, ML 결과와 PICO / cylinder별 과거 데이터를 보관하고 Web 데이터 제공 계층으로 사용할 수 있다.

목표 역할:

```text
Raspberry Pi 5
→ Sensor / Cycle, STFT, RMS / FFT, Feature Extraction, ML Inference
→ 필요한 데이터 Supabase INSERT / UPDATE

Supabase PostgreSQL
→ Render 공개 Web에서 필요한 데이터 제공 가능
```

현재 구현 흐름:

```text
Backend
→ Supabase INSERT / UPDATE

Supabase PostgreSQL
→ Supabase Realtime
→ Frontend 직접 갱신

Frontend
→ Supabase 직접 SELECT
```

Frontend에는 공개 가능한 Key와 RLS를 사용한다. Secret / Service Role Key는 Backend에서만 사용한다.

목표 구조에서는 Pi가 처리 결과를 Supabase로 전송한다. 기존 구현이 Render Backend를 거치는 경우 해당 코드와 경로를 확인 없이 변경하거나 폐기하지 않는다. Render가 Supabase만 조회할지, Gateway를 사용할지와 최종 실시간 Web 방식은 아직 확정하지 않는다.

현재 RLS/Realtime 계약:

- `raw_data`, `processed_features`, `ml_results` 모두 RLS를 활성화한다.
- Frontend는 `processed_features`, `ml_results`만 SELECT할 수 있으며 `raw_data` 접근 및 모든 INSERT/UPDATE/DELETE는 허용하지 않는다.
- Backend는 환경변수의 Service Role Key로 필요한 INSERT/UPDATE만 수행한다.
- Realtime publication 대상은 `processed_features`, `ml_results`이며 `raw_data`는 대상이 아니다.
- `collection_sessions`는 Backend 전용 내부 테이블로 RLS를 활성화하고 Frontend 접근 정책이나 Realtime publication을 추가하지 않는다.
- `process_orders`와 `process_judgments`는 A/B 공정 테스트 전용이며 센서
  테이블과 분리한다. 두 테이블은 RLS를 활성화하고 `anon`과
  `authenticated`의 직접 권한을 허용하지 않으며 서버 역할만 접근한다.
- `process_orders.order_id + PROCESS_START`와
  `process_judgments.order_id + PROCESS_JUDGMENT`는 각각 하나의 논리
  이벤트다. dispatch 상태는 Pi bridge의 중복 Publish 방지에 사용한다.

## 검증
2026-10-08 조회 최적화: Monitoring 기록은 Runtime 상태·수신 시각·Packet 지표만 JSON 경로로 투영하고 STFT 행렬은 최신 Preview 조회에만 포함한다. 이미 읽은 같은 세션의 처리 완료 행을 재사용하여 불필요한 fallback SELECT를 생략한다. Preview 정리의 미충전 범위는 마지막 행까지 조회했음을 이용해 재확인 SELECT를 생략하되 가득 찬 범위는 기존 backlog 검사를 유지한다. Raw 삭제·Schema·RLS 변경은 없으며 실제 응답시간 개선은 배포 후 별도 측정한다.

2026-10-07 지연 완화 수정: 확인된 세션과 마지막 Raw 쓰기 응답은 고정 Cylinder별 1개만 메모리에 유지한다. 세션 의미가 바뀌면 거절하고 새 세션/프로세스에서는 DB 검증을 다시 수행한다. Raw 쓰기 응답의 고유 Row ID와 메시지 식별값이 일치할 때만 Runtime PATCH 전 재조회를 생략한다. Monitoring의 최신 Raw가 처리 중이면 같은 OPERATION 세션의 마지막 Runtime 저장 행을 조회하며 수신 시각을 갱신하거나 STALE을 LIVE로 바꾸지 않는다. 설치된 Wheel 반영과 실제 지연 개선은 별도 검증 대상이다.

0.1.7 `runtime.packet_metrics`는 전처리 버전과 센서별 유한한 비음수 RMS·Peak 및 샘플 수·샘플링률만 허용하는 선택적 표시용 JSON이다. 원본 Sensor·세션 라벨·스키마·RLS는 보존하고 이전 Runtime JSON도 읽을 수 있어야 한다. 이 값은 학습 Dataset이나 Cycle Feature가 아니다.

`raw_data.raw_payload.runtime`은 Pi 운영 Metadata이며 Sensor Raw 및 Ground Truth와 구분한다. Runtime 갱신과 Preview 보관 정리는 Sensor 필드를 보존하고, Preview만 외부 보관 개수에 따라 제거한다. Cylinder별 단일 Pi Writer를 전제로 한다. Monitoring 서버 조회는 OPERATION Session만 대상으로 PCM과 Ground Truth를 제외하며, 학습 조회는 기존 processed Feature 계약을 유지한다.

```powershell
cd "C:\Smart Cylinder Case\system\DB\Supabase"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- RLS, SELECT/INSERT/UPDATE 권한 임의 변경 금지
- Realtime 대상 테이블 임의 변경 금지
- Service Role Key를 Frontend에 넣지 않는다.
- `.env`, `config.py`, `secrets.py`는 사용자 승인 없이 생성하지 않는다.
- PostgreSQL 스키마 역할을 이 폴더에 중복 구현하지 않는다.
- 현재 DB Schema와 실제 테이블 이름을 우선하며 역할 문서 변경만으로 Schema를 변경하지 않는다.

## 커밋 / PR
`<type>(supabase): <변경 내용>`

Frontend 직접 Realtime/SELECT와 Backend 서버 권한이 분리되어 동작해야 완료다.
