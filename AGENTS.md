# Smart Cylinder Case

## 프로젝트 개요

스마트 실린더 케이스는 공압 실린더의 소리와 동작 상태를 수집·분석하여 상태를 확인하는 시스템이다.

## 주요 목표

- 센서 장착 조건 일정화
- 실린더 소리 및 동작 상태 수집
- STFT 기반 실린더 동작음 검출
- RMS·FFT 기반 상태 특징 분석
- 누설 정도 수치화
- 시간에 따른 상태 변화 기록
- 웹 실시간 모니터링
- 향후 통계적 수명 분석

## 전체 아키텍처

SPH0645 / INMP441  
→ Pico W 01~06  
→ MQTT QoS 1  
→ Raspberry Pi 5 메인 Edge 처리  
→ Sensor / Cycle, STFT, RMS / FFT, Feature Extraction, ML Inference  
→ Supabase PostgreSQL 중앙 데이터 저장소  
→ Web 데이터 제공 계층  
→ Render 공개 Web 진입점 `https://ml-cylinder.onrender.com/`  
→ Data worX 및 외부 Browser

`192.168.137.xxx` 주소는 Pico, Raspberry Pi 5와 공장 내부 장치가 사용하는 로컬 네트워크 주소다. Render 공개 URL은 외부 Web 접속 주소이며 내부 MQTT Broker 주소가 아니다. Render와 Raspberry Pi 5 사이의 정확한 연결·중계 방식과 최종 실시간 Web 방식은 구현 확인 전 확정하지 않는다.

## MQTT 공통 규칙

### 세션 기반 중복 판별

Pico MQTT 메시지는 `session_id`를 포함한다. 중복 판별 기준은 `cylinder_id + session_id + sequence_id`이며, Wi-Fi/MQTT 재연결은 session을 초기화하지 않는다. 중복 메시지는 downstream 처리로 전달하지 않는다.

Pico W와 Raspberry Pi 5 사이의 통신은 MQTT를 사용한다.

- Pico W → Pi 5: `Publish → Subscribe`
- QoS: `1`
- Pico와 Pi는 동일한 Topic과 메시지 규격을 사용한다.
- Payload 필수값은 `cylinder_id`, `session_id`, `sequence_id`, `timestamp`, `sph0645`, `inmp441`이다.
- `client_id`는 MQTT 연결 식별값이며 Payload 또는 중복 키에는 넣지 않는다.
- 장치 매핑은 `pico01`~`pico06`에서 각각 `cylinder_01`~`cylinder_06`으로 일대일 고정한다. client_id와 cylinder_id는 같은 값이 아니다.
- Sensor Topic은 `smart-cylinder/{cylinder_id}/sensor`이며, Pico Publish Topic과 Payload cylinder_id는 같은 매핑을 사용한다.
- timestamp는 NTP 동기화 후 생성한 ISO 8601 `+09:00` 문자열만 사용한다. 시간 동기화 전에는 정상 센서 Payload를 Publish하지 않는다.
- MQTT 규격 변경 시 Pico와 Pi 양쪽을 함께 수정한다.

### Broker 및 인증 계약

- MQTT Broker는 Raspberry Pi 5에서 실행하는 Mosquitto이며 외부 Broker는 사용하지 않는다.
- Pico는 Pi LAN IP의 `1883` 포트에 연결하며 `localhost`/`127.0.0.1`을 사용하지 않는다.
- Pi 내부 paho-mqtt Subscriber는 `127.0.0.1:1883`에 연결한다.
- Pico 고정 장치 ID와 MQTT client_id/username은 `pico01`~`pico06` 중 하나로 동일하다.
- Pi Subscriber는 별도 `pi-subscriber` 계정을 사용한다.
- password는 외부에서 주입하며 코드, Git, 문서, 로그, Payload, 예외 메시지에 평문으로 기록하지 않는다.
- Wi-Fi password도 외부에서 주입하며, 이 프로젝트에는 Secret 저장 파일을 만들지 않는다.

### 장비 상태

MQTT Will Message를 이용해 Pico W의 연결 상태를 확인한다.

- Topic: `cylinder/status/[cylinder_id]`
- 정상: `ok`
- 단절: `failed`

예:

`pico01 → ok`  
`pico02 → ok`

pico02 단절 시:

`pico01 → ok`  
`pico02 → failed`

## 디렉터리 역할

- `pico/`: 센서 수집 및 MQTT Publish
- `system/`: Raspberry Pi 5 MQTT Subscribe, 데이터 처리, STFT 동작음 검출, RMS / FFT 특징 분석, DB 및 웹 연동

각 폴더의 세부 구현은 해당 폴더의 `AGENTS.md`를 따른다.

## 공통 개발 규칙

- 기존 기능을 임의로 삭제하지 않는다.
- **새로운 폴더를 임의로 생성하지 않는다.**
- 기존 폴더 구조를 우선 사용한다.
- 새 폴더가 반드시 필요한 경우 생성하기 전에 목적과 필요성을 먼저 확인한다.
- 기존 파일을 임의로 이동하거나 폴더 구조를 재구성하지 않는다.
- DB 구조를 임의로 변경하지 않는다.
- MQTT Topic 및 메시지 구조를 임의로 변경하지 않는다.
- MQTT 변경 시 Pico와 Pi 양쪽의 호환성을 확인한다.
- Secret Key, API Key, 비밀번호를 소스코드에 작성하지 않는다.
- 미확정 기능을 임의로 확정하지 않는다.
- 작업 완료 시 최상위 `C:\Smart Cylinder Case\README.md`의 날짜별 작업 기록(리마인드)에 한국 시간 기준 `YYYY-MM-DD`, 수정 내용, 검증 결과, 배포 여부와 미확인/남은 작업을 추가한다. 사용자의 "리마인드 MD"는 이 README를 의미하며 별도 파일을 만들지 않는다. 기존 기록과 규칙은 보존하고 Secret은 기록하지 않는다.

## 금지 구역

- 기존 코드, 파일, 폴더, 설정, DB 구조를 사용자 허락 없이 수정하거나 삭제하지 않는다.
- 수정이 필요한 경우 수정 대상, 수정 내용, 이유를 먼저 사용자에게 설명한다.
- 사용자의 명확한 허락을 받은 범위에서만 수정한다.
- 허락받은 범위를 넘어 추가 수정하지 않는다.
- 오류를 발견하더라도 사용자 허락 없이 임의로 수정하지 않는다.
