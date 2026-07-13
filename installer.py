from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

APP_NAME = "PEDIT-EDU"
ZIP_NAME = "PEDIT-EDU-1.0.3-windows.zip"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = base / name
    if candidate.exists():
        return candidate
    dist_candidate = base / "dist" / name
    return dist_candidate if dist_candidate.exists() else candidate


def validate_package_members(names: list[str]) -> None:
    for name in names:
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
            raise RuntimeError("설치 패키지에 허용되지 않는 경로가 있습니다.")


def install_to(target_dir: Path) -> Path:
    zip_path = resource_path(ZIP_NAME)
    if not zip_path.exists():
        raise FileNotFoundError(f"설치 파일 내부에서 {ZIP_NAME}을 찾지 못했습니다.")
    app_dir = target_dir / APP_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        validate_package_members(names)
        if any(name.replace("\\", "/").lower().endswith("/education_log.db") for name in names):
            raise RuntimeError("설치 패키지에 사용자 DB가 포함되어 있습니다.")
        zf.extractall(target_dir)
    exe_path = app_dir / f"{APP_NAME}.exe"
    if not exe_path.exists():
        raise FileNotFoundError("설치 후 실행파일을 찾지 못했습니다.")
    return exe_path


def create_desktop_shortcut(exe_path: Path) -> None:
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    if not desktop.exists():
        return
    shortcut = desktop / f"{APP_NAME}.lnk"
    ps = "\n".join(
        [
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut('{shortcut}')",
            f"$shortcut.TargetPath = '{exe_path}'",
            f"$shortcut.WorkingDirectory = '{exe_path.parent}'",
            f"$shortcut.IconLocation = '{exe_path},0'",
            "$shortcut.Save()",
        ]
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def self_check() -> None:
    zip_path = resource_path(ZIP_NAME)
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    validate_package_members(list(names))
    required = {
        f"{APP_NAME}/{APP_NAME}.exe",
        f"{APP_NAME}/_internal/static/index.html",
        f"{APP_NAME}/_internal/static/app.js",
        f"{APP_NAME}/_internal/static/styles.css",
        f"{APP_NAME}/_internal/static/app.ico",
        f"{APP_NAME}/_internal/static/pedit-edu-logo.png",
        f"{APP_NAME}/_internal/static/fonts/H2HDRM.TTF",
    }
    missing = required - names
    if missing:
        raise RuntimeError(f"설치 패키지 누락: {', '.join(sorted(missing))}")
    if any(name.replace("\\", "/").lower().endswith("/education_log.db") for name in names):
        raise RuntimeError("설치 패키지에 사용자 DB가 포함되어 있습니다.")
    with tempfile.TemporaryDirectory() as tmp:
        unsafe_zip = Path(tmp) / "unsafe.zip"
        for unsafe_name in ("/escape.txt", "\\escape.txt", "C:\\escape.txt", "../escape.txt"):
            with zipfile.ZipFile(unsafe_zip, "w") as zf:
                zf.writestr(unsafe_name, "test")
            try:
                with zipfile.ZipFile(unsafe_zip) as zf:
                    validate_package_members(zf.namelist())
            except RuntimeError:
                continue
            raise AssertionError(f"unsafe installer ZIP path was accepted: {unsafe_name}")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    if "--install-dir" in sys.argv:
        index = sys.argv.index("--install-dir")
        try:
            target_dir = Path(sys.argv[index + 1])
        except IndexError as exc:
            raise SystemExit("--install-dir 경로가 필요합니다.") from exc
        install_to(target_dir)
        return

    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.withdraw()
    default_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
    target = filedialog.askdirectory(
        title=f"{APP_NAME} 설치 위치 선택",
        initialdir=str(default_dir.parent),
    )
    if not target:
        return
    try:
        exe_path = install_to(Path(target))
        create_desktop_shortcut(exe_path)
    except Exception as error:
        messagebox.showerror(f"{APP_NAME} 설치 실패", str(error))
        raise
    if messagebox.askyesno(f"{APP_NAME} 설치 완료", "설치가 완료되었습니다. 지금 실행할까요?"):
        subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))


if __name__ == "__main__":
    main()
