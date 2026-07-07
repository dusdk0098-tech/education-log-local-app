from __future__ import annotations

import json
import hashlib
import mimetypes
import os
import subprocess
import sqlite3
import sys
import tempfile
import threading
import webbrowser
import zipfile
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse
from urllib import request
from xml.etree import ElementTree as ET

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DB_PATH = APP_DIR / "education_log.db"
APP_VERSION = "1.0.0"
DEFAULT_UPDATE_MANIFEST_URL = "https://github.com/dusdk0098-tech/education-log-local-app/releases/latest/download/update.json"
DEFAULT_XLSM = Path(
    r"C:\Users\user\Desktop\북평택교육\안전보건교육일지 (2023.09.27 개정 기준) 카페업로드용 2026-03-06 (수정).xlsm"
)

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
IMAGE_DATA_PREFIXES = (
    "data:image/png;base64,",
    "data:image/jpeg;base64,",
    "data:image/webp;base64,",
    "data:image/gif;base64,",
)

DEFAULT_COURSES = [
    ("50-1", "정기교육", "사무직 종사 근로자", "사무직 종사 근로자", "매반기 6시간 이상", "regular", "50"),
    ("50-2", "정기교육", "판매업무 직접 종사 근로자", "판매업무 직접 종사 근로자", "매반기 6시간 이상", "regular", "50"),
    ("50-3", "정기교육", "그 밖의 근로자", "그 밖의 근로자", "매반기 12시간 이상", "regular", "50"),
    ("51-1", "채용시교육", "일용근로자 및 1주 이하 기간제근로자", "일용근로자", "1시간 이상", "regular", "51"),
    ("51-2", "채용시교육", "1주 초과 1개월 이하 기간제근로자", "기간제근로자", "4시간 이상", "regular", "51"),
    ("52-1", "작업내용 변경교육", "일용근로자 및 1주 이하 기간제근로자", "작업내용 변경 근로자", "1시간 이상", "regular", "52"),
    ("52-2", "작업내용 변경교육", "그 밖의 근로자", "작업내용 변경 근로자", "2시간 이상", "regular", "52"),
    ("1-39(1)", "특별교육", "유해위험작업 일용/1주 이하", "유해위험작업 종사 근로자", "2시간 이상", "special", "14"),
    ("1-39(2)", "특별교육", "타워크레인 신호수", "타워크레인 신호업무 근로자", "8시간 이상", "special", "39"),
    ("1-39(2-1)", "특별교육", "특별교육 2종 묶음", "유해위험작업 종사 근로자", "2시간 이상", "dual_special", "14,26"),
    ("1-39(2-2)", "특별교육", "특별교육 2종 묶음", "유해위험작업 종사 근로자", "8시간 이상", "dual_special", "14,26"),
    ("1-39(2-3)", "특별교육", "특별교육 2종 묶음", "유해위험작업 종사 근로자", "16시간 이상", "dual_special", "14,26"),
    ("60", "관리감독자", "관리감독자 정기교육", "관리감독자", "연간 16시간 이상", "regular", "60"),
    ("61", "관리감독자", "관리감독자 채용시교육", "관리감독자", "8시간 이상", "regular", "61"),
    ("62", "관리감독자", "관리감독자 작업내용 변경교육", "관리감독자", "2시간 이상", "regular", "62"),
    ("70", "특수형태근로종사자", "특수형태근로종사자 최초 노무제공", "특수형태근로종사자", "2시간 이상", "regular", "70"),
    ("80", "물질안전보건자료", "물질안전보건자료 교육", "MSDS 취급 근로자", "필요 시간", "regular", "80"),
    ("90", "소음/난청", "소음성 난청 예방교육", "소음 노출 작업자", "필요 시간", "regular", "90"),
]

FALLBACK_CONTENT = [
    ("50", "가. 정기교육", "산업안전 및 사고 예방, 산업보건 및 직업병 예방, 건강증진 및 질병 예방, 유해·위험 작업환경 관리, 직무스트레스 예방, 산재보상보험 제도"),
    ("51", "나. 채용시교육", "작업 개요, 기계·기구의 위험성과 작업순서, 정리정돈, 사고 발생 시 긴급조치, 물질안전보건자료, 보호구 착용"),
    ("52", "다. 작업내용 변경교육", "변경된 작업의 위험요인, 안전작업 절차, 보호구, 비상조치, 유해·위험 방지대책"),
    ("14", "14. 1톤 이상의 크레인을 사용하는 작업", "방호장치의 종류와 기능, 인양방법, 신호방법, 작업반경 내 출입금지, 줄걸이 안전수칙"),
    ("26", "26. 비계의 조립·해체 또는 변경작업", "비계 조립순서, 작업발판 및 안전난간 설치, 추락재해 방지, 보호구 착용, 해체작업 안전수칙"),
    ("39", "39. 타워크레인을 사용하는 작업시 신호업무", "타워크레인 신호방법, 인양물 확인, 작업반경 통제, 운전자와 신호수 간 의사소통, 비상정지 절차"),
    ("60", "관리감독자 정기교육", "작업공정의 유해·위험과 재해 예방대책, 표준안전작업방법, 관리감독자의 역할과 책임"),
    ("80", "물질안전보건자료 교육", "화학물질 명칭, 유해성·위험성, 취급주의사항, 응급조치, 보호구와 저장방법"),
    ("90", "소음성 난청 예방교육", "소음 유해성, 청력보호구 착용, 소음저감 조치, 건강진단과 작업환경 관리"),
]

