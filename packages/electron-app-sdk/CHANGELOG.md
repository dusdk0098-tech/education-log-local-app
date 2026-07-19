# Changelog

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
