# system/AGENTS.md

## 프로젝트 개요
`system/`은 스마트 실린더 케이스의 메인 소프트웨어 영역이다.

```text
system/
├─ Backend/
│  ├─ API/
│  ├─ Service/
│  └─ Server/
├─ DB/
│  ├─ Supabase/
│  └─ PostgreSQL/
├─ Frontend/
├─ ML/
│  ├─ Condition/
│  └─ WeibullAFT/
├─ MQTT/
├─ Sensor/
├─ PLC/
├─ DataWorX/
└─ YOLO/
```

핵심 흐름:

```text
SPH0645 / INMP441
→ Pico W 01~06
→ MQTT QoS 1
→ Raspberry Pi 5 / Mosquitto
→ Sensor에서 Cycle 정보 결합
→ ML STFT 기반 실린더 동작음 검출
→ 검출된 동작 구간의 RMS + FFT 특징 분석
→ Feature Extraction / Saved Model ML Inference
→ Supabase PostgreSQL
→ Web 데이터 제공 계층
→ Render 공개 Web 진입점 https://ml-cylinder.onrender.com/
→ Data worX / 외부 Browser
```

학습 데이터 흐름:

```text
Pico W
→ MQTT
→ Raspberry Pi 5
→ Parser
→ PCM 복원
→ STFT 기반 실린더 동작음 검출
→ 검출된 동작 구간
→ Feature Extraction
→ Supabase
→ Training Dataset Load
→ Model Training
→ Saved Model
```

실시간 추론 데이터 흐름:

```text
Pico W
→ MQTT
→ Raspberry Pi 5
→ Parser
→ PCM 복원
→ STFT 기반 실린더 동작음 검출
→ 검출된 동작 구간
→ Feature Extraction
→ Saved Model
→ Prediction
→ Supabase
→ Web Dashboard
```

Supabase는 학습 데이터와 특징값을 저장하는 저장소이며 모델을 직접 학습하지 않는다. 실시간 추론은 Pi에서 특징값을 계산한 뒤 Saved Model을 바로 호출하며, 모델 입력을 위해 Supabase를 다시 조회하지 않는다.

`ML/`은 STFT 동작음 검출, Cycle 데이터 처리, RMS, FFT, 특징값, 정상 기준과 상태 판별을 담당한다. Sensor의 기존 Cycle 판별과 ML의 STFT 동작음 검출은 서로 다른 역할이며, STFT가 Cycle 시작·종료 판단을 대체하지 않는다.

Raspberry Pi 5는 MQTT, Sensor / Cycle, STFT, RMS / FFT, Feature Extraction, ML Inference와 주요 Edge Backend 처리를 실행하며 필요하면 Local Web / Backend를 실행할 수 있다. Render는 센서 신호처리나 ML 계산 위치가 아니라 외부 공개 Web 진입점이다. 기존 Render Backend / Frontend 자산은 유지하지만, Render와 Pi 사이의 Gateway·Relay·Supabase·Reverse 연결 중 최종 방식은 확정하지 않는다.

공장 내부의 `192.168.137.xxx` 주소는 Pico, Pi와 내부 장치 통신에만 사용한다. `https://ml-cylinder.onrender.com/`은 Data worX 및 외부 PC·노트북·휴대폰이 접근하는 공개 Web 주소이며 Pico MQTT Broker 주소로 사용하지 않는다. 하나의 공개 Web 서비스가 `pico01`~`pico06`의 상세 화면을 구분하고 각각 `cylinder_01`~`cylinder_06` 데이터만 조회한다. 최종 상세 Route는 실제 Frontend / Backend 구조 확인 전 확정하지 않는다.

Raspberry Pi 수집 프로그램은 `COLLECTION_MODE` 환경변수를 필수로 사용하며 허용값은 `TRAINING`, `OPERATION`, `TEST`다. 기본값은 두지 않는다. 이번 사용자 승인 실험의 임시 매핑은 `TRAINING`에서 `cylinder_01`을 `TRAINING_NORMAL / NORMAL`, `cylinder_02`를 `TRAINING_ABNORMAL / SEAL_LEAK`로 등록하며 Ground Truth source는 `MANUAL_EXPERIMENT`다. 실제 정상/씰 손상 실린더 장착 조건이 라벨의 근거이며 장치 ID 자체를 고장 판정으로 사용하지 않는다. 장치와 라벨의 상관관계는 `DEVICE_BIAS_RISK`이며 향후 교차 수집은 별도 실험으로 남긴다. `TEST`는 `TEST / NULL`, `OPERATION`은 `RAW_OPERATION / NULL`로 등록하며, 세션 의미는 `collection_sessions`에서 관리한다. 과거 세션의 라벨은 변경하지 않고 새 수집 세션을 사용한다. Pico Payload와 MQTT 규격에는 수집 모드를 추가하지 않는다.

현재 구현의 Frontend 실시간 갱신은 **Supabase Realtime 직접 연결**, 과거 데이터 조회는 Supabase 직접 SELECT를 사용하며 Frontend에는 공개 가능한 Key + RLS만 사용한다. 목표 구조에서 Pi는 필요한 데이터를 Supabase에 전송하고 Backend는 서버 전용 Secret만 보관한다. WebSocket / SSE / Supabase Realtime 중 최종 실시간 방식과 Render ↔ Pi 연결 방식은 아직 확정하지 않는다.

PLC/Data worX는 유지한다.