DEFAULT_OPTIONS = {
    "trade": ["사무실", "토목공사", "철콘공사", "전기공사"],
    "time": ["08:00", "09:00", "10:00", "13:00", "14:00", "15:00"],
    "method": ["집체교육", "토론식", "시청각교육", "현장교육"],
    "place": ["현장사무실", "교육장", "작업장"],
    "instructor": ["현장소장", "안전관리자", "관리감독자"],
}


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS option_items (
                kind TEXT NOT NULL,
                value TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                PRIMARY KEY (kind, value)
            );
            CREATE TABLE IF NOT EXISTS education_content (
                code TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS courses (
                sheet TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                target TEXT NOT NULL,
                legal_hours TEXT NOT NULL,
                template TEXT NOT NULL,
                content_code TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS report_instances (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS worker_training_records (
                id INTEGER PRIMARY KEY,
                report_id INTEGER NOT NULL,
                worker_name TEXT NOT NULL,
                training_date TEXT NOT NULL,
                course_name TEXT NOT NULL,
                category TEXT NOT NULL,
                legal_hours TEXT NOT NULL,
                completed_hours REAL NOT NULL,
                template TEXT NOT NULL,
                project_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_worker_training_name ON worker_training_records(worker_name);
            CREATE INDEX IF NOT EXISTS idx_worker_training_date ON worker_training_records(training_date);
            """
        )
        con.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", ("projectName", "154kV 북평택변전소 토건공사"))
        con.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", ("updateManifestUrl", DEFAULT_UPDATE_MANIFEST_URL))
        con.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", ("autoUpdateEnabled", "1"))
        for kind, values in DEFAULT_OPTIONS.items():
            for index, value in enumerate(values):
                con.execute("INSERT OR IGNORE INTO option_items VALUES (?, ?, ?)", (kind, value, index))
        for row in DEFAULT_COURSES:
            con.execute("INSERT OR IGNORE INTO courses VALUES (?, ?, ?, ?, ?, ?, ?)", row)
        imported = import_xlsm_db_rows(DEFAULT_XLSM) if DEFAULT_XLSM.exists() else []
        for row in imported or FALLBACK_CONTENT:
            if row[0] and row[1]:
                con.execute("INSERT OR IGNORE INTO education_content VALUES (?, ?, ?)", row)
        backfill_worker_records(con)


def import_xlsm_db_rows(path: Path) -> list[tuple[str, str, str]]:
    with zipfile.ZipFile(path) as zf:
        shared = read_shared_strings(zf)
        sheet_path = find_sheet_path(zf, "DB")
        if not sheet_path:
            return []
        root = ET.fromstring(zf.read(sheet_path))
        rows: list[tuple[str, str, str]] = []
        for row in root.findall(f".//{NS_MAIN}sheetData/{NS_MAIN}row"):
            values = {"A": "", "B": "", "C": ""}
            for cell in row.findall(f"{NS_MAIN}c"):
                ref = cell.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                if col in values:
                    values[col] = cell_text(cell, shared).strip()
            if any(values.values()):
                rows.append((normalize_code(values["A"]), values["B"], values["C"]))
        return rows


def find_sheet_path(zf: zipfile.ZipFile, sheet_name: str) -> str | None:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{NS_PKG_REL}Relationship")}
    for sheet in workbook.findall(f".//{NS_MAIN}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            target = rel_map.get(sheet.attrib.get(f"{NS_REL}id", ""))
            if target:
                normalized = target.lstrip("/")
                return normalized if normalized.startswith("xl/") else "xl/" + normalized
    return None


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall(f"{NS_MAIN}si"):
        values.append("".join(t.text or "" for t in item.findall(f".//{NS_MAIN}t")))
    return values


def cell_text(cell: ET.Element, shared: list[str]) -> str:
    value = cell.find(f"{NS_MAIN}v")
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return shared[int(value.text)] if value.text.isdigit() and int(value.text) < len(shared) else ""
    return value.text


def normalize_code(value: str) -> str:
    return value[:-2] if value.endswith(".0") else value


def rows(query: str, args: tuple = ()) -> list[dict]:
    with connect() as con:
        return [dict(row) for row in con.execute(query, args).fetchall()]


def bootstrap() -> dict:
    settings = {r["key"]: r["value"] for r in rows("SELECT key, value FROM settings")}
    settings["currentVersion"] = APP_VERSION
    return {
        "settings": settings,
        "options": {
            kind: [r["value"] for r in rows("SELECT value FROM option_items WHERE kind=? ORDER BY sort_order, value", (kind,))]
            for kind in DEFAULT_OPTIONS
        },
        "courses": rows(
            """
            SELECT * FROM courses
            ORDER BY
              CASE
                WHEN sheet LIKE '50-%' THEN 0
                WHEN sheet LIKE '51-%' THEN 1
                WHEN sheet LIKE '52-%' THEN 2
                WHEN sheet LIKE '1-39%' THEN 3
                ELSE 4
              END,
              sheet
            """
        ),
        "specialTasks": rows("SELECT code, task_name, content FROM education_content ORDER BY CAST(code AS INTEGER), code"),
    }


def save_settings(payload: dict) -> None:
    with connect() as con:
        for key, value in payload.get("settings", {}).items():
            con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
        for kind, values in payload.get("options", {}).items():
            if kind not in DEFAULT_OPTIONS:
                continue
            con.execute("DELETE FROM option_items WHERE kind=?", (kind,))
            for index, value in enumerate([v.strip() for v in values if str(v).strip()]):
                con.execute("INSERT OR REPLACE INTO option_items VALUES (?, ?, ?)", (kind, value, index))
        course_rows = payload.get("courses")
        if isinstance(course_rows, list) and course_rows:
            con.execute("DELETE FROM courses")
            for row in course_rows:
                sheet = str(row.get("sheet", "")).strip()
                if not sheet:
                    continue
                con.execute(
                    "INSERT OR REPLACE INTO courses VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        sheet,
                        str(row.get("category", "")).strip(),
                        str(row.get("name", "")).strip(),
                        str(row.get("target", "")).strip(),
                        str(row.get("legal_hours", "")).strip(),
                        str(row.get("template", "regular")).strip() or "regular",
                        str(row.get("content_code", "")).strip(),
                    ),
                )
        content_rows = payload.get("educationContent")
        if isinstance(content_rows, list) and content_rows:
            con.execute("DELETE FROM education_content")
            for row in content_rows:
                code = str(row.get("code", "")).strip()
                task_name = str(row.get("task_name", "")).strip()
                if not code or not task_name:
                    continue
                con.execute(
                    "INSERT OR REPLACE INTO education_content VALUES (?, ?, ?)",
                    (code, task_name, str(row.get("content", "")).strip()),
                )


def setting_value(key: str, default: str = "") -> str:
    with connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return str(row["value"]) if row else default


def update_config() -> dict:
    return {
        "currentVersion": APP_VERSION,
        "manifestUrl": setting_value("updateManifestUrl"),
        "autoUpdateEnabled": setting_value("autoUpdateEnabled") == "1",
    }


def version_key(value: str) -> tuple[int, int, int, int]:
    parts = []
    for token in str(value).replace("-", ".").split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple((parts + [0, 0, 0, 0])[:4])


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    return version_key(latest) > version_key(current)


def fetch_json(url: str) -> dict:
    req = request.Request(url, headers={"User-Agent": f"LocalEducationLogApp/{APP_VERSION}"})
    with request.urlopen(req, timeout=10) as res:
        raw = res.read(2_000_001)
    if len(raw) > 2_000_000:
        raise RuntimeError("업데이트 정보 파일이 너무 큽니다.")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("업데이트 정보 형식이 올바르지 않습니다.")
    return data


def check_update(manifest_url: str = "") -> dict:
    url = (manifest_url or setting_value("updateManifestUrl")).strip()
    result = {
        **update_config(),
        "manifestUrl": url,
        "available": False,
        "latestVersion": APP_VERSION,
        "zipUrl": "",
        "notes": "",
        "message": "업데이트 URL이 설정되지 않았습니다.",
    }
    if not url:
        return result
    manifest = fetch_json(url)
    latest = str(manifest.get("version") or "").strip()
    zip_url = str(manifest.get("zip_url") or manifest.get("url") or "").strip()
    if latest:
        result["latestVersion"] = latest
    if zip_url:
        result["zipUrl"] = urljoin(url, zip_url)
    result["notes"] = str(manifest.get("notes") or "")
    result["sha256"] = str(manifest.get("sha256") or "")
    result["available"] = bool(latest and zip_url and is_newer_version(latest))
    if latest and not zip_url:
        result["message"] = "업데이트 파일 URL이 없습니다."
    else:
        result["message"] = "새 업데이트가 있습니다." if result["available"] else "현재 최신 버전입니다."
    return result


def download_update_zip(url: str, target: Path) -> None:
    req = request.Request(url, headers={"User-Agent": f"LocalEducationLogApp/{APP_VERSION}"})
    with request.urlopen(req, timeout=30) as res:
        target.write_bytes(res.read())


def validate_update_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            path = Path(name)
            if info.is_dir():
                continue
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError("업데이트 압축 파일에 허용되지 않는 경로가 있습니다.")


def update_source_dir(extract_dir: Path) -> Path:
    if (extract_dir / "server.py").is_file():
        return extract_dir
    children = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(children) == 1 and (children[0] / "server.py").is_file():
        return children[0]
    raise RuntimeError("업데이트 압축 파일에서 server.py를 찾지 못했습니다.")


def verify_sha256(path: Path, expected: str) -> None:
    if not expected:
        return
    actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
    if actual != expected.lower():
        raise RuntimeError("업데이트 파일 검증에 실패했습니다.")


def write_update_batch(source_dir: Path, temp_dir: Path) -> Path:
    script = temp_dir / "apply_update.bat"
    log_path = temp_dir / "update.log"
    script.write_text(
        "\r\n".join(
            [
                "@echo off",
                "chcp 65001 >nul",
                "setlocal",
                f'set "APP_DIR={APP_DIR}"',
                f'set "SRC_DIR={source_dir}"',
                f'set "LOG_PATH={log_path}"',
                f'set "APP_PID={os.getpid()}"',
                ":wait_app",
                'tasklist /FI "PID eq %APP_PID%" | find "%APP_PID%" >nul',
                "if not errorlevel 1 (",
                "  timeout /t 1 /nobreak >nul",
                "  goto wait_app",
                ")",
                'robocopy "%SRC_DIR%" "%APP_DIR%" /E /XD "__pycache__" "qa_outputs" /XF "education_log.db" "server.pid" "server.log" > "%LOG_PATH%" 2>&1',
                "if %ERRORLEVEL% GEQ 8 (",
                '  echo update copy failed. see "%LOG_PATH%"',
                "  pause",
                "  exit /b %ERRORLEVEL%",
                ")",
                'start "" "%APP_DIR%\\run_app.bat"',
                "endlocal",
            ]
        )
        + "\r\n",
        encoding="utf-8",
    )
    return script


def apply_update(manifest_url: str = "") -> dict:
    if os.name != "nt":
        raise RuntimeError("자동 업데이트 적용은 Windows 실행 환경에서만 지원합니다.")
    info = check_update(manifest_url)
    if not info["available"]:
        return {**info, "updating": False}
    temp_dir = Path(tempfile.mkdtemp(prefix="education-log-update-"))
    zip_path = temp_dir / "update.zip"
    extract_dir = temp_dir / "package"
    download_update_zip(info["zipUrl"], zip_path)
    verify_sha256(zip_path, str(info.get("sha256") or ""))
    validate_update_zip(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    source_dir = update_source_dir(extract_dir)
    script = write_update_batch(source_dir, temp_dir)
    subprocess.Popen(["cmd.exe", "/c", "start", "", str(script)], close_fds=True)
    return {**info, "updating": True}


def update_error(error: Exception, manifest_url: str = "") -> dict:
    return {
        **update_config(),
        "manifestUrl": manifest_url or setting_value("updateManifestUrl"),
        "available": False,
        "updating": False,
        "error": str(error),
        "message": "업데이트 확인 중 오류가 발생했습니다.",
    }


def save_report(payload: dict) -> dict:
    title = f"{payload.get('date', '')} {payload.get('courseName', '교육일지')}".strip()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_dir = str(payload.get("saveDirectory") or "").strip()
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("saveDirectory", save_dir))
        cur = con.execute(
            "INSERT INTO report_instances (title, created_at, payload) VALUES (?, ?, ?)",
            (title, created_at, json.dumps(payload, ensure_ascii=False)),
        )
        report_id = int(cur.lastrowid)
        insert_worker_records(con, report_id, payload, created_at)
    if not save_dir:
        return {"id": report_id, "exportPath": ""}
    try:
        export_path = export_report_pdf(payload, report_id, title, save_dir)
        return {"id": report_id, "exportPath": str(export_path)}
    except Exception as error:
        return {"id": report_id, "exportPath": "", "exportError": str(error)}


def export_report_pdf(payload: dict, report_id: int, title: str, save_dir: str) -> Path:
    chrome = chrome_exe()
    if not chrome:
        raise RuntimeError("Chrome 또는 Edge를 찾지 못해 PDF 저장을 할 수 없습니다.")
    folder = Path(save_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in title).strip()[:80] or "교육일지"
    pdf_path = folder / f"{safe_title}_{report_id}.pdf"
    html = (
        '<!doctype html><meta charset="utf-8">'
        f'<link rel="stylesheet" href="{(STATIC_DIR / "styles.css").resolve().as_uri()}">'
        f'<body><div class="preview">{render_report({**payload, "renderScope": "all"})}</div></body>'
    )
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "report.html"
        html_path.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                str(chrome),
                "--headless=new",
                "--disable-gpu",
                "--virtual-time-budget=3000",
                f"--print-to-pdf={pdf_path}",
                html_path.as_uri(),
            ],
            check=True,
            timeout=60,
        )
    return pdf_path


def chrome_exe() -> Path | None:
    for value in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        path = Path(value)
        if path.exists():
            return path
    return None


def backfill_worker_records(con: sqlite3.Connection) -> None:
    reports = con.execute(
        """
        SELECT r.id, r.created_at, r.payload
        FROM report_instances r
        LEFT JOIN worker_training_records w ON w.report_id = r.id
        WHERE w.id IS NULL
        """
    ).fetchall()
    for report in reports:
        try:
            payload = json.loads(report["payload"])
        except json.JSONDecodeError:
            continue
        insert_worker_records(con, int(report["id"]), payload, report["created_at"])


def insert_worker_records(con: sqlite3.Connection, report_id: int, payload: dict, created_at: str) -> None:
    names = attendee_names(payload)
    if not names:
        return
    training_date = str(payload.get("date") or created_at[:10])
    completed_hours = completed_hours_value(payload)
    for name in names:
        con.execute(
            """
            INSERT INTO worker_training_records
            (report_id, worker_name, training_date, course_name, category, legal_hours, completed_hours, template, project_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                name,
                training_date,
                str(payload.get("courseName") or "교육일지"),
                str(payload.get("category") or ""),
                str(payload.get("legalHours") or ""),
                completed_hours,
                str(payload.get("template") or "regular"),
                str(payload.get("projectName") or ""),
                created_at,
            ),
        )


def attendee_names(payload: dict) -> list[str]:
    names = []
    seen = set()
    for line in str(payload.get("attendees", "")).splitlines():
        name = " ".join(line.split())
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def completed_hours_value(payload: dict) -> float:
    try:
        total = float(payload.get("totalHours") or 0)
        if total:
            return total
    except (TypeError, ValueError):
        pass
    try:
        return float(payload.get("session1Hours") or 0) + float(payload.get("session2Hours") or 0)
    except (TypeError, ValueError):
        return 0.0


def worker_statistics() -> dict:
    summary = rows(
        """
        SELECT
          COUNT(DISTINCT report_id) AS total_reports,
          COUNT(*) AS total_completions,
          COUNT(DISTINCT worker_name) AS total_workers,
          ROUND(COALESCE(SUM(completed_hours), 0), 1) AS total_hours
        FROM worker_training_records
        """
    )[0]
    return {
        "summary": summary,
        "workers": rows(
            """
            SELECT
              worker_name,
              COUNT(*) AS completion_count,
              ROUND(SUM(completed_hours), 1) AS total_hours,
              MAX(training_date) AS last_date,
              GROUP_CONCAT(DISTINCT category) AS categories,
              GROUP_CONCAT(DISTINCT course_name) AS courses
            FROM worker_training_records
            GROUP BY worker_name
            ORDER BY last_date DESC, completion_count DESC, worker_name
            """
        ),
        "courses": rows(
            """
            SELECT
              course_name,
              category,
              COUNT(*) AS completion_count,
              COUNT(DISTINCT worker_name) AS worker_count,
              ROUND(SUM(completed_hours), 1) AS total_hours
            FROM worker_training_records
            GROUP BY course_name, category
            ORDER BY completion_count DESC, course_name
            """
        ),
        "monthly": rows(
            """
            SELECT
              SUBSTR(training_date, 1, 7) AS month,
              COUNT(DISTINCT report_id) AS report_count,
              COUNT(*) AS completion_count,
              COUNT(DISTINCT worker_name) AS worker_count,
              ROUND(SUM(completed_hours), 1) AS total_hours
            FROM worker_training_records
            GROUP BY SUBSTR(training_date, 1, 7)
            ORDER BY month DESC
            LIMIT 12
            """
        ),
        "records": rows(
            """
            SELECT
              worker_name,
              training_date,
              course_name,
              category,
              legal_hours,
              completed_hours,
              template,
              project_name,
              created_at
            FROM worker_training_records
            ORDER BY training_date DESC, created_at DESC, worker_name
            """
        ),
    }


def render_report(payload: dict) -> str:
    template = payload.get("template") or "regular"
    scope = str(payload.get("renderScope") or "all")
    attendees = [line.strip() for line in str(payload.get("attendees", "")).splitlines() if line.strip()]
    if template == "dual_special":
        body = render_dual_special(payload, attendees)
    elif template == "special":
        body = render_special(payload, attendees)
    else:
        body = render_regular(payload, attendees)
    if scope == "journal":
        return body
    if scope == "photos":
        return render_photo_pages(payload, include_blank=True)
    if scope == "certificates":
        return render_certificate_pages(payload, include_blank=True)
    return body + render_attachment_pages(payload)


def render_regular(payload: dict, attendees: list[str]) -> str:
    return f"""
    <article class="paper report-page">
      <table class="report-table sheet-grid regular-sheet">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "regular")}
        <tr class="regular-content-row"><th colspan="5">교육내용</th><td colspan="23">{multiline(payload.get("content", ""))}</td></tr>
        <tr class="regular-extra-row"><th colspan="5">추가내용</th><td colspan="23">{multiline(payload.get("extraContent", "•"))}</td></tr>
        {sheet_attendee_rows(attendees, 5)}
      </table>
    </article>
    """


def render_special(payload: dict, attendees: list[str]) -> str:
    common = "산업안전 및 사고 예방, 산업보건 및 직업병 예방, 건강증진 및 질병 예방, 유해·위험 작업환경 관리"
    return f"""
    <article class="paper report-page">
      <table class="report-table sheet-grid special-sheet">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "special")}
        <tr class="special-task-row"><th colspan="5">대상작업명</th><td colspan="23">{esc(payload.get("taskName", ""))}</td></tr>
        <tr class="special-common-row"><th colspan="3" rowspan="3">교육내용</th><th colspan="2"><span class="stacked-label">공통<br>내용</span></th><td colspan="23">{multiline(common)}</td></tr>
        <tr class="special-individual-row"><th colspan="2"><span class="stacked-label">개별<br>내용</span></th><td colspan="23">{multiline(payload.get("content", ""))}</td></tr>
        <tr class="special-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{multiline(payload.get("extraContent", "•"))}</td></tr>
      </table>
    </article>
    <article class="paper report-page attendee-page">
      <table class="report-table sheet-grid attendee-sheet">
        {sheet_colgroup()}
        <tr class="sheet-row-title"><td colspan="28" class="sheet-title">교육 참석자 명단</td></tr>
        <tr class="sheet-row-caption"><td colspan="28">{esc(payload.get("projectName", ""))}</td></tr>
        {sheet_attendee_rows(attendees, 30)}
      </table>
    </article>
    """


def render_dual_special(payload: dict, attendees: list[str]) -> str:
    common = "산업안전 및 사고 예방, 산업보건 및 직업병 예방, 건강증진 및 질병 예방, 유해·위험 작업환경 관리"
    return f"""
    <article class="paper report-page dual-page-one">
      <table class="report-table sheet-grid dual-special-sheet">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "special")}
        <tr class="dual-task-row"><th colspan="5">대상작업명 1</th><td colspan="23">{esc(payload.get("taskName", ""))}</td></tr>
        <tr class="dual-task-row"><th colspan="5">대상작업명 2</th><td colspan="23">{esc(payload.get("taskName2", ""))}</td></tr>
        <tr class="dual-common-row"><th colspan="3" rowspan="2">교육내용</th><th colspan="2"><span class="stacked-label">공통<br>내용</span></th><td colspan="23">{multiline(common)}</td></tr>
        <tr class="dual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{multiline(payload.get("extraContent", "•"))}</td></tr>
      </table>
    </article>
    <article class="paper report-page dual-page-two">
      <table class="report-table sheet-grid dual-special-sheet dual-continuation-sheet">
        {sheet_colgroup()}
        {sheet_repeat_title_rows(payload)}
        <tr class="dual-individual-row"><th colspan="3" rowspan="4">교육내용</th><th colspan="2"><span class="stacked-label">개별<br>내용<br>(1)</span></th><td colspan="23">{multiline(payload.get("content", ""))}</td></tr>
        <tr class="dual-individual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{multiline(payload.get("extraContent", "•"))}</td></tr>
        <tr class="dual-individual-row"><th colspan="2"><span class="stacked-label">개별<br>내용<br>(2)</span></th><td colspan="23">{multiline(payload.get("content2", ""))}</td></tr>
        <tr class="dual-individual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{multiline(payload.get("extraContent", "•"))}</td></tr>
        <tr class="dual-spacer-row"><td colspan="28"></td></tr>
        {sheet_attendee_rows(attendees, 15)}
      </table>
    </article>
    """


def render_attachment_pages(payload: dict) -> str:
    return render_photo_pages(payload) + render_certificate_pages(payload)


def render_photo_pages(payload: dict, include_blank: bool = False) -> str:
    return render_image_pages(payload, "교육사진대지", image_attachments(payload.get("photoAttachments")), "photo-board-page", include_blank)


def render_certificate_pages(payload: dict, include_blank: bool = False) -> str:
    return render_image_pages(payload, "기초이수증 사진대지", image_attachments(payload.get("certificateAttachments")), "certificate-page", include_blank)


def image_attachments(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for row in value[:40]:
        if not isinstance(row, dict):
            continue
        data_url = str(row.get("dataUrl") or "")
        if not valid_image_data_url(data_url):
            continue
        items.append({
            "dataUrl": data_url,
            "caption": str(row.get("caption") or row.get("name") or ""),
        })
    return items


def valid_image_data_url(data_url: str) -> bool:
    return data_url.startswith(IMAGE_DATA_PREFIXES)


def render_image_pages(payload: dict, title: str, items: list[dict], class_name: str, include_blank: bool = False) -> str:
    pages = []
    starts = range(0, len(items), 2) if items else ([0] if include_blank else [])
    for start in starts:
        chunk = items[start:start + 2]
        pages.append(
            f"""
            <article class="paper attachment-page {class_name}">
              {attachment_header(payload, title)}
              <div class="attachment-slots">{attachment_slots(chunk)}</div>
            </article>
            """
        )
    return "".join(pages)


def attachment_header(payload: dict, title: str) -> str:
    return f"""
    <table class="attachment-header-table">
      <tr><td colspan="2" class="attachment-title">{esc(title)}</td></tr>
      <tr><th>공사명</th><td>{esc(payload.get("projectName", ""))}</td></tr>
      <tr><th>교육일자</th><td>{date_label(payload.get("date", ""))}</td></tr>
    </table>
    """


def attachment_slots(items: list[dict]) -> str:
    slots = []
    for index in range(2):
        item = items[index] if index < len(items) else None
        if item:
            slots.append(
                f"""
                <figure class="attachment-slot">
                  <div class="attachment-image-box"><img src="{esc(item["dataUrl"])}" alt="{esc(item["caption"])}"></div>
                  <figcaption>{esc(item["caption"])}</figcaption>
                </figure>
                """
            )
        else:
            slots.append(
                """
                <figure class="attachment-slot attachment-empty">
                  <div class="attachment-image-box"></div>
                  <figcaption></figcaption>
                </figure>
                """
            )
    return "".join(slots)


SHEET_COLUMN_WIDTHS = [
    3.125, 13, 13, 3.125, 13, 13, 13, 13, 3.125, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 3.75, 3.125, 13, 13,
]


def sheet_colgroup() -> str:
    total = sum(SHEET_COLUMN_WIDTHS)
    cols = "".join(f"<col style=\"width:{width / total * 100:.4f}%\">" for width in SHEET_COLUMN_WIDTHS)
    return f"<colgroup>{cols}</colgroup>"


def sheet_top_rows(payload: dict, layout: str) -> str:
    title = "특별 2종" if payload.get("template") == "dual_special" else "특별" if payload.get("template") == "special" else payload.get("category", "정기")
    trades = [v for v in payload.get("trades", []) if v]
    while len(trades) < 5:
        trades.append("")
    start1, end1 = time_points(payload.get("session1Start", ""), payload.get("session1Hours", ""))
    start2, end2 = time_points(payload.get("session2Start", ""), payload.get("session2Hours", ""))
    rows = [
        f"<tr class=\"sheet-row-title\"><td colspan=\"28\" class=\"sheet-title\">({esc(title)}) 안전보건교육일지</td></tr>",
        f"<tr class=\"sheet-row-caption\"><td colspan=\"28\">{law_caption(payload.get('template'))}</td></tr>",
        f"<tr class=\"sheet-row-caption\"><td colspan=\"28\">{basis_caption()}</td></tr>",
        f"""
        <tr class="sheet-row-project">
          <td colspan="18" rowspan="2" class="project-cell">{esc(payload.get("projectName", ""))}</td>
          <td colspan="10" rowspan="3" class="approval-box-cell">{approval_box(payload)}</td>
        </tr>
        <tr class="sheet-row-sign"></tr>
        <tr class="sheet-row-info">
          <th colspan="5">교육일자</th><td colspan="13">{date_label(payload.get("date", ""))}</td>
        </tr>
        """,
        f"<tr class=\"sheet-row-info\"><th colspan=\"5\">공종</th><td colspan=\"5\">{esc(trades[0])}</td><td colspan=\"5\">{esc(trades[1])}</td><td colspan=\"5\">{esc(trades[2])}</td><td colspan=\"4\">{esc(trades[3])}</td><td colspan=\"4\">{esc(trades[4])}</td></tr>",
    ]
    if layout == "regular":
        rows.extend([
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육명</th><td colspan=\"12\">{esc(payload.get('courseName', ''))}</td><th colspan=\"4\">법정교육시간</th><td colspan=\"7\">{esc(payload.get('legalHours', ''))}</td></tr>",
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육대상</th><td colspan=\"23\">{esc(payload.get('target', ''))}</td></tr>",
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육대상인원</th><td colspan=\"9\">{esc(payload.get('headcount', ''))} 명</td><th colspan=\"5\">금회실시인원</th><td colspan=\"9\">{esc(payload.get('attendeeCount', ''))} 명</td></tr>",
            time_row(payload, start1, end1, start2, end2),
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육강사</th><td colspan=\"9\">{esc(payload.get('instructor', ''))}</td><th colspan=\"5\">교육장소</th><td colspan=\"9\">{esc(payload.get('place', ''))}</td></tr>",
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육방법</th><td colspan=\"9\">{esc(payload.get('method', ''))}</td><th colspan=\"5\">사용교재</th><td colspan=\"9\">{esc(payload.get('material', ''))}</td></tr>",
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육내용명</th><td colspan=\"23\">{esc(payload.get('taskName') or payload.get('courseName', ''))}</td></tr>",
        ])
    else:
        rows.extend([
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육명</th><td colspan=\"8\">{esc(payload.get('courseName', ''))}</td><th colspan=\"4\">법정교육시간</th><td colspan=\"11\">{esc(payload.get('legalHours', ''))}</td></tr>",
            f"<tr class=\"sheet-row-info special-target\"><th colspan=\"5\">교육대상</th><td colspan=\"23\">{esc(payload.get('target', ''))}</td></tr>",
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육대상인원</th><td colspan=\"9\">{esc(payload.get('headcount', ''))} 명</td><th colspan=\"5\">금회실시인원</th><td colspan=\"9\">{esc(payload.get('attendeeCount', ''))} 명</td></tr>",
            time_row(payload, start1, end1, start2, end2),
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육강사</th><td colspan=\"9\">{esc(payload.get('instructor', ''))}</td><th colspan=\"5\">교육장소</th><td colspan=\"9\">{esc(payload.get('place', ''))}</td></tr>",
            f"<tr class=\"sheet-row-info\"><th colspan=\"5\">교육방법</th><td colspan=\"9\">{esc(payload.get('method', ''))}</td><th colspan=\"5\">사용교재</th><td colspan=\"9\">{esc(payload.get('material', ''))}</td></tr>",
        ])
    return "".join(rows)


def sheet_repeat_title_rows(payload: dict) -> str:
    title = "특별 2종" if payload.get("template") == "dual_special" else "특별" if payload.get("template") == "special" else payload.get("category", "정기")
    return (
        f"<tr class=\"sheet-row-title\"><td colspan=\"28\" class=\"sheet-title\">({esc(title)}) 안전보건교육일지</td></tr>"
        f"<tr class=\"sheet-row-caption\"><td colspan=\"28\">{law_caption(payload.get('template'))}</td></tr>"
    )


def time_row(payload: dict, start1: str, end1: str, start2: str, end2: str) -> str:
    return f"""
    <tr class="sheet-row-info">
      <th colspan="5">교육시간</th><td colspan="5">{esc(str(payload.get("totalHours", "")))} 시간</td>
      <td colspan="18" class="time-box-cell">{time_box(start1, end1, start2, end2)}</td>
    </tr>
    """


def approval_box(payload: dict) -> str:
    safety = approval_signature(payload, "safety", "안전관리자 서명")
    site = approval_signature(payload, "site", "현장소장 서명")
    return f"""
    <table class="approval-grid">
      <colgroup><col class="approval-label-col"><col class="approval-sign-col"><col class="approval-sign-col"></colgroup>
      <tr><th rowspan="2" class="approval-label-cell">결<br>재</th><td class="approval-role">안전관리자</td><td class="approval-role">현장소장</td></tr>
      <tr><td class="approval-sign-cell">{safety}</td><td class="approval-sign-cell">{site}</td></tr>
    </table>
    """


def approval_signature(payload: dict, key: str, alt: str) -> str:
    signatures = payload.get("approvalSignatures")
    item = signatures.get(key) if isinstance(signatures, dict) else None
    if not isinstance(item, dict):
        return ""
    data_url = str(item.get("dataUrl") or "")
    if not valid_image_data_url(data_url):
        return ""
    return f"<img class=\"approval-signature\" src=\"{esc(data_url)}\" alt=\"{esc(alt)}\">"


def time_box(start1: str, end1: str, start2: str, end2: str) -> str:
    second = (
        f"<th>2회차</th><td>{esc(start2)}</td><td>~</td><td>{esc(end2)}</td>"
        if start2 or end2
        else "<th>2회차</th><td colspan=\"3\">없음</td>"
    )
    return f"""
    <table class="time-grid">
      <colgroup>
        <col class="time-label-col"><col class="time-point-col"><col class="time-sep-col"><col class="time-point-col">
        <col class="time-label-col"><col class="time-point-col"><col class="time-sep-col"><col class="time-point-col">
      </colgroup>
      <tr><th>1회차</th><td>{esc(start1)}</td><td>~</td><td>{esc(end1)}</td>{second}</tr>
    </table>
    """


def sheet_attendee_rows(attendees: list[str], rows_count: int) -> str:
    rows = [
        "<table class=\"attendee-grid\">",
        attendee_colgroup(),
        "<tr class=\"attendee-title-row\"><th colspan=\"9\">교육 참석자 명단</th></tr>",
        attendee_header_row(),
    ]
    for row_index in range(rows_count):
        first = row_index * 3
        names = [esc(spaced_name(attendees[first + slot])) if first + slot < len(attendees) else "" for slot in range(3)]
        rows.append(
            "<tr class=\"attendee-data-row\">"
            f"<td class=\"seq-cell\">{first + 1}</td><td class=\"name-cell\">{names[0]}</td><td></td>"
            f"<td class=\"seq-cell\">{first + 2}</td><td class=\"name-cell\">{names[1]}</td><td></td>"
            f"<td class=\"seq-cell\">{first + 3}</td><td class=\"name-cell\">{names[2]}</td><td></td>"
            "</tr>"
        )
    rows.append("</table>")
    return f"<tr class=\"attendee-block-row\"><td colspan=\"28\">{''.join(rows)}</td></tr>"


def attendee_header_row() -> str:
    return (
        "<tr class=\"attendee-header-row\">"
        "<th>순번</th><th>이&nbsp;&nbsp;&nbsp;&nbsp;름</th><th>서&nbsp;&nbsp;명</th>"
        "<th>순번</th><th>이&nbsp;&nbsp;&nbsp;&nbsp;름</th><th>서&nbsp;&nbsp;명</th>"
        "<th>순번</th><th>이&nbsp;&nbsp;&nbsp;&nbsp;름</th><th>서&nbsp;&nbsp;명</th>"
        "</tr>"
    )


def attendee_colgroup() -> str:
    cols = "".join("<col class=\"attendee-seq\"><col class=\"attendee-name\"><col class=\"attendee-sign\">" for _ in range(3))
    return f"<colgroup>{cols}</colgroup>"


def spaced_name(value: str) -> str:
    return " ".join("".join(str(value).split()))


def time_points(start: str, hours: str) -> tuple[str, str]:
    if not start or not hours:
        return "", ""
    try:
        h, m = [int(v) for v in start.split(":")[:2]]
        end = (datetime(2000, 1, 1, h, m) + timedelta(hours=float(hours))).time()
        return f"{h}시 {m:02d}분", f"{end.hour}시 {end.minute:02d}분"
    except (ValueError, TypeError):
        return esc(start), ""


def basis_caption() -> str:
    return "관련근거 : 산업안전보건법 제77조 (특수형태근로종사자에 대한 안전조치 및 보건조치 등)"


def report_header(payload: dict) -> str:
    title = "특별 2종" if payload.get("template") == "dual_special" else "특별" if payload.get("template") == "special" else payload.get("category", "정기")
    return f"""
    <header class="report-header">
      <div>
        <h1>({esc(title)}) 안전보건교육일지</h1>
        <p>{law_caption(payload.get("template"))}</p>
      </div>
      <table class="approval">
        <colgroup><col class="approval-label"><col class="approval-sign"><col class="approval-sign"></colgroup>
        <tr><th rowspan="2">결재</th><td>안전관리자</td><td>현장소장</td></tr>
        <tr><td class="sign-space"></td><td class="sign-space"></td></tr>
      </table>
    </header>
    <div class="project-name">{esc(payload.get("projectName", ""))}</div>
    """


def info_table(payload: dict) -> str:
    trades = [v for v in payload.get("trades", []) if v]
    trade_text = " / ".join(trades) if trades else "-"
    return f"""
    <table class="report-table info-table">
      <tr><th>교육일자</th><td>{date_label(payload.get("date", ""))}</td><th>공종</th><td>{esc(trade_text)}</td></tr>
      <tr><th>교육명</th><td>{esc(payload.get("courseName", ""))}</td><th>법정교육시간</th><td>{esc(payload.get("legalHours", ""))}</td></tr>
      <tr><th>교육대상</th><td>{esc(payload.get("target", ""))}</td><th>교육대상인원</th><td>{esc(payload.get("headcount", ""))} 명</td></tr>
      <tr><th>금회실시인원</th><td>{esc(payload.get("attendeeCount", ""))} 명</td><th>교육시간</th><td>{esc(str(payload.get("totalHours", "")))} 시간</td></tr>
      <tr><th>1회차</th><td>{time_range(payload.get("session1Start", ""), payload.get("session1Hours", ""))}</td><th>2회차</th><td>{time_range(payload.get("session2Start", ""), payload.get("session2Hours", ""))}</td></tr>
      <tr><th>교육강사</th><td>{esc(payload.get("instructor", ""))}</td><th>교육장소</th><td>{esc(payload.get("place", ""))}</td></tr>
      <tr><th>교육방법</th><td>{esc(payload.get("method", ""))}</td><th>사용교재</th><td>{esc(payload.get("material", ""))}</td></tr>
    </table>
    """


def attendee_table(attendees: list[str], minimum: int, grouped: bool) -> str:
    count = max(minimum, len(attendees))
    body = []
    for index in range(count):
        name = esc(attendees[index]) if index < len(attendees) else ""
        group = " class=\"group-line\"" if grouped and index and index % 5 == 0 else ""
        body.append(f"<tr{group}><td>{index + 1}</td><td>{name}</td><td></td><td></td></tr>")
    return "<table class=\"report-table attendee-table\"><thead><tr><th>번호</th><th>성명</th><th>서명</th><th>비고</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def law_caption(template: str | None) -> str:
    if template in ("special", "dual_special"):
        return "산업안전보건법 제29조제3항 유해위험작업 채용시 및 작업내용 변경시 안전보건교육"
    return "산업안전보건법 제29조제1항 및 제2항 안전보건교육"


def date_label(value: str) -> str:
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return esc(value)
    weekdays = "월화수목금토일"
    return f"{d.year}년 {d.month}월 {d.day}일 {weekdays[d.weekday()]}요일"


def time_range(start: str, hours: str) -> str:
    if not start or not hours:
        return ""
    try:
        h, m = [int(v) for v in start.split(":")[:2]]
        end = (datetime(2000, 1, 1, h, m) + timedelta(hours=float(hours))).time()
        return f"{h}시 {m:02d}분 ~ {end.hour}시 {end.minute:02d}분"
    except (ValueError, TypeError):
        return esc(start)


def multiline(value: object) -> str:
    return "<br>".join(esc(line) for line in str(value or "").splitlines())


def esc(value: object) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            self.json(bootstrap())
        elif parsed.path == "/api/reports":
            self.json({"reports": rows("SELECT id, title, created_at FROM report_instances ORDER BY id DESC LIMIT 50")})
        elif parsed.path == "/api/worker-stats":
            self.json(worker_statistics())
        elif parsed.path == "/api/update/status":
            self.json(update_config())
        elif parsed.path == "/" or parsed.path.startswith("/static/"):
            self.static_file(parsed.path)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        payload = self.read_json()
        if self.path == "/api/render-report":
            self.json({"html": render_report(payload)})
        elif self.path == "/api/save-report":
            self.json(save_report(payload))
        elif self.path == "/api/settings":
            save_settings(payload)
            self.json(bootstrap())
        elif self.path == "/api/update/check":
            manifest_url = str(payload.get("manifestUrl") or "")
            try:
                self.json(check_update(manifest_url))
            except Exception as error:
                self.json(update_error(error, manifest_url))
        elif self.path == "/api/update/apply":
            manifest_url = str(payload.get("manifestUrl") or "")
            try:
                result = apply_update(manifest_url)
            except Exception as error:
                self.json(update_error(error, manifest_url))
                return
            self.json(result)
            if result.get("updating"):
                threading.Timer(0.8, self.server.shutdown).start()
        else:
            self.send_error(404)

    def read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size).decode("utf-8") or "{}")

    def json(self, data: dict) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def static_file(self, path: str) -> None:
        rel = "index.html" if path == "/" else path.removeprefix("/static/")
        target = (STATIC_DIR / rel).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
            self.send_error(404)
            return
        raw = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args)


def sample_payload() -> dict:
    data = bootstrap()
    course = data["courses"][0]
    task = next((row for row in data["specialTasks"] if row["code"] == course["content_code"]), data["specialTasks"][0])
    return {
        "projectName": data["settings"].get("projectName", ""),
        "date": date.today().isoformat(),
        "courseName": course["name"],
        "category": course["category"],
        "target": course["target"],
        "legalHours": course["legal_hours"],
        "template": course["template"],
        "headcount": "3",
        "attendeeCount": "3",
        "trades": ["사무실"],
        "session1Start": "09:00",
        "session1Hours": "1",
        "session2Start": "",
        "session2Hours": "",
        "totalHours": "1",
        "instructor": "현장소장",
        "place": "현장사무실",
        "method": "집체교육",
        "material": "자체 교안",
        "taskName": task["task_name"],
        "content": task["content"],
        "extraContent": "•",
        "attendees": "홍길동\n김철수\n이영희",
    }


def self_check() -> None:
    init_db()
    payload = sample_payload()
    regular = render_report(payload)
    assert "안전보건교육일지" in regular and "attachment-mark" not in regular
    payload["template"] = "special"
    special = render_report(payload)
    assert "교육 참석자 명단" in special and special.count("<article") == 2
    payload["template"] = "dual_special"
    payload["taskName2"] = "26. 비계의 조립·해체 또는 변경작업"
    payload["content2"] = "비계 조립순서와 추락재해 방지"
    dual = render_report(payload)
    assert "(특별 2종)" in dual and "대상작업명 2" in dual and dual.count("<article") == 2
    attached_payload = sample_payload()
    image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l1aZ8QAAAABJRU5ErkJggg=="
    attached_payload["photoAttachments"] = [{"dataUrl": image, "caption": "교육사진"}]
    attached_payload["certificateAttachments"] = [{"dataUrl": image, "caption": "기초이수증"}]
    attached_payload["approvalSignatures"] = {"safety": {"dataUrl": image}, "site": {"dataUrl": image}}
    attached = render_report(attached_payload)
    assert "교육사진대지" in attached and "기초이수증 사진대지" in attached and "approval-signature" in attached and attached.count("<article") == 3
    assert render_report({**attached_payload, "renderScope": "journal"}).count("<article") == 1
    assert "교육사진대지" in render_report({**attached_payload, "renderScope": "photos"})
    assert "기초이수증 사진대지" in render_report({**attached_payload, "renderScope": "certificates"})
    assert "홍 길 동" in attached
    assert attendee_names(payload) == ["홍길동", "김철수", "이영희"]
    stats = worker_statistics()
    assert stats["summary"]["total_reports"] >= 0 and isinstance(stats["records"], list)
    assert is_newer_version("1.0.1", APP_VERSION) and not is_newer_version(APP_VERSION, APP_VERSION)
    with tempfile.TemporaryDirectory() as tmp:
        valid_zip = Path(tmp) / "update.zip"
        with zipfile.ZipFile(valid_zip, "w") as zf:
            zf.writestr("LocalEducationLogApp/server.py", "# test")
        validate_update_zip(valid_zip)
    print("self-check ok")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    init_db()
    port = 8787
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"로컬 교육일지 앱 실행: {url}")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
