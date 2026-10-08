# MQTT Client/AGENTS.md

## 1. 폴더 개요

`pico/MQTT/MQTT Client/`는 Raspberry Pi Pico W의 **MQTT Client 연결과 Publish**를 담당한다.

Pico W는 Raspberry Pi 5에서 실행되는 MQTT Broker에 연결하고, `Message/`에서 만들어진 센서 Payload를 지정된 Topic으로 MQTT QoS 1 방식으로 전송한다.

---

## 2. 담당 범위

이 폴더의 역할은 다음으로 제한한다.

- MQTT Client 생성
- Raspberry Pi 5 MQTT Broker 연결
- 연결 상태 확인
- MQTT Publish
- Publish 성공·실패 처리
- 연결 끊김 감지
- 재연결 기능 호출

관련 기능의 담당 폴더:

```text
../MQTT Broker/  → Broker Host / Port 정보
../../Message/   → Payload 생성·검증
../../Topic/     → Topic 규칙
../../QoS/       → QoS 1 규칙
../../reconnect/ → 실제 재연결 정책
```

MQTT Client에서 센서 데이터를 직접 만들거나 분석하지 않는다.

---

## 3. 통신 규칙

기본 통신 구조:

```text
Pico W MQTT Client
        ↓
MQTT QoS 1 Publish
        ↓
Raspberry Pi 5 MQTT Broker
```

Publish할 메시지는 프로젝트에서 확정된 다음 정보를 포함해야 한다.

```text
cylinder_id
session_id
sequence_id
timestamp
SPH0645 데이터
INMP441 데이터
```

Broker 주소, Topic, QoS, Payload 구조를 이 폴더에서 임의로 변경하지 않는다.

### 연결·인증 계약

- MicroPython `umqtt.simple.MQTTClient`를 사용한다.
- `broker_host`는 Raspberry Pi 5 LAN IP를 외부에서 받고 기본 `broker_port`는 `1883`이다.
- Pico에서 `localhost`와 `127.0.0.1`은 Broker Host로 금지한다.
- `client_id`와 `username`은 동일한 고정 Pico ID이며 `pico01`~`pico06`만 허용한다.
- client_id는 각각 같은 번호의 cylinder_id에만 연결한다. 예: `pico01`은 `cylinder_01`이며 Publish Topic은 `smart-cylinder/cylinder_01/sensor`다.
- Publisher는 Topic, payload cylinder_id, client_id 매핑이 일치하지 않으면 Publish 전에 거부한다.
- password는 외부 주입값이며 어떤 문서, 코드, 로그, 예외에도 평문으로 쓰지 않는다.
- 새 정상 센서 Payload는 주입된 `TimestampProvider.time_synced=True` 상태에서만 Publish한다. NTP 동기화 전에는 Publish를 거부하며, QoS 1 재전송은 기존 serialized Payload 규칙을 유지한다.

---

## 4. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\MQTT\MQTT Client"
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

구현 모듈은 `client.py`이다. 다만 실제 Pico 실행 진입점과 Wi-Fi·MQTT 연결 조립 방식은 아직 확정되지 않았다.

따라서 사용자 승인 없이 `main.py`, `client.py` 같은 파일을 새로 만들거나 존재하지 않는 파일의 실행 명령을 문서에 추가하지 않는다.

실제 실행 파일이 확정되면 이 문서에 복사 실행 가능한 명령을 추가한다.

---

## 5. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
MQTT_QOS = 1


def connect_client():
    pass


def publish_message():
    pass
```

패턴 규칙:

- 연결과 Publish 역할을 명확하게 분리한다.
- MQTT Callback 또는 Publish 함수 안에 센서 분석 코드를 넣지 않는다.
- 연결 실패와 Publish 실패를 구분해서 처리한다.
- 재연결이 필요하면 `../../reconnect/`의 규칙을 따른다.
- 비밀번호, Secret, Token을 로그에 출력하지 않는다.

---

## 6. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- Pico W에서 MQTT Broker 서버 실행
- Broker Host / Port 임의 변경
- QoS 1 변경
- Topic 규칙 변경
- Payload 구조 변경
- `sequence_id` 생성 규칙 변경
- `timestamp` 생성 규칙 변경
- Wi-Fi 연결 정책 변경
- 재연결 정책을 이 폴더에 중복 구현
- 센서 직접 읽기
- RMS·FFT 계산
- NORMAL/ABNORMAL 판별
- DB 저장
- Secret Key, 비밀번호, Token 하드코딩

새 파일이 필요하면 먼저 다음을 사용자에게 확인한다.

```text
새 파일:
필요한 이유:
기존 구조로 해결할 수 없는 이유:
영향받는 MQTT 기능:
```

---

## 7. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(mqtt-client): <변경 내용>
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
feat(mqtt-client): publish sensor payload with qos1
fix(mqtt-client): handle publish failure
docs(mqtt-client): update client rules
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] Raspberry Pi 5 Broker 연결 확인
- [ ] MQTT QoS 1 Publish 확인
- [ ] Pi 5에서 메시지 수신 확인
- [ ] Broker Host / Port 규격 유지
- [ ] Topic / Payload 규격 유지
- [ ] 재연결 역할이 `reconnect/`와 충돌하지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] 민감정보가 코드나 로그에 노출되지 않음
- [ ] 통신 규격 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 8. 완료 기준

## 세션 Publish 규칙

QoS 1 재전송은 같은 논리 메시지의 `session_id`와 `sequence_id` 및 serialized Payload를 유지한다. 새 논리 메시지에서만 다음 sequence를 할당한다.

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. Pico W가 Raspberry Pi 5 MQTT Broker에 연결됨
4. MQTT QoS 1로 Publish 성공
5. Pi 5에서 해당 메시지 수신 확인
6. 기존 Broker / Topic / Payload 규격 유지
7. Publish 실패 시 프로그램이 이유 없이 전체 종료되지 않음
8. 재연결 관련 처리가 `reconnect/` 규칙과 충돌하지 않음
9. 사용자 승인 없는 새 파일·폴더 생성 없음
10. 실제 Pico W 검증을 하지 못한 항목은 `미검증`으로 보고

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
