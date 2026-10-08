# MQTT Broker/AGENTS.md

## 1. 폴더 개요

`pico/MQTT/MQTT Broker/`는 Pico W가 접속할 **Raspberry Pi 5 MQTT Broker의 연결 대상 정보**만 관리한다.

Pico W에서 Broker 서버를 실행하지 않는다. 실제 MQTT Broker는 Raspberry Pi 5에서 실행하며, 이 폴더는 Host, Port 등 Pico가 접속에 필요한 정보만 다룬다.

---

## 2. 담당 범위

이 폴더에서 다루는 값:

```text
broker_host
broker_port
TLS 사용 여부(추후 확정)
```

현재 구조:

```text
Pico W
↓ MQTT Client
Raspberry Pi 5 MQTT Broker
```

현재 개발 단계의 기본 MQTT Port는 `1883`을 사용한다.

실제 Raspberry Pi 5 IP 주소는 환경에 따라 달라질 수 있으므로 AGENTS.md에 고정값으로 적지 않는다.

---

## 3. 파일 생성 규칙

현재 이 폴더에서 확정된 파일은 다음 하나뿐이다.

```text
MQTT Broker/
└─ AGENTS.md
```

사용자 승인 없이 다음을 만들지 않는다.

- `config.py`
- `broker.py`
- `mosquitto.py`
- `settings.py`
- 기타 Python 파일
- 새 하위 폴더

실제 Broker 설정값을 저장할 파일이 필요해지면 먼저 사용자에게 아래 내용을 확인한다.

```text
만들 파일:
필요한 이유:
저장할 값:
다른 폴더에 미치는 영향:
```

사용자 승인 후에만 새 파일을 만든다.

---

## 4. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\MQTT\MQTT Broker"
```

Python 버전 확인:

```powershell
python --version
```

Black 검사:

```powershell
python -m black --check .
```

Python 문법 검사:

```powershell
python -m compileall .
```

현재 실행 진입 파일은 확정되지 않았으므로 임의의 실행 명령이나 `main.py`를 만들지 않는다.

실제 설정 파일이 확정되면 복사 실행 가능한 검증 명령을 이 문서에 추가한다.

---

## 5. 코드 스타일

Python 또는 MicroPython 파일이 추가될 경우 포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
broker_host = "..."
broker_port = 1883

DEFAULT_MQTT_PORT = 1883
```

Broker 주소를 사용하는 코드와 실제 MQTT Client 연결·Publish 로직을 한곳에 섞지 않는다.

실제 Client 연결과 Publish는 `../MQTT Client/`의 책임이다.

---

## 6. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- Pico W에서 MQTT Broker 서버 실행
- Pico W에 Mosquitto Broker 설치·실행 코드 작성
- Raspberry Pi 5의 Broker 설정 직접 변경
- Broker Host 임의 변경
- Broker Port 임의 변경
- QoS 규칙 변경
- Topic 규칙 변경
- Payload 구조 변경
- MQTT Client Publish 로직 추가
- Wi-Fi 연결 로직 추가
- 재연결 로직 추가
- 새 파일·폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- IP 주소, 비밀번호, Secret, Token을 코드에 임의 하드코딩

Broker 연결 정보 변경이 필요하면 Raspberry Pi 5의 MQTT 설정과 Pico W MQTT Client에 미치는 영향을 먼저 확인한다.

---

## 7. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(mqtt-broker): <변경 내용>
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
docs(mqtt-broker): define pico broker target rules
fix(mqtt-broker): correct broker port configuration
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] Pico W에서 Broker 서버를 실행하는 코드가 없음
- [ ] 실제 Broker 역할이 Raspberry Pi 5에 유지됨
- [ ] Broker Host/Port를 사용자 승인 없이 변경하지 않음
- [ ] MQTT Client 로직이 이 폴더에 섞이지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] 민감정보가 코드나 로그에 노출되지 않음
- [ ] 연결 규격이 바뀌었다면 관련 AGENTS.md도 같은 PR에서 수정

---

## 8. 완료 기준

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. Pico W가 Broker 역할이 아니라 MQTT Client 역할만 유지
4. MQTT Broker가 Raspberry Pi 5에서 실행되는 구조 유지
5. Broker Host/Port 설정이 현재 프로젝트 규격과 일치
6. MQTT Client, QoS, Topic 등 다른 폴더 역할이 섞이지 않음
7. 사용자 승인 없는 새 파일·폴더 생성 없음
8. 수행하지 않은 실제 연결 검증은 `미검증`으로 명시

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
