# MQTT/AGENTS.md

## 역할
Raspberry Pi 5의 MQTT 통신을 하나의 폴더에서 관리한다. Broker/Receiver 등으로 추가 분리하지 않는다.

Broker 프로그램은 **Mosquitto**를 사용한다.

확정 통신:

```text
Pico W → Pi 5 Mosquitto
QoS 1

Pi 5 ↔ Data worX
MQTT QoS 1
```

Pico W는 Client, Pi 5는 Broker이다.

Pico는 Pi LAN IP의 `1883` 포트에 연결하며 `localhost`/`127.0.0.1`을 사용하지 않는다. Pi 내부 paho-mqtt Subscriber는 `127.0.0.1:1883`에 연결한다.

Pico 메시지 최소 정보:

```text
cylinder_id
session_id
sequence_id
timestamp
SPH0645 데이터
INMP441 데이터
```

중복 기준은 `cylinder_id + session_id + sequence_id`이다.

세 값이 모두 같은 QoS 1 재전송은 downstream으로 다시 전달하지 않는다.

## 연결 식별 및 인증

- Pico client_id와 username은 같은 고정 ID `pico01`~`pico06` 중 하나다.
- Pico password는 외부 주입값이며 평문을 코드, Git, 문서, 로그, Payload, 예외에 기록하지 않는다.
- Pi Subscriber는 Pico 계정을 재사용하지 않고 `pi-subscriber` client_id/username과 외부 주입 password를 사용한다.
- Pi Subscriber 연결 순서는 `username_pw_set()` → `connect()` → `subscribe()`다.
- 실제 Pi 적용 시 Mosquitto는 `allow_anonymous false`와 password file 또는 해당 버전의 인증 방식을 사용한다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\MQTT"
python -m black --check .
python -m compileall .
```

실제 Mosquitto 서비스 점검은 Raspberry Pi 5 환경에서 수행한다.

## 보호 규칙
- QoS 1 변경 금지
- Topic/Payload 필드 임의 변경 금지
- Broker/Receiver/Publisher 하위 폴더 임의 생성 금지
- MQTTS/TLS는 현재 임의 적용하지 않는다.
- RMS/FFT/Cycle/DB 기능을 MQTT에 구현하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR

## 세션 기반 Payload 규칙

필수 식별값은 `cylinder_id`, `session_id`, `sequence_id`, `timestamp`다. 중복 키는 `cylinder_id + session_id + sequence_id`이며 QoS 1, Topic, 센서 형식은 유지한다.
`<type>(mqtt): <변경 내용>`

Mosquitto에서 Pico 메시지를 받고 Data worX 통신과 충돌 없이 전달할 수 있어야 완료다.
