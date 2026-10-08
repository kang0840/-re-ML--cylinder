# pico/AGENTS.md

## 1. 폴더 개요

`pico/`는 Raspberry Pi Pico W에서 센서 데이터를 수집하고, Wi-Fi와 MQTT를 통해 Raspberry Pi 5로 전송하는 코드 영역이다.

Pico W는 **MQTT Client** 역할만 하며 MQTT Broker는 Raspberry Pi 5에서 실행한다.

---

## 2. 전체 흐름

```text
SPH0645 / INMP441
↓
sensor/
↓
timestamp/ + sequence_id/
↓
Message/
↓
Topic/ + QoS/
↓
MQTT/MQTT Client/
↓
Wi-Fi/
↓
Raspberry Pi 5 MQTT Broker
```

연결이 끊긴 경우:

```text
Wi-Fi 또는 MQTT 연결 끊김
↓
reconnect/
↓
연결 복구
↓
기존 전송 흐름 재개
```

---

## 3. 하위 폴더 역할

```text
Message/             → MQTT Payload 생성·검증
MQTT/                → Pico MQTT 공통 규칙
MQTT/MQTT Broker/    → Pi 5 Broker Host/Port 정보
MQTT/MQTT Client/    → Pico MQTT Client 연결·Publish
QoS/                 → QoS 1 규칙
reconnect/           → Wi-Fi/MQTT 재연결
sensor/              → SPH0645 / INMP441 Raw 데이터 수집
sequence_id/         → session_id 생성 및 sequence_id 생성·증가
timestamp/           → 인터넷 시간 동기화 및 timestamp 생성
Topic/               → MQTT Topic 규칙
Wi-Fi/               → 고정 Wi-Fi 최초 연결 및 상태 확인
```

`main.py`는 Pico 실행 조립 진입점이다. 외부에서 password, Pi Broker Host, UUID random-byte 함수를 받아 `client_id 확인 → cylinder_id 매핑 → Wi-Fi → NTP → MQTT 연결` 순서로 기존 모듈을 호출한다. import만으로 네트워크를 실행하지 않으며 센서 데이터를 생성·Publish하지 않는다. Wi-Fi 또는 NTP 실패 시 MQTT 연결을 진행하지 않는다.

세부 규칙은 각 하위 폴더의 `AGENTS.md`를 따른다.

---

## 4. 프로젝트 공통 규칙

### MQTT

```text
Pico W → Raspberry Pi 5
MQTT QoS = 1
```

Pico W는 Broker 서버를 실행하지 않는다.

MQTT Broker는 Raspberry Pi 5에서 실행한다.

### 메시지 최소 정보

```text
cylinder_id
session_id
sequence_id
timestamp
SPH0645 데이터
INMP441 데이터
```

Pi 5에서 중복 메시지는 다음 기준으로 판별한다.

```text
cylinder_id + session_id + sequence_id
```

같은 세 값이 다시 들어오면 QoS 1 재전송으로 분류하며 downstream 처리로 전달하지 않는다.

### Pico 연결 식별·인증

Pico MQTT Client는 `umqtt.simple.MQTTClient`를 사용한다. `client_id`와 `username`은 같은 고정 Pico ID이며 허용값은 `pico01`~`pico06`이다. password는 외부 주입값이며 문서·코드·로그에 평문으로 쓰지 않는다.

`client_id`는 재부팅 후에도 유지하는 장치 식별자다. `session_id`는 부팅마다 새 UUID를 생성하는 세션 식별자이며 Payload 및 중복 키에만 사용한다.

실제 6대 provisioning에서 논리 ID는 COM 포트가 아니라 `machine.unique_id()`의 hex 값으로 확인한다. 장치 전용 `device_config`는 `PICO_ID`, 매핑된 `CYLINDER_ID`, `EXPECTED_UID`만 가지며 Wi-Fi/MQTT Secret과 분리한다. Runtime은 UID 또는 Pico↔Cylinder mapping이 불일치하면 Wi-Fi, MQTT, Publish 전에 `DEVICE UID MISMATCH`로 중단한다. device-local 설정 및 Secret 파일은 Git에 저장하지 않는다.

고정 장치·실린더 매핑은 `pico01` → `cylinder_01`부터 `pico06` → `cylinder_06`까지의 일대일 관계다. Sensor Topic은 `smart-cylinder/{cylinder_id}/sensor`이며 client_id는 Payload에 넣지 않는다.

timestamp는 NTP 동기화 후 ISO 8601 `+09:00` 형식으로 만든다. 동기화 전에는 정상 센서 Payload를 Publish하지 않으며, 이미 동기화된 시간 상태는 Wi-Fi/MQTT 재연결에서 유지한다.

### 센서

```text
SPH0645
INMP441
SPH0645 acquisition rate = 16000 Hz
SPH0645 analysis rate = 4000 Hz after future anti-alias low-pass and 4:1 downsampling
SPH0645 target frequency = 2~1000 Hz
INMP441 acquisition rate = 16000 Hz
INMP441 analysis rate = 16000 Hz
INMP441 leakage feature band = experiment data after confirmation
```

`sensor/i2s_microphones.py`는 SPH0645(I2S0, GPIO16/17/18)와 INMP441(I2S1, GPIO10/11/12)을 각각 32-bit MONO RX, 16000 Hz, `ibuf=8192`로 초기화한다. 각 센서의 4096-byte read buffer만 재사용하며 전체 Raw 데이터를 RAM에 누적하지 않는다. I2S 모듈 자체에는 filtering, downsampling, MQTT, Cycle 및 분석을 넣지 않는다.

