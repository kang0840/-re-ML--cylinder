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

0.1.5 Pi 학습 실행기는 장치 ID, 실제 실험 라벨 `NORMAL / SEAL_LEAK`, 실험 ID를 명시한다. 같은 장치로 두 라벨을 수집할 수 있지만 한 실행의 라벨과 세션은 고정하며 기존 장치별 임시 매핑보다 명시한 실험 설정을 우선한다. 선택하지 않은 장치, 첫 sequence가 1이 아닌 스트림, 이미 DB에 존재하는 세션과 실행 중 다른 세션은 거절한다. 기존 세션 의미를 수정하지 않으며 Raw 저장은 기존 Repository를 재사용한다.

## 검증
2026-10-08 Monitoring의 실제 현재 시각은 DB 조회 완료 후 계산한다. 테스트에서 주입한 시각은 그대로 사용하며 미래 시각·누락·STALE 계약을 완화하지 않는다.

2026-10-07 처리 중 Raw의 Runtime 누락은 `WAITING_FOR_DATA`이며 설정 오류로 추정하지 않는다. 저장된 Runtime의 명시적 `CONFIG_REQUIRED`는 그대로 전달한다. 이전 완료 결과를 표시하더라도 원래 Pi 수신 시각과 STALE 판정을 유지한다.

0.1.7 Monitoring은 검증된 `packet_metrics`만 별도 응답 필드로 전달한다. 누락·잘못된 지표는 NULL이며 Packet 지표를 Cycle RMS·Prediction으로 대체하지 않는다.

Monitoring은 Canonical Repository의 OPERATION 데이터만 조합하고 Pi `last_received_at` 기준 기존 10초 STALE 계약을 사용한다. 실제 Feature와 Prediction이 없으면 NULL과 대기 상태를 유지한다. 측정 시각, 수신 시각, Cycle Feature 시각과 Preview 시각을 서로 대체하지 않는다.

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
