# Wi-Fi/AGENTS.md

## 1. 폴더 개요

`pico/Wi-Fi/`는 Raspberry Pi Pico W의 **Wi-Fi 최초 연결과 연결 상태 확인**만 담당한다.

Pico W가 사용할 Wi-Fi SSID는 아래 값으로 고정한다.

```text
DESKTOP-S9R9HQ2 5984
```

Wi-Fi 비밀번호도 사용자가 지정한 고정값을 사용한다. 단, 비밀번호 원문은 `AGENTS.md`, Git 추적 파일, 로그에 평문으로 기록하지 않는다.

MQTT 연결·Publish, 재연결 정책, Topic, QoS, Payload, 센서 수집은 다른 폴더에서 담당한다.

---

## 2. Wi-Fi 고정 규칙

기본 연결 흐름:

```text
Pico W 시작
↓
DESKTOP-S9R9HQ2 5984 연결
↓
연결 성공 여부 확인
↓
MQTT 연결 단계로 이동
```

연결 실패 또는 연결 끊김:

```text
Wi-Fi 연결 실패 / 끊김
↓
../reconnect/
↓
DESKTOP-S9R9HQ2 5984로 재연결
↓
Wi-Fi 연결 성공 확인
↓
MQTT 연결 상태 확인
```

역할 분리:

```text
Wi-Fi/      → 최초 연결 및 연결 상태 확인
reconnect/  → 연결이 끊긴 뒤 같은 Wi-Fi로 재연결
MQTT/       → MQTT 통신
```

규칙:

- Wi-Fi SSID는 `DESKTOP-S9R9HQ2 5984`로 고정한다.
- 다른 SSID로 자동 전환하지 않는다.
- 사용자 승인 없이 SSID를 변경하지 않는다.
- Wi-Fi 연결 성공 전에 MQTT 연결을 시작하지 않는다.
- Wi-Fi 연결 코드는 password를 외부 인자 또는 생성자 인자로 주입받는다.
- 비밀번호 원문은 `AGENTS.md`, Git 추적 파일, 로그, 예외에 남기지 않는다.
- 이번 단계에서는 `secrets.py`, `.env`, `wifi_secret.py`, `config_secret.py` 같은 Secret 저장 파일을 만들지 않는다.

---

## 3. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\Wi-Fi"
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

`compileall`은 PC Python 문법 검사이며 Pico W의 실제 Wi-Fi 연결을 보장하지 않는다.

구현 모듈은 `wifi.py`다. `WiFiConnection(ssid, password, timeout_seconds=15)`는 외부 주입받은 단일 SSID/password만 사용하며 `CONNECTED` 또는 `FAILED`를 반환한다. `reconnect()`는 같은 설정을 재사용하고 다른 SSID 탐색·fallback을 수행하지 않는다.

현재 독립 실행 파일은 확정되지 않았다.

사용자 승인 없이 `main.py`, `wifi.py`, `secrets.py`, `config.py` 같은 파일을 새로 만들거나 존재하지 않는 실행 명령을 추가하지 않는다.

---

## 4. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
WIFI_SSID = "DESKTOP-S9R9HQ2 5984"


def connect_wifi():
    pass


def is_wifi_connected():
    pass
```

패턴 규칙:

- Wi-Fi 최초 연결과 재연결 로직을 섞지 않는다.
- 연결 함수 안에서 MQTT 연결이나 Publish를 직접 실행하지 않는다.
- 연결 실패 이유를 무조건 숨기지 않는다.
- 연결 상태를 다른 모듈이 확인할 수 있는 형태로 제공한다.
- 실제 비밀번호 값을 코드 예제나 로그에 출력하지 않는다.
- 다른 Wi-Fi로 자동 전환하는 로직을 추가하지 않는다.

---

## 5. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- SSID `DESKTOP-S9R9HQ2 5984` 변경
- 다른 SSID 자동 전환 기능 추가
- Wi-Fi 연결 우선순위 기능 추가
- 비밀번호 관리 방식 임의 변경
- 비밀번호를 `AGENTS.md`, Git 추적 파일, 로그에 평문으로 기록
- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- Wi-Fi 재연결 정책을 이 폴더에 중복 구현
- MQTT Broker/Client 연결 코드 추가
- Topic 규칙 변경
- QoS 1 변경
- Payload 구조 변경
- `sequence_id` 규칙 변경
- `timestamp` 규칙 변경
- 센서 수집 코드 추가
- RMS·FFT 계산
- NORMAL/ABNORMAL 판별
- DB 저장

Wi-Fi 설정 또는 비밀번호 저장 방식 변경이 필요하면 먼저 다음 내용을 사용자에게 확인한다.

```text
변경하려는 설정:
현재 방식:
변경하려는 방식:
필요한 이유:
reconnect/ 및 MQTT에 미치는 영향:
```

---

## 6. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(wifi): <변경 내용>
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
feat(wifi): connect pico to fixed wifi
fix(wifi): report connection failure
docs(wifi): define fixed ssid rule
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] Pico W가 `DESKTOP-S9R9HQ2 5984`에 연결됨
- [ ] 연결 성공·실패 상태 확인 가능
- [ ] MQTT 연결 전에 Wi-Fi 연결 성공 여부를 확인
- [ ] 연결 실패/끊김 시 `reconnect/`에서 같은 SSID로 재연결
- [ ] 다른 SSID 자동 전환 로직 없음
- [ ] 재연결 로직이 `../reconnect/`와 중복되지 않음
- [ ] 비밀번호가 코드·문서·로그에 평문으로 노출되지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] Wi-Fi 구조 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 7. 완료 기준

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. Pico W가 `DESKTOP-S9R9HQ2 5984`에 연결 가능
4. 연결 성공·실패 상태를 확인 가능
5. 다른 SSID로 자동 전환하지 않음
6. 연결이 끊기면 `reconnect/`가 같은 SSID로 재연결
7. MQTT 연결 전 Wi-Fi 연결 상태를 확인
8. 비밀번호 원문이 `AGENTS.md`, Git 추적 파일, 로그에 노출되지 않음
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
