from __future__ import annotations

import json
import base64
import hashlib
import mimetypes
import os
import re
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import threading
import webbrowser
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from urllib import request
from xml.etree import ElementTree as ET

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
STATIC_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "static"
DB_PATH = APP_DIR / "education_log.db"
APP_VERSION = "1.0.3"
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

DEFAULT_COURSE_ROWS = [
    ("50-1", "정기교육", "가. 정기교육", "1)사무직 종사 근로자", "매반기 6시간 이상", "regular", "50"),
    ("50-2", "정기교육", "가. 정기교육", "가) 판매업무에 직접 종사하는 근로자", "매반기 6시간 이상", "regular", "50"),
    ("50-3", "정기교육", "가. 정기교육", "나) 판매업무에 직접 종사하는 근자외의 근로자", "매반기 12시간 이상", "regular", "50"),
    ("51-1", "채용시교육", "나. 채용시 교육", "1) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자", "1시간 이상", "regular", "51"),
    ("51-2", "채용시교육", "나. 채용시 교육", "2) 근로계약기간이 1주일 초과 1개월 이하인 기간제근로자", "4시간 이상", "regular", "51"),
    ("52-1", "작업내용 변경교육", "다. 작업내용 변경 시 교육", "1) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자", "1시간 이상", "regular", "52"),
    ("52-2", "작업내용 변경교육", "다. 작업내용 변경 시 교육", "2) 그 밖의 근로자", "2시간 이상", "regular", "52"),
    ("1-39(1)", "특별교육", "라. 특별교육", "1) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자: 별표 5 제1호라목(제39호는 제외한다)에 해당하는 작업에 종사하는 근로자에 한정한다.", "2시간 이상", "special", "14"),
    ("1-39(2)", "특별교육", "라. 특별교육", "2) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자: 별표 5 제1호라목제39호에 해당하는 작업에 종사하는 근로자에 한정한다.", "8시간 이상", "special", "39"),
    ("1-39(3)", "특별교육", "라. 특별교육", "3) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자를 제외한 근로자: 별표 5 제1호라목에 해당하는 작업에 종사하는 근로자에 한정한다.", "16시간 이상", "special", "38"),
    ("1-39(4)", "특별교육", "라. 특별교육", "3) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자를 제외한 근로자: 별표 5 제1호라목에 해당하는 작업에 종사하는 근로자에 한정한다. (단기간 작업 또는 간헐적 작업)", "2시간 이상", "special", "38"),
    ("1-39(2-1)", "특별교육", "라. 특별교육 2 종", "1) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자: 별표 5 제1호라목(제39호는 제외한다)에 해당하는 작업에 종사하는 근로자에 한정한다.", "(2+2) 4시간 이상", "dual_special", "12,38"),
    ("1-39(2-2)", "특별교육", "라. 특별교육 2 종", "3) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자를 제외한 근로자: 별표 5 제1호라목에 해당하는 작업에 종사하는 근로자에 한정한다.", "(16+16) 32시간 이상", "dual_special", "12,38"),
    ("1-39(2-3)", "특별교육", "라. 특별교육 2 종", "3) 일용근로자 및 근로계약기간이 1주일 이하인 기간제근로자를 제외한 근로자: 별표 5 제1호라목에 해당하는 작업에 종사하는 근로자에 한정한다. (단기간 작업 또는 간헐적 작업)", "(2+2) 4시간 이상", "dual_special", "12,38"),
    ("60", "관리감독자", "가. 정기교육", "관리감독자 정기 안전보건교육", "연간 16시간 이상", "regular", "60"),
    ("61", "관리감독자", "나. 채용 시 교육", "관리감독자 채용 시 안전보건교육", "8시간 이상", "regular", "61"),
    ("62", "관리감독자", "다. 작업내용 변경 시 교육", "관리감독자 작업내용 변경 시 안전보건교육", "2시간 이상", "regular", "62"),
    ("1-39(60)", "관리감독자", "라. 특별교육", "관리감독자 특별 안전보건교육", "16시간 이상", "special", "35"),
    ("1-39(61)", "관리감독자", "라. 특별교육", "관리감독자 특별 안전보건교육 (단기간 작업 또는 간헐적 작업)", "2시간 이상", "special", "35"),
    ("70", "특수형태근로종사자", "가. 최초 노무제공 시 교육", "특수형태근로종사자 최초 노무 제공 시 교육", "2시간 이상", "regular", "70"),
    ("71", "특수형태근로종사자", "가. 최초 노무제공 시 교육", "단기간 작업 또는 간헐적 작업에 노무를 제공하는 경우", "1시간 이상", "regular", "71"),
    ("1-39(70)", "특수형태근로종사자", "나. 특별교육", "특수형태근로종사자 특별교육", "16시간 이상", "special", "35"),
    ("1-39)71)", "특수형태근로종사자", "나. 특별교육", "단기간 작업 또는 간헐적 작업에 노무를 제공하는 경우", "2시간 이상", "special", "35"),
    ("80", "물질안전보건자료", "물질안전보건자료 교육", "물질안전보건자료대상물질을 취급하는 근로자", "1시간 이상", "regular", "80"),
    ("90", "소음/난청", "소음과 소음성 난청 관련 교육", "소음과 소음성 난청 관련 작업자", "1시간 이상", "regular", "90"),
    ("91", "혹서기 온열질환", "혹서기 온열질환 예방교육", "혹서기 폭염 관련 작업자", "1시간 이상", "regular", "91"),
]
COURSE_DISPLAY_TARGET_OVERRIDES = {
    "50-2": "2)그 밖의 근로자 - 가) 판매업무에 직접 종사하는 근로자",
    "50-3": "2)그 밖의 근로자 - 나) 판매업무에 직접 종사하는 근자외의 근로자",
    "1-39)71)": "특수형태근로종사자 특별교육 - 단기간 작업 또는 간헐적 작업에 노무를 제공하는 경우",
}
TARGET_FIXED_BREAK_SHEETS = {"1-39(2-2)", "1-39(2-3)", "1-39(4)"}
DEFAULT_COURSES = [
    (*row, COURSE_DISPLAY_TARGET_OVERRIDES.get(row[0], row[3]))
    for row in DEFAULT_COURSE_ROWS
]
COURSE_DEFAULTS_VERSION = "2026-07-09-original-course-db-v9-print-target-71"
CONTENT_DEFAULTS_VERSION = "2026-07-08-original-content-db-v2"
WORKER_TARGETS_VERSION = "2026-07-09-display-course-targets-v1"

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


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


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
                content_code TEXT NOT NULL,
                display_target TEXT NOT NULL DEFAULT ''
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
                course_target TEXT NOT NULL DEFAULT '',
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
        con.execute("UPDATE settings SET value=? WHERE key=? AND TRIM(value)=''", (DEFAULT_UPDATE_MANIFEST_URL, "updateManifestUrl"))
        for kind, values in DEFAULT_OPTIONS.items():
            for index, value in enumerate(values):
                con.execute("INSERT OR IGNORE INTO option_items VALUES (?, ?, ?)", (kind, value, index))
        ensure_worker_training_schema(con)
        ensure_courses_schema(con)
        course_defaults = load_course_defaults()
        sync_default_courses(con, course_defaults)
        imported = import_xlsm_db_rows(DEFAULT_XLSM) if DEFAULT_XLSM.exists() else []
        sync_default_content(con, imported or FALLBACK_CONTENT)
        backfill_worker_records(con)
        sync_worker_course_targets(con)