2026-10-07 사용자 승인 전환: 0.1.5 Pi 학습 실행기는 장치 ID, 실험 ID와 실제 장착 조건의 `NORMAL / SEAL_LEAK`를 선택하며 이 명시한 실험 설정은 위 장치별 임시 매핑보다 우선한다. 정상/비정상 원본은 모두 기존 `raw_data`에 저장하고 `collection_sessions`의 실험 라벨에 따라 전용 View로 조회한다. 전환 시 기존 수집을 종료하고 새 Pico 세션을 사용하며 과거 정상 데이터와 세션 라벨을 변경하지 않는다. 자세한 저장 보호와 실행기 규칙은 Backend Service/Server 및 DB 하위 규칙을 따른다.

```text
Raspberry Pi 5 ↔ MQTT QoS 1 ↔ Data worX ↔ PLC
```

A/B 공정 주문 테스트는 기존 Render 서비스가 Supabase의 `process_orders`와
`process_judgments`에 기록하고, Raspberry Pi 5의
`DataWorX/process_order_bridge.py`가 미전송 이벤트를 로컬 Mosquitto의
`smart-cylinder/process/events`로 QoS 1 Publish하는 중계 구조를 사용한다.
Browser는 MQTT에 직접 연결하지 않는다.

실린더 전진/후진/Cycle 판단은 PLC 신호가 아니라 HC-SR04 3개가 담당한다.

YOLO 개발 기능은 유지하지만 현재 발표 범위에서는 제외한다.

## 검증 명령
```powershell
cd "C:\Smart Cylinder Case\system"
python -m black --check .
python -m compileall .
```

Python은 Black을 사용한다. JavaScript에서 블록 스타일이 필요한 경우 Allman 스타일을 유지한다.

코드 스타일은 기존 naming을 유지하고 함수와 클래스의 책임을 분리한다. 불필요한 helper/utils 파일이나 하나의 작은 함수를 위한 폴더를 생성하지 않는다.

## 구조 변경 규칙
2026-10-08 후속 승인: 상태 판별·Weibull-AFT 선택적 Runtime 연결의 공통 패키지는 0.1.10이다. 이전 Wheel은 보존하고 GitHub 업로드와 Pi/Render 실제 설치를 구분한다. 기준·모델·실제 수명 데이터 없는 예측은 생성하지 않는다.

2026-10-08: DB 조회 투영·동일 세션 결과 재사용·Preview 정리 조회 축소와 DB 조회 완료 후 LIVE 시각 판정을 포함한 공통 배포 산출물은 0.1.9다. 기존 Wheel은 불변으로 보존하며 패키지 생성·로컬 설치 검증과 Pi/Render 실제 배포 완료를 구분한다.

2026-10-06 사용자 후속 결정: 실제 수집·분석 원본은 Canonical `system/`이며 `sensor_runtime.py`와 배포 Adapter `ML-cylinder/deploy/pi_sensor_runtime.py`를 사용한다. `token_main.py`는 수정·Import·기능 복사하지 않는 LEGACY / ROLLBACK ONLY다. Smart Cylinder Pico Monitor는 read-only 통신 확인용으로 유지한다. 파일 존재·Package 설치와 실제 Service 실행을 구분하고, Pi 전환 및 실제 Raw 저장·라벨 검증 전 본 수집 준비 완료로 보고하지 않는다.

공통 Python 코드의 유일한 개발 원본은 최상위 `system/`이다. `smart-cylinder-common` Wheel은 이 원본에서 자동 생성하는 버전 고정 배포 산출물이며 Render와 Pi는 동일 산출물을 사용한다. 개발 테스트는 원본을, 배포 테스트는 설치된 Wheel을 검증한다. `ML-cylinder/system/` 중복 패키지는 검증·승인 후 제거했으며, 공통 코드를 `ML-cylinder` 내부에 수동 복사하거나 별도 업무 구현·자동 Fallback을 추가하지 않는다. 설치 성공과 실제 import 경로·버전·내용 검증을 구분하며, 원본 변경 시 패키지 버전을 올리고 같은 버전의 Wheel을 다른 내용으로 덮어쓰지 않는다.

사용자 승인 없이 새 파일/폴더 생성, 삭제, 이동, 이름 변경을 하지 않는다.

새 구조가 필요하면 먼저 다음을 보고한다.

```text
새 파일/폴더:
생성 위치:
필요한 이유:
기존 구조로 해결할 수 없는 이유:
영향 범위:
```

## 금지
- MQTT QoS, Cycle 정의, DB 구조, ML 판별 방식 임의 변경 금지
- Secret/비밀번호/Token 평문 저장 금지
- 미확정 임계값/성능/모델 파라미터 임의 확정 금지
- 하위 폴더의 책임을 다른 폴더에 중복 구현하지 않기

## 커밋 / PR
```text
<type>(scope): <변경 내용>
```

허용 type: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

PR 전:
- Black / 문법 검사
- 관련 AGENTS.md 동시 갱신
- 민감정보 노출 확인
- 사용자 승인 없는 구조 변경 없음
- 실제 환경 미검증 항목은 `미검증`으로 명시
- 한 커밋은 하나의 논리적 변경 단위를 유지
- 관련 없는 파일 수정 금지
- PR에 변경 파일, 변경 이유, 테스트 결과와 영향 범위 기록

## 완료 기준
코드가 담당 폴더 역할을 지키고, 검증 명령이 통과하며, 실제 하드웨어/Render/Supabase에서 확인하지 못한 항목을 숨기지 않으면 완료로 본다.

실시간 ML 연결은 Syntax·Import, 기존 Parser·PCM·중복 제거, 11개 특징 계산, 저장된 feature name·order·input shape·scaler, 모델 3개 호출, Mock E2E와 Secret Scan을 검증하고 기존 MQTT·DB·Supabase 규격이 변경되지 않아야 완료로 본다. 테스트 실패 상태는 완료로 판단하지 않는다.
