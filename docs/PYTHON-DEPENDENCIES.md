# Python 의존성 재현성

이 문서는 PEDIT EDU의 Python 개발·검증 환경을 재현하기 위한 기준과 잠금
전략을 기록합니다. 현재 저장소에는 Python 의존성 입력 파일과 잠금 파일이
없으므로, 아래 버전 목록은 설치 정본이 아니라 마지막으로 전체 검증을 통과한
환경의 baseline입니다.

## 검증된 baseline

2026-07-20에 새 Windows PC의 fresh virtual environment에서 다음 조합으로
Python 테스트, self-check, PyInstaller 패키징, Electron 테스트, launcher
conformance 및 Protocol v2 mock E2E를 검증했습니다.

| 구성 요소 | 버전 |
| --- | --- |
| Python | 3.12.10 |
| pip | 26.1.2 |
| setuptools | 83.0.0 |
| wheel | 0.47.0 |
| PyInstaller | 6.21.0 |
| pywin32 | 312 |
| packaging | 26.2 |
| pyinstaller-hooks-contrib | 2026.6 |
| pefile | 2024.8.26 |
| pywin32-ctypes | 0.2.3 |
| altgraph | 0.17.5 |

## 새 검증 환경 부트스트랩

저장소 루트에서 Python 3.12 virtual environment를 새로 만들고 현재 PowerShell
프로세스에서만 활성화한다. 실행 정책에 의존하는 활성화 스크립트는 사용하지 않는다.
현재 `package.json`의 Python 명령은 `py -3`를 사용하므로, npm 검증을 시작하기
전에 그 명령이 방금 만든 환경을 선택하는지 fail-closed로 확인해야 한다.

```powershell
py -3.12 -m venv .venv
$venvPath = (Resolve-Path .\.venv).Path
$env:VIRTUAL_ENV = $venvPath
$env:PATH = "$venvPath\Scripts;$env:PATH"

$expectedPython = (Resolve-Path "$venvPath\Scripts\python.exe").Path
$actualPython = py -3 -c "import sys; print(sys.executable)"
if ((Resolve-Path -LiteralPath $actualPython).Path -ne $expectedPython) {
  throw "py -3가 PEDIT EDU .venv를 사용하지 않습니다."
}
```

후속 PR에서 hashed lock을 도입한 뒤에는 패키지 설치도 같은 interpreter를
명시하고 해시 검증을 강제한다.

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes `
  -r requirements\locked-windows-x64-py312.txt
```

새 검증 환경은 Python 3.12를 사용해야 합니다. Python minor version을 바꾸거나
baseline의 patch version을 갱신할 때에도 아래 잠금 갱신 절차와 전체 검증을
거쳐야 합니다.

## 권장 잠금 구조

후속 PR에서 직접 의존성과 해석된 잠금 결과를 분리합니다.

- 사람이 관리하는 입력 파일에는 앱이 직접 import하거나 빌드 명령이 직접
  실행하는 패키지만 선언합니다. 현재 확인된 후보는 runtime의 `pywin32`와
  build의 `PyInstaller`입니다.
- 입력 파일은 runtime과 build 용도를 구분하고, build 입력이 runtime 입력을
  포함하도록 구성합니다.
- Windows/Python 3.12 전용 잠금 파일은 전이 의존성까지 모두 정확한 버전으로
  고정합니다.
- 가능한 경우 `pip-compile --generate-hashes`와 같은 검증된 도구로 각 배포
  파일의 해시를 포함하고, 설치 시 해시 검증을 강제합니다.
- 잠금 파일을 생성한 Python minor version, 대상 OS와 CPU architecture를 파일명
  또는 파일 머리말에 명시합니다.

예상 구조는 다음과 같습니다.

```text
requirements/
  runtime.in
  build.in
  locked-windows-x64-py312.txt
```

## 도입 및 갱신 절차

1. 소스 import와 빌드 스크립트를 검토해 직접 의존성 목록을 확정합니다.
2. Python 3.12의 깨끗한 virtual environment에서 입력 파일로부터 hashed lock을
   생성합니다.
3. 새 virtual environment를 만들고 잠금 파일만 사용해 의존성을 설치합니다.
4. 설치된 Python minor version과 전체 패키지 버전이 잠금 기준과 일치하는지
   확인합니다.
5. Python 테스트와 `server.py --self-check`를 실행합니다.
6. PyInstaller backend와 Electron 패키지를 빌드한 뒤 launcher conformance 및
   Protocol v2 mock E2E까지 실행합니다.
7. 검증 결과와 의존성 변경 이유를 같은 PR에 기록합니다.

의존성 업데이트는 입력 파일을 먼저 수정한 다음 잠금 파일을 재생성해야 하며,
잠금 파일만 수동 편집해서는 안 됩니다. CI도 새 환경에서 잠금 파일로 설치한 뒤
동일한 검증을 수행하도록 구성하는 것이 권장됩니다.

## 이번 PR에서 잠금 파일을 추가하지 않는 이유

현재 검증 환경의 패키지 목록에는 직접 의존성과 PyInstaller가 가져온 전이
의존성이 함께 들어 있습니다. 이를 그대로 requirements 파일로 저장하면 우연히
설치된 전이 패키지를 직접 의존성으로 오인하거나, 실제 runtime/build 경계를
잘못 고정할 수 있습니다. 따라서 이번에는 검증된 baseline과 도입 절차만
문서화하고, 직접 의존성 확정·hashed lock 생성·fresh environment 전체 검증을
하나의 별도 변경으로 수행합니다.
