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

배포 서버에 최신 앱 zip과 manifest JSON을 올리고, 사용자 앱의 `문서 설정 > 프로그램 업데이트`에 manifest URL을 입력한 뒤 `앱 시작 시 자동 업데이트 적용`을 켜면 됩니다.

manifest 예시:

```json
{
  "version": "1.0.1",
  "zip_url": "https://github.com/dusdk0098-tech/education-log-local-app/releases/latest/download/LocalEducationLogApp-1.0.1.zip",
  "sha256": "",
  "notes": "양식 및 통계 기능 개선"
}
```

zip에는 `server.py`, `run_app.bat`, `static/` 폴더가 포함되어야 합니다. 업데이트 적용 시 사용자 PC의 `education_log.db`, `server.log`, `qa_outputs/`는 덮어쓰지 않습니다.

## 자체검사

```bat
py -3 server.py --self-check
```
