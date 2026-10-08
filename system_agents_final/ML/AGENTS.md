# ML/AGENTS.md

## 역할
ML 영역은 두 기능으로만 나눈다.

```text
ML/
├─ Condition/
└─ WeibullAFT/
```

RMS/FFT/Feature/Baseline/Detection을 각각 별도 폴더로 만들지 않는다.

- `Condition/` → Cycle 데이터, RMS, FFT, 특징값, 정상 기준, NORMAL/ABNORMAL, Leakage Score
- `WeibullAFT/` → 수명 예측

Ground Truth와 Prediction은 반드시 분리한다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\ML"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- Condition을 RMS/FFT 등으로 추가 세분화하지 않는다.
- 모델/임계값/성능 수치를 데이터 없이 임의 확정하지 않는다.
- Sensor/MQTT/DB 역할을 ML에 중복 구현하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(ml): <변경 내용>`

Condition과 Weibull-AFT 책임이 분리되어야 완료다.
