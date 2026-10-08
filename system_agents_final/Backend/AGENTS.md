# Backend/AGENTS.md

## 역할
Render Web Service에서 실행되는 Backend 영역이다.

```text
Backend/
├─ API/
├─ Service/
└─ Server/
```

Raspberry Pi 5의 분석 결과는 Backend REST API를 통해 전달하고, Backend가 Supabase에 INSERT/UPDATE한다.

Frontend의 실시간 갱신 자체는 Backend Push가 아니라 **Supabase Realtime 직접 연결**을 사용한다.

현재 서버 구조는 `Python + Flask + Gunicorn + Render`를 유지한다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\Backend"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- Flask를 다른 프레임워크로 임의 교체하지 않는다.
- 기존 API 경로/응답을 임의 변경하지 않는다.
- Supabase Secret / Service Role Key는 Backend에서만 사용한다.
- ML, MQTT, Sensor 로직을 Backend에 중복 구현하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성한다.

## 커밋 / PR
`<type>(backend): <변경 내용>`

API/Service/Server 역할 분리가 유지되고 기존 Backend 기능이 깨지지 않아야 완료다.
