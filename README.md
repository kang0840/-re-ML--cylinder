# 스마트 실린더 케이스 프로젝트

> 기존 공압 실린더에 센서를 일정한 조건으로 장착하여 음향 데이터를 수집하고, 신호처리와 데이터 기반 분석을 통해 상태 변화를 확인하는 프로젝트이다.  
> 현재는 **Pico W → Raspberry Pi 5 → Supabase → Render → Data WorX / Web** 구조와 **A/B 가공 MQTT 테스트**를 함께 개발하고 있다.

---

## 저장소 변경 및 개발 재시작 배경

기존 개발은 [ML-cylinder 저장소](https://github.com/kang0840/ML-cylinder)에서 진행했다. 센서 수집, 분석, 웹 모니터링과 배포 기능을 단계적으로 추가하는 과정에서 여러 차례 구조와 실행 방식이 변경되었다. 그러나 변경사항을 충분히 정리하지 못하면서 이전 코드와 새 코드, 중복 구현 및 과거 배포 파일이 함께 남게 되었다.

그 결과 어떤 파일이 실제 실행에 사용되는지, 어디를 수정해야 하는지, 수정이 다른 기능에 어떤 영향을 주는지 파악하기 어려워졌다. 개발이 진행될수록 코드와 파일 사이의 관계가 복잡하게 얽혔고, 기존 상태에서 부분적인 수정만으로 안정성을 확보하기 어렵다고 판단했다. 이는 GitHub 자체의 문제가 아니라 개발 과정에서 코드 구조와 변경 이력을 일관되게 관리하지 못한 데서 발생한 문제다.

따라서 기존 상태를 그대로 이어서 수정하는 대신, 프로젝트 구조와 각 파일의 역할을 다시 점검하고 개발 기준을 재정립하는 방향으로 개발을 다시 시작했다. 새 개발 기준을 구분하기 위해 [새 저장소 -re-ML--cylinder](https://github.com/kang0840/-re-ML--cylinder)를 만들고, 현재 프로젝트의 파일 스냅샷과 문서를 옮겼다. 기존에 검증한 기능을 모두 폐기하거나 모든 코드를 처음부터 다시 작성했다는 의미는 아니다. 재사용할 기능은 유지하면서 중복 코드, 실행 경로와 배포 산출물의 관계를 명확히 정리하는 것이 목적이다.

앞으로는 공통 코드의 원본을 최상위 `system/`으로 관리하고, 수정 내용·검증 결과·배포 상태를 이 README의 날짜별 작업 기록에 남긴다. 코드 수정과 실제 장비·웹 배포 완료를 구분하고, 기존 파일이나 기능의 삭제·이동은 확인과 승인 후 진행한다. 새 저장소를 만들었다는 사실만으로 모든 정리와 검증이 끝났다고 판단하지 않는다.

기존 저장소는 과거 개발 이력과 참고를 위해 보존한다. 2026-10-08 현재 기존 Render 서비스의 저장소 연결은 변경하지 않았으며, 새 저장소로의 배포 연결 전환은 별도 작업이다.

---

## 0. 목차

- 01\. 프로젝트 개요
- 02\. 하드웨어 및 장치 구성
- 03\. 센서 데이터 수집 및 MQTT
- 04\. 신호처리 및 상태 분석
- 05\. Weibull / Weibull-AFT 수명 분석
- 06\. A/B 제품 자동화 및 YOLO
- 07\. A/B 주문 및 MQTT 공정 테스트
- 08\. 데이터베이스
- 09\. Web / Render / Data WorX
- 10\. 전체 시스템 아키텍처
- 11\. 소프트웨어 스택
- 12\. 보안 구조
- 13\. 현재 확정된 핵심 기술
- 14\. 현재 미확정 및 실험 필요 항목
- 15\. 현재 전체 흐름
- 16\. 프로젝트 핵심 한계
- 17\. 프로젝트를 한 문장으로 정리
- 18\. 날짜별 작업 기록 (리마인드)

## 1. 프로젝트 개요

### 1-1. 프로젝트 목적

현재 공압 실린더의 상태를 확인하고 유지보수하는 방식은 크게 다음과 같다.

- 공장 라인에 별도의 센서를 설치하여 상태 측정
- 작업자가 직접 점검
- 센서가 부착된 실린더 또는 센서 내장형 제품으로 교체

이러한 방식은 설비를 정지하거나 기존 설비를 변경해야 하는 경우가 있고 설치 및 교체 비용이 발생할 수 있다.

#### 센서 고정형의 문제점

- 센서 설치 시 설비 정지가 필요할 수 있음
- 센서의 설치 위치가 달라질 수 있음
- 센서의 압착 강도가 달라질 수 있음
- 재설치 시 같은 측정 조건을 유지하기 어려움

스마트 실린더 케이스 역시 장착 과정에서 설비 정지가 필요할 수 있기 때문에 **“설비를 정지하지 않아도 된다”**를 핵심 차별점으로 사용하지 않는다.

본 프로젝트의 핵심 차별점은 **센서의 설치 위치와 압착 조건을 케이스 구조를 이용하여 일정하게 유지하는 것**이다.

#### 센서 내장형의 문제점

센서가 실린더 내부 또는 실린더 자체에 포함된 방식은 기존 실린더 자체를 교체해야 할 가능성이 있다.

- 기존 생산라인 변경
- 새로운 실린더 구매
- 초기 도입 비용 발생 가능

### 1-2. 해결 방법

기존 실린더에 센서를 하나씩 직접 고정하는 것이 아니라 센서의 위치와 압착 상태를 일정하게 유지할 수 있는 **케이스 형태의 장치**를 제작한다.

```text
일반 센서 설치
    ↓
작업자마다 센서 위치 차이 발생 가능
    ↓
압착 강도 차이 발생 가능
    ↓
측정 데이터 차이 발생 가능
```

```text
스마트 실린더 케이스
    ↓
정해진 위치에 케이스 장착
    ↓
센서 위치 고정
    ↓
압착 조건 일정화
    ↓
반복 측정 조건 최대한 동일하게 유지
```

케이스는 실린더 외부에 장착할 수 있도록 **클러치 형태의 구조**로 제작한다.

### 1-3. 현재 재개발 기준

현재 프로젝트는 기존에 개발하던 스마트 실린더 케이스 시스템을 기반으로 하되 소프트웨어 구조를 다시 정리하면서 개발하고 있다.

현재 추가·변경 중인 주요 항목은 다음과 같다.

- STFT 기반 실린더 동작음 확인
- Pico 01~06 장치 구분
- TEST / TRAINING / OPERATION 데이터 구분
- session 기반 데이터 관리
- Render 기반 공개 Web
- Data WorX 연동
- A/B 가공 MQTT 통신
- YOLO 수동 대체 테스트

---

## 2. 하드웨어 및 장치 구성

### 2-1. 수명예측 대상 실린더

본 프로젝트의 수명 분석 대상은 **SMC CD85N25-25-B** 공압 실린더이다.

주요 사양:

- 시리즈: C85
- 동작 방식: 복동
- 단로드
- 보어: 25 mm
- 스트로크: 25 mm
- 내장 자석 사용
- Rubber Bumper 사용

C85 계열의 해당 규격에서는 NBR 계열 씰이 사용된다.

프로젝트에서는 실린더 내부의 **NBR 씰이 반복적인 작동과 마찰에 의해 열화되는 과정**을 주요 수명 분석 대상으로 설정한다.

### 2-2. 음향 센서

#### SPH0645

실린더 몸체에서 발생하는 소리 및 구조 진동과 관련된 신호를 측정한다.

#### INMP441

실린더 패킹에서 발생하는 누설음과 관련된 신호를 측정한다.

두 센서는 I2S 방식으로 음향 데이터를 수집한다.

### 2-3. 초음파 센서

실린더는 전진과 후진 동작 자체에서 소리가 발생한다.

이 소리를 누설음으로 잘못 판단할 수 있기 때문에 현재 실린더의 동작상태를 함께 기록한다.

판단 상태:

- 정지
- 전진
- 후진

Raspberry Pi 측에 초음파 거리 센서를 사용하여 실린더 위치를 확인하고 시간 정보와 함께 저장한다.

이를 통해 **전진 과정의 정상 동작음인지**, 또는 **정지 상태에서도 계속 발생하는 누설음인지**를 구분할 수 있도록 한다.

### 2-4. Pico 01~06 장치 매핑

| Pico ID | Cylinder ID |
|---|---|
| `pico01` | `cylinder_01` |
| `pico02` | `cylinder_02` |
| `pico03` | `cylinder_03` |
| `pico04` | `cylinder_04` |
| `pico05` | `cylinder_05` |
| `pico06` | `cylinder_06` |

각 Pico에서 전달되는 데이터가 어느 실린더에서 발생한 데이터인지 확인하기 위해 이 매핑을 사용한다.

### 2-5. Raspberry Pi Pico W 역할

- 센서 측정
- 시간정보 생성
- JSON 생성
- MQTT Publish

Pico W에서는 복잡한 FFT나 AI 모델 실행보다 **센서 수집 및 전송**을 담당한다.

### 2-6. Raspberry Pi 5 역할

Raspberry Pi 5는 프로젝트의 메인 처리장치이다.

- MQTT Broker 또는 MQTT 데이터 수신
- Sensor / Cycle 처리
- STFT 기반 동작음 검출
- RMS 계산
- FFT 처리
- 특징값 계산
- ML 추론
- 누설 관련 특징 분석
- Supabase 연결
- YOLO 결과 수신
- 주문값과 검출 결과 비교
- OK / NG / ERROR 생성
- PLC / Data WorX 연결

---

## 3. 센서 데이터 수집 및 MQTT

### 3-1. 기본 데이터 흐름

```text
공압 실린더
    ↓
SPH0645 / INMP441
    ↓
Raspberry Pi Pico W
    ↓ MQTT QoS 1
Raspberry Pi 5
```

### 3-2. 시간 데이터

센서 데이터에는 측정값뿐만 아니라 시간정보도 함께 저장한다.

| 시간 | 실린더 ID | 상태 | 특징값 |
|---|---|---|---:|
| 10:00:01 | `cylinder_01` | 전진 | 0.31 |
| 10:00:02 | `cylinder_01` | 후진 | 0.28 |
| 10:00:03 | `cylinder_01` | 정지 | 0.09 |

시간정보는 단순히 현재 값을 확인하기 위한 것이 아니라 **시간에 따른 상태 변화**와 이후 Weibull-AFT의 관찰시간을 계산하기 위해 사용한다.

### 3-3. MQTT QoS

Pico W에서 Raspberry Pi 5로 센서 데이터를 전달할 때 **QoS 1**을 사용한다.

QoS 1은 메시지가 적어도 한 번 전달되지만 중복 전달 가능성이 있기 때문에 메시지 식별정보를 함께 사용한다.

### 3-4. MQTT 메시지 식별정보

주요 정보:

- `cylinder_id`
- `session_id`
- `sequence_id`
- `timestamp`

| 필드 | 역할 |
|---|---|
| `cylinder_id` | 어느 실린더의 데이터인지 확인 |
| `session_id` | Pico의 현재 실행 세션 구분 |
| `sequence_id` | 같은 세션 안에서 메시지 순서 구분 |
| `timestamp` | 실제 데이터 측정 시간 |

중복 메시지 판단 기준:

```text
cylinder_id + session_id + sequence_id
```

### 3-5. 데이터 수집 모드

#### TEST

- MQTT 연결 확인
- 센서 연결 확인
- 박수 또는 간단한 소리 테스트
- 통신 상태 확인
- 실제 학습 데이터로 사용하지 않음

#### TRAINING

실제 머신러닝 학습용 데이터만 저장한다.

예:

- 정상 패킹 → `NORMAL`
- 실제 손상 패킹 → `SEAL_LEAK`

실제 실험조건을 알고 있는 데이터만 Ground Truth로 사용한다.

#### OPERATION

실제 시스템 운전용 데이터이다.

Ground Truth와 모델의 Prediction을 구분하여 관리한다.

### 3-6. 데이터 세션 관리

현재 주요 데이터 구조:

```text
collection_sessions
        ↓
raw_data
        ↓
processed_features
        ↓
ml_results
```

| 데이터 | 역할 |
|---|---|
| `collection_sessions` | 어떤 목적으로 데이터를 수집했는지 기록 |
| `raw_data` | 센서 원본 데이터 |
| `processed_features` | RMS / FFT 등 처리된 특징값 |
| `ml_results` | 머신러닝 판별 결과 |

TEST와 TRAINING 데이터가 섞이지 않도록 session 정보와 수집 목적을 함께 확인한다.

### 3-7. MQTT 보안

현재 개발단계에서는 MQTT를 사용하고, 향후 MQTTS(TLS) 적용을 검토한다.

민감정보는 코드나 Git에 직접 저장하지 않는다.

### 3-8. Raspberry Pi → PLC

PLC 방향의 명령은 같은 명령이 두 번 실행되면 실제 설비가 중복 동작할 수 있으므로 다음 구조를 고려한다.

- command ID
- ACK
- 실행 여부
- 중복 명령 방지
- QoS 2 검토

---

## 4. 신호처리 및 상태 분석

### 4-1. STFT

STFT는 **Short-Time Fourier Transform**의 약자이다.

FFT가 한 구간에서 **어떤 주파수가 얼마나 강한지** 확인한다면, STFT는 이를 짧은 시간 구간마다 반복하여 **주파수 성분이 시간에 따라 어떻게 나타나는지** 확인한다.

#### STFT 사용 목적

본 프로젝트에서는 STFT를 **실린더가 실제로 동작할 때 발생하는 동작음인지 확인하는 용도**로 사용한다.

```text
기준 실린더 동작음
        ↓
STFT
        ↓
시간-주파수 패턴
```

```text
실시간 음향 데이터
        ↓
STFT
        ↓
시간-주파수 패턴
        ↓
기준 패턴과 비교
        ↓
실린더 동작음 검출
```

STFT 자체가 `NORMAL / ABNORMAL`을 직접 판단하지 않는다.

### 4-2. FFT

FFT는 센서의 시간 데이터를 주파수 영역으로 변환하는 신호처리 기술이다.

기본 개념:

```text
원본 시간 데이터
        ↓
FFT
        ↓
주파수별 진폭
```

기본적인 형태:

```text
진폭 = |FFT(원본 데이터)|
```

예:

| 주파수 | 진폭 |
|---:|---:|
| 100 Hz | 0.12 |
| 200 Hz | 0.31 |
| 300 Hz | 0.82 |
| 400 Hz | 0.18 |

이 경우 300 Hz 성분이 가장 크게 발생하고 있다는 것을 확인할 수 있다.

FFT는 정상 실린더와 패킹 이상 실린더를 비교하여 **씰 상태에 따라 변화하는 주파수 특징**을 찾는 데 사용한다.

### 4-3. RMS

RMS는 일정한 시간 동안 발생한 신호의 전체적인 크기를 하나의 값으로 표현하는 특징값이다.

실린더의 상태가 변화하면서 전체 음향 신호의 크기가 달라지는지를 확인하기 위해 사용한다.

본 프로젝트의 주요 음향 특징은 **RMS + FFT 특징값**이다.

### 4-4. STFT / RMS / FFT 역할 구분

| 처리 | 역할 |
|---|---|
| STFT | 실린더 동작음 검출 |
| RMS | 동작 구간의 전체적인 신호 크기 |
| FFT | 동작 구간의 주파수 특징 |
| ML | 특징값을 이용한 상태 판별 |

전체 흐름:

```text
센서 Raw 음향
      ↓
STFT
      ↓
실린더 동작음 검출
      ↓
RMS + FFT
      ↓
특징값
      ↓
ML
      ↓
NORMAL / ABNORMAL
```

### 4-5. 누설 점수

누설 점수는 Weibull 공식이 아니라 현재 센서 데이터가 정상 상태와 손상 패킹 상태 중 어디에 가까운지 쉽게 표현하기 위한 **상태 비교 지표**이다.

```text
누설 점수 = (현재값 - 정상값) ÷ (이상값 - 정상값) × 100
```

예:

```text
정상값 = 0.2
이상값 = 1.0
현재값 = 0.6

누설 점수 = (0.6 - 0.2) ÷ (1.0 - 0.2) × 100
          = 50점
```

- 0점에 가까움 → 실험에서 측정한 정상 상태에 가까움
- 100점에 가까움 → 실험에서 만든 패킹 이상 상태에 가까움

이 값은 **실제 고장 확률이나 수명 비율을 의미하지 않는다.**

### 4-6. RMS / FFT 이론적 근거

참고 연구:

**Acoustic Emission-Based Condition Monitoring and Remaining Useful Life Prediction of Hydraulic Cylinder Rod Seals**

해당 연구에서는 실린더의 씰 상태 변화와 Acoustic Emission 신호의 관계를 분석하였고 RMS 값과 주파수 영역 분석을 함께 수행하였다.

본 프로젝트에서는 **씰 상태의 변화가 RMS와 주파수 특징의 변화로 나타날 수 있다**는 방법론을 참고한다.

단, 해당 연구는 유압 실린더와 높은 주파수 영역의 AE 센서를 사용하고 본 프로젝트는 공압 실린더와 I2S 음향 센서를 사용한다.

따라서 특정 주파수값이나 임계값을 그대로 사용하지 않고 실제 CD85N25-25-B에서 수집한 데이터로 결정한다.

### 4-7. 학습 데이터 구분

정상 데이터:

```text
label = normal
```

손상 패킹 데이터:

```text
label = seal_leak
```

별도 OK DB / BAT DB를 반드시 만드는 것이 아니라 데이터의 label과 collection mode를 이용하여 구분할 수 있다.

---

## 5. Weibull / Weibull-AFT 수명 분석

### 5-1. Weibull

Weibull은 기계나 부품이 **얼마나 사용된 뒤 고장날 가능성이 있는지**를 확률적으로 표현하기 위해 사용하는 수명분포이다.

생존확률:

```text
S(t) = exp(-(t / λ)^ρ)
```

| 기호 | 의미 |
|---|---|
| `S(t)` | 시간 t까지 고장나지 않고 동작할 확률 |
| `t` | 가동시간 |
| `λ` | 수명의 크기를 나타내는 척도계수 |
| `ρ` | 고장 형태를 나타내는 형상계수 |

형상계수:

- `ρ < 1` → 초기 고장이 많이 발생하는 형태
- `ρ = 1` → 시간에 따른 고장위험이 일정
- `ρ > 1` → 사용시간 증가에 따라 마모·열화 고장위험 증가

### 5-2. Weibull 평균수명

```text
평균 수명 = λ × Γ(1 + 1 / ρ)
```

여러 실린더의 실제 수명 데이터에서 `λ`와 `ρ`를 추정할 수 있다면 평균적인 수명값을 계산할 수 있다.

### 5-3. Weibull-AFT

AFT는 **Accelerated Failure Time**의 약자이다.

Weibull-AFT는 **센서 특징과 고장시간의 관계를 데이터에서 학습하여 특정 조건에서 수명이 어떻게 변화하는지를 분석하는 생존분석 모델**이다.

### 5-4. 입력 데이터

개념적으로 사용하는 데이터:

- `X1 = RMS 특징값`
- `X2 = FFT 특징값`
- `T = 실제 관찰된 가동시간`
- `Event = 실제 고장 발생 여부`

고장이 발생한 경우:

```text
Event = 1
```

실험이 끝났지만 고장이 발생하지 않은 경우:

```text
Event = 0
```

`Event = 0`인 데이터도 검열 데이터(Censored Data)로 사용할 수 있다.

### 5-5. Weibull-AFT 수식

학생 수준에서 모델 구조를 표현하면:

```text
log(T) = b0 + b1X1 + b2X2 + W
```

| 기호 | 의미 |
|---|---|
| `T` | 고장까지 걸리는 시간 |
| `X1` | RMS |
| `X2` | FFT 특징값 |
| `b0` | 기본 수명과 관련된 값 |
| `b1` | RMS가 수명에 미치는 영향 |
| `b2` | FFT 특징이 수명에 미치는 영향 |
| `W` | Weibull 분포의 확률적 오차항 |

`b0`, `b1`, `b2`는 사람이 임의로 정하는 것이 아니라 실제 센서 데이터와 고장시간 데이터를 이용하여 모델이 추정한다.

### 5-6. 평균 예상 수명 계산

개념적으로:

```text
λ(X) = exp(b0 + b1 × RMS + b2 × FFT특징)
```

이후:

```text
E[T|X] = λ(X) × Γ(1 + 1 / ρ)
```

정상 상태와 열화 상태의 RMS / FFT 특징에 따라 서로 다른 평균 예상 수명이 계산되는 구조이다.

### 5-7. 공압 실린더 수명 연구 활용

참고 연구:

**Analyzing Pneumatic Cylinder Service Life through Seal Material Selection, Simulation, and Experimentation**

해당 연구에서는 서로 다른 씰 재질을 사용하는 공압 실린더를 반복 동작시키면서 실제 수명시험을 수행하고 Weibull 분석을 적용하였다.

다만 해당 연구의 실린더와 CD85N25-25-B는 동일한 제품이 아니므로 연구에 제시된 수명값을 CD85N25-25-B의 실제 수명으로 사용하지 않는다.

해당 연구는 **NBR 씰을 사용하는 공압 실린더에서 반복동작과 열화 데이터를 이용해 Weibull 수명분석을 수행할 수 있다는 근거**로 활용한다.

### 5-8. 성능평가

#### C-index

실제로 먼저 고장나는 실린더를 더 위험하다고 판단했는지 확인한다.

- 약 0.5 → 무작위 판단에 가까움
- 1에 가까움 → 실제 고장 순서를 잘 구분

#### MAE

평균 예상 수명값의 실제 오차를 확인한다.

```text
MAE = |실제 수명 - 예측 수명|의 평균
```

#### 95% 신뢰구간

Bootstrap 방식으로 테스트 데이터를 반복적으로 다시 추출하고 성능을 계산하여 95% 신뢰구간을 함께 표시한다.

### 5-9. 현재 한계

현재 가장 큰 한계는 **CD85N25-25-B의 충분한 Run-to-Failure 데이터가 없다는 것**이다.

필요한 데이터:

- RMS
- FFT 특징값
- 가동시간
- 고장 발생 여부
- 실제 고장시간

현재 단계에서는 다음을 먼저 구현한다.

```text
센서 데이터 수집
      ↓
RMS / FFT 추출
      ↓
시간에 따른 상태 변화 데이터 축적
      ↓
Weibull-AFT 학습용 DB 구축
```

충분한 고장 데이터가 확보되면 이후 Weibull-AFT를 학습한다.

---

## 6. A/B 제품 자동화 및 YOLO

### 6-1. YOLO11 Nano

사용 모델:

**YOLO11 Nano (YOLO11n)**

본 프로젝트에서는 생산라인에서 이동하는 제품 A와 B를 구별하기 위해 사용한다.

선정 이유:

- 모델 크기가 작음
- 연산량이 비교적 적음
- 빠른 추론
- IMX500에 적용 가능

### 6-2. Raspberry Pi AI Camera

본 프로젝트에서는 **Raspberry Pi AI Camera**를 사용한다.

AI Camera 내부에는 **Sony IMX500 Intelligent Vision Sensor**가 들어 있다.

```text
YOLO11n 학습
     ↓
IMX500용 모델 변환
     ↓
양자화
     ↓
AI Camera 적용
     ↓
IMX500에서 실시간 추론
```

### 6-3. YOLO 학습

```text
A/B 이미지 수집
      ↓
Bounding Box / Class 라벨링
      ↓
YOLO11n 학습
      ↓
A/B 시각적 특징 학습
      ↓
학습 모델 생성
```

사람이 직접 `빨간색이면 A`, `크기가 크면 B` 같은 규칙을 만드는 것이 아니라 딥러닝 모델이 이미지 데이터에서 특징을 학습한다.

### 6-4. YOLO 제품 인식

```text
Raspberry Pi AI Camera
        ↓
IMX500
        ↓
YOLO11n
        ↓
A 또는 B 검출
```

출력 예:

```text
Class = A
Confidence = 0.96
Bounding Box = 제품 위치
```

YOLO의 역할은 **A인지 B인지 인식하는 것까지**이다.

YOLO 자체가 OK / NG / ERROR를 판단하지 않는다.

### 6-5. AI와 일반 로직 구분

#### AI가 하는 것

```text
A/B 이미지 학습
      ↓
YOLO11n
      ↓
IMX500 추론
      ↓
A/B 제품 인식
```

#### 일반 프로그램이 하는 것

```text
주문정보 저장
      ↓
검출 결과와 주문 비교
      ↓
OK / NG
      ↓
Timeout 확인
      ↓
ERROR
```

즉 **AI가 제품을 인식하고, 일반 프로그램이 AI 결과를 이용하여 공정을 판단한다.**

---

## 7. A/B 주문 및 MQTT 공정 테스트

### 7-1. 현재 Frontend

현재 A/B 제품 가공 테스트에 사용할 Frontend 파일:

```text
C:\Users\USER\Downloads\order-system.html
```

| 항목 | 사용 기술 |
|---|---|
| Frontend | HTML |
| 배포 | Render |
| 데이터 저장 | Supabase PostgreSQL |

사용자는 화면에서 **A 가공 또는 B 가공**을 선택하여 주문한다.

### 7-2. 현재 테스트 목적

현재는 YOLO11n을 실제 설비에서 완전히 동작시키지 못한 상태이다.

따라서 먼저 다음 전체 흐름이 정상적으로 동작하는지 확인한다.

```text
주문
 ↓
MQTT
 ↓
Data WorX
 ↓
가공
 ↓
제품 판단
 ↓
결과 전달
```

현재 테스트에서는 YOLO 대신 사용자가 직접 **A 또는 B**를 입력한다.

### 7-3. 첫 번째 MQTT 메시지 — 동작 시작

메시지 종류:

```text
PROCESS_START
```

주요 데이터:

- `order_id`
- `requested_product`

예:

```text
PROCESS_START
requested_product = A
```

Data WorX에서는 이 값을 확인하여 **A 가공인지 B 가공인지 구분**한다.

### 7-4. 수동 YOLO 대체 테스트

현재 검출 데이터의 출처:

```text
MANUAL
```

향후:

```text
YOLO
```

판단 규칙:

| 주문 | 검출 | 결과 |
|---|---|---|
| A | A | OK |
| A | B | NG |
| B | B | OK |
| B | A | NG |

기본 판단식:

```text
requested_product == detected_product
```

### 7-5. 두 번째 MQTT 메시지 — 가공 판단

메시지 종류:

```text
PROCESS_JUDGMENT
```

주요 데이터:

- `order_id`
- `requested_product`
- `detected_product`
- `judgment`

예:

```text
requested_product = A
detected_product = A
judgment = OK
```

또는:

```text
requested_product = A
detected_product = B
judgment = NG
```

### 7-6. ERROR 판단

ERROR는 YOLO가 순간적으로 제품을 검출하지 못했다고 바로 발생시키지 않는다.

주문 이후 실제 제품이 저장고에서 나와 컨베이어를 이동하여 카메라 위치까지 도착하는 시간이 필요하기 때문이다.

개념:

```text
주문 발생
    ↓
주문시간 기록
    ↓
제품 도착 대기
    ↓
정해진 시간 내 제품 검출
    ├─ A/B 비교 → OK / NG
    └─ 제품 미도착 → ERROR
```

현재 60초는 임시 Timeout 값이며 실제 주문 → 제품 도착시간을 반복 측정한 뒤 수정한다.

### 7-7. 주문 상태 흐름

```text
사용자 주문
    ↓
REQUESTED
    ↓
MQTT PROCESS_START
    ↓
STARTED
    ↓
A/B 검출
    ↓
주문값과 검출값 비교
    ↓
OK 또는 NG
    ↓
판단 결과 저장
    ↓
COMPLETED
```

MQTT 전송 또는 DB 저장이 실패한 경우에는 정상적으로 완료된 것처럼 `COMPLETED`로 처리하지 않는다.

### 7-8. 현재 전체 테스트 흐름

```text
사용자
  ↓
order-system.html
  ↓
A 또는 B 가공 선택
  ↓
Render Backend
  ↓
Supabase PostgreSQL
  ↓
process_orders 저장
  ↓
MQTT PROCESS_START
  ↓
Data WorX
  ↓
A 또는 B 가공 신호 확인

[가공 후]

수동 A/B 입력
  ↓
detected_product 생성
  ↓
주문값과 비교
  ↓
OK / NG
  ↓
process_judgments 저장
  ↓
MQTT PROCESS_JUDGMENT
  ↓
Data WorX
  ↓
최종 가공 판단 확인
```

### 7-9. 향후 YOLO 연결

```text
현재
Manual Input
      ↓
detected_product
      ↓
주문 비교
      ↓
OK / NG
```

```text
향후
Raspberry Pi AI Camera
      ↓
IMX500
      ↓
YOLO11n
      ↓
detected_product
      ↓
주문 비교
      ↓
OK / NG
```

주문 비교와 OK / NG 로직은 유지하고 검출 데이터를 만드는 부분만 **MANUAL → YOLO**로 변경한다.

---

## 8. 데이터베이스

### 8-1. Supabase PostgreSQL

메인 데이터베이스는 **Supabase PostgreSQL**을 사용한다.

현재 주요 센서 데이터 구조:

- `collection_sessions`
- `raw_data`
- `processed_features`
- `ml_results`

### 8-2. Raw Data

센서에서 측정한 원본 데이터를 저장한다.

목적:

- 원본 데이터 보존
- FFT 처리방법 변경 시 재처리
- 데이터 오류 확인
- 새로운 특징 추출 시 재사용

### 8-3. Processed Features

Raw 데이터를 처리한 특징값을 저장한다.

예:

- RMS
- 주파수
- 진폭
- Peak
- Crest Factor
- 주파수 대역 에너지
- 누설 관련 특징값
- 누설 점수

### 8-4. ML Results

분석 및 모델 결과를 저장한다.

예:

- `cylinder_id`
- `timestamp`
- 상태
- RMS
- FFT 특징값
- 누설 점수
- 평균 예상 수명
- `model_version`

### 8-5. 주문 테이블 — process_orders

사용자가 요청한 A/B 가공 주문을 저장한다.

주요 데이터:

- `order_id`
- `requested_product`
- `status`
- `created_at`
- `started_at`
- `completed_at`

`requested_product`:

- A
- B

`status` 예:

- `REQUESTED`
- `STARTED`
- `COMPLETED`
- `FAILED`

### 8-6. 판단 테이블 — process_judgments

주문값과 실제 검출값을 비교한 결과를 저장한다.

주요 데이터:

- `order_id`
- `requested_product`
- `detected_product`
- `judgment`
- `detection_source`
- `created_at`

| 항목 | 값 |
|---|---|
| `detected_product` | A 또는 B |
| `judgment` | OK 또는 NG |
| 현재 `detection_source` | MANUAL |
| 향후 `detection_source` | YOLO |

### 8-7. Supabase Realtime

개념적으로:

```text
Raspberry Pi / Backend
        ↓
Supabase PostgreSQL
        ↓
Supabase Realtime 또는 API
        ↓
Web
```

실시간 표시 방식은 실제 구현에 따라 Backend API, Realtime 등을 사용할 수 있다.

---

## 9. Web / Render / Data WorX

### 9-1. Web 시스템 확인 기준

현재 홈페이지는 **로컬 구현**, **Git 반영**, **Render 배포**, **실제 연동 검증**을 서로 다른 상태로 구분해서 관리한다.

| 상태 | 의미 |
|---|---|
| 구현됨 | 로컬 코드에 화면 또는 기능이 존재함 |
| 배포됨 | Git 및 Render에 변경 내용이 실제 반영됨 |
| 실제 동작 검증됨 | 공개 서비스 또는 실제 장비에서 정상 동작을 직접 확인함 |
| 미구현 | 필요한 기능이나 코드가 아직 없음 |
| 미확인 | 코드 또는 배포는 존재할 수 있으나 실제 동작을 확인하지 못함 |

`/health`가 성공하더라도 실제 DB 읽기·쓰기, Pi 연결, MQTT 수신, Data WorX 연동까지 모두 정상이라고 판단하지 않는다.

---

### 9-2. 공개 Web 주소

현재 공개 서비스:

**https://ml-cylinder.onrender.com/**

| 구분 | 주소 예시 | 역할 |
|---|---|---|
| 노트북 Hotspot | `192.168.137.1` | 로컬 네트워크 제공 |
| Raspberry Pi 5 / Pico | `192.168.137.xxx` | 내부 장치 통신 |
| Render Web | `ml-cylinder.onrender.com` | 외부 Web 접속 |

`192.168.137.xxx`는 내부 네트워크 주소이고 `ml-cylinder.onrender.com`은 Render에 실제 배포된 공개 Web 서비스 주소이다.

---

### 9-3. 메인 홈페이지

**URL:** `/`  
**파일:** `ML-cylinder/public/index.html`

담당 역할:

- 프로젝트 소개
- 구매 및 시리얼 번호 발급
- 시리얼 번호 입력
- 대시보드 진입

현재 상태:

| 항목 | 상태 |
|---|---|
| 메인 화면 코드 | 구현됨 |
| 시리얼 검증 Backend API | 구현됨 |
| 시리얼 발급 Backend API | 구현됨 |
| 실제 시리얼 발급 | 미확인 |
| 실제 시리얼 검증 | 미확인 |
| 검증 후 화면 이동 | 미확인 |
| 필요한 API 접근 보호 | 미확인 |

확인 대상:

- ADXL345 및 컨베이어 설명이 현재 센서 구성과 일치하는지
- `smart-cylinder-monitor.com` 링크의 실제 용도와 유효성
- 구매 기능이 실제 결제인지 단순 시리얼 발급 테스트인지
- 시리얼 검증이 단순 화면 이동뿐 아니라 필요한 API 접근도 보호하는지

---

### 9-4. 센서 모니터링 화면

**URL:** `/monitoring.html`  
**파일:** `ML-cylinder/public/monitoring.html`  
**관련 JavaScript:** `ML-cylinder/public/real-monitor.js`

담당 역할:

- 센서 수집 상태 확인
- SPH0645 / INMP441 데이터 표시
- RMS 변화 그래프
- 데이터 연결 상태 표시
- 데이터 갱신 상태 표시

현재 상태:

| 항목 | 상태 |
|---|---|
| 모니터링 화면 | 구현됨 |
| 그래프 관련 코드 | 구현됨 |
| 센서 조회 Backend API | 구현됨 |
| 과거 Pi MQTT 센서 메시지 수신 이력 | 실제 확인 이력 있음 |
| 현재 Pi 최신 데이터 → Render | 미확인 |
| 현재 Render → Browser 최신 데이터 | 미확인 |
| Pico01~06 전체 장치 표시 | 미확인 |
| 데이터 지연·끊김 표시 | 확인 필요 |

확인해야 할 실제 경로:

```text
Pico W
  ↓ MQTT
Raspberry Pi 5
  ↓
Supabase
  ↓
Render
  ↓
Browser
```

추가 확인 대상:

- 화면이 실제로 호출하는 API
- 실제 데이터 / 재생 데이터 / 모의 데이터 구분
- Pico01~06 중 실제 표시 가능한 장치
- 마지막 수신 시각
- 데이터 지연 및 연결 끊김 표시
- RMS / Peak 등의 계산 위치와 단위
- 값이 0이거나 오래된 경우 정상 최신 데이터처럼 표시되는지

---

### 9-5. 카메라 화면

**URL:** `/smart-cylinder-camera.html`  
**파일:** `ML-cylinder/public/smart-cylinder-camera.html`

담당 역할:

- Raspberry Pi 카메라 영상 또는 이미지 표시
- 연결 상태 표시
- 재연결 안내

현재 상태:

| 항목 | 상태 |
|---|---|
| 카메라 화면 코드 | 구현됨 |
| 로컬 Backend 카메라 업로드 API | 구현됨 |
| 로컬 Backend 카메라 조회 API | 구현됨 |
| 카메라 API Git 반영 | 미확인 |
| 카메라 API Render 배포 | 미확인 |
| 실제 Raspberry Pi 영상 수신 | 미확인 |
| YOLO / IMX500 실제 연동 | 미확인 |

확인 대상:

- 영상 또는 프레임의 실제 제공 경로
- Raspberry Pi 측 송신 프로그램 존재 여부
- 스트리밍인지 주기적 이미지 갱신인지
- Cloudflare 임시 Tunnel에 의존하는 코드가 남아 있는지
- YOLO / IMX500 연동 여부

YOLO / IMX500은 실제 코드와 실행 근거가 확인되기 전까지 구현됐다고 표현하지 않는다.

---

### 9-6. 가공 주문 화면

**URL:** `/order-system.html`  
**파일:** `ML-cylinder/order-system.html`

담당 역할:

- A / B 가공 주문 생성
- 주문 목록 및 상태 표시
- MANUAL A / B 검출 결과 입력
- 주문값과 검출값 비교
- OK / NG 판단 결과 표시

관련 API:

```text
GET  /api/process-orders
POST /api/process-orders
GET  /api/process-orders/<order_id>
POST /api/process-orders/<order_id>/manual-detection
```

현재 상태:

| 항목 | 상태 |
|---|---|
| 주문 화면 | 구현됨 |
| 주문 API | 구현됨 |
| Git 반영 | 반영됨 |
| `process_orders` | 실제 Supabase 생성 완료 |
| `process_judgments` | 실제 Supabase 생성 완료 |
| 두 테이블 RLS | 활성화 완료 |
| 서버 역할 쓰기 권한 | 구성 완료 |
| 공개 `GET /api/process-orders?limit=1` | 실제 동작 검증됨 |
| 공개 주문 생성 | 미확인 |
| 공개 MANUAL 판정 저장 | 미확인 |
| Pi Bridge 실제 실행 | 미확인 |
| 실제 MQTT Publish | 미확인 |
| 실제 Data WorX 수신 | 미확인 |
| 실제 PLC 가공 동작 | 미확인 |

공개 서비스에서 확인된 읽기 응답:

```text
HTTP 200
{"orders":[]}
```

이 결과는 **Render → Backend → Supabase 주문 조회 경로가 동작했다는 의미**이며, 주문 생성·판정 저장·설비 동작까지 검증되었다는 의미는 아니다.

현재 검출 방식:

```text
detection_source = MANUAL
```

현재 단계에서 YOLO가 구현됐다고 표현하지 않는다.

판단 규칙:

| 주문 | Manual 검출 | 결과 |
|---|---|---|
| A | A | OK |
| A | B | NG |
| B | B | OK |
| B | A | NG |

Pi 연결 프로그램:

```text
system/DataWorX/process_order_bridge.py
```

MQTT 계약:

| 항목 | 값 |
|---|---|
| Broker | Raspberry Pi 5 Local Mosquitto |
| Pi Bridge 접속 주소 | `127.0.0.1` |
| Data WorX 접속 주소 | Raspberry Pi 5 LAN IP |
| Port | `1883` |
| Topic | `smart-cylinder/process/events` |
| QoS | `1` |
| Retain | `false` |
| 메시지 구분 | `PROCESS_START`, `PROCESS_JUDGMENT` |
| 중복 식별 기준 | `order_id + message_type` |

현재 실제 `Pi → MQTT → Data WorX → 설비` 흐름은 **미확인**이다.

---

### 9-7. 관리자 화면

**URL:** `/admin.html`  
**파일:** `ML-cylinder/public/admin.html`

담당 역할:

- 관리자 로그인 / 로그아웃
- 시리얼 번호 목록 조회
- 시리얼 번호 등록
- 관리자 비밀번호 변경

현재 상태:

| 항목 | 상태 |
|---|---|
| 관리자 화면 | 구현됨 |
| 관련 Backend API | 구현됨 |
| 공개 Render 배포 | 미확인 |
| 실제 로그인 | 미확인 |
| 실제 로그아웃 | 미확인 |
| 실제 시리얼 등록 | 미확인 |
| 실제 비밀번호 변경 | 미확인 |

확인 대상:

- 비로그인 상태에서 관리자 API 차단 여부
- 인증 Token 만료 처리
- 로그아웃 처리
- 관리자 비밀번호 저장 위치
- 재시작 후 비밀번호 유지 여부
- 시리얼 데이터의 실제 저장 위치
- DB 오류 시 JSON 저장으로 조용히 대체되는지 여부

현재 `serials`, `admin_settings`의 기존 RLS 설정은 이번 Web 현황 정리 때문에 변경하지 않는다.

---

### 9-8. PICO별 상세 Web 화면

PICO별로 Render 서비스를 6개 만드는 것이 아니라 **하나의 Render Web 서비스에서 PICO ID에 따라 상세 정보를 구분**하는 구조를 목표로 한다.

| PICO | Cylinder |
|---|---|
| PICO 01 | `cylinder_01` |
| PICO 02 | `cylinder_02` |
| PICO 03 | `cylinder_03` |
| PICO 04 | `cylinder_04` |
| PICO 05 | `cylinder_05` |
| PICO 06 | `cylinder_06` |

현재 최종 PICO 상세 Route와 실제 화면 구현·배포 상태는 **미확인**으로 관리한다.

---

### 9-9. Data WorX Web 연동

Data WorX에서는 PICO별 상세 정보를 확인할 수 있도록 **더보기** 메뉴를 구성할 계획이다.

```text
더보기
├─ PICO 01
├─ PICO 02
├─ PICO 03
├─ PICO 04
├─ PICO 05
└─ PICO 06
       ↓
선택한 PICO의 Render 상세 화면
```

Data WorX 자체에서 STFT, RMS, FFT, Condition ML을 계산하지 않는다.

Data WorX 역할:

- PLC 상태 및 자동화 화면
- MQTT `PROCESS_START` 확인
- MQTT `PROCESS_JUDGMENT` 확인
- PICO별 상세 Web 화면 진입

현재 실제 MQTT 수신과 PICO 상세 Web 이동은 별도 실제 검증이 필요하다.

---

### 9-10. 화면별 역할 요약

| 화면 | 핵심 역할 | 현재 상태 |
|---|---|---|
| `/` | 프로젝트 소개, 시리얼, 대시보드 진입 | 구현됨 / 실제 전체 흐름 미확인 |
| `/monitoring.html` | 센서 모니터링 | 구현됨 / 최신 Pi 연동 미확인 |
| `/smart-cylinder-camera.html` | 카메라 화면 | 구현됨 / 실제 영상 연동 미확인 |
| `/order-system.html` | A/B 주문·MANUAL 판정 | 구현됨 / DB 읽기 실제 검증됨 / 설비 연동 미확인 |
| `/admin.html` | 관리자·시리얼 관리 | 구현됨 / 실제 인증·저장 미확인 |

---

### 9-11. 현재 사용 가능한 것으로 확인된 기능

- Render 공개 서비스 접속
- 주문 화면 코드
- 주문 API 코드
- Supabase `process_orders`
- Supabase `process_judgments`
- 두 주문 테이블 RLS
- 공개 `GET /api/process-orders?limit=1`을 통한 실제 DB 읽기
- 로컬 자동 테스트에서 A/A, A/B, B/B, B/A 판단 로직

---

### 9-12. 코드만 존재하고 실제 연동은 확인되지 않은 기능

- 메인 페이지의 실제 시리얼 발급 / 검증 전체 흐름
- 모니터링 화면의 현재 Pi 최신 데이터 수신
- Pico01~06 전체 장치 모니터링
- 카메라 실제 영상 / 이미지 수신
- YOLO / IMX500 실제 화면 연동
- 관리자 실제 로그인 / 로그아웃
- 관리자 시리얼 등록
- 관리자 비밀번호 변경
- 공개 서비스의 주문 생성
- 공개 서비스의 MANUAL 판정 저장
- Pi `process_order_bridge.py` 실제 실행
- Mosquitto 실제 Publish
- Data WorX 실제 MQTT 수신
- PLC 실제 가공

---

### 9-13. 오래된 설명·링크·임시 구현 점검 대상

- 메인 페이지의 ADXL345 설명
- 메인 페이지의 컨베이어 설명
- `smart-cylinder-monitor.com` 링크
- 구매 기능의 실제 의미
- Cloudflare 임시 Tunnel 관련 코드
- 실제 데이터와 모의 / 재생 데이터 혼용 가능성
- 오래된 센서 구성 설명
- YOLO가 이미 동작하는 것처럼 보이는 문구
- MANUAL TEST와 실제 YOLO 결과의 UI 구분

---

### 9-14. 화면 간 역할 구분

```text
메인 홈페이지
→ 프로젝트 소개 / 시리얼 / 진입

센서 모니터링
→ SPH0645 / INMP441 / RMS / 연결 상태

카메라
→ Camera 영상 또는 프레임

가공 주문
→ A/B 주문 / MANUAL 판정 / OK·NG

관리자
→ 관리자 인증 / 시리얼 관리
```

센서 상태, 주문, 카메라, 관리자 기능을 하나의 화면에 중복 구현하지 않는다.

---

### 9-15. 권장 메뉴 구성

```text
Home
├─ 프로젝트 소개
├─ 센서 모니터링
├─ 카메라
├─ A/B 가공 주문
└─ 관리자
```

향후 PICO 상세 화면이 구현되면:

```text
센서 모니터링
├─ PICO 01
├─ PICO 02
├─ PICO 03
├─ PICO 04
├─ PICO 05
└─ PICO 06
```

---

### 9-16. 우선 확인·수정 대상

#### 1순위 — 실제 배포 상태와 로컬 코드 일치 여부

로컬에 구현된 기능이 Git / Render에 반영되지 않으면 실제 사용자 화면에서는 사용할 수 없다.

확인 대상:

- `server.py`
- `order-system.html`
- 카메라 API
- 관리자 API
- 모니터링 API

#### 2순위 — 센서 모니터링 데이터 출처

실제 데이터, 오래된 데이터, 재생 데이터, 모의 데이터가 구분되지 않으면 화면 값을 신뢰하기 어렵다.

#### 3순위 — 메인 홈페이지 오래된 설명

ADXL345 등 현재 센서 구성과 다른 설명이 남아 있을 가능성이 있다.

#### 4순위 — 인증과 관리자 기능

화면 이동만 막고 API가 보호되지 않는 구조라면 실제 접근제어가 되지 않는다.

#### 5순위 — Camera 실제 연결

화면 코드와 Backend API 존재만으로 실제 Raspberry Pi 영상 연동이 완료됐다고 볼 수 없다.

#### 6순위 — Data WorX 실장 검증

현재 주문 로직과 DB는 구현됐지만 `process_order_bridge.py → Mosquitto → Data WorX → PLC` 실제 흐름은 아직 확인되지 않았다.

---

### 9-17. 수정에 필요한 승인 범위

현황 조사만으로 다음 항목을 임의 변경하지 않는다.

수정이 필요하다고 확인된 경우 사용자 승인 후 작업한다.

승인이 필요한 예:

- HTML 문구 수정
- 오래된 링크 제거 또는 교체
- API 인증 방식 변경
- 관리자 인증 수정
- Camera 연결 방식 수정
- 모니터링 API 변경
- Render 배포 변경
- Git Push
- Supabase 데이터 쓰기 / 삭제
- DB Schema 변경
- RLS 변경
- MQTT Topic 변경
- Data WorX 설정 변경
- PLC 프로그램 변경

센서 시스템, STFT, RMS / FFT, Condition ML, Weibull-AFT, Pico MQTT, YOLO, 기존 DB Schema 및 기존 RLS 설정은 이 Web 현황 정리 때문에 변경하지 않는다.

---

## 10. 전체 시스템 아키텍처

### 10-1. 센싱 계층

- SMC CD85N25-25-B
- SPH0645
- INMP441
- 초음파 거리 센서

### 10-2. 센서 수집 계층

**Raspberry Pi Pico W**

- MicroPython
- 센서 데이터 수집
- timestamp / session / sequence 생성
- MQTT QoS 1 Publish

### 10-3. 메인 처리 계층

**Raspberry Pi 5**

- MQTT Broker / 수신
- Sensor / Cycle 처리
- STFT
- RMS
- FFT
- 특징값 생성
- ML 추론
- Supabase 연결
- AI Camera 결과 처리
- 주문 결과 비교

### 10-4. 영상 AI 계층

```text
Raspberry Pi AI Camera
        ↓
Sony IMX500
        ↓
YOLO11n
        ↓
A/B 객체 인식
```

### 10-5. 자동화 계층

```text
Raspberry Pi 5
      ↓
Data WorX
      ↓
PLC
      ↓
실린더 / 컨베이어 제어
```

### 10-6. 데이터 계층

**Supabase PostgreSQL**

- `collection_sessions`
- `raw_data`
- `processed_features`
- `ml_results`
- `process_orders`
- `process_judgments`

### 10-7. 사용자 계층

```text
Supabase / Backend
        ↓
Render Web
        ↓
┌───────────────────┐
│ Data WorX          │
│ 외부 PC / 노트북  │
│ 휴대폰             │
└───────────────────┘
```

---
## 11. 소프트웨어 스택

| 영역 | 기술 |
|---|---|
| Raspberry Pi Pico W | MicroPython, MQTT |
| Raspberry Pi 5 | Python, NumPy, STFT, RMS, FFT, MQTT |
| AI Camera | Raspberry Pi AI Camera, Sony IMX500, YOLO11n |
| Database | Supabase PostgreSQL |
| Backend | Python, Flask 또는 추후 결정할 Backend Framework, REST API |
| Frontend | HTML, CSS, JavaScript |
| 배포 | Render |
| 자동화 | Data WorX, PLC, MQTT |

---

## 12. 보안 구조

- 일반 웹 사용자는 필요한 데이터만 읽을 수 있도록 권한을 구분한다.
- Raspberry Pi와 Backend에서 DB 쓰기 작업이 필요한 경우 서버 측 인증정보를 사용한다.
- Secret Key 등 민감정보를 HTML / JavaScript에 직접 저장하지 않는다.
- MQTT Password, Wi-Fi Password, Service Role Key, Token 등을 Git에 저장하지 않는다.
- Raspberry Pi의 MQTT 포트를 인터넷에 직접 공개하지 않는다.
- 내부 네트워크 주소와 공개 Web 주소를 구분한다.

---

## 13. 현재 확정된 핵심 기술

| 항목 | 현재 기준 |
|---|---|
| 센서 데이터 처리 | STFT + RMS + FFT |
| STFT 역할 | 동작음 검출 |
| RMS / FFT 역할 | 상태 특징 분석 |
| 실린더 상태 확인 | 초음파 센서 |
| Pico → Pi | MQTT QoS 1 |
| 센서 제어 | MicroPython |
| 메인 연산 | Raspberry Pi 5 |
| 메인 DB | Supabase PostgreSQL |
| 공개 Web | Render |
| 자동화 연동 | Data WorX / PLC |
| 영상 AI 목표 | Raspberry Pi AI Camera + IMX500 + YOLO11n |
| YOLO 실제 연동 | 미확인 |
| 현재 A/B 검출 테스트 | MANUAL |
| 공정 판단 로직 | OK / NG / ERROR |
| 수명모델 | Weibull-AFT |
| 수명 출력 목표 | 평균 예상 수명시간 |

---

## 14. 현재 미확정 및 실험 필요 항목

### 14-1. STFT

- Window Size
- Hop Length
- Window Function
- FFT Size
- 동작음 유사도 계산 방식
- 동작음 판정 임계값

실제 실린더 동작음을 반복 수집한 뒤 결정한다.

### 14-2. FFT 특징값

후보:

- 특정 주파수 진폭
- 주파수 대역 에너지
- RMS
- Peak
- Crest Factor

정상 패킹과 손상 패킹의 데이터를 비교하여 차이가 크게 나타나는 특징을 선정한다.

### 14-3. 누설 점수 기준

정상값과 이상값은 실제 측정한 데이터로 결정한다.

### 14-4. 정지 판단 임계값

실제 정지 상태 데이터를 수집한 후 결정한다.

### 14-5. ERROR Timeout

현재 60초는 임시값이며 실제 주문 → 제품 도착시간을 반복 측정한 뒤 수정한다.

### 14-6. Weibull-AFT

실제 Run-to-Failure 데이터가 충분히 확보되어야 신뢰성 있는 모델 학습이 가능하다.

### 14-7. Render ↔ Raspberry Pi 5

실시간 데이터를 어떤 방식으로 전달할지는 현재 최종 확정하지 않는다.

### 14-8. PICO 상세 페이지 URL

PICO별 상세 페이지 구조는 사용하지만 최종 URL Route는 아직 확정하지 않는다.

### 14-9. YOLO 실제 연동

현재는 MANUAL 입력을 사용하며 실제 YOLO11n / IMX500 연결 후 교체한다.

---

## 15. 현재 전체 흐름

### 15-1. 실린더 상태 분석

```text
SPH0645 / INMP441
        ↓
Pico W 01~06
        ↓ MQTT QoS 1
Raspberry Pi 5
        ↓
STFT 동작음 검출
        ↓
RMS + FFT 특징 추출
        ↓
ML 추론
        ↓
Supabase PostgreSQL
        ↓
Render Web
        ↓
Data WorX / 외부 Browser
```

### 15-2. 현재 A/B 자동화 테스트

```text
order-system.html
        ↓
A / B 주문
        ↓
process_orders
        ↓
MQTT PROCESS_START
        ↓
Data WorX
        ↓
가공 동작
        ↓
Manual A/B Input
        ↓
주문값 비교
        ↓
OK / NG
        ↓
process_judgments
        ↓
MQTT PROCESS_JUDGMENT
        ↓
Data WorX
```

### 15-3. 향후 A/B 자동화

> 아래 흐름은 목표 구조이며 현재 실제 YOLO / IMX500 연동은 미확인이다.

```text
사용자 주문
    ↓
Data WorX / PLC 가공
    ↓
AI Camera
    ↓
IMX500
    ↓
YOLO11n
    ↓
A / B 검출
    ↓
주문값 비교
    ↓
OK / NG
```

---

## 16. 프로젝트 핵심 한계

현재 가장 큰 한계는 **실린더의 실제 장기 수명 데이터가 부족하다는 것**이다.

현재 정상 패킹과 손상 패킹 데이터로 다음 단계까지 구현할 수 있다.

- RMS
- FFT
- STFT
- 누설 관련 특징
- 상태 비교

하지만 Weibull-AFT를 이용하여 실제 수명값을 신뢰성 있게 출력하려면 다음 데이터가 필요하다.

- 여러 실린더
- 센서 특징값
- 실제 가동시간
- 실제 고장여부
- 실제 고장시간

따라서 현재 프로젝트에서는 **센서 데이터 수집 및 상태분석 시스템을 먼저 구현하고, 이후 실제 고장 데이터가 축적되면 Weibull-AFT 기반 수명예측까지 확장**한다.

---

## 17. 프로젝트를 한 문장으로 정리

**스마트 실린더 케이스는 기존 공압 실린더에 일정한 조건으로 센서를 장착하여 음향 데이터를 수집하고, STFT로 동작 구간을 확인한 뒤 RMS와 FFT를 이용해 상태 변화를 분석하며, 축적된 고장 데이터를 Weibull-AFT에 적용해 평균 예상 수명정보 제공을 목표로 하는 시스템이다. 또한 Raspberry Pi AI Camera의 IMX500과 YOLO11n을 이용하여 생산라인의 A/B 제품을 인식하고 주문정보와 비교해 OK·NG·ERROR를 판단하며, 현재는 YOLO 연결 전 MANUAL A/B 입력을 이용해 MQTT와 Data WorX의 전체 자동화 흐름을 검증하고 있다.**

---

## 18. 날짜별 작업 기록 (리마인드)

사용자가 지칭하는 리마인드 MD는 이 최상위 `README.md`다. 앞으로 작업 완료 시 날짜와 수정 내용, 검증 결과, 배포 여부 및 남은 작업을 이 절에 추가한다. 날짜는 한국 시간 기준이며, 미검증 또는 미배포 작업을 완료로 기록하지 않는다. 아래는 대화·실행 결과로 날짜를 확인할 수 있는 최근 작업부터 기록했다.

### 2026-10-07

- **0.1.8 저장·모니터링 개선:** 확인된 세션 재등록·재조회와 방금 저장한 Raw 재조회를 줄였다. 일반 패킷의 DB 요청 경로를 5회에서 2회로 줄이고, 최신 Raw가 처리 중이면 같은 세션의 마지막 Runtime 저장 결과를 조회하도록 수정했다.
- **상태 표시 수정:** Runtime 누락은 `WAITING_FOR_DATA`로 표시한다. 기존 수신 시각과 10초 STALE 계약을 유지하며 오래된 데이터를 LIVE로 만들지 않는다.
- **패키지 검증:** 0.1.8 Wheel 생성, Canonical Source/내용/SHA 검증 완료. 관련 테스트 177개 통과, 8개 건너뜀. 기존 0.1.7 Wheel은 변경하지 않았다.
- **Git 반영:** `kang0840/ML-cylinder`의 `main`에 Commit `283a962`를 Push했다. 이 기록만으로 Render의 새 버전 배포 완료를 확정하지 않는다.
- **Pi 및 웹 관찰:** 사용자 실행 로그에서 Raw·STFT·Preview·Runtime 저장 성공을 확인했다. 공개 웹 API의 관찰 시점에는 수신 지연이 약 2~3초였고 이전 약 52초 지연보다 줄었다. 다만 조회 중 도착한 최신 행이 NO_DATA로 표시되는 LIVE 판정 시각 오류를 추가 발견했다. 지속 성능 보장은 아니다.

### 2026-10-08

- **오늘 최종 확인·남은 작업:** 사용자가 패드에서 공개 모니터링 그래프가 표시되는 것을 확인했다. 오늘은 0.1.9 Wheel 생성·검증(220 통과/8 건너뜀), 웹 중복 요청·시간 초과·429 대기·마지막 그래프 보존 수정(142 통과/8 건너뜀), 기존 Render 연결 저장소의 `065b436` 웹 배포와 `3a5653a` 0.1.9 배포를 진행했다. 사용자가 Render 배포 완료를 확인했으며 이후 공개 API 3회 모두 HTTP 200과 STFT Preview를 확인했다. 과거 데이터(STALE)의 다른 기기 표시 문제는 패드에서 해소 확인됐지만 친구 PC 재확인·새 센서 입력 LIVE·장시간 안정성·서버 내부 병목 및 Pi 0.1.9 설치는 남아 있다. 아래 미배포·미확인 문구는 각 작업 당시의 중간 기록이며 이 최종 확인과 구분한다. DB Schema·RLS·MQTT 규격·원본 데이터·학습 기준은 변경하지 않았다. 이 README만 새 개발 저장소 `kang0840/-re-ML--cylinder`에 반영하며 해당 저장소의 코드 동기화나 Render 연결 전환을 의미하지 않는다.

- **0.1.9 Render 배포 후 확인:** 사용자가 배포 완료를 확인했다. 공개 Canonical API(limit=100)를 순차 3회 조회하여 모두 HTTP 200, 응답 3.12초·3.55초·2.91초, STFT Preview 존재 및 STALE 상태를 확인했다. 평균 약 3.19초이며 측정 환경이 다르므로 지속 성능 향상 보장은 아니다. 실제 다중 기기 그래프 표시·새 센서 입력 LIVE와 Pi 0.1.9 설치는 미검증이다.

- **Render용 0.1.9 Git 반영:** 사용자 승인으로 기존 Render 연결 저장소 `kang0840/ML-cylinder`의 `main`에 0.1.9 Wheel과 requirements 경로·SHA 변경 두 파일만 Commit `3a5653a`으로 Push했다. Wheel의 22개 Canonical 모듈·Source Manifest·최종 SHA 일치를 재확인했다. 기존 Wheel과 다른 로컬 변경은 보존했다. Render 실제 설치 버전·Live 커밋 확인 및 배포 후 응답시간 비교는 별도 검증 대상이며 Pi 설치는 수행하지 않았다.

- **웹 조회 누적 방지 Git 반영:** 기존 Render 연결 저장소 `kang0840/ML-cylinder`의 `main`에 `public/real-monitor.js`만 Commit `065b436`으로 Push했다. 다른 로컬 변경, 0.1.9 Wheel 및 저장소 연결 전환은 포함하지 않았다. Push 직후 공개 JavaScript는 HTTP 200이지만 새 단일 요청·시간 제한 코드가 없어 아직 구버전임을 확인했다. Render 배포 완료와 실제 그래프 복구는 미확인이다.

- **웹 조회 누적 방지:** `real-monitor.js`의 2초 고정 중첩 요청을 완료 후 재예약 방식으로 변경했다. 단일 요청 잠금, 15초 AbortController 제한, 실패 시 최대 30초 backoff와 HTTP 429 시 60초 대기를 추가했다. 조회 오류는 마지막 정상 그래프를 지우지 않고 LIVE 아님을 표시한다. 관련 통합 테스트 142개 통과, 실제 장비/데이터 필요 8개 건너뜀 및 JavaScript 문법 검사를 통과했다. Git Push·Render 배포는 수행하지 않았고 서버 지연·429 발생 계층 확인과 실제 다중 기기 검증은 남아 있다. Frontend 자산 수정이며 기존 0.1.9 Wheel은 변경하지 않았다.

- **DB 조회 최적화:** Monitoring 과거 기록 조회는 Runtime 전체 대신 수신 시각·상태·Packet 지표만 JSON 경로로 조회한다. 큰 STFT 행렬은 최신 Preview 조회에만 포함한다. 이미 가져온 같은 세션의 처리 완료 행은 재사용하여 추가 조회를 생략한다.
- **Preview 정리 최적화:** 조회 범위가 마지막 행까지 도달한 경우 중복 확인 SELECT를 생략한다. 범위가 가득 찬 경우에는 기존 backlog 확인을 유지한다. Raw를 삭제하지 않는다.
- **LIVE 판정 수정:** 실제 현재 시각을 DB 조회 완료 후 계산한다. 테스트의 명시적 시각 주입과 미래 시각·누락·STALE 판정은 유지한다.
- **검증:** 관련 통합 테스트 141개 통과, 8개 건너뜀. 실제 DB 최근 OPERATION 100건을 읽기 전용으로 비교한 Runtime JSON 크기는 329,222바이트에서 필요한 필드 43,621바이트로 약 87% 감소했다. 이 수치는 JSON 내용량 비교이며 실제 네트워크 지연 또는 응답시간 측정값은 아니다.
- **변경하지 않은 영역:** DB Schema, RLS, MQTT 규격, 원본 Raw, Pico 코드 및 ML 판정 기준.
- **배포 상태:** 이번 최적화는 로컬 소스에만 적용했다. 0.1.9 Wheel 생성 및 Pi/Render 배포는 아직 진행하지 않았다. 기존 0.1.8 Wheel은 보존했다. 배포 후 실제 응답시간·LIVE 안정성 확인이 남아 있다.
- **기록 규칙 확정:** 별도 리마인드 파일을 만들지 않고 최상위 README의 이 절을 날짜별 작업 기록으로 사용한다.
- **새 공개 저장소 업로드 준비:** 사용자 지정 `kang0840/-re-ML--cylinder`에 최상위 구조를 유지한 현재 파일 스냅샷을 올린다. README·AGENTS·Canonical system·Pico·ML-cylinder·Wheel·롤백 폴더를 포함하고 기존 Git 이력, Secret/.env, 캐시, 운영 로그, DB 백업, 학습 엑셀 및 이전 배포 ZIP은 공개 대상에서 제외한다. 로컬 원본을 삭제하거나 기존 `ML-cylinder` 원격 및 Render 연결을 변경하지 않는다. 이 항목은 업로드 준비 기록이며 Push 완료 여부는 후속 기록으로 구분한다.
- **새 공개 저장소 업로드 완료:** 271개 파일의 현재 스냅샷을 `https://github.com/kang0840/-re-ML--cylinder`의 `main`에 최초 Commit `8267529`로 Push했다. 확인한 Secret 서명 검사에서 일치 항목은 없었으며 기존 Git 이력은 포함하지 않았다. 기존 저장소/Render 연결 변경 및 새 서비스 배포는 수행하지 않았다. 최신 Canonical 소스에는 2026-10-08 조회 최적화가 있지만 설치용 Wheel은 아직 0.1.8이므로 코드와 배포 산출물의 차이는 0.1.9 생성 시 해소해야 한다.
- **저장소 변경 배경 문서화:** 코드와 파일의 관계가 복잡하게 얽히고 정리가 누적되지 않아 기존 상태에서 부분 수정으로 안정성을 확보하기 어려웠던 점, 새 저장소에서 개발 기준을 재정립하며 개발을 다시 시작한 이유를 README 앞부분에 추가했다. 기존 기능의 전면 폐기나 기존 저장소/Render 연결 전환 완료로 표현하지 않는다.
- **README 목차 반영:** 사용자가 추가한 1~18번 목차를 확인하고 내용을 보존했다. Markdown 표시를 위한 빈 줄만 보완하여 새 저장소에 반영한다.
- **목차 숫자 표시 수정:** GitHub에서 목차 번호가 중첩 번호 목록으로 해석되어 로마 숫자로 보이는 현상을 방지하기 위해 마침표를 Markdown 이스케이프했다. 목차 번호는 `01`~`18` 그대로 표시되도록 하고 항목 제목과 본문은 유지했다.
- **0.1.9 Wheel 생성·검증 완료:** 앞서 로컬에 적용한 DB 조회 투영, 같은 세션의 결과 재사용, Preview 정리 조회 축소와 DB 조회 완료 후 LIVE 시각 판정을 포함하여 공통 패키지를 0.1.9로 생성했다. pyproject·패키지 버전, requirements Wheel/SHA 참조, Pi Adapter 버전 검사와 패키지 테스트 기준을 갱신했다. 22개 Canonical Python 모듈 및 내장 Source Manifest 일치 검증과 로컬 설치 후 관련 통합·패키지·A/B 회귀 테스트 220개 통과, 8개 건너뜀을 확인했다. 최종 Wheel SHA-256은 `497fc5542799e4bd33d0501fe32e8d91b61edd6a4acbf5267ec7baca78af8b0b`다. 기존 0.1.8 및 이전 Wheel은 보존했다. Pi·Render 배포, Git Push와 실제 장비 LIVE 안정성 검증은 이번 작업에서 수행하지 않았다. DB Schema·RLS·MQTT 규격·Raw 원본·분석 기준 변경은 없다.
