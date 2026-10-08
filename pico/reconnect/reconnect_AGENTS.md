# reconnect/AGENTS.md

## 1. 폴더 개요

`pico/reconnect/`는 Pico W의 **Wi-Fi 및 MQTT 연결이 끊겼을 때 다시 연결하는 처리**만 담당한다.

Wi-Fi 최초 연결, MQTT Publish, Topic, QoS, Payload 생성, 센서 수집은 각 담당 폴더에서 처리하며 이 폴더에서는 재연결 흐름만 관리한다.

---

## 2. 재연결 규칙

기본 흐름은 다음과 같다.

```text
연결 상태 확인
↓
연결 끊김 감지
↓
재연결 시도
↓
연결 성공 확인
↓
기존 동작 재개
```

Wi-Fi가 끊긴 경우:

```text
Wi-Fi 연결 복구
↓
MQTT Broker 연결 상태 확인
↓
필요하면 MQTT 재연결
```

MQTT만 끊긴 경우:

```text
Wi-Fi 연결 상태 확인
↓
MQTT Broker 재연결
↓
Publish 재개
```

Wi-Fi/MQTT 재연결은 기존 Pico 장치 `client_id`와 현재 부팅 `session_id`를 재사용한다. `sequence_id`를 초기화하거나 재전송용 새 ID를 만들지 않으며, QoS 1 재전송은 기존 serialized Payload를 사용한다. 새 session_id는 Pico 재부팅/전원 재인가 때만 만든다.

재연결 실패 시 CPU를 과도하게 사용하는 무한 반복을 만들지 않는다.

재시도 간격, 최대 재시도 횟수, Backoff 방식은 아직 확정되지 않았으므로 임의의 최종값으로 고정하지 않는다.

---

## 3. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\reconnect"
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

현재 독립 실행 파일은 확정되지 않았다.

사용자 승인 없이 `main.py`, `reconnect.py` 같은 파일을 새로 만들거나 존재하지 않는 실행 명령을 작성하지 않는다.

---

## 4. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
def reconnect_wifi():
    pass


def reconnect_mqtt():
    pass
```

패턴 규칙:

- Wi-Fi 재연결과 MQTT 재연결을 구분한다.
- 실패 이유를 확인할 수 있게 처리한다.
- 재연결 루프에서 불필요한 Busy Loop를 만들지 않는다.
- 연결 복구 후 기존 통신 흐름으로 정상 복귀할 수 있어야 한다.
- 실제 Wi-Fi 설정은 `../Wi-Fi/`의 규칙을 따른다.
- MQTT 연결 방식은 `../MQTT/MQTT Client/`의 규칙을 따른다.

---

## 5. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- Wi-Fi SSID/비밀번호 규칙 변경
- Broker Host/Port 변경
- MQTT QoS 1 변경
- Topic 규칙 변경
- Payload 구조 변경
- `sequence_id` 규칙 변경
- `timestamp` 규칙 변경
- 센서 수집 코드 추가
- RMS·FFT 계산
- NORMAL/ABNORMAL 판별
- 재시도 간격·횟수·Backoff 값을 임의 확정
- Secret Key, 비밀번호, Token 하드코딩

새 파일이나 재연결 정책 변경이 필요하면 먼저 사용자에게 이유와 영향 범위를 설명하고 승인을 받는다.

---

## 6. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(reconnect): <변경 내용>
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
feat(reconnect): restore mqtt connection after disconnect
fix(reconnect): avoid busy reconnect loop
docs(reconnect): update reconnect rules
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] Wi-Fi 끊김 감지 가능
- [ ] Wi-Fi 복구 후 MQTT 연결 상태 확인
- [ ] MQTT 끊김 후 재연결 가능
- [ ] 재연결 실패 시 Busy Loop가 발생하지 않음
- [ ] 다른 폴더의 설정 규칙을 임의 변경하지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] 재연결 정책 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 7. 완료 기준

## 세션 유지 규칙

Wi-Fi 및 MQTT 재연결은 기존 `session_id`와 sequence 상태를 재사용한다. 해당 상태는 Pico 재부팅/전원 재인가 때만 새로 만든다.

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. Wi-Fi 연결이 끊긴 뒤 다시 연결 가능
4. MQTT 연결이 끊긴 뒤 다시 연결 가능
5. Wi-Fi 복구 후 필요한 경우 MQTT 연결도 복구
6. 연결 복구 후 센서 전송 흐름이 다시 동작
7. 재연결 실패 상태에서 CPU를 과도하게 점유하지 않음
8. 사용자 승인 없는 새 파일·폴더 생성 없음
9. 실제 Pico W에서 확인하지 못한 항목은 `미검증`으로 보고

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
