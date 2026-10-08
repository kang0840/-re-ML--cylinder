# API/AGENTS.md

## 역할
REST API Route, 요청값 검증, HTTP 응답을 담당한다.

```text
HTTP 요청
→ Parameter 검증
→ Service 호출
→ JSON 응답
```

기존 `/api/real-cylinder?limit=1` 등 이미 존재하는 API는 사용자 승인 없이 변경하지 않는다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\Backend\API"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- API에서 직접 SQL/ML/MQTT/Sensor 처리를 하지 않는다.
- 응답 필드 이름/타입/의미를 임의 변경하지 않는다.
- Secret을 응답이나 로그에 노출하지 않는다.
- 새 Route/파일/폴더는 사용자 승인 후 추가한다.

## 커밋 / PR
`<type>(api): <변경 내용>`

정상 요청과 오류 요청을 구분하고 기존 API 호환성을 유지해야 완료다.
