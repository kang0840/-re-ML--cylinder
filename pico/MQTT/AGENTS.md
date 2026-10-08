# MQTT AGENTS.md

## 1. 프로젝트 개요

이 폴더는 Pico W의 MQTT 공통 연결 규칙을 담당한다. Pico W는 MQTT Broker를 실행하지 않고 Raspberry Pi 5의 Mosquitto Broker에 MQTT QoS 1로 Publish한다.

---

## 2. 고정 파일 구조

`pico/MQTT/`에서는 기존 승인 파일과 폴더 구조를 사용한다.

```text
MQTT/
├─ MQTT Broker/  → Raspberry Pi 5 Broker Host/Port 정보
├─ MQTT Client/  → Pico MQTT Client 연결·Publish
└─ AGENTS.md
```

역할:

- `MQTT Client/client.py`: `umqtt.simple.MQTTClient` 기반 Pi Broker 연결·QoS 1 Publish
- `MQTT Broker/`: Pico가 접속할 Pi LAN Host/Port 규칙

### 파일 생성 규칙

위 목록에 없는 파일이나 하위 폴더를 임의로 만들지 않는다.

새 파일이 필요하다고 판단해도 먼저 기존 파일 안에서 해결 가능한지 확인한다. 기존 구조로 해결할 수 없다면 작업을 멈추고 사용자에게 아래 내용을 먼저 묻는다.

```text
새로 만들려는 파일:
필요한 이유:
기존 파일에 넣을 수 없는 이유:
영향받는 파일:
```

사용자의 명시적 승인 전에는 새 파일·새 폴더를 만들지 않는다.

기존 파일의 삭제, 이동, 이름 변경, 자동 분리도 사용자 승인 없이 하지 않는다.

---

## 3. MQTT 메시지 규칙

Pico W → Raspberry Pi 5는 MQTT QoS 1을 사용한다.

센서 메시지에는 최소한 다음 정보가 포함되어야 한다.

```text
cylinder_id
session_id
sequence_id
timestamp
SPH0645 데이터
INMP441 데이터
```

실제 필드명과 Payload 구조는 현재 프로젝트 코드의 규격을 따른다. 기존 Topic, Payload 구조, QoS를 임의로 변경하지 않는다.

### 중복 처리

중복 판단 키:

```text
cylinder_id + session_id + sequence_id
```

세 값이 모두 같은 재수신은 QoS 1 재전송이며 Pi downstream 처리로 다시 전달하지 않는다.

### Pico Broker 및 인증

- Broker는 Raspberry Pi 5 Mosquitto이며 Pico는 `<PI_LAN_IP>:1883`에 접속한다.
- Pico에서 `localhost`와 `127.0.0.1`은 Broker 주소로 사용하지 않는다.
- `client_id`와 `username`은 동일한 고정 장치 ID(`pico01`~`pico06`)다.
- 장치·실린더 매핑은 `pico01` → `cylinder_01`부터 `pico06` → `cylinder_06`까지 일대일이다. client_id와 cylinder_id는 같은 값이 아니다.
- Sensor Topic은 `smart-cylinder/{cylinder_id}/sensor`이며, Publish Topic과 Payload cylinder_id는 같은 매핑이어야 한다.
- password는 외부에서 주입하며 평문을 문서, 코드, 로그에 기록하지 않는다.

---

## 4. 실행·검증 명령

PowerShell 기준이다.

MQTT 폴더 이동:

```powershell
cd "C:\Smart Cylinder Case\pico\MQTT"
```

Python 확인:

```powershell
python --version
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

Pico MQTT Client는 MicroPython의 `umqtt.simple`을 사용한다. paho-mqtt Subscriber 실행은 `system/MQTT/`의 Raspberry Pi 5 책임이며 이 폴더에서 실행하지 않는다.

실제 Pico 실행 진입점은 아직 확정되지 않았으므로 PC에서는 문법·Mock 검증만 수행한다.

---

## 5. 코드 스타일·네이밍·패턴

Python 포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
cylinder_id = "cylinder_01"
MQTT_QOS = 1

def parse_message():
    pass

class MQTTClient:
    pass
```

