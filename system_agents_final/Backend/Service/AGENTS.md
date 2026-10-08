# Service/AGENTS.md

## 역할
API와 DB 사이의 Backend 업무 로직을 담당한다.

```text
API
→ Service
→ DB
→ Service
→ API
```

DB 조회 결과를 조합·정리하되 데이터 의미를 바꾸지 않는다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\Backend\Service"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- HTTP Route 정의 금지
- DB 스키마 변경 금지
- RMS/FFT/NORMAL/ABNORMAL/Weibull-AFT 구현 금지
- MQTT/Sensor/YOLO 기능 중복 구현 금지
- Secret 평문 저장 금지
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(service): <변경 내용>`

데이터 없음과 오류를 구분하고 API에 필요한 결과를 기존 의미 그대로 반환해야 완료다.
