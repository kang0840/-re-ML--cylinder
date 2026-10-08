# Condition/AGENTS.md

## 역할
한 Cycle의 상태 분석을 **한 기능 영역에서 처리**한다.

```text
Sensor가 Cycle 시작/종료 결정
↓
해당 구간 SPH0645 / INMP441 데이터 구성
↓
RMS
↓
FFT
↓
특징값 추출
↓
정상 기준 비교
↓
NORMAL / ABNORMAL
↓
Leakage Condition Score
```

RMS/FFT/Feature/Baseline/Detection을 별도 하위 폴더로 나누지 않는다.

## 정상 기준
정상 패킹의 여러 Cycle만 사용해 정상 기준을 만든다.

손상 패킹 데이터는 정상 기준 생성용이 아니라 **검증용**이다.

정확한 정상 범위 통계식과 최종 Threshold는 실제 정상 데이터 수집 후 확정한다.

## Ground Truth / Prediction
```text
Ground Truth = 실제 실험 조건
Prediction   = 시스템 판정
```

둘은 반드시 분리한다.

## Leakage Score
```text
(현재 특징값 - 정상 기준값)
/
(손상 기준값 - 정상 기준값)
× 100
```

이 값은 실제 누설률%, 고장확률%, 수명잔존율%로 단정하지 않는다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\ML\Condition"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- `전진 + 후진 = 1 Cycle`
- Cycle 시작/종료 판단 자체는 Sensor 담당
- Sampling Rate 1600 Hz 기준 유지
- 정상-only 기준 생성 방식 임의 변경 금지
- RMS/FFT 하위 폴더 추가 금지
- 새 파일은 사용자 승인 후 생성

## 커밋 / PR
`<type>(condition): <변경 내용>`

한 Cycle을 정상 기준과 비교해 Prediction을 만들고 Ground Truth와 분리할 수 있어야 완료다.
