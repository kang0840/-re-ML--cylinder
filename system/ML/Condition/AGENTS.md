# Condition/AGENTS.md

## 역할
한 Cycle의 상태 분석을 **한 기능 영역에서 처리**한다.

MQTT 계층에서 검증·중복 제거·PCM 복원이 끝난 센서 데이터에서 STFT로 실린더 동작음 구간을 검출하고, 해당 구간의 RMS/FFT 기반 특징을 생성한다. 저장된 Condition 모델의 기존 전처리를 사용해 실시간 상태 추론을 수행한다.

```text
Sensor가 Cycle 시작/종료 결정
↓
해당 구간 SPH0645 / INMP441 데이터 구성
↓
STFT 기반 동작음 검출
↓
동작음 구간
↓
RMS
↓
FFT
↓
특징값 추출
↓
정상 기준 / Saved Model
↓
NORMAL / ABNORMAL
↓
Leakage Condition Score
```

학습에서 Condition은 PCM 복원 결과의 STFT 동작음 검출, 검출 구간의 Feature Extraction과 Condition 학습 입력 구성을 담당한다. Training Dataset Load와 Model Training은 검증된 Ground Truth를 사용하며 Saved Model을 생성한다.

실시간 추론에서 Condition은 PCM 복원 결과에서 STFT로 동작음 구간을 검출하고 해당 구간의 RMS / FFT Feature Extraction 후 Saved Model을 호출해 Prediction을 생성한다. STFT 자체를 NORMAL / ABNORMAL 모델로 취급하지 않는다. MQTT 통신 규격과 PCM 복원은 상위 AGENTS.md와 MQTT 영역의 규칙을 따른다.

모델 입력 11개 특징은 `mean`, `standard_deviation`, `rms`, `maximum`, `minimum`, `peak`, `peak_to_peak`, `crest_factor`, `dominant_frequency`, `dominant_amplitude`, `spectral_energy` 순서를 저장 모델의 `feature_names`과 대조한 뒤 사용한다. 모델의 input shape와 저장된 scaler/preprocessing을 검증하고 실시간 데이터로 scaler를 fit하지 않는다.

RMS/FFT/Feature/Baseline/Detection을 별도 하위 폴더로 나누지 않는다.

`analysis.py`의 `calculate_stft`는 Memory Sample Array, sample_rate와 외부 Window/Hop/n_fft/Window Function 설정으로 SciPy ShortTimeFFT를 계산한다. 출력은 frequencies, 창 중심 상대 시간 times와 (frequency_bins, time_frames) magnitude이며 완전한 창만 계산한다. 설정 누락은 CONFIG_REQUIRED로 보고한다. 이 계산은 Threshold·Reference Pattern·동작음 검출·Runtime 연결의 구현 완료를 의미하지 않는다.

## 정상 기준
정상 패킹의 여러 Cycle만 사용해 정상 기준을 만든다.

현재 정상 수집 실험과 학습 편입 조건은 상위 `ML/AGENTS.md`를 따른다. 모니터에서 보이는 RMS·Peak·주파수 값만으로 검증된 Cycle Feature 저장 또는 학습 완료를 확정하지 않는다. 실제 정상 데이터와 저장된 Ground Truth가 일치하는지 확인한 뒤 기존 정상 기준 생성 경로를 사용하며, Reference·Threshold는 데이터 검증 전 미확정 상태를 유지한다.

손상 패킹 데이터는 정상 기준 생성용이 아니라 **검증용**이다.

정확한 정상 범위 통계식과 최종 Threshold는 실제 정상 데이터 수집 후 확정한다.

최종 모델 검증 전 동일 센서와 동일 장착 조건에서 NORMAL과 SEAL_LEAK 데이터를 교차 수집하여 장치 편향 여부를 검증한다.

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
0.1.6 분석 입력은 `analysis.py`의 `preprocess_samples`로 분석 단위별 평균을 제거한 새 float64 배열을 사용한다. Raw PCM은 변경·덮어쓰기하지 않는다. 학습과 실시간 특징 계산은 같은 Extractor와 분석 단위 경계를 사용하며 전처리 식별자는 `mean_remove_analysis_unit_v1`이다. 기존 모델이나 기준값에 이 계약이 확인되지 않으면 재사용하지 않고 MODEL_REQUIRED로 남긴다. 주파수 필터·클리핑 복구·임계값 확정을 의미하지 않는다.

```powershell
cd "C:\Smart Cylinder Case\system\ML\Condition"
python -m black --check .
python -m compileall .
```

코드 스타일은 상위 `system/AGENTS.md`의 Python Black과 naming 규칙을 따른다. 기존 `analysis.py`의 책임을 유지하고 실시간 연결은 승인된 `realtime_inference.py`에만 구현한다.

## 보호 규칙
- `전진 + 후진 = 1 Cycle`
- Cycle 시작/종료 판단 자체는 Sensor 담당
- STFT는 Cycle 판별을 대체하지 않고 분석할 실린더 동작음 구간만 검출
- STFT 자체를 NORMAL / ABNORMAL 판정 또는 Saved Model로 취급하지 않기
- SPH0645 analysis rate 4000 Hz, target frequency 2~1000 Hz 유지
- INMP441 analysis rate 16000 Hz 유지; leakage feature band는 정상/손상 패킹 실험 데이터 비교 후 확정
- I2S acquisition rate와 GPIO 등 하드웨어 세부사항은 Sensor 영역의 책임으로 유지
- Pi에서 compact FFT feature(RMS, Peak, Peak-to-Peak, Crest Factor, dominant frequency/magnitude)를 계산한다. SPH0645 FFT 범위는 2~1000 Hz이며 INMP441 leakage band는 임의로 고정하지 않는다.
- baseline, 허용 편차, 손상 기준값은 외부 입력으로만 사용한다. 데이터가 없으면 Prediction 또는 Leakage Score를 만들지 않는다.
- 정상-only 기준 생성 방식 임의 변경 금지
- RMS/FFT 하위 폴더 추가 금지
- 새 파일은 사용자 승인 후 생성
- MQTT Topic·Payload·QoS, Parser 중복 제거, PCM 포맷, Sample Rate와 수집 길이 변경 금지
- Supabase·DB Schema 및 Repository 임의 변경 금지
- 실시간 추론을 위한 Supabase 재조회, 모델 재학습, scaler `fit` 금지
- 모델·scaler·feature count/order·input shape·NaN/Inf·추론 오류는 MQTT Subscriber를 종료시키지 않고 명확히 보고
- Secret, Wi-Fi·MQTT password, Service Role Key 하드코딩·출력 금지

## 커밋 / PR
`<type>(condition): <변경 내용>`

한 커밋은 하나의 논리적 변경 단위를 유지한다. Commit 전 Syntax·Import·Parser·PCM·Feature·Model·Mock E2E 테스트와 Secret 포함 여부를 확인하고 관련 없는 파일을 수정하지 않는다. PR에는 변경 파일·이유·테스트 결과와 영향 범위를 기록한다.

한 Cycle을 정상 기준과 비교해 Prediction을 만들고 Ground Truth와 분리할 수 있어야 완료다.

실시간 연결은 11개 특징과 저장 모델 3개의 입력 계약, 저장된 scaler, Mock MQTT→Parser→PCM→Feature→Model E2E, 중복·잘못된 Payload·모델 오류 격리 테스트가 통과해야 완료다. 실제 모델 런타임이나 하드웨어에서 확인하지 못한 항목은 미검증으로 명시한다.
