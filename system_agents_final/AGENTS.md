# system/AGENTS.md

## 프로젝트 개요
`system/`은 스마트 실린더 케이스의 메인 소프트웨어 영역이다.

```text
system/
├─ Backend/
│  ├─ API/
│  ├─ Service/
│  └─ Server/
├─ DB/
│  ├─ Supabase/
│  └─ PostgreSQL/
├─ Frontend/
├─ ML/
│  ├─ Condition/
│  └─ WeibullAFT/
├─ MQTT/
├─ Sensor/
├─ PLC/
├─ DataWorX/
└─ YOLO/
```

핵심 흐름:

```text
Pico W
→ MQTT QoS 1
→ Raspberry Pi 5 / Mosquitto
→ Sensor + ML
→ Backend REST API
→ Supabase PostgreSQL
→ Supabase Realtime
→ Frontend
```

Frontend의 실시간 갱신은 **Supabase Realtime에 직접 연결**한다. 과거 데이터 조회도 Frontend가 Supabase에서 직접 SELECT하며, Frontend에는 공개 가능한 Key + RLS만 사용한다. Backend는 서버 전용 Secret을 보관하고 Pi 데이터를 Supabase에 INSERT/UPDATE한다.

PLC/Data worX는 유지한다.

```text
Raspberry Pi 5 ↔ MQTT QoS 1 ↔ Data worX ↔ PLC
```

실린더 전진/후진/Cycle 판단은 PLC 신호가 아니라 HC-SR04 3개가 담당한다.

YOLO 개발 기능은 유지하지만 현재 발표 범위에서는 제외한다.

## 검증 명령
```powershell
cd "C:\Smart Cylinder Case\system"
python -m black --check .
python -m compileall .
```

Python은 Black을 사용한다. JavaScript에서 블록 스타일이 필요한 경우 Allman 스타일을 유지한다.

## 구조 변경 규칙
사용자 승인 없이 새 파일/폴더 생성, 삭제, 이동, 이름 변경을 하지 않는다.

새 구조가 필요하면 먼저 다음을 보고한다.

```text
새 파일/폴더:
생성 위치:
필요한 이유:
기존 구조로 해결할 수 없는 이유:
영향 범위:
```

## 금지
- MQTT QoS, Cycle 정의, DB 구조, ML 판별 방식 임의 변경 금지
- Secret/비밀번호/Token 평문 저장 금지
- 미확정 임계값/성능/모델 파라미터 임의 확정 금지
- 하위 폴더의 책임을 다른 폴더에 중복 구현하지 않기

## 커밋 / PR
```text
<type>(scope): <변경 내용>
```

허용 type: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

PR 전:
- Black / 문법 검사
- 관련 AGENTS.md 동시 갱신
- 민감정보 노출 확인
- 사용자 승인 없는 구조 변경 없음
- 실제 환경 미검증 항목은 `미검증`으로 명시

## 완료 기준
코드가 담당 폴더 역할을 지키고, 검증 명령이 통과하며, 실제 하드웨어/Render/Supabase에서 확인하지 못한 항목을 숨기지 않으면 완료로 본다.