def sync_default_courses(con: sqlite3.Connection, course_defaults: list[tuple[str, str, str, str, str, str, str, str]] | None = None) -> None:
    current = con.execute("SELECT value FROM settings WHERE key=?", ("courseDefaultsVersion",)).fetchone()
    if current and current["value"] == COURSE_DEFAULTS_VERSION:
        return
    for row in course_defaults or load_course_defaults():
        con.execute(
            """
            INSERT OR IGNORE INTO courses
              (sheet, category, name, target, legal_hours, template, content_code, display_target)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
    con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("courseDefaultsVersion", COURSE_DEFAULTS_VERSION))


def sync_default_content(con: sqlite3.Connection, content_rows: list[tuple[str, str, str]]) -> None:
    current = con.execute("SELECT value FROM settings WHERE key=?", ("contentDefaultsVersion",)).fetchone()
    if current and current["value"] == CONTENT_DEFAULTS_VERSION:
        return
    for row in content_rows:
        if row[0] and row[1]:
            con.execute("INSERT OR IGNORE INTO education_content VALUES (?, ?, ?)", row)
    con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("contentDefaultsVersion", CONTENT_DEFAULTS_VERSION))


def ensure_worker_training_schema(con: sqlite3.Connection) -> None:
    columns = {row["name"] for row in con.execute("PRAGMA table_info(worker_training_records)").fetchall()}
    if "course_target" not in columns:
        con.execute("ALTER TABLE worker_training_records ADD COLUMN course_target TEXT NOT NULL DEFAULT ''")


def ensure_courses_schema(con: sqlite3.Connection) -> None:
    columns = {row["name"] for row in con.execute("PRAGMA table_info(courses)").fetchall()}
    if "display_target" not in columns:
        con.execute("ALTER TABLE courses ADD COLUMN display_target TEXT NOT NULL DEFAULT ''")


def load_course_defaults() -> list[tuple[str, str, str, str, str, str, str, str]]:
    if not DEFAULT_XLSM.exists():
        return DEFAULT_COURSES
    return import_xlsm_course_rows(DEFAULT_XLSM) or DEFAULT_COURSES


def import_xlsm_course_rows(path: Path) -> list[tuple[str, str, str, str, str, str, str, str]]:
    with zipfile.ZipFile(path) as zf:
        shared = read_shared_strings(zf)
        toc_path = find_sheet_path(zf, "목차")
        toc_values = read_sheet_values(zf, shared, toc_path) if toc_path else {}
        rows: list[tuple[str, str, str, str, str, str, str, str]] = []
        for fallback in DEFAULT_COURSES:
            sheet, category, fallback_name, fallback_target, fallback_legal, template, content_code, fallback_display = fallback
            sheet_path = find_sheet_path(zf, sheet, exact=False)
            if not sheet_path:
                rows.append(fallback)
                continue
            values, formulas = read_sheet_values(zf, shared, sheet_path, refs={"F8", "F9", "R8", "V8"}, include_formulas=True)
            name = values.get("F8") or fallback_name
            target = values.get("F9") or fallback_target
            legal_hours = values.get("V8") or values.get("R8") or fallback_legal
            display_target = COURSE_DISPLAY_TARGET_OVERRIDES.get(sheet) or display_target_from_source(formulas.get("F9", ""), target, toc_values) or fallback_display
            rows.append((sheet, category, name, target, legal_hours, template, content_code, display_target))
        return rows


def display_target_from_source(formula: str, target: str, source_values: dict[str, str]) -> str:
    match = re.fullmatch(r"(?:'목차'|목차)!\$?C\$?(\d+)", formula.strip())
    if not match:
        return target
    source_row = int(match.group(1))
    parent = source_values.get(f"B{source_row}", "").strip()
    while not parent and source_row > 1:
        source_row -= 1
        parent = source_values.get(f"B{source_row}", "").strip()
    if parent and target and parent not in target:
        return f"{parent} - {target}"
    return target


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
            code = normalize_code(values["A"])
            if code.isdigit() and values["B"]:
                rows.append((code, values["B"], values["C"]))
        return rows


def find_sheet_path(zf: zipfile.ZipFile, sheet_name: str, exact: bool = True) -> str | None:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{NS_PKG_REL}Relationship")}
    for sheet in workbook.findall(f".//{NS_MAIN}sheet"):
        candidate = sheet.attrib.get("name", "")
        matches = candidate == sheet_name if exact else candidate.strip() == sheet_name.strip()
        if matches:
            target = rel_map.get(sheet.attrib.get(f"{NS_REL}id", ""))
            if target:
                normalized = target.lstrip("/")
                return normalized if normalized.startswith("xl/") else "xl/" + normalized
    return None


def read_sheet_values(
    zf: zipfile.ZipFile,
    shared: list[str],
    sheet_path: str,
    refs: set[str] | None = None,
    include_formulas: bool = False,
) -> dict[str, str] | tuple[dict[str, str], dict[str, str]]:
    root = ET.fromstring(zf.read(sheet_path))
    values: dict[str, str] = {}
    formulas: dict[str, str] = {}
    for cell in root.findall(f".//{NS_MAIN}sheetData/{NS_MAIN}row/{NS_MAIN}c"):
        ref = cell.attrib.get("r", "")
        if not ref or (refs is not None and ref not in refs):
            continue
        values[ref] = cell_text(cell, shared).strip()
        formula = cell.find(f"{NS_MAIN}f")
        if formula is not None and formula.text:
            formulas[ref] = formula.text
    return (values, formulas) if include_formulas else values


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
    if value is not None and value.text is not None and cell.attrib.get("t") == "s":
        return shared[int(value.text)] if value.text.isdigit() and int(value.text) < len(shared) else ""
    if value is not None and value.text is not None:
        return value.text
    inline = cell.find(f"{NS_MAIN}is")
    if inline is not None:
        return "".join(t.text or "" for t in inline.findall(f".//{NS_MAIN}t"))
    return ""


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
                    """
                    INSERT OR REPLACE INTO courses
                      (sheet, category, name, target, legal_hours, template, content_code, display_target)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sheet,
                        str(row.get("category", "")).strip(),
                        str(row.get("name", "")).strip(),
                        str(row.get("target", "")).strip(),
                        str(row.get("legal_hours", "")).strip(),
                        str(row.get("template", "regular")).strip() or "regular",
                        str(row.get("content_code", "")).strip(),
                        str(row.get("display_target") or row.get("target", "")).strip(),
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
        "manifestUrl": setting_value("updateManifestUrl", DEFAULT_UPDATE_MANIFEST_URL).strip() or DEFAULT_UPDATE_MANIFEST_URL,
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


def is_trusted_update_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.port not in (None, 443)
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            return False
        path = parsed.path
        if "%" in path or "\\" in path or unquote(path) != path:
            return False
        prefix = "/dusdk0098-tech/education-log-local-app/releases/"
        if not path.startswith(prefix):
            return False
        parts = path[len(prefix):].split("/")
        return (
            len(parts) == 3
            and all(parts)
            and all(part not in (".", "..") for part in parts)
            and (
                parts[0:2] == ["latest", "download"]
                or parts[0] == "download"
            )
        )
    except ValueError:
        return False


def is_valid_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", value.strip()))


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
    url = (manifest_url or update_config()["manifestUrl"]).strip()
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
    if not is_trusted_update_url(url):
        result["message"] = "승인된 GitHub 업데이트 주소만 사용할 수 있습니다."
        return result
    manifest = fetch_json(url)
    latest = str(manifest.get("version") or "").strip()
    zip_url = str(manifest.get("zip_url") or manifest.get("url") or "").strip()
    sha256 = str(manifest.get("sha256") or "").strip()
    if latest:
        result["latestVersion"] = latest
    if zip_url:
        result["zipUrl"] = urljoin(url, zip_url)
    result["notes"] = str(manifest.get("notes") or "")
    result["sha256"] = sha256
    if latest and not zip_url:
        result["message"] = "업데이트 파일 URL이 없습니다."
    elif zip_url and not is_trusted_update_url(result["zipUrl"]):
        result["message"] = "승인된 GitHub 릴리스 파일만 사용할 수 있습니다."
    elif latest and not is_valid_sha256(sha256):
        result["message"] = "업데이트 파일 검증값이 올바르지 않습니다."
    else:
        result["available"] = bool(latest and zip_url and is_newer_version(latest))
        result["message"] = "새 업데이트가 있습니다." if result["available"] else "현재 최신 버전입니다."
    return result


def download_update_zip(url: str, target: Path) -> None:
    req = request.Request(url, headers={"User-Agent": f"LocalEducationLogApp/{APP_VERSION}"})
    with request.urlopen(req, timeout=30) as res:
        target.write_bytes(res.read())


def validate_update_zip_member(name: str) -> None:
    normalized = name.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(name)
    if (
        not normalized
        or "\x00" in name
        or normalized.startswith("/")
        or posix_path.is_absolute()
        or windows_path.drive
        or windows_path.root
        or ".." in posix_path.parts
    ):
        raise RuntimeError("업데이트 압축 파일에 허용되지 않는 경로가 있습니다.")


def validate_update_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            validate_update_zip_member(info.filename)


def update_runtime_dir(extract_dir: Path) -> Path:
    if (extract_dir / "PEDIT-EDU.exe").is_file():
        return extract_dir
    children = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(children) == 1 and (children[0] / "PEDIT-EDU.exe").is_file():
        return children[0]
    raise RuntimeError("업데이트 압축 파일에서 PEDIT-EDU.exe를 찾지 못했습니다.")


def verify_sha256(path: Path, expected: str) -> None:
    if not is_valid_sha256(expected):
        raise RuntimeError("업데이트 파일 검증값이 올바르지 않습니다.")
    actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
    if actual != expected.lower():
        raise RuntimeError("업데이트 파일 검증에 실패했습니다.")


def write_update_batch(runtime_dir: Path, temp_dir: Path) -> Path:
    script = temp_dir / "apply_update.bat"
    log_path = temp_dir / "update.log"
    script.write_text(
        "\r\n".join(
            [
                "@echo off",
                "chcp 65001 >nul",
                "setlocal",
                f'set "APP_DIR={APP_DIR}"',
                f'set "SRC_DIR={runtime_dir}"',
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
                'start "" "%APP_DIR%\\PEDIT-EDU.exe"',
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
    runtime_dir = update_runtime_dir(extract_dir)
    script = write_update_batch(runtime_dir, temp_dir)
    subprocess.Popen(["cmd.exe", "/c", "start", "", str(script)], close_fds=True)
    return {**info, "updating": True}


def apply_startup_update() -> bool:
    if not getattr(sys, "frozen", False):
        return False
    try:
        if not update_config()["autoUpdateEnabled"]:
            return False
        return bool(apply_update().get("updating"))
    except Exception as error:
        print(f"자동 업데이트 확인 실패: {error}")
        return False


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
    title = f"{payload.get('date', '')} {course_display_name(payload)}".strip()
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


def list_reports() -> list[dict]:
    reports = rows("SELECT id, title, created_at, payload FROM report_instances ORDER BY id DESC LIMIT 50")
    for report in reports:
        try:
            payload = json.loads(report.pop("payload") or "{}")
        except json.JSONDecodeError:
            payload = {}
        report["educationCount"] = payload.get("attendeeCount") or payload.get("headcount") or ""
        report["courseTarget"] = display_course_target(payload)
        report["courseName"] = payload.get("courseName") or ""
        report["courseDisplayName"] = course_display_name(payload)
    return reports


def clear_reports() -> dict:
    with connect() as con:
        report_count = con.execute("SELECT COUNT(*) FROM report_instances").fetchone()[0]
        worker_count = con.execute("SELECT COUNT(*) FROM worker_training_records").fetchone()[0]
        con.execute("DELETE FROM worker_training_records")
        con.execute("DELETE FROM report_instances")
    return {"ok": True, "deletedReports": report_count, "deletedWorkerRecords": worker_count}


def export_report_pdf(payload: dict, report_id: int, title: str, save_dir: str) -> Path:
    folder = Path(save_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in title).strip()[:80] or "교육일지"
    pdf_path = folder / f"{safe_title}_{report_id}.pdf"
    write_report_pdf(payload, pdf_path)
    return pdf_path


def write_report_pdf(payload: dict, pdf_path: Path) -> None:
    write_chrome_report_pdf(payload, pdf_path)


def write_chrome_report_pdf(payload: dict, pdf_path: Path) -> None:
    chrome = chrome_exe()
    if not chrome:
        raise RuntimeError("Chrome 또는 Edge를 찾지 못해 PDF 저장을 할 수 없습니다.")
    stylesheet = (STATIC_DIR / "styles.css").resolve()
    html = (
        '<!doctype html><meta charset="utf-8">'
        f'<link rel="stylesheet" href="{stylesheet.as_uri()}">'
        f"<style>{pdf_font_face_style()}</style>"
        f'<body><div class="preview">{render_report(payload)}</div></body>'
    )
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "report.html"
        html_path.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                str(chrome),
                "--headless=new",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--virtual-time-budget=3000",
                f"--print-to-pdf={pdf_path}",
                html_path.as_uri(),
            ],
            check=True,
            timeout=60,
        )


def write_excel_report_pdf(payload: dict, pdf_path: Path) -> None:
    if os.name != "nt":
        raise RuntimeError("Windows에서만 Excel 출력 경로를 사용할 수 있습니다.")
    if not DEFAULT_XLSM.exists():
        raise RuntimeError("원본 Excel 템플릿 파일을 찾지 못했습니다.")
    if str(payload.get("renderScope") or "journal") not in ("all", "journal"):
        raise RuntimeError("교육일지 외 탭은 Chrome 출력 경로를 사용합니다.")
    if payload.get("photoAttachments") or payload.get("certificateAttachments"):
        raise RuntimeError("첨부 출력은 Chrome 출력 경로를 사용합니다.")
    sheet = str(payload.get("sheet") or "").strip()
    if not sheet:
        raise RuntimeError("Excel 출력용 sheet 값이 없습니다.")
    import pythoncom
    import win32com.client

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    excel = None
    with tempfile.TemporaryDirectory() as tmp:
        workbook_path = Path(tmp) / DEFAULT_XLSM.name
        shutil.copy2(DEFAULT_XLSM, workbook_path)
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            excel.EnableEvents = False
            excel.AskToUpdateLinks = False
            excel.AutomationSecurity = 3
            wb = excel.Workbooks.Open(
                str(workbook_path),
                UpdateLinks=0,
                ReadOnly=False,
                IgnoreReadOnlyRecommended=True,
            )
            try:
                ws = excel_worksheet(wb, sheet)
                fill_excel_payload(wb, ws, payload)
                excel.CalculateFullRebuild()
                ws.ExportAsFixedFormat(0, str(pdf_path.resolve()))
            finally:
                wb.Close(False)
        finally:
            if excel is not None:
                excel.Quit()
            pythoncom.CoUninitialize()


def excel_worksheet(wb, sheet: str):
    try:
        return wb.Worksheets(sheet)
    except Exception:
        target = sheet.strip()
        for index in range(1, wb.Worksheets.Count + 1):
            ws = wb.Worksheets(index)
            if str(ws.Name).strip() == target:
                return ws
        raise


def fill_excel_payload(wb, ws, payload: dict) -> None:
    try:
        wb.Worksheets("안내").Range("C12").Value = excel_literal_text(payload.get("projectName"))
    except Exception:
        ws.Range("A4").Value = excel_literal_text(payload.get("projectName"))
    date_value = str(payload.get("date") or "").strip()
    if date_value:
        ws.Range("AF8").Value2 = excel_date_serial(date_value)
    headcount = str(payload.get("headcount") or payload.get("attendeeCount") or "").strip()
    ws.Range("AF9").Value = int(float(headcount)) if headcount else ""
    fill_excel_trades(ws, payload)
    ws.Range("AF14").Value = number_or_blank(payload.get("session1Hours"))
    ws.Range("AF15").Value = excel_time_or_blank(payload.get("session1Start"))
    ws.Range("AF17").Value = number_or_blank(payload.get("session2Hours"))
    ws.Range("AF18").Value = excel_time_or_blank(payload.get("session2Start")) if number_or_blank(payload.get("session2Hours")) != "" else ""
    ws.Range("AF19").Value = excel_literal_text(payload.get("method"))
    ws.Range("AF20").Value = excel_literal_text(payload.get("material"))
    ws.Range("AF21").Value = excel_literal_text(payload.get("instructor"))
    ws.Range("AF22").Value = excel_literal_text(payload.get("place"))
    if str(payload.get("sheet") or "").strip() == "91":
        start1 = excel_time_or_blank(payload.get("session1Start"))
        hours1 = number_or_blank(payload.get("session1Hours"))
        ws.Range("F12").Value = duration_label(completed_hours_value(payload))
        ws.Range("M12").Value2 = start1
        ws.Range("Q12").Value2 = (start1 + hours1 / 24) % 1 if start1 != "" and hours1 != "" else ""
        ws.Range("T13").Value = excel_literal_text(payload.get("place"))
        ws.Range("F15").Value = excel_literal_text(payload.get("taskName") or payload.get("target"))
    extra = str(payload.get("extraContent") or "").strip()
    if extra:
        ws.Range("F27" if str(payload.get("template")) == "special" else "F22").Value = excel_literal_text(excel_extra_content(extra, str(payload.get("template"))))
    fill_excel_attendees(ws, payload)


def number_or_blank(value: object) -> object:
    text = str(value or "").strip()
    if not text:
        return ""
    number = float(text)
    return int(number) if number.is_integer() else number


def excel_time_or_blank(value: object) -> object:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = datetime.strptime(text, "%H:%M")
    return (parsed.hour * 60 + parsed.minute) / 1440


def excel_date_serial(value: str) -> int:
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return (parsed - datetime(1899, 12, 30).date()).days


def excel_extra_content(value: str, template: str) -> str:
    if value.strip() == "•":
        return "•\n•\n•" if template in ("special", "dual_special") else "•\n•\n•\n•\n•\n•"
    return value


def excel_literal_text(value: object) -> str:
    text = str(value or "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def fill_excel_attendees(ws, payload: dict) -> None:
    names = attendee_names(payload)
    used = ws.UsedRange
    first_row = int(used.Row)
    last_row = first_row + int(used.Rows.Count) - 1
    title_row = next(
        (
            row
            for row in range(first_row, last_row + 1)
            if "참석자 명단" in str(ws.Cells(row, 1).Value or "")
        ),
        None,
    )
    if title_row is None:
        return
    print_rows = [int(value) for value in re.findall(r"\$(\d+)", str(ws.PageSetup.PrintArea or ""))]
    if print_rows:
        last_row = min(last_row, max(print_rows))
    start_row = title_row + 2
    slots = max(0, last_row - start_row + 1) * 3
    name_cols = ("B", "K", "T")
    seq_cols = ("A", "J", "S")
    has_sequence_columns = "순번" in str(ws.Cells(title_row + 1, 1).Value or "")
    for index in range(1, int(ws.Shapes.Count) + 1):
        shape = ws.Shapes(index)
        if (
            int(shape.Type) == 13
            and title_row <= int(shape.TopLeftCell.Row) <= last_row
            and int(shape.TopLeftCell.Column) <= 28
        ):
            shape.Visible = 0 if names else -1
    for index in range(slots):
        row = start_row + index // 3
        slot = index % 3
        name_range = ws.Range(f"{name_cols[slot]}{row}")
        name_range.Value = ""
        name_range.HorizontalAlignment = -4108
        name_range.VerticalAlignment = -4108
        name_range.Font.Size = 11
        if has_sequence_columns:
            seq_range = ws.Range(f"{seq_cols[slot]}{row}")
            seq_range.Value = index + 1
            seq_range.HorizontalAlignment = -4108
            seq_range.VerticalAlignment = -4108
    for index, name in enumerate(names[:slots]):
        row = start_row + index // 3
        col = name_cols[index % 3]
        ws.Range(f"{col}{row}").Value = excel_literal_text(spaced_name(name))


def fill_excel_trades(ws, payload: dict) -> None:
    sheet = str(payload.get("sheet") or "")
    values = display_trade_values(payload.get("trades") or [], sheet)
    for cell in ("AF10", "AF11", "AF12"):
        ws.Range(cell).Value = ""
    for cell, trade in zip(excel_trade_cells(sheet), values):
        ws.Range(cell).Value = excel_literal_text(trade)
    for cell, trade in zip(visible_trade_cells(sheet), values):
        rng = ws.Range(cell)
        rng.Value = excel_literal_text(trade)
        if " / " in trade:
            rng.ShrinkToFit = True
            rng.WrapText = False


def pdf_font_face_style() -> str:
    font_path = STATIC_DIR / "fonts" / "H2HDRM.TTF"
    if not font_path.exists():
        return ""
    encoded = base64.b64encode(font_path.read_bytes()).decode("ascii")
    return (
        "@font-face{font-family:XH2;"
        f'src:url(data:font/truetype;base64,{encoded}) format("truetype");'
        "font-weight:400;font-style:normal;}"
        "td.course-fill{font-family:XH2!important;}"
    )


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


def sync_worker_course_targets(con: sqlite3.Connection) -> None:
    current = con.execute("SELECT value FROM settings WHERE key=?", ("workerTargetsVersion",)).fetchone()
    if current and current["value"] == WORKER_TARGETS_VERSION:
        return
    reports = con.execute("SELECT id, payload FROM report_instances").fetchall()
    for report in reports:
        try:
            payload = json.loads(report["payload"])
        except json.JSONDecodeError:
            continue
        target = display_course_target(payload)
        if target:
            con.execute(
                "UPDATE worker_training_records SET course_target=? WHERE report_id=?",
                (target, int(report["id"])),
            )
    con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("workerTargetsVersion", WORKER_TARGETS_VERSION))


def course_display_name(payload: dict) -> str:
    course_name = str(payload.get("courseName") or "").strip()
    target = display_course_target(payload)
    if target and target != course_name:
        return f"{course_name} - {target}" if course_name else target
    return course_name or "교육일지"


def display_course_target(payload: dict) -> str:
    sheet = str(payload.get("sheet") or "").strip()
    target = str(payload.get("displayTarget") or payload.get("display_target") or "").strip()
    if target:
        return target
    if sheet in COURSE_DISPLAY_TARGET_OVERRIDES:
        return COURSE_DISPLAY_TARGET_OVERRIDES[sheet]
    target = str(payload.get("target") or payload.get("courseTarget") or "").strip()
    course_name = str(payload.get("courseName") or payload.get("course_name") or "").strip()
    if course_name == "가. 정기교육" and target == "가) 판매업무에 직접 종사하는 근로자":
        return COURSE_DISPLAY_TARGET_OVERRIDES["50-2"]
    if course_name == "가. 정기교육" and target == "나) 판매업무에 직접 종사하는 근자외의 근로자":
        return COURSE_DISPLAY_TARGET_OVERRIDES["50-3"]
    return target


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
            (report_id, worker_name, training_date, course_name, course_target, category, legal_hours, completed_hours, template, project_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                name,
                training_date,
                str(payload.get("courseName") or "교육일지"),
                display_course_target(payload),
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
              GROUP_CONCAT(DISTINCT CASE
                WHEN COALESCE(course_target, '')='' OR course_target=course_name THEN course_name
                ELSE course_name || ' - ' || course_target
              END) AS courses
            FROM worker_training_records
            GROUP BY worker_name
            ORDER BY last_date DESC, completion_count DESC, worker_name
            """
        ),
        "courses": rows(
            """
            SELECT
              course_name,
              course_target,
              category,
              COUNT(*) AS completion_count,
              COUNT(DISTINCT worker_name) AS worker_count,
              ROUND(SUM(completed_hours), 1) AS total_hours
            FROM worker_training_records
            GROUP BY course_name, course_target, category
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
              course_target,
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
        body = (
            render_inline_special(payload, attendees)
            if payload.get("category") in ("관리감독자", "특수형태근로종사자")
            else render_special(payload, attendees)
        )
    elif payload.get("category") in ("소음/난청", "혹서기 온열질환"):
        body = render_special_one_page(payload, attendees)
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
    extra_content = payload.get("extraContent")
    if not str(extra_content or "").strip() or str(extra_content).strip() == "•":
        extra_content = default_regular_extra_content(payload)
    content = str(payload.get("content", ""))
    if payload.get("sheet") == "60":
        content = content.replace("응급조치에 관한 사항을 포함한다)", "응급조\n치에 관한 사항을 포함한다)")
    attendee_rows = 10 if payload.get("category") == "물질안전보건자료" else 5
    return f"""
    <article class="paper report-page">
      <table class="report-table sheet-grid regular-sheet {regular_sheet_class(payload)}">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "regular")}
        <tr class="regular-content-row"><th colspan="5"><span class="regular-content-label-text">교육내용</span></th><td colspan="23"><div class="regular-content-text">{multiline(content)}</div></td></tr>
        <tr class="regular-extra-row"><th colspan="5"><span class="regular-extra-label-text">추가내용</span></th><td colspan="23">{multiline(extra_content)}</td></tr>
        {sheet_attendee_rows(attendees, attendee_rows, show_empty_mark=payload.get("category") in ("정기교육", "채용시교육", "작업내용 변경교육", "특수형태근로종사자"))}
      </table>
    </article>
    """


REGULAR_EXTRA_CONTENT = "•\n•\n•\n•\n•\n•"
FIVE_BULLET_EXTRA_CONTENT = "•\n•\n•\n•\n•"
SPECIAL_COMMON_CONTENT = """•산업안전 및 산업재해 예방에 관한 사항(화재ㆍ폭발 사고 발생 시 대피에 관한 사항을 포함한다)
•산업보건 및 건강장해 예방에 관한 사항
•위험성 평가에 관한 사항
•산업안전보건법령 및 산업재해보상보험 제도에 관한 사항
•직무스트레스 예방 및 관리에 관한 사항
•직장 내 괴롭힘, 고객의 폭언 등으로 인한 건강장해 예방 및 관리에 관한 사항
•기계ㆍ기구의 위험성과 작업의 순서 및 동선에 관한 사항
•작업 개시 전 점검에 관한 사항
•정리정돈 및 청소에 관한 사항
•사고 발생 시 긴급조치에 관한 사항
•물질안전보건자료에 관한 사항"""
DEFAULT_EXTRA_CONTENT = "•\n•\n•"
SPECIAL_ONE_EXTRA_CONTENT = "•\n•\n•\n•"


def special_one_extra_content(value: object) -> str:
    text = str(value or "").strip()
    return SPECIAL_ONE_EXTRA_CONTENT if not text or text == "•" else str(value)


def special_extra_content(value: object) -> str:
    text = str(value or "").strip()
    return DEFAULT_EXTRA_CONTENT if not text or text == "•" else str(value)


def default_regular_extra_content(payload: dict) -> str:
    if payload.get("category") in ("관리감독자", "물질안전보건자료", "특수형태근로종사자"):
        return FIVE_BULLET_EXTRA_CONTENT
    return REGULAR_EXTRA_CONTENT


def render_special(payload: dict, attendees: list[str]) -> str:
    attendee_marked = payload.get("sheet") in ("1-39(2)", "1-39(3)")
    attendee_page_class = " special-attendee-marked-page" if attendee_marked else ""
    common_extra = (
        '<span class="special-common-extra-note">•<span class="special-common-extra-note-text">공통교육내용은 앞시간 교육 진행</span></span><br><span class="special-common-extra-bullet">•</span><br><span class="special-common-extra-bullet">•</span>'
        if payload.get("sheet") == "1-39(1)"
        else '<span class="special-common-leading-bullet">•</span><br><span class="special-common-extra-bullet">•</span><br><span class="special-common-extra-bullet">•</span>'
    )
    return f"""
    <article class="paper report-page">
      <table class="report-table sheet-grid special-sheet">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "special")}
        <tr class="special-task-row"><th colspan="5"><span class="special-task-label-text">대상작업명</span></th><td colspan="23"><span class="special-task-text">{special_task_name(payload.get("taskName", ""))}</span></td></tr>
        <tr class="special-common-row"><th colspan="3" rowspan="4"><span class="special-content-label-text">교육내용</span></th><th colspan="2"><span class="stacked-label">&lt;공통<br>내용&gt;</span></th><td colspan="23"><div class="special-common-text">{multiline_tight_bullets(SPECIAL_COMMON_CONTENT)}</div></td></tr>
        <tr class="special-extra-row special-common-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{common_extra}</td></tr>
        <tr class="special-individual-row"><th colspan="2"><span class="stacked-label">개별<br>내용</span></th><td colspan="23"><div class="special-individual-text">{multiline_tight_bullets(payload.get("content", ""))}</div></td></tr>
        <tr class="special-extra-row special-individual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{multiline(special_extra_content(payload.get("extraContent")))}</td></tr>
      </table>
    </article>
    <article class="paper report-page attendee-page special-attendee-page{attendee_page_class}">
      <table class="report-table sheet-grid attendee-sheet">
        {sheet_colgroup()}
        {sheet_attendee_rows(attendees, 30, "안전교육 참석자 명단", show_empty_mark=attendee_marked)}
      </table>
    </article>
    """


def render_inline_special(payload: dict, attendees: list[str]) -> str:
    inline_class = "special-inline-sheet"
    is_special_worker = payload.get("category") == "특수형태근로종사자"
    is_management = payload.get("category") == "관리감독자"
    attendee_row_count = 1 if is_special_worker else 2
    common_extra_content = special_extra_content(payload.get("extraContent"))
    individual_extra_content = common_extra_content
    if common_extra_content == DEFAULT_EXTRA_CONTENT:
        common_extra_content = "•\n•"
    if is_management:
        inline_class += " management-inline-sheet"
    if is_special_worker:
        inline_class += " special-worker-inline-sheet"
    if payload.get("sheet") == "1-39(70)" or (
        payload.get("category") == "특수형태근로종사자" and "16" in str(payload.get("legalHours") or "")
    ):
        inline_class += " special-worker-long-inline-sheet"
    return f"""
    <article class="paper report-page">
      <table class="report-table sheet-grid special-sheet {inline_class}">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "special")}
        <tr class="special-task-row"><th colspan="5"><span class="special-task-label-text">대상작업명</span></th><td colspan="23"><span class="special-task-text">{special_task_name(payload.get("taskName", ""))}</span></td></tr>
        <tr class="special-common-row"><th colspan="3" rowspan="4"><span class="special-content-label-text">교육내용</span></th><th colspan="2"><span class="stacked-label">&lt;공통<br>내용&gt;</span></th><td colspan="23">{multiline_tight_bullets(SPECIAL_COMMON_CONTENT)}</td></tr>
        <tr class="special-extra-row special-common-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{multiline(common_extra_content)}</td></tr>
        <tr class="special-individual-row"><th colspan="2"><span class="stacked-label">개별<br>내용</span></th><td colspan="23">{multiline_tight_bullets(payload.get("content", ""))}</td></tr>
        <tr class="special-extra-row special-individual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23"><span class="special-individual-extra-text">{multiline(individual_extra_content)}</span></td></tr>
        {sheet_attendee_rows(attendees, attendee_row_count, "안전교육 참석자 명단", show_empty_mark=is_special_worker and payload.get("sheet") == "1-39(70)")}
      </table>
    </article>
    """


def render_special_one_page(payload: dict, attendees: list[str]) -> str:
    heat_class = " heat-special-one-page-sheet" if payload.get("category") == "혹서기 온열질환" else ""
    return f"""
    <article class="paper report-page">
      <table class="report-table sheet-grid special-sheet special-one-page-sheet{heat_class}">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "special")}
        <tr class="special-task-row"><th colspan="5"><span class="special-task-label-text">대상작업명</span></th><td colspan="23"><span class="special-task-text">{special_task_name(payload.get("taskName", ""))}</span></td></tr>
        <tr class="special-one-content-row"><th colspan="3" rowspan="2"><span class="special-one-content-label-text">교육내용</span></th><th colspan="2"><span class="stacked-label">개별<br>내용</span></th><td colspan="23"><div class="special-one-content-text">{multiline_tight_bullets(payload.get("content", ""))}</div></td></tr>
        <tr class="special-one-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23"><div class="special-one-extra-text">{multiline(special_one_extra_content(payload.get("extraContent")))}</div></td></tr>
        {sheet_attendee_rows(attendees, 5, "안전교육 참석자 명단")}
      </table>
    </article>
    """


def render_dual_special(payload: dict, attendees: list[str]) -> str:
    attendee_marked = payload.get("sheet") == "1-39(2-1)"
    tail_page = "" if is_short_dual_special(payload) else f"""
    <article class="paper report-page dual-tail-page">
      <table class="report-table sheet-grid dual-special-sheet dual-tail-sheet">
        {sheet_colgroup()}
        {sheet_repeat_title_rows(payload)}
        <tr class="dual-tail-attendee-row"><td colspan="28">{dual_tail_attendee_grid()}</td></tr>
      </table>
    </article>
    """
    return f"""
    <article class="paper report-page dual-page-one">
      <table class="report-table sheet-grid dual-special-sheet">
        {sheet_colgroup()}
        {sheet_top_rows(payload, "special")}
        <tr class="dual-task-row"><th colspan="5"><span class="dual-task-label-text">대상작업명 1</span></th><td colspan="23"><span class="special-task-text">{multiline(payload.get("taskName", ""))}</span></td></tr>
        <tr class="dual-task-row"><th colspan="5"><span class="dual-task-label-text">대상작업명 2</span></th><td colspan="23"><span class="special-task-text">{multiline(payload.get("taskName2", ""))}</span></td></tr>
        <tr class="dual-common-row"><th colspan="3" rowspan="2">교육내용</th><th colspan="2"><span class="stacked-label">공통<br>내용</span></th><td colspan="23">{multiline_tight_bullets(SPECIAL_COMMON_CONTENT)}</td></tr>
        <tr class="dual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">{multiline(special_extra_content(payload.get("extraContent")))}</td></tr>
      </table>
    </article>
    <article class="paper report-page dual-page-two">
      <table class="report-table sheet-grid dual-special-sheet dual-continuation-sheet">
        {sheet_colgroup()}
        {sheet_repeat_title_rows(payload)}
        <tr class="dual-individual-row"><th colspan="3" rowspan="4">교육내용</th><th colspan="2"><span class="stacked-label">개별<br>내용<br>(1)</span></th><td colspan="23"><div class="dual-individual-text">{multiline_tight_bullets(payload.get("content", ""))}</div></td></tr>
        <tr class="dual-individual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23"><div class="dual-individual-extra-text">{multiline(special_extra_content(payload.get("extraContent")))}</div></td></tr>
        <tr class="dual-individual-row"><th colspan="2"><span class="stacked-label">개별<br>내용<br>(2)</span></th><td colspan="23"><div class="dual-individual-text">{multiline_tight_bullets(payload.get("content2", ""))}</div></td></tr>
        <tr class="dual-individual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23"><div class="dual-individual-extra-text">{multiline(special_extra_content(payload.get("extraContent")))}</div></td></tr>
        <tr class="dual-spacer-row"><td colspan="28"></td></tr>
        {sheet_attendee_rows(attendees, 15, "안전교육 참석자 명단", show_empty_mark=attendee_marked)}
      </table>
    </article>
    {tail_page}
    """


def is_short_dual_special(payload: dict) -> bool:
    return payload.get("sheet") == "1-39(2-3)" or "단기간" in str(payload.get("target") or "")


def render_attachment_pages(payload: dict) -> str:
    return render_photo_pages(payload) + render_certificate_pages(payload)


def dual_tail_attendee_grid() -> str:
    return (
        '<table class="attendee-grid no-seq-attendee-grid dual-tail-grid">'
        f"{attendee_colgroup(True)}"
        '<tr class="attendee-data-row"><td></td><td></td><td></td><td></td><td></td><td></td></tr>'
        "</table>"
    )


def render_photo_pages(payload: dict, include_blank: bool = False) -> str:
    items = image_attachments(payload.get("photoAttachments"))
    pages = []
    starts = range(0, len(items), 2) if items else ([0] if include_blank else [])
    for start in starts:
        chunk = items[start:start + 2]
        pages.append(
            f"""
            <article class="paper attachment-page photo-board-page">
              {photo_board_header(payload)}
              <div class="photo-board-frame">{attachment_slots(chunk, 2)}</div>
            </article>
            """
        )
    return "".join(pages)


def render_certificate_pages(payload: dict, include_blank: bool = False) -> str:
    items = image_attachments(payload.get("certificateAttachments"))
    pages = []
    starts = range(0, len(items)) if items else ([0] if include_blank else [])
    for start in starts:
        item = items[start] if start < len(items) else None
        pages.append(
            f"""
            <article class="paper certificate-sheet-page">
              <h1 class="certificate-sheet-title">사 진 대 지</h1>
              {certificate_frame(item)}
            </article>
            """
        )
    return "".join(pages)


def certificate_frame(item: dict | None) -> str:
    if not item:
        return '<figure class="certificate-frame"><div class="certificate-image-box"></div></figure>'
    return (
        '<figure class="certificate-frame">'
        f'<div class="certificate-image-box"><img src="{esc(item["dataUrl"])}" alt="{esc(item["caption"])}"></div>'
        '</figure>'
    )


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


def render_image_pages(payload: dict, title: str, items: list[dict], class_name: str, include_blank: bool = False, slots_per_page: int = 2) -> str:
    pages = []
    starts = range(0, len(items), slots_per_page) if items else ([0] if include_blank else [])
    for start in starts:
        chunk = items[start:start + slots_per_page]
        pages.append(
            f"""
            <article class="paper attachment-page {class_name}">
              {attachment_header(payload, title)}
              <div class="attachment-slots">{attachment_slots(chunk, slots_per_page)}</div>
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


def photo_board_header(payload: dict) -> str:
    return f"""
    <div class="photo-board-heading">
      <div class="photo-board-project">{esc(payload.get("projectName", ""))}</div>
      <div class="photo-board-title"><span>안전교육</span><strong>사진대지</strong></div>
    </div>
    """


def attachment_slots(items: list[dict], slots_per_page: int) -> str:
    slots = []
    for index in range(slots_per_page):
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
    *([18.75] * 24), 22.5, 18.75, 18.75, 18.75,
]


def sheet_colgroup() -> str:
    total = sum(SHEET_COLUMN_WIDTHS)
    cols = "".join(f"<col style=\"width:{width / total * 100:.4f}%\">" for width in SHEET_COLUMN_WIDTHS)
    return f"<colgroup>{cols}</colgroup>"


def display_trade_values(trades: list[str], sheet: str = "") -> list[str]:
    filled = [trade for trade in trades if trade]
    slots = len(excel_trade_cells(sheet))
    if len(filled) > slots:
        return filled[:slots - 1] + [" / ".join(filled[slots - 1:])]
    return filled + [""] * (slots - len(filled))


def excel_trade_cells(sheet: str = "") -> tuple[str, ...]:
    return ("AF10", "AF11", "AF12")


def visible_trade_cells(sheet: str = "") -> tuple[str, ...]:
    return ("F7", "N7", "V7")


def trade_box(trades: list[str], sheet: str = "") -> str:
    values = display_trade_values(trades, sheet)
    slots = len(values)
    if slots == 2:
        cols = "<colgroup><col style=\"width:34.7826%\"><col style=\"width:65.2174%\"></colgroup>"
    else:
        cols = "<colgroup><col style=\"width:34.8611%\"><col style=\"width:38.5185%\"><col style=\"width:26.6204%\"></colgroup>"
    cells = "".join(
        f"<td><span class=\"{'top-info-value trade-joined trade-joined-' + str(slots) if ' / ' in trade else 'top-info-value'}\">{esc(trade)}</span></td>"
        for trade in values
    )
    return f"<table class=\"sheet-trade-grid\">{cols}<tr>{cells}</tr></table>"


def label_th(text: str, colspan: int) -> str:
    chars = "".join(f"<span>{esc(char)}</span>" for char in text if char.strip())
    return f"<th colspan=\"{colspan}\"><span class=\"distributed-label\">{chars}</span></th>"


def target_display_html(payload: dict, layout: str, target: str) -> str:
    sheet = str(payload.get("sheet") or "").strip()
    if sheet in COURSE_DISPLAY_TARGET_OVERRIDES:
        target = str(payload.get("target") or target).strip()
    marker = "(제39호는 제외한다)"
    if layout == "special" and payload.get("template") == "special" and marker in target:
        before, _, after = target.partition(marker)
        rendered = f"{esc(before)}<br><span class=\"special-target-continuation\">{esc(marker + after)}</span>"
    else:
        rendered = esc(target)
    if sheet not in TARGET_FIXED_BREAK_SHEETS:
        return rendered
    before, marker, after = target.partition("제1호라목")
    if not marker:
        return rendered
    first_line = f'<span class="target-fixed-line">{esc(before.rstrip())}</span><br>'
    if sheet in {"1-39(2-3)", "1-39(4)"} and after.endswith("업)"):
        return f'{first_line}<span class="target-fixed-line">{esc(marker + after[:-2].rstrip())}</span><br><span class="target-fixed-line">{esc(after[-2:])}</span>'
    return first_line + esc(marker + after)


def sheet_top_rows(payload: dict, layout: str) -> str:
    title = sheet_heading(payload, layout)
    target_display = display_course_target(payload)
    target_html = target_display_html(payload, layout, target_display)
    trades = [v for v in payload.get("trades", []) if v]
    while len(trades) < 5:
        trades.append("")
    start1, end1 = time_points(payload.get("session1Start", ""), payload.get("session1Hours", ""))
    start2, end2 = time_points(payload.get("session2Start", ""), payload.get("session2Hours", ""))
    rows = [
        f"<tr class=\"sheet-row-title\"><td colspan=\"28\" class=\"sheet-title\"><span class=\"sheet-title-text\">{esc(title)}</span></td></tr>",
        f"<tr class=\"sheet-row-caption law-caption\"><td colspan=\"28\"><span class=\"law-caption-text\">{law_caption(payload)}</span></td></tr>",
    ]
    rows.extend([
        f"""
        <tr class="sheet-row-project">
          <td colspan="18" rowspan="2" class="project-cell"><span class="project-cell-text">{esc(payload.get("projectName", ""))}</span></td>
          <td colspan="10" rowspan="3" class="approval-box-cell">{approval_box(payload)}</td>
        </tr>
        <tr class="sheet-row-sign"></tr>
        <tr class="sheet-row-info sheet-date-row">
          {label_th("교육일자", 5)}<td colspan="13" class="excel-left top-info-cell"><span class="top-info-value date-value-text">{date_label(payload.get("date", ""))}</span></td>
        </tr>
        """,
        f"<tr class=\"sheet-row-info sheet-trade-row\">{label_th('공종', 5)}<td colspan=\"23\" class=\"trade-box-cell\">{trade_box(trades, str(payload.get('sheet') or ''))}</td></tr>",
    ])
    if layout == "regular":
        rows.extend([
            f"<tr class=\"sheet-row-info sheet-course-row\">{label_th('교육명', 5)}<td colspan=\"12\" class=\"course-fill\"><span class=\"course-value-text\">{esc(payload.get('courseName', ''))}</span></td>{label_th('법정교육시간', 4)}<td colspan=\"7\" class=\"legal-hours-fill\"><span class=\"top-info-value top-info-value-light\">{esc(payload.get('legalHours', ''))}</span></td></tr>",
            f"<tr class=\"sheet-row-info\">{label_th('교육대상', 5)}<td colspan=\"23\" class=\"excel-left target-cell\"><span class=\"top-info-value target-value-text\">{target_html}</span></td></tr>",
            f"<tr class=\"sheet-row-info\">{label_th('교육대상인원', 5)}<td colspan=\"9\" class=\"excel-bold count-cell\"><span class=\"top-info-value count-value-text\">{esc(payload.get('headcount', ''))} 명</span></td>{label_th('금회실시인원', 5)}<td colspan=\"9\" class=\"excel-bold count-cell\"><span class=\"top-info-value count-value-text\">{esc(payload.get('attendeeCount', ''))} 명</span></td></tr>",
            time_row(payload, start1, end1, start2, end2, zero_empty_second=True),
            f"<tr class=\"sheet-row-info regular-instructor-row\">{label_th('교육강사', 5)}<td colspan=\"9\"><span class=\"field-value-text\">{esc(payload.get('instructor', ''))}</span></td>{label_th('교육장소', 5)}<td colspan=\"9\"><span class=\"field-value-text\">{esc(payload.get('place', ''))}</span></td></tr>",
            f"<tr class=\"sheet-row-info\">{label_th('교육방법', 5)}<td colspan=\"9\"><span class=\"field-value-text\">{esc(payload.get('method', ''))}</span></td>{label_th('사용교재', 5)}<td colspan=\"9\" class=\"material-cell\"><span class=\"material-value-text\">{esc(payload.get('material', ''))}</span></td></tr>",
            f"<tr class=\"sheet-row-info\">{label_th('대상작업명', 5)}<td colspan=\"23\" class=\"excel-left regular-target-fill\">{esc(payload.get('courseName') or payload.get('taskName', ''))}</td></tr>",
        ])
    else:
        rows.extend([
            f"<tr class=\"sheet-row-info sheet-course-row\">{label_th('교육명', 5)}<td colspan=\"8\" class=\"course-fill\"><span class=\"course-value-text\">{esc(payload.get('courseName', ''))}</span></td>{label_th('법정교육시간', 4)}<td colspan=\"11\" class=\"legal-hours-fill\"><span class=\"top-info-value top-info-value-light\">{esc(payload.get('legalHours', ''))}</span></td></tr>",
            f"<tr class=\"sheet-row-info special-target\">{label_th('교육대상', 5)}<td colspan=\"23\" class=\"excel-left target-cell\"><span class=\"top-info-value target-value-text\">{target_html}</span></td></tr>",
            f"<tr class=\"sheet-row-info special-count-row\">{label_th('교육대상인원', 5)}<td colspan=\"9\" class=\"excel-bold count-cell\"><span class=\"top-info-value count-value-text\">{esc(payload.get('headcount', ''))} 명</span></td>{label_th('금회실시인원', 5)}<td colspan=\"9\" class=\"excel-bold count-cell\"><span class=\"top-info-value count-value-text\">{esc(payload.get('attendeeCount', ''))} 명</span></td></tr>",
            time_row(payload, start1, end1, start2, end2, zero_empty_second=True, row_class="special-time-row"),
            f"<tr class=\"sheet-row-info special-instructor-row\">{label_th('교육강사', 5)}<td colspan=\"9\"><span class=\"field-value-text\">{esc(payload.get('instructor', ''))}</span></td>{label_th('교육장소', 5)}<td colspan=\"9\"><span class=\"field-value-text\">{esc(payload.get('place', ''))}</span></td></tr>",
            f"<tr class=\"sheet-row-info special-method-row\">{label_th('교육방법', 5)}<td colspan=\"9\"><span class=\"field-value-text\">{esc(payload.get('method', ''))}</span></td>{label_th('사용교재', 5)}<td colspan=\"9\" class=\"material-cell\"><span class=\"material-value-text\">{esc(payload.get('material', ''))}</span></td></tr>",
        ])
    return "".join(rows)


def sheet_repeat_title_rows(payload: dict) -> str:
    title = sheet_heading(payload, "special")
    return (
        f"<tr class=\"sheet-row-title\"><td colspan=\"28\" class=\"sheet-title\"><span class=\"sheet-title-text\">{esc(title)}</span></td></tr>"
        f"<tr class=\"sheet-row-caption law-caption\"><td colspan=\"28\"><span class=\"law-caption-text\">{law_caption(payload)}</span></td></tr>"
    )


def sheet_heading(payload: dict, layout: str) -> str:
    title = sheet_title(payload, layout)
    suffix = "교육일지" if payload.get("category") == "물질안전보건자료" else "안전보건교육일지"
    return f"({title}) {suffix}"


def sheet_title(payload: dict, layout: str) -> str:
    if payload.get("template") == "dual_special":
        return "특별 2종"
    if payload.get("template") == "special":
        if payload.get("category") == "관리감독자":
            return "관리감독자 특별"
        if payload.get("category") == "특수형태근로종사자":
            return "특수형태 근로종사자 특별"
        return "특별"
    if payload.get("category") == "관리감독자":
        course_name = str(payload.get("courseName") or "")
        if "채용" in course_name:
            return "관리감독자 채용 시"
        if "작업내용" in course_name:
            return "관리감독자 작업내용 변경 시"
        return "관리감독자 정기"
    if payload.get("category") == "특수형태근로종사자":
        target = str(payload.get("target") or "")
        course_name = str(payload.get("courseName") or "")
        return "특수형태 근로종사자 최초" if "최초" in target or course_name.startswith("가. 최초") else "특수형태 근로종사자"
    title = str(payload.get("category") or "정기")
    if title == "채용시교육":
        return "채용 시"
    if title == "작업내용 변경교육":
        return "작업내용 변경 시"
    if title in ("소음/난청", "혹서기 온열질환"):
        return "특별"
    return "정기" if layout == "regular" and title == "정기교육" else title


def regular_sheet_class(payload: dict) -> str:
    classes = []
    if payload.get("category") == "정기교육":
        classes.append("routine-regular-sheet")
    if payload.get("sheet") == "50-3":
        classes.append("routine-attachment-sheet")
    if payload.get("category") == "특수형태근로종사자":
        classes.append("special-worker-sheet")
    if payload.get("category") == "관리감독자":
        classes.append("supervisor-sheet")
    if payload.get("sheet") == "60":
        classes.append("supervisor-annual-sheet")
    if payload.get("category") in ("채용시교육", "작업내용 변경교육"):
        classes.append("short-regular-sheet")
    if payload.get("category") == "물질안전보건자료":
        classes.append("msds-sheet")
    return " ".join(classes)


def time_row(payload: dict, start1: str, end1: str, start2: str, end2: str, zero_empty_second: bool = False, row_class: str = "") -> str:
    total_hours = payload.get("totalHours") or payload.get("durationHours", "")
    total_label = duration_label(total_hours)
    class_attr = f" sheet-row-info {row_class}".strip()
    black_empty_second = payload.get("sheet") in ("51-1", "61", "80") and not start2 and not end2
    return f"""
    <tr class="{class_attr}">
      {label_th("교육시간", 5)}<td colspan="5" class="total-time-cell"><span>{esc(total_label)}</span></td>
      <td colspan="18" class="time-box-cell">{time_box(start1, end1, start2, end2, zero_empty_second, black_empty_second)}</td>
    </tr>
    """


def duration_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "시간" in text or "분" in text:
        return text
    try:
        minutes = round(float(text) * 60)
    except ValueError:
        return text
    if minutes and minutes < 60:
        return f"{minutes}분"
    if minutes % 60 == 0:
        return f"{minutes // 60} 시간"
    return f"{float(text):g} 시간"


def approval_box(payload: dict) -> str:
    safety = approval_signature(payload, "safety", "안전관리자 서명")
    site = approval_signature(payload, "site", "현장소장 서명")
    return f"""
    <table class="approval-grid">
      <colgroup><col class="approval-label-col"><col class="approval-blank-col"><col class="approval-safety-col"><col class="approval-site-col"></colgroup>
      <tr><th rowspan="2" class="approval-label-cell"><span class="approval-label-text">결<br>재</span></th><td class="approval-role"></td><td class="approval-role"><span class="approval-role-text">안전관리자</span></td><td class="approval-role"><span class="approval-role-text">현장소장</span></td></tr>
      <tr><td class="approval-sign-cell approval-diagonal-cell"></td><td class="approval-sign-cell">{safety}</td><td class="approval-sign-cell">{site}</td></tr>
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


def time_box(start1: str, end1: str, start2: str, end2: str, zero_empty_second: bool = False, black_empty_second: bool = False) -> str:
    empty_second_class = " empty-second-time" if black_empty_second else ""
    second = (
        f"<th><span>2회차</span></th><td class=\"time-start\"><span>{esc(start2)}</span></td><td class=\"time-sep\"><span>~</span></td><td class=\"time-end\"><span>{esc(end2)}</span></td>"
        if start2 or end2
        else f"<th><span>2회차</span></th><td class=\"time-start{empty_second_class}\"><span>0시 00분</span></td><td class=\"time-sep{empty_second_class}\"><span>~</span></td><td class=\"time-end{empty_second_class}\"><span>0시 00분</span></td>"
        if zero_empty_second
        else "<th><span>2회차</span></th><td colspan=\"3\"><span>없음</span></td>"
    )
    return f"""
    <table class="time-grid">
      <colgroup>
        <col class="time-label-col"><col class="time-point-col"><col class="time-sep-main-col"><col class="time-point-col">
        <col class="time-label-col"><col class="time-point-col"><col class="time-sep-last-col"><col class="time-point-last-col">
      </colgroup>
      <tr><th><span>1회차</span></th><td class="time-start"><span>{esc(start1)}</span></td><td class="time-sep"><span>~</span></td><td class="time-end"><span>{esc(end1)}</span></td>{second}</tr>
    </table>
    """


def sheet_attendee_rows(
    attendees: list[str],
    rows_count: int,
    title: str = "안전교육 참석자 명단",
    show_empty_mark: bool = False,
) -> str:
    empty_mark = '<div class="attendee-empty-mark">별도 첨부</div>' if show_empty_mark and not attendees else ""
    block_class = "attendee-block-row attendee-empty-block" if not attendees else "attendee-block-row"
    display_rows = rows_count
    no_seq = rows_count in (1, 2, 10, 15, 30)
    table_class = "attendee-grid no-seq-attendee-grid" if no_seq else "attendee-grid"
    colspan = 6 if no_seq else 9
    rows = [
        f"<table class=\"{table_class}\">",
        attendee_colgroup(no_seq),
        f"<tr class=\"attendee-title-row\"><th colspan=\"{colspan}\"><span class=\"attendee-title-text\">{esc(title)}</span></th></tr>",
        attendee_header_row(no_seq),
    ]
    for row_index in range(display_rows):
        first = row_index * 3
        names = [
            f'<span class="attendee-name-text">{esc(spaced_name(attendees[first + slot]))}</span>'
            if first + slot < len(attendees)
            else ""
            for slot in range(3)
        ]
        if not attendees and rows_count == 5:
            seqs = ["5", "10", "15"] if row_index == display_rows - 1 else ["", "", ""]
        else:
            seqs = [str(first + 1), str(first + 2), str(first + 3)]
        if no_seq:
            rows.append(
                "<tr class=\"attendee-data-row\">"
                f"<td class=\"name-cell\">{names[0]}</td><td></td>"
                f"<td class=\"name-cell\">{names[1]}</td><td></td>"
                f"<td class=\"name-cell\">{names[2]}</td><td></td>"
                "</tr>"
            )
            continue
        rows.append(
            "<tr class=\"attendee-data-row\">"
            f"<td class=\"seq-cell\">{seq_text(seqs[0], not attendees and rows_count == 5)}</td><td class=\"name-cell\">{names[0]}</td><td></td>"
            f"<td class=\"seq-cell\">{seq_text(seqs[1], not attendees and rows_count == 5)}</td><td class=\"name-cell\">{names[1]}</td><td></td>"
            f"<td class=\"seq-cell\">{seq_text(seqs[2], not attendees and rows_count == 5)}</td><td class=\"name-cell\">{names[2]}</td><td></td>"
            "</tr>"
        )
    rows.append("</table>")
    return f"<tr class=\"{block_class}\"><td colspan=\"28\">{''.join(rows)}{empty_mark}</td></tr>"


def seq_text(value: str, empty_regular_rows: bool) -> str:
    single_class = " seq-single" if empty_regular_rows and len(value) == 1 else ""
    return f"<span class=\"seq-text{single_class}\">{esc(value)}</span>"


def attendee_header_row(no_seq: bool = False) -> str:
    name = '<span class="attendee-header-text">이&nbsp;&nbsp;&nbsp;&nbsp;름</span>'
    sign = '<span class="attendee-header-text">서&nbsp;&nbsp;명</span>'
    if no_seq:
        return (
            "<tr class=\"attendee-header-row\">"
            f"<th>{name}</th><th>{sign}</th>"
            f"<th>{name}</th><th>{sign}</th>"
            f"<th>{name}</th><th>{sign}</th>"
            "</tr>"
        )
    return (
        "<tr class=\"attendee-header-row\">"
        f"<th colspan=\"2\">{name}</th><th>{sign}</th>"
        f"<th colspan=\"2\">{name}</th><th>{sign}</th>"
        f"<th colspan=\"2\">{name}</th><th>{sign}</th>"
        "</tr>"
    )


def attendee_colgroup(no_seq: bool = False) -> str:
    widths = [93.75, 75, 93.75, 75, 93.75, 97.5] if no_seq else [18.75, 75, 75, 18.75, 75, 75, 18.75, 75, 97.5]
    total = sum(widths)
    cols = "".join(f"<col style=\"width:{width / total * 100:.4f}%\">" for width in widths)
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
        <p><span class="law-caption-text">{law_caption(payload)}</span></p>
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
    total_hours = payload.get("totalHours") or payload.get("durationHours", "")
    target_display = display_course_target(payload)
    return f"""
    <table class="report-table info-table">
      <tr><th>교육일자</th><td>{date_label(payload.get("date", ""))}</td><th>공종</th><td>{esc(trade_text)}</td></tr>
      <tr><th>교육명</th><td>{esc(payload.get("courseName", ""))}</td><th>법정교육시간</th><td>{esc(payload.get("legalHours", ""))}</td></tr>
      <tr><th>교육대상</th><td>{esc(target_display)}</td><th>교육대상인원</th><td>{esc(payload.get("headcount", ""))} 명</td></tr>
      <tr><th>금회실시인원</th><td>{esc(payload.get("attendeeCount", ""))} 명</td><th>교육시간</th><td>{esc(duration_label(total_hours))}</td></tr>
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


def law_caption(payload: object) -> str:
    if not isinstance(payload, dict):
        if payload in ("special", "dual_special"):
            return "산업안전보건법 제29조제3항 (유해위험작업 채용시 및 작업내용 변경시 안전보건교육)"
        return "산업안전보건법 제29조제1항 (정기 안전보건교육)"
    category = str(payload.get("category", ""))
    course_name = str(payload.get("courseName", ""))
    template = str(payload.get("template", "regular"))
    if category == "물질안전보건자료":
        return "산업안전보건법 제114조제3항 (물질안전보건자료의 게시 및 교육)"
    if category == "특수형태근로종사자":
        return "산업안전보건법 제77조제2항 (특수형태근로종사자 안전보건교육)"
    if category in ("소음/난청", "혹서기 온열질환"):
        return "산업안전보건법 제29조제3항 (유해위험작업 채용시 및 작업내용 변경시 안전보건교육)"
    if template in ("special", "dual_special"):
        return "산업안전보건법 제29조제3항 (유해위험작업 채용시 및 작업내용 변경시 안전보건교육)"
    if course_name.startswith("나.") or course_name.startswith("다."):
        return "산업안전보건법 제29조제2항 (채용 시 및 작업내용 변경 시 안전보건교육)"
    return "산업안전보건법 제29조제1항 (정기 안전보건교육)"


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
    return "<br>".join(esc(line).replace("\t", "&nbsp;") for line in str(value or "").splitlines())


def multiline_tight_bullets(value: object) -> str:
    lines = []
    for line in str(value or "").splitlines():
        text = esc(line).replace("\t", '<span class="excel-tab-glyph">o</span>')
        if line.startswith("•"):
            text = '<span class="tight-bullet">•</span>' + text[1:]
        lines.append(text)
    return "<br>".join(lines)


def special_task_name(value: object) -> str:
    text = str(value or "").replace("5대 이상 보유한 사업장에서", "5대 이상 보\n유한 사업장에서")
    return multiline(text)


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
            self.json({"reports": list_reports()})
        elif parsed.path == "/api/worker-stats":
            self.json(worker_statistics())
        elif parsed.path == "/api/update/status":
            self.json(update_config())
        elif parsed.path == "/" or parsed.path.startswith("/static/"):
            self.static_file(parsed.path)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        payload = self.read_json()
        if self.path == "/api/render-report":
            self.json({"html": render_report(payload)})
        elif self.path in ("/api/export-report-pdf", "/api/export-excel-reference-pdf"):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    pdf_path = Path(tmp) / "report.pdf"
                    writer = (
                        write_excel_report_pdf
                        if self.path == "/api/export-excel-reference-pdf"
                        else write_report_pdf
                    )
                    writer(payload, pdf_path)
                    raw = pdf_path.read_bytes()
            except Exception as error:
                raw = str(error).encode("utf-8", "replace")
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
        elif self.path == "/api/save-report":
            self.json(save_report(payload))
        elif self.path == "/api/clear-reports":
            self.json(clear_reports())
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
    global DB_PATH
    original_db_path = DB_PATH
    temporary_db = tempfile.TemporaryDirectory()
    DB_PATH = Path(temporary_db.name) / "education_log.db"
    init_db()
    assert hashlib.sha256((STATIC_DIR / "fonts" / "H2HDRM.TTF").read_bytes()).hexdigest() == "273cbb76d95e6c7f78855edff070f2a8dd73e8be18c9329cefd9cf0e4befe2fd"
    class FakeSheet:
        def __init__(self, name: str) -> None:
            self.Name = name

    class FakeSheets:
        Count = 2

        def __call__(self, key):
            if key == 1:
                return FakeSheet("50-1")
            if key == 2:
                return FakeSheet("1-39(2-2) ")
            raise Exception("not found")

    fake_wb = type("FakeWorkbook", (), {"Worksheets": FakeSheets()})()
    assert excel_worksheet(fake_wb, "1-39(2-2)").Name == "1-39(2-2) "
    assert excel_date_serial("2026-07-10") == 46213
    assert excel_literal_text("=1+1") == "'=1+1" and excel_literal_text("현장") == "현장"
    payload = sample_payload()
    regular = render_report(payload)
    assert "안전보건교육일지" in regular and "attachment-mark" not in regular
    assert "attendee-name-text" in regular
    generic_special = render_report({**payload, "sheet": "1-39(2)", "template": "special", "category": "특별교육"})
    assert "공통교육내용은 앞시간 교육 진행" not in generic_special
    assert '<span class="tight-bullet">•</span>산업안전' in generic_special
    assert "공통교육내용은 앞시간 교육 진행" in render_report({**payload, "sheet": "1-39(1)", "template": "special", "category": "특별교육"})
    target_4 = next(course["target"] for course in bootstrap()["courses"] if course["sheet"] == "1-39(4)")
    assert "target-fixed-line" in render_report({**payload, "sheet": "1-39(4)", "template": "special", "category": "특별교육", "target": target_4})
    print_targets = (
        ("50-2", "regular", "정기교육", "가) 판매업무에 직접 종사하는 근로자"),
        ("50-3", "regular", "정기교육", "나) 판매업무에 직접 종사하는 근자외의 근로자"),
        ("1-39)71)", "special", "특수형태근로종사자", "단기간 작업 또는 간헐적 작업에 노무를 제공하는 경우"),
    )
    for sheet, template, category, target in print_targets:
        printed = render_report({**payload, "sheet": sheet, "template": template, "category": category, "target": target, "displayTarget": COURSE_DISPLAY_TARGET_OVERRIDES[sheet]})
        assert f'target-value-text">{target}</span>' in printed
    assert "routine-attachment-sheet" in regular_sheet_class({"sheet": "50-3", "category": "정기교육"})
    assert ">-<" not in trade_box(["사무실"], "50-1")
    assert display_trade_values(["사무실", "토목공사", "철콘공사", "전기공사", "설비공사"], "50-1") == ["사무실", "토목공사", "철콘공사 / 전기공사 / 설비공사"]
    assert trade_box(["사무실", "토목공사", "철콘공사"], "50-1").count("<td>") == 3
    assert "34.8611%" in trade_box(["사무실"], "50-1")
    assert trade_box(["사무실", "토목공사", "철콘공사"], "80").count("<td>") == 3
    assert "trade-joined-3" in trade_box(["사무실", "토목공사", "철콘공사", "전기공사"], "80")
    assert visible_trade_cells("50-1") == ("F7", "N7", "V7")
    assert "(채용 시) 안전보건교육일지" in render_report({**payload, "category": "채용시교육", "courseName": "나. 채용시 교육"})
    hire_default = render_report({**payload, "sheet": "51-1", "category": "채용시교육", "courseName": "나. 채용시 교육", "extraContent": "•"})
    assert "비산먼지" not in hire_default
    assert "(작업내용 변경 시) 안전보건교육일지" in render_report({**payload, "category": "작업내용 변경교육", "courseName": "다. 작업내용 변경 시 교육"})
    course80 = next(course for course in bootstrap()["courses"] if course["sheet"] == "80")
    assert course80["legal_hours"] == "1시간 이상"
    msds = render_report({**payload, "sheet": "80", "category": "물질안전보건자료", "courseName": "물질안전보건자료 교육", "legalHours": course80["legal_hours"]})
    assert "(물질안전보건자료) 교육일지" in msds
    assert "1시간 이상" in msds
    assert "msds-sheet" in msds and msds.count("attendee-data-row") == 10
    assert "msds-combined-content" not in msds
    assert "empty-second-time" in msds
    assert "별도 첨부" in render_report({**payload, "category": "채용시교육", "courseName": "나. 채용시 교육", "attendees": ""})
    assert "별도 첨부" in render_report({**payload, "category": "작업내용 변경교육", "courseName": "다. 작업내용 변경 시 교육", "attendees": ""})
    regular_empty_second = render_report({**payload, "sheet": "51-1", "category": "채용시교육", "courseName": "나. 채용시 교육", "session2Start": "", "session2Hours": ""})
    assert "0시 00분" in regular_empty_second and "없음" not in regular_empty_second
    assert "empty-second-time" in regular_empty_second
    assert "6 시간" in render_report({**payload, "totalHours": "", "durationHours": "6"})
    half_hour = render_report({**payload, "totalHours": 0.5, "durationHours": ""})
    assert "30분" in half_hour and "0.5 시간" not in half_hour
    special_worker_empty = render_report({**payload, "category": "특수형태근로종사자", "target": "특수형태근로종사자 최초 노무 제공 시 교육", "attendees": ""})
    assert "별도 첨부" in special_worker_empty
    special_worker_short_target = render_report({**payload, "category": "특수형태근로종사자", "courseName": "가. 최초 노무제공 시 교육", "target": "단기간 작업 또는 간헐적 작업에 노무를 제공하는 경우"})
    assert "(특수형태 근로종사자 최초) 안전보건교육일지" in special_worker_short_target
    assert "attendee-header-row" in special_worker_short_target and special_worker_short_target.count("attendee-data-row") == 5
    supervisor_empty = render_report({**payload, "category": "관리감독자", "target": "관리감독자 정기 안전보건교육", "attendees": ""})
    assert "별도 첨부" not in supervisor_empty
    supervisor_annual = render_report({**payload, "sheet": "60", "category": "관리감독자", "content": "•산업보건 및 건강장해 예방에 관한 사항(폭염ㆍ한파작업으로 인한 건강장해 발생 시 응급조치에 관한 사항을 포함한다)"})
    assert "응급조<br>치에 관한 사항을 포함한다)" in supervisor_annual
    management_special = render_report({**payload, "template": "special", "category": "관리감독자", "target": "관리감독자 특별 안전보건교육"})
    assert "attendee-header-row" in management_special and management_special.count("attendee-data-row") == 2
    assert 'special-individual-extra-text">•<br>•<br>•</span>' in management_special
    special_worker_special = render_report({**payload, "template": "special", "category": "특수형태근로종사자", "sheet": "1-39(70)"})
    assert "attendee-header-row" in special_worker_special and special_worker_special.count("attendee-data-row") == 1
    assert '<span class="special-content-label-text">교육내용</span>' in special_worker_special
    assert "공통교육내용은 앞시간 교육 진행" not in management_special + special_worker_special
    assert "•<br>•<br>•<br>•<br>•" in render_report({**payload, "extraContent": "•"})
    noise = render_report({**payload, "category": "소음/난청", "courseName": "소음과 소음성 난청 관련 교육", "template": "regular"})
    assert "(특별) 안전보건교육일지" in noise and "제29조제3항" in noise and "개별<br>내용" in noise and noise.count("<article") == 1
    assert "attendee-header-row" in noise and noise.count("attendee-data-row") == 5
    assert multiline_tight_bullets("•항목\t\t").count("excel-tab-glyph") == 2
    heat = render_report({**payload, "category": "혹서기 온열질환", "courseName": "혹서기 온열질환 예방교육", "template": "regular"})
    assert "(특별) 안전보건교육일지" in heat and "제29조제3항" in heat and "개별<br>내용" in heat and heat.count("<article") == 1
    payload["template"] = "special"
    special = render_report(payload)
    assert "교육 참석자 명단" in special and special.count("<article") == 2
    assert "•<br>•<br>•" in special
    assert "attendee-header-row" in special and special.count("attendee-data-row") == 30
    assert "0시 00분" in special and "없음" not in special
    payload["template"] = "dual_special"
    payload["sheet"] = "1-39(2-1)"
    payload["taskName"] = "5대 이상 보유한 사업장에서 해당 기계로 하는 작업"
    payload["taskName2"] = "26. 비계의 조립·해체 또는 변경작업"
    payload["content2"] = "비계 조립순서와 추락재해 방지"
    dual = render_report(payload)
    assert "(특별 2종)" in dual and "대상작업명 2" in dual and dual.count("<article") == 3
    assert "dual-combined-content" not in dual and '<tr class="dual-extra-row"><th colspan="2"><span class="stacked-label">추가<br>내용</span></th><td colspan="23">' in dual
    assert "공통<br>내용" in dual
    assert "5대 이상 보유한 사업장에서" in dual and "5대 이상 보<br>유한 사업장에서" not in dual
    assert "홍 길 동" in dual and "김 철 수" in dual and "이 영 희" in dual
    assert "별도 첨부" not in dual
    assert dual.count('class="attendee-data-row"') == 16
    dual_empty = render_report({**payload, "attendees": ""})
    assert "홍 길 동" not in dual_empty and "별도 첨부" in dual_empty
    assert excel_extra_content("•", "dual_special").count("•") == 3
    attached_payload = sample_payload()
    image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l1aZ8QAAAABJRU5ErkJggg=="
    attached_payload["photoAttachments"] = [{"dataUrl": image, "caption": "교육사진"}]
    attached_payload["certificateAttachments"] = [{"dataUrl": image, "caption": "기초이수증"}]
    attached_payload["approvalSignatures"] = {"safety": {"dataUrl": image}, "site": {"dataUrl": image}}
    attached = render_report(attached_payload)
    assert "안전교육" in attached and "사진대지" in attached and "사 진 대 지" in attached and "approval-signature" in attached and attached.count("<article") == 3
    assert "photo-board-frame" in attached and "certificate-frame" in attached and "attachment-header-table" not in attached
    assert render_report({**attached_payload, "renderScope": "journal"}).count("<article") == 1
    photo_only = render_report({**attached_payload, "renderScope": "photos"})
    assert "photo-board-frame" in photo_only and "attachment-header-table" not in photo_only and photo_only.count('<figure class="attachment-slot') == 2
    certificate_only = render_report({**attached_payload, "renderScope": "certificates"})
    assert "사 진 대 지" in certificate_only and "certificate-frame" in certificate_only and "attachment-header-table" not in certificate_only
    assert "홍 길 동" in attached
    assert attendee_names(payload) == ["홍길동", "김철수", "이영희"]
    stats = worker_statistics()
    assert stats["summary"]["total_reports"] >= 0 and isinstance(stats["records"], list)
    test_db_path = DB_PATH
    with tempfile.TemporaryDirectory() as tmp:
        try:
            DB_PATH = Path(tmp) / "education_log.db"
            init_db()
            with connect() as con:
                course = con.execute("SELECT sheet FROM courses ORDER BY sheet LIMIT 1").fetchone()
                content = con.execute("SELECT code FROM education_content ORDER BY code LIMIT 1").fetchone()
                assert course and content
                con.execute("UPDATE courses SET target=? WHERE sheet=?", ("사용자 교육대상", course["sheet"]))
                con.execute("UPDATE education_content SET content=? WHERE code=?", ("사용자 교육내용", content["code"]))
                con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("courseDefaultsVersion", "old"))
                con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("contentDefaultsVersion", "old"))
            init_db()
            with connect() as con:
                assert con.execute("SELECT target FROM courses WHERE sheet=?", (course["sheet"],)).fetchone()["target"] == "사용자 교육대상"
                assert con.execute("SELECT content FROM education_content WHERE code=?", (content["code"],)).fetchone()["content"] == "사용자 교육내용"
            save_report({**sample_payload(), "saveDirectory": ""})
            reports = list_reports()
            assert len(reports) == 1 and str(reports[0]["educationCount"]) == "3"
            cleared = clear_reports()
            assert cleared["deletedReports"] == 1 and cleared["deletedWorkerRecords"] == 3
            assert not list_reports()
            assert worker_statistics()["summary"]["total_reports"] == 0
        finally:
            DB_PATH = test_db_path
    assert is_newer_version("1.0.4", APP_VERSION) and not is_newer_version(APP_VERSION, APP_VERSION)
    assert is_trusted_update_url(DEFAULT_UPDATE_MANIFEST_URL)
    assert not is_trusted_update_url("http://github.com/dusdk0098-tech/education-log-local-app/releases/latest/download/update.json")
    assert not is_trusted_update_url("https://example.com/update.json")
    assert not is_trusted_update_url("https://github.com/dusdk0098-tech/education-log-local-app/releases/latest/download/%5c%5cattacker")
    assert not is_trusted_update_url("https://github.com/dusdk0098-tech/education-log-local-app/releases/latest/download/%252e%252e")
    assert is_valid_sha256("a" * 64) and not is_valid_sha256("")
    with tempfile.TemporaryDirectory() as tmp:
        update_root = Path(tmp) / "update"
        runtime_dir = update_root / "PEDIT-EDU"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "PEDIT-EDU.exe").write_bytes(b"test")
        assert update_runtime_dir(update_root) == runtime_dir
        valid_zip = Path(tmp) / "update.zip"
        with zipfile.ZipFile(valid_zip, "w") as zf:
            zf.writestr("PEDIT-EDU/PEDIT-EDU.exe", "test")
        validate_update_zip(valid_zip)
        for unsafe_name in ("/escape.txt", "\\escape.txt", "C:\\escape.txt", "../escape.txt"):
            with zipfile.ZipFile(valid_zip, "w") as zf:
                zf.writestr(unsafe_name, "test")
            try:
                validate_update_zip(valid_zip)
            except RuntimeError:
                continue
            raise AssertionError(f"unsafe update ZIP path was accepted: {unsafe_name}")
    original_frozen = getattr(sys, "frozen", None)
    original_update_config = globals()["update_config"]
    try:
        sys.frozen = False
        assert not apply_startup_update()
        sys.frozen = True
        globals()["update_config"] = lambda: (_ for _ in ()).throw(RuntimeError("settings unavailable"))
        assert not apply_startup_update()
    finally:
        globals()["update_config"] = original_update_config
        if original_frozen is None:
            del sys.frozen
        else:
            sys.frozen = original_frozen
    DB_PATH = original_db_path
    temporary_db.cleanup()
    print("self-check ok")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    init_db()
    if apply_startup_update():
        return
    port = 8787
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"로컬 교육일지 앱 실행: {url}")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
