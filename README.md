# 안전보건교육일지 로컬 앱

원본 엑셀의 `안내`/`목차`/`DB`/인쇄 양식 구조를 로컬 웹앱으로 다시 구현한 버전입니다.

## 실행

```bat
run_app.bat
```

또는:

```bat
py -3 server.py
```

브라우저가 `http://127.0.0.1:8787`로 열립니다.

## 구조

- `server.py`: 로컬 HTTP 서버, SQLite DB, 엑셀 DB 시트 읽기, 인쇄 HTML 생성
- `static/index.html`: 앱 화면
- `static/styles.css`: 화면 UX와 A4 인쇄 양식 CSS
- `static/app.js`: 입력, 미리보기, 저장, 설정 화면 동작
- `education_log.db`: 최초 실행 시 자동 생성되는 로컬 DB

`DB 설정` 화면에서 공사명, 공종, 시간, 장소, 강사뿐 아니라 교육과정과 교육내용 DB까지 수정할 수 있습니다.

작성 화면의 교육내용은 DB에서 자동 반영되며, 사용자는 추가내용과 참석자 명단만 입력하면 됩니다.

교육과정 DB의 양식은 `일반`, `특별`, `특별 2종`을 지원합니다. `특별 2종`은 원본 엑셀의 `1-39(2-1)`, `1-39(2-2)`, `1-39(2-3)`처럼 특별교육 작업명 2개를 한 교육일지에 함께 출력합니다.

저장된 교육일지는 참석자 명단을 기준으로 근로자별 이수 기록에 자동 누적됩니다. 앱의 `근로자 통계` 화면에서 이름 검색, 개별 이수 내역, 교육과정별, 월별 집계를 확인할 수 있습니다.

## 자동 업데이트 배포

설치형 `PEDIT-EDU.exe`는 시작할 때 승인된 GitHub 릴리스의 manifest를 확인하고, 새 버전이 있으면 앱을 종료한 뒤 자동으로 교체·재실행합니다. 기본값은 자동 업데이트 사용입니다. 개발용 `server.py` 실행은 자동 업데이트를 적용하지 않습니다.

v1.0.3부터 이 시작 자동 업데이트가 적용됩니다. v1.0.2 이하 버전에는 시작 업데이트 연결이 없으므로, 사용자는 이번 v1.0.3 설치 파일 또는 실행용 ZIP으로 한 번만 수동 업그레이드해야 이후 버전부터 자동 업데이트를 받을 수 있습니다.

manifest 예시:

```json
{
  "version": "1.0.3",
  "zip_url": "https://github.com/dusdk0098-tech/education-log-local-app/releases/latest/download/LocalEducationLogApp-1.0.3.zip",
  "sha256": "",
  "notes": "PEDIT-EDU 로고와 작성·DB 설정 UX 개선"
}
```

일반 업데이트 ZIP에는 최상위 `PEDIT-EDU/` 폴더와 그 안의 `PEDIT-EDU.exe`, `_internal/`이 포함되어야 합니다. 1.0.2 호환 업데이트 ZIP은 루트에 `server.py`, `run_app.bat`, `PEDIT-EDU.exe`, `_internal/`을 함께 둡니다. 업데이트 매니페스트의 `sha256`은 필수이며, 승인된 GitHub 릴리스 URL과 일치하지 않으면 적용하지 않습니다. 업데이트 적용 시 실행 파일 묶음 전체를 교체한 뒤 다시 시작하며, 사용자 PC의 `education_log.db`, `server.log`, `qa_outputs/`는 덮어쓰지 않습니다.

## 자체검사

```bat
py -3 server.py --self-check
```

## 개발 환경 재현성

Python 빌드 환경의 검증 baseline과 잠금 파일 도입 방안은
[`docs/PYTHON-DEPENDENCIES.md`](docs/PYTHON-DEPENDENCIES.md)를 참고합니다.
