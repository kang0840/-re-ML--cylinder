# ML/AGENTS.md

## 역할
ML 영역은 두 기능으로만 나눈다.

Smart Cylinder Case의 Raspberry Pi 5 ML 계층이다. MQTT 계층이 검증·복원한 센서 데이터에서 STFT로 실린더 동작음 구간을 검출하고, 해당 구간의 특징을 학습 데이터와 실시간 추론 입력으로 사용한다.

```text
ML/
├─ Condition/
└─ WeibullAFT/
```

RMS/FFT/Feature/Baseline/Detection을 각각 별도 폴더로 만들지 않는다.

- `Condition/` → Cycle 데이터, STFT 동작음 검출, RMS, FFT, 특징값, 정상 기준, Saved Model 상태 추론, NORMAL/ABNORMAL, Leakage Score
- `WeibullAFT/` → 수명 예측

Ground Truth와 Prediction은 반드시 분리한다.

```text
한 주기 음향 데이터 입력
↓
STFT
↓
시간-주파수 패턴 생성
↓
기준 실린더 동작음 패턴과 비교
↓
실린더 동작음 구간 검출
↓
검출된 동작 구간
↓
RMS 계산
↓
FFT 계산
↓
특징값 추출
↓
정상 기준 / Saved Model
↓
NORMAL / ABNORMAL
```

학습은 Supabase에 저장된 Feature Extraction 결과와 검증된 Ground Truth를 Training Dataset으로 불러와 Model Training을 수행하고 Saved Model을 생성한다.

Training Dataset은 `collection_sessions`에서 `collection_mode=TRAINING`이며 `TRAINING_NORMAL / NORMAL` 또는 `TRAINING_ABNORMAL / SEAL_LEAK` 조합인 세션만 포함한다. `TEST`, `RAW_OPERATION`, Ground Truth가 NULL인 데이터는 학습에서 제외한다.

현재 수집 Runtime과 임시 실험 매핑은 상위 `system/AGENTS.md`의 사용자 후속 결정을 따른다. Raw PCM 수집은 STFT·Reference·Threshold·Model이 없어도 가능해야 하며 미확정 분석값을 생성하지 않는다. 모니터 표시를 학습 Dataset 저장 증거로 취급하지 않으며 실제 저장 경로와 Session Ground Truth를 확인하기 전 학습 입력으로 편입하지 않는다. 장치 편향 위험을 유지하며 Prediction을 Ground Truth로 사용하지 않는다.

실시간 추론은 Feature Extraction 결과를 Saved Model에 입력해 Prediction을 생성한다. MQTT 수신과 PCM 복원은 MQTT 영역, Supabase 저장은 DB 영역의 AGENTS.md 규칙을 따른다.

실시간 추론은 Supabase를 다시 조회하지 않고 Pi의 Feature Extraction 결과를 Saved Model에 직접 전달한다. 저장된 feature name, feature order, input shape, scaler와 preprocessing을 그대로 사용하며 실시간 데이터로 scaler를 다시 fit하지 않는다.

### STFT

STFT는 실린더 동작음을 검출하기 위해 사용한다. 입력 음향 신호를 짧은 시간 구간으로 나누고 각 구간에 FFT를 적용하여 시간에 따른 주파수 변화를 확인한다.

```text
기준 실린더 동작음 여러 회 수집
→ 동일 조건 STFT
→ 반복적으로 나타나는 기준 시간-주파수 패턴 생성
→ 저장

실시간 음향
→ 동일 조건 STFT
→ 실시간 시간-주파수 패턴
→ 기준 패턴과 유사도 비교
→ 동작음 / 비동작음 판단
```

실린더 동작음 기준은 단 한 번의 소리로 만들지 않는다. 실제 실린더 동작음을 여러 번 수집하고 동일한 STFT 설정으로 변환한 뒤 반복적으로 나타나는 시간-주파수 특징을 기준으로 사용한다.

STFT 자체는 NORMAL / ABNORMAL 판정 결과가 아니며 동작음 구간을 찾기 위한 전처리·검출 단계다. 동작음으로 검출된 구간에서 기존 RMS 및 FFT 특징값을 계산한다. RMS는 신호 전체 크기 특징을, FFT는 검출된 동작 구간의 주파수별 특징값을 제공하며 정상 기준 또는 Saved Model 입력으로 사용한다. STFT는 기존 FFT 상태 특징 분석을 대체하지 않는다.

최종 유사도 알고리즘, Cosine Similarity 사용 여부, Threshold, Window Size, Hop Length, Window Function, STFT FFT Size와 동작음 판별 경계값은 실제 실린더 동작음 데이터를 수집한 후 결정하며 임의로 확정하지 않는다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\ML"
python -m black --check .
python -m compileall .
```

코드 스타일은 상위 `system/AGENTS.md`의 Python Black과 naming 규칙을 따른다. 함수·클래스 책임을 분리하고 불필요한 helper/utils 파일과 세분화 폴더를 생성하지 않는다.

## 보호 규칙
- Condition을 RMS/FFT 등으로 추가 세분화하지 않는다.
- 모델/임계값/성능 수치를 데이터 없이 임의 확정하지 않는다.
- Sensor/MQTT/DB 역할을 ML에 중복 구현하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성
- MQTT Topic·Payload·QoS, Parser 중복 제거, PCM 포맷, Sample Rate와 수집 길이 변경 금지
- Supabase·DB Schema 변경 금지
- 기존 모델 임의 재학습 및 실시간 추론 중 재학습 금지
- Secret, Wi-Fi·MQTT password, Service Role Key 하드코딩·출력 금지
- 사용자 승인 없는 기존 기능 삭제와 파일 삭제·이동·이름 변경 금지

## 커밋 / PR
`<type>(ml): <변경 내용>`

한 커밋은 하나의 논리적 변경 단위를 유지한다. Commit 전 Syntax·Import·테스트와 Secret 포함 여부를 확인하고 관련 없는 파일을 수정하지 않는다. PR에는 변경 파일·이유·테스트 결과와 기존 기능 영향 범위를 기록한다.

Condition과 Weibull-AFT 책임이 분리되어야 완료다.

완료 기준은 상위 `system/AGENTS.md`의 검증 항목을 통과하고, 모델 입력 계약과 저장된 preprocessing 사용이 확인되며, 테스트 실패가 없어야 한다.
