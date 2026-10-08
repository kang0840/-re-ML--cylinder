# QoS/AGENTS.md

## 1. 폴더 개요

`pico/QoS/`는 Pico W → Raspberry Pi 5 MQTT 통신에서 사용할 **QoS 1 규칙**만 관리한다.

QoS 값을 결정하고 적용 범위를 정의하는 역할만 담당하며, Topic, Payload, Broker 연결, 재연결, 센서 수집 로직은 이 폴더에서 구현하지 않는다.

---

## 2. QoS 규칙

현재 프로젝트의 Pico W → Raspberry Pi 5 MQTT 전송은 다음으로 고정한다.

```text
QoS = 1
```

QoS 1은 메시지가 최소 한 번 전달되도록 하지만 같은 메시지가 다시 전달될 수 있다.

중복 메시지 판별은 QoS 폴더에서 처리하지 않는다.

중복 여부는 Pi 5 측에서 다음 기준으로 처리한다.

```text
cylinder_id + session_id + sequence_id
```

같은 `cylinder_id + session_id + sequence_id`가 다시 들어오면 QoS 1 재전송으로 처리하며 Pi downstream에는 다시 전달하지 않는다.

`sequence_id` 생성 규칙은 `../sequence_id/`에서 관리한다.

---

## 3. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\QoS"
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

사용자 승인 없이 `main.py`, `qos.py` 같은 실행 파일을 새로 만들지 않는다.

실제 QoS 적용 파일이 확정되면 이 문서에 복사 실행 가능한 검증 명령을 추가한다.

---

## 4. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
MQTT_QOS = 1
```

QoS 관련 값은 한 곳에서 명확하게 관리하고 같은 값을 여러 파일에 중복 정의하지 않는다.

---

## 5. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- QoS 1을 QoS 0 또는 QoS 2로 변경
- QoS 값을 임의로 자동 결정
- 중복 메시지 저장 로직 추가
- `sequence_id` 생성 규칙 변경
- Topic 규칙 변경
- Payload 구조 변경
- Broker Host / Port 변경
- MQTT Client 연결 코드 추가
- 재연결 정책 추가
- 센서 수집 코드 추가
- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- Secret Key, 비밀번호, Token 하드코딩

QoS 변경이 필요하면 Pico W 발행 코드와 Pi 5 수신 코드에 미치는 영향을 먼저 확인하고 사용자 승인을 받는다.

---

## 6. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(qos): <변경 내용>
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
docs(qos): define qos1 rule
fix(qos): keep sensor publish at qos1
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] QoS 1 유지
- [ ] Pi 5 수신 구조와 충돌 없음
- [ ] 중복 처리를 QoS 폴더에 중복 구현하지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] QoS 규칙 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 7. 완료 기준

## 중복 키 규칙

QoS 1 중복 판별은 Pi에서 `cylinder_id + session_id + sequence_id`로 수행한다.

새 논리 메시지에서만 sequence_id를 증가한다. QoS 1 재전송은 기존 serialized Payload와 session_id/sequence_id를 유지한다.

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. Pico W Publish에 QoS 1이 적용됨
4. Raspberry Pi 5에서 QoS 1 메시지 수신 확인
5. 동일 메시지 재전달 가능성을 고려한 기존 `sequence_id` 구조가 유지됨
6. QoS 외 다른 기능이 이 폴더에 섞이지 않음
7. 사용자 승인 없는 새 파일·폴더 생성 없음
8. 실제 통신 검증을 하지 못한 항목은 `미검증`으로 보고

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