`sensor/pcm_decoder.py`는 RP2 I2S MONO RX의 little-endian 32-bit container를 signed 24-bit PCM으로 stream decode한다. Raw 32-bit container의 하위 8 bit padding을 제외하며, SPH0645의 18-bit precision은 signed 24-bit 결과의 하위 6 bit가 0인 상태로 보존한다. PCM decoder는 I2S 초기화·MQTT·filtering·downsampling을 수행하지 않는다.

`sensor/sph0645_decimator.py`는 고정 Q15 63-tap Hamming FIR 상태와 4:1 decimation phase를 chunk 경계에서도 유지한다. SPH0645만 16000 Hz PCM에서 4000 Hz PCM으로 변환하며, Pico에서 FFT/RMS는 수행하지 않는다. INMP441은 16000 Hz PCM을 유지한다.

새 logical MQTT message는 약 64 ms chunk를 사용한다. `sph0645`와 `inmp441`은 각각 `sample_rate`, `sample_format=s32le`, `sample_count`, `encoding=base64`, `data`를 가진 compact PCM chunk object다. JSON integer array·Pico 전체 Cycle Raw 저장은 금지한다.

### Wi-Fi

Pico W의 고정 SSID:

```text
DESKTOP-S9R9HQ2 5984
```

다른 SSID로 자동 전환하지 않는다.

비밀번호는 외부에서 주입받으며 `AGENTS.md`, Git 추적 파일, 로그에는 평문으로 기록하지 않는다. 이번 단계에서 Secret 저장 파일을 만들지 않는다.

---

## 5. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico"
```

Black 적용:

```powershell
python -m black .
```

Black 검사:

```powershell
python -m black --check .
```

Python 문법 검사:

```powershell
python -m compileall .
```

`compileall`은 PC Python 문법 검사이며 MicroPython 하드웨어 동작을 보장하지 않는다.

Pico W, I2S 센서, Wi-Fi, MQTT 관련 기능은 실제 하드웨어 검증이 필요하다.

---

## 6. 코드 스타일

Python/MicroPython 포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

하위 폴더별 역할을 섞지 않는다.

예:

```text
sensor/에서 MQTT Publish 구현 금지
QoS/에서 Topic 생성 금지
Topic/에서 Payload 생성 금지
Wi-Fi/에서 MQTT Publish 구현 금지
```

---

## 7. 파일·폴더 변경 규칙

사용자 승인 없이 다음 행동을 하지 않는다.

- 새 파일 생성
- 새 폴더 생성
- 기존 파일 삭제
- 기존 폴더 삭제
- 파일·폴더 이동
- 파일·폴더 이름 변경
- 임의의 `utils/`, `helpers/`, `config/` 생성
- 임의의 `main.py`, `config.py`, `secrets.py` 생성

새 파일이나 폴더가 필요하면 먼저 다음을 사용자에게 설명한다.

```text
새 파일/폴더:
생성 위치:
필요한 이유:
기존 구조로 해결할 수 없는 이유:
영향받는 파일/폴더:
```

사용자 승인 후에만 생성한다.

---

## 8. 금지 사항

사용자 승인 없이 다음을 변경하지 않는다.

- MQTT QoS 1
- Broker 역할 구조
- Message 필드 구조
- Topic 규칙
- `sequence_id` 규칙
- timestamp 규칙
- I2S acquisition rate 16000 Hz
- SPH0645 analysis rate 4000 Hz and target frequency 2~1000 Hz
- INMP441 analysis rate 16000 Hz; leakage feature band remains unconfirmed
- SPH0645 / INMP441 역할
- 고정 Wi-Fi SSID
- 재연결 정책의 미확정 값

Pico W에서 다음 기능을 구현하지 않는다.

- RMS 계산
- FFT 계산
- NORMAL/ABNORMAL 판별
- DB 저장
- Raspberry Pi 5 Broker 서버 실행

---

## 9. 커밋·PR 규칙

커밋 메시지:

```text
<type>(pico): <변경 내용>
```

하위 기능이 명확하면 해당 scope를 사용한다.

예:

```text
feat(sensor): add i2s sample collection
fix(mqtt-client): handle publish failure
docs(wifi): define fixed ssid rule
```

허용 type:

```text
feat
fix
refactor
test
docs
chore
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] 각 기능이 담당 폴더에 위치
- [ ] MQTT QoS 1 유지
- [ ] Pico W가 MQTT Client 역할만 수행
- [ ] Pi 5가 Broker 역할을 유지
- [ ] Message 최소 필드 유지
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] 비밀번호·Secret·Token 노출 없음
- [ ] 규칙 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 10. 완료 기준

## 세션 기반 메시지 규칙

Pico 부팅마다 새 `session_id`를 만들고 같은 부팅 세션에서는 유지한다. `sequence_id`는 새 논리 메시지에서 1부터 증가하며 QoS 1 재전송에서는 기존 serialized Payload와 ID를 유지한다. 중복 키는 `cylinder_id + session_id + sequence_id`이며, 재연결은 session/sequence 상태를 초기화하지 않는다.

다음 조건을 모두 만족해야 완료로 판단한다.

1. Black 검사 성공
2. Python 문법 검사 성공
3. Pico W에서 센서 Raw 데이터 수집 가능
4. 고정 Wi-Fi에 연결 가능
5. Raspberry Pi 5 MQTT Broker 연결 가능
6. QoS 1 Publish 가능
7. Message에 필수 정보 포함
8. 하위 폴더 역할 분리 유지
9. 사용자 승인 없는 구조 변경 없음
10. 실제 하드웨어에서 확인하지 못한 항목은 `미검증`으로 보고

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