패턴 규칙:

- MQTT Callback 안에서 FFT, DB 저장, ML 판별 같은 무거운 작업을 직접 실행하지 않는다.
- 연결, 수신, 파싱, 중복 확인, 발행 역할을 가능한 한 기존 고정 파일 역할에 맞게 분리한다.
- 연결이 끊기면 프로그램 전체를 즉시 종료하지 말고 재연결을 시도한다.
- 재연결 성공 후 필요한 Topic을 다시 구독한다.
- 예외를 무조건 숨기지 말고 원인을 확인할 수 있게 로그를 남긴다.
- 비밀번호, Secret Key, Token은 코드나 로그에 직접 남기지 않는다.

---

## 6. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- 허용 목록 밖 파일 생성
- `pico/MQTT/` 내부 새 하위 폴더 생성
- 기존 파일 삭제·이동·이름 변경
- 리팩터링을 이유로 파일 임의 분리
- MQTT Topic 임의 변경
- Payload 구조 임의 변경
- QoS 임의 변경
- `cylinder_id`, `sequence_id`, `timestamp` 규칙 임의 변경
- Pico W와 호환되지 않는 MQTT 변경
- `../../system/`, `../Message/`, `../sequence_id/`, `../reconnect/` 임의 수정
- DB 스키마 변경
- RMS·FFT·NORMAL/ABNORMAL 판별 기준 변경
- Secret Key, 비밀번호, Token 하드코딩

MQTT 규격 변경이 반드시 필요하면 Pico W 발행 코드와 Pi 5 구독 코드에 미치는 영향을 먼저 확인하고 사용자에게 승인받는다.

---

## 7. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(mqtt): <변경 내용>
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

예:

```text
feat(mqtt): add pico sensor subscriber
fix(mqtt): suppress duplicate downstream delivery
fix(mqtt): restore subscription after reconnect
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] Pico W 메시지 QoS 1 Publish 확인
- [ ] 필수 Payload 필드 확인
- [ ] 동일 `cylinder_id + session_id + sequence_id` 재전송에서 sequence_id와 serialized Payload가 유지되는지 확인
- [ ] Broker 연결 끊김 후 재연결 확인
- [ ] 재연결 후 Topic 재구독 확인
- [ ] 잘못된 메시지 1개 때문에 Subscriber 전체가 종료되지 않는지 확인
- [ ] 허용 목록 밖 파일·폴더가 생성되지 않았는지 확인
- [ ] 담당 범위 밖 파일을 임의 수정하지 않았는지 확인
- [ ] 코드 구조·명령이 바뀌었다면 AGENTS.md도 같은 PR에서 수정

---

## 8. 완료 기준

## 세션 중복 규칙

Pico와 Pi의 중복 키는 `cylinder_id + session_id + sequence_id`다. Pico 재연결은 session을 유지하고 재부팅은 새 session을 만든다.

다음 조건을 모두 만족해야 작업을 완료한 것으로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. Pico W의 MQTT QoS 1 메시지를 Pi 5 Broker로 Publish
4. `cylinder_id`, `session_id`, `sequence_id`, `timestamp`, SPH0645, INMP441 데이터 확인
5. QoS 1 재전송 시 기존 serialized Payload와 identity를 유지
6. Pico가 Pi LAN IP Broker에 인증하여 연결
7. Broker 재연결 후 Topic 재구독 및 메시지 수신 재개
8. 잘못된 메시지가 들어와도 Subscriber 전체가 종료되지 않음
9. 사용자 승인 없는 새 파일·폴더 생성 없음
10. 기존 MQTT 기능과 Pico W 호환성이 깨지지 않음

검증하지 못한 항목은 완료했다고 쓰지 말고 `미검증`으로 보고한다.

작업 완료 보고에는 최소한 다음을 포함한다.

```text
수정한 파일:
추가/수정한 기능:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
