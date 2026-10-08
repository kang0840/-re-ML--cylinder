# sequence_id/AGENTS.md

## 1. 폴더 개요

`pico/sequence_id/`는 Pico W가 전송하는 MQTT 메시지의 **`sequence_id` 생성·증가·관리 규칙**만 담당한다.

`sequence_id`는 같은 Pico 부팅 session에서 전송되는 메시지의 순서를 구분하고, Raspberry Pi 5에서 중복 메시지를 판별할 때 사용한다.

---

## 2. sequence_id 규칙

기본 규칙:

```text
전송 1 → sequence_id = 1
전송 2 → sequence_id = 2
전송 3 → sequence_id = 3
...
```

Pi 5의 중복 판단 기준:

```text
cylinder_id + session_id + sequence_id
```

세 값이 모두 같은 재수신은 QoS 1 재전송이며 Pi downstream 처리로 다시 전달하지 않는다.

### 확정된 세션 규칙

`session_id`는 Pico 부팅 세션 UUID다. 재부팅/전원 재인가 시 새 값을 만들고, Wi-Fi/MQTT 재연결에는 유지한다. `sequence_id`는 새 session에서 1부터 시작하여 새 논리 메시지에서만 증가한다. QoS 1 재전송은 기존 session_id, sequence_id 및 serialized Payload를 재사용한다.

다음 내용은 사용자 승인 없이 임의로 정하지 않는다.

- Pico W 재부팅 후 sequence 최대값/overflow 처리 방식
- 마지막 `sequence_id`를 영구 저장할지
- 최대값에 도달했을 때 초기화 방식
- 저장 위치 또는 영속화 방식

해당 정책이 필요해지면 구현 전에 사용자에게 확인한다.

---

## 3. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\sequence_id"
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

사용자 승인 없이 `main.py`, `sequence_id.py` 같은 파일을 새로 만들거나 존재하지 않는 실행 명령을 추가하지 않는다.

---

## 4. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
sequence_id = 1


def next_sequence_id():
    pass
```

패턴 규칙:

- `sequence_id` 생성과 증가만 담당한다.
- MQTT Publish 함수 안에서 직접 증가 규칙을 중복 구현하지 않는다.
- `cylinder_id + session_id + sequence_id` 결합 중복 판정은 Pi 5 측에서 처리한다.
- 한 메시지에 사용할 `sequence_id`는 생성 후 임의로 바꾸지 않는다.

---

## 5. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- `sequence_id` 증가 규칙 임의 변경
- 재부팅 후 초기화 정책 임의 확정
- 영구 저장 방식 임의 추가
- `cylinder_id` 규칙 변경
- timestamp 생성
- Topic 규칙 변경
- QoS 1 변경
- MQTT Broker/Client 연결 코드 추가
- Payload 전체 구조 변경
- 센서 수집 코드 추가
- RMS·FFT 계산
- NORMAL/ABNORMAL 판별
- DB 저장

정책 변경이 필요하면 먼저 다음을 사용자에게 확인한다.

```text
변경하려는 규칙:
현재 동작:
변경하려는 동작:
필요한 이유:
Pi 5 중복 처리에 미치는 영향:
```

---

## 6. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(sequence-id): <변경 내용>
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
feat(sequence-id): add sequential message id
fix(sequence-id): prevent duplicate increment
docs(sequence-id): update sequence rules
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] 메시지마다 `sequence_id`가 순서대로 증가
- [ ] 동일 메시지 처리 중 불필요한 이중 증가 없음
- [ ] Pi 5의 `cylinder_id + session_id + sequence_id` 중복 처리와 충돌 없음
- [ ] 미확정 재부팅·영속화 정책을 임의 구현하지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] 규칙 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 7. 완료 기준

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. 연속 메시지에서 `sequence_id`가 순서대로 증가
4. 하나의 메시지에 동일한 `sequence_id`가 유지됨
5. Pi 5의 중복 판별 규칙과 충돌하지 않음
6. 재부팅·영속화 등 미확정 정책을 임의로 구현하지 않음
7. 사용자 승인 없는 새 파일·폴더 생성 없음
8. 실제 Pico W 검증을 하지 못한 항목은 `미검증`으로 보고

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
