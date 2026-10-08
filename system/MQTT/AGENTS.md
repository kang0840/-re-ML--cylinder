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

Sensor Topic은 `smart-cylinder/{cylinder_id}/sensor`이며 Pi Subscriber는 `smart-cylinder/+/sensor`로 여섯 sensor Topic을 구독한다. 허용 cylinder_id는 `cylinder_01`~`cylinder_06`이고 Pico의 `pico01`~`pico06`과 같은 번호로 일대일 매핑된다. client_id는 Payload에 넣지 않는다.

Pico 메시지 최소 정보:

```text
cylinder_id
session_id
sequence_id
timestamp
SPH0645 데이터
INMP441 데이터
```

`sph0645`와 `inmp441`은 compact PCM chunk object다. 각 object는 `sample_rate`, `sample_format=s32le`, `sample_count`, `encoding=base64`, `data`를 포함한다. Parser는 SPH0645=4000 Hz, INMP441=16000 Hz, Base64·sample_count·byte length를 검증한 뒤 Pi signed PCM으로 복원한다. 전체 JSON integer array는 사용하지 않는다.

중복 기준은 `cylinder_id + session_id + sequence_id`이다.

timestamp는 NTP 동기화된 ISO 8601 `+09:00` 문자열이어야 하며 Pi Parser가 timezone과 허용 offset을 검증한다. 동기화되지 않은 Pico는 정상 센서 Payload를 Publish하지 않는다.

세 값이 모두 같은 QoS 1 재전송은 downstream으로 다시 전달하지 않는다.

Data worX A/B 공정 이벤트는 단일 Topic
`smart-cylinder/process/events`를 QoS 1, retain false로 사용한다.
`PROCESS_START`와 `PROCESS_JUDGMENT`는 `message_type`으로 구분하며,
중복 식별값은 `order_id + message_type`이다. Payload의 `event_id`는
`{order_id}:{message_type}` 형식으로 고정하고 Data worX는 같은 event_id를
새 설비 명령으로 다시 실행하지 않는다.

`PiMqttClient`는 Subscriber가 `enqueue_message`를 제공하면 Topic과 wire Payload를 해당 비동기 진입점에 전달한다. 기존 Subscriber의 동기 진입점은 호환 유지한다. Queue·분석 Worker와 자원 제한은 Backend Server Runtime 규칙을 따르며 MQTT 콜백에서 STFT나 저장을 직접 실행하지 않는다. QoS 1의 Broker 수신 확인과 Runtime Queue 수락·영구 저장 성공은 서로 다른 상태다.

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

현재 실행 기준은 상위 `system/AGENTS.md`의 사용자 결정을 따른다. Smart Cylinder Pico Monitor의 실제 수신 확인은 Sensor 메시지 수신 시각과 증가하는 sequence_id로 판단하며, retained `ok`만으로 현재 연결이나 수집 성공을 확정하지 않는다. 기존 read-only 진단 역할은 유지하고 학습 데이터 저장 완료로 보고하지 않는다.

## 보호 규칙
- QoS 1 변경 금지
- Topic/Payload 필드 임의 변경 금지
- Broker/Receiver/Publisher 하위 폴더 임의 생성 금지
- MQTTS/TLS는 현재 임의 적용하지 않는다.
- RMS/FFT/Cycle/DB 기능을 MQTT에 구현하지 않는다. Parser의 transport PCM 복원은 허용하지만 특징 계산은 Condition 책임이다.
- `pico_status_monitor.py`는 기존 Parser, Dedup, Condition Feature Extractor를 호출하는 read-only 진단 도구다. Sensor Topic과 `cylinder/status/+`의 retained `ok`/`failed` 상태를 구독하며, `pi-subscriber` 계정을 사용한다. Cycle 생성, DB 쓰기, Condition 변경, MQTT 제어 Publish를 수행하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR

## 세션 기반 Payload 규칙

필수 식별값은 `cylinder_id`, `session_id`, `sequence_id`, `timestamp`다. 중복 키는 `cylinder_id + session_id + sequence_id`이며 QoS 1, Topic, 센서 형식은 유지한다.
`<type>(mqtt): <변경 내용>`

Mosquitto에서 Pico 메시지를 받고 Data worX 통신과 충돌 없이 전달할 수 있어야 완료다.
