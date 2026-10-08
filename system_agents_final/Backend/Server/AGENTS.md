# Server/AGENTS.md

## 역할
Flask 애플리케이션 시작, Gunicorn 실행, Render 배포 환경을 담당한다.

```text
Render
→ Gunicorn
→ Flask
→ API
```

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\Backend\Server"
python -m black --check .
python -m compileall .
```

실제 실행 파일/모듈 이름이 확정되기 전에는 임의의 실행 명령을 만들지 않는다.

## 보호 규칙
- Flask/Gunicorn/Render 구조를 임의 변경하지 않는다.
- Worker/Timeout/Thread 값은 실제 환경 확인 전 임의 확정하지 않는다.
- `.env`, `config.py`, `secrets.py`, `app.py`, `wsgi.py` 등을 사용자 승인 없이 만들지 않는다.
- 서버 Secret은 Frontend/API 응답/로그에 노출하지 않는다.

## 커밋 / PR
`<type>(server): <변경 내용>`

Render에서 서버가 정상 시작되고 API가 연결되며 민감정보가 노출되지 않아야 완료다.
