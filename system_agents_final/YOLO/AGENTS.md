# YOLO/AGENTS.md

## 역할
IMX500 + YOLO11n 기반 A/B 제품 검출 기능을 담당한다.

개발 기능은 유지하지만 **현재 발표 범위에서는 제외**한다.

```text
IMX500
→ YOLO11n
→ 제품 A/B 검출
→ 주문 정보와 비교
```

주문 후 1분 이내 미검출 ERROR 조건과 정확도 목표 90%는 기존 개발 목표로 유지한다. 실제 검증값과 목표값을 혼동하지 않는다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\YOLO"
python -m black --check .
python -m compileall .
```

실제 검증은 Raspberry Pi + IMX500에서 수행한다.

## 보호 규칙
- YOLO11n / IMX500 구조 임의 변경 금지
- Class A/B 구조 임의 변경 금지
- 검증하지 않은 정확도 수치 작성 금지
- 현재 발표 자료의 핵심 ML 상태판별 흐름에 YOLO를 끼워 넣지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(yolo): <변경 내용>`

제품 검출 개발 기능을 유지하되 현재 발표 범위와 분리되어야 완료다.
