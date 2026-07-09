from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APP_NAME = "PEDIT-EDU"
ZIP_NAME = "PEDIT-EDU-1.0.2-windows.zip"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = base / name
    if candidate.exists():
        return candidate
    dist_candidate = base / "dist" / name
    return dist_candidate if dist_candidate.exists() else candidate


def install_to(target_dir: Path) -> Path:
    zip_path = resource_path(ZIP_NAME)
    if not zip_path.exists():
        raise FileNotFoundError(f"설치 파일 내부에서 {ZIP_NAME}을 찾지 못했습니다.")
    app_dir = target_dir / APP_NAME
    if app_dir.exists():
        shutil.rmtree(app_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
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
    required = {
        f"{APP_NAME}/{APP_NAME}.exe",
        f"{APP_NAME}/_internal/static/index.html",
        f"{APP_NAME}/_internal/static/app.js",
        f"{APP_NAME}/_internal/static/styles.css",
        f"{APP_NAME}/_internal/static/app.ico",
    }
    missing = required - names
    if missing:
        raise RuntimeError(f"설치 패키지 누락: {', '.join(sorted(missing))}")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
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
