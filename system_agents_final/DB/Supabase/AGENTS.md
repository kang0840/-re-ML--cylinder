# Supabase/AGENTS.md

## 역할
Supabase 연결, Realtime, RLS, 권한, Key 사용 규칙을 담당한다.

확정 흐름:

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

현재 RLS/Realtime 계약:

- `raw_data`, `processed_features`, `ml_results` 모두 RLS를 활성화한다.
- Frontend는 `processed_features`, `ml_results`만 SELECT할 수 있으며 `raw_data` 접근 및 모든 INSERT/UPDATE/DELETE는 허용하지 않는다.
- Backend는 환경변수의 Service Role Key로 필요한 INSERT/UPDATE만 수행한다.
- Realtime publication 대상은 `processed_features`, `ml_results`이며 `raw_data`는 대상이 아니다.

## 검증
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

## 커밋 / PR
`<type>(supabase): <변경 내용>`

Frontend 직접 Realtime/SELECT와 Backend 서버 권한이 분리되어 동작해야 완료다.
