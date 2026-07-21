# Changelog

## Unreleased — PEDIT-20260721-017

- 예기치 않은 Launcher Pipe 종료를 다음 heartbeat까지 기다리지 않고 `LAUNCHER_PIPE_CLOSED`로 즉시 fail-closed 처리
- 이미 닫힌 Pipe로 오류 보고가 실패해도 로컬 fail-closed 전환을 완료

## 0.4.0

- protocol 2 실행 인자와 필수 `--package-hash` 검증
- Named Pipe bootstrap 및 HMAC `app.hello` proof
- `launcher.session`과 `launcher.session-renewed` 파싱
- Main Process 전용 메모리 세션 저장소
- 5초 heartbeat와 생명주기 메시지 지원
- 메시지 timestamp freshness와 `messageId` replay 방어
- 앱별 permission service와 민감정보 차단 이벤트 로거

현재 버전은 online 세션만 지원한다. `offlinePermit`, `launchAssertion`, `offline`,
`recovery`는 구현되지 않았다.
