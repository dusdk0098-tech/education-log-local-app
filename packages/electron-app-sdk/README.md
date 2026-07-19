# @pedit/electron-app-sdk

Pedit 통합 런처와 Electron 업무 앱의 Main Process를 연결하는 공통 SDK입니다.

- 현재 버전: `0.4.0`
- 런처 프로토콜: `2`
- 통신: Windows Named Pipe, UTF-8 JSON Lines
- 인증: PID 검증 Pipe bootstrap + HMAC proof
- heartbeat: 기본 5초
- 필수 실행 인자: `--package-hash`
- 권한: `AppPermissionService`를 이용한 Main Process 역할·scope 판정
- 운영 이벤트: 소비자가 sink를 전달할 때만 동작하는 민감정보 차단 구조화 이벤트

Electron Main Process에서만 사용하세요. Renderer 또는 Preload에서 import하지 않습니다.
`appSessionToken`은 SDK 내부 Main Process 메모리에만 보관되며 `withAccessToken()` callback 밖으로 반환하지 마세요.
`AppPermissionService`와 `AppSdkEventLogger`도 Main Process에서만 사용하고 Renderer에는 업무별 최소 IPC만 노출하세요.

앱 저장소에 이 폴더를 workspace package로 복사한 뒤 다음과 같이 연결할 수 있습니다.

```json
{
  "dependencies": {
    "@pedit/electron-app-sdk": "file:packages/electron-app-sdk"
  }
}
```

상세 계약은 [`../../docs/app-team-launcher-handoff-v2.md`](../../docs/app-team-launcher-handoff-v2.md)와 [`../../docs/launcher-app-protocol-v2.md`](../../docs/launcher-app-protocol-v2.md)를 확인하세요.
