#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT_DIR / ".conda-env"
PATH_LINE = 'export PATH="$HOME/.local/bin:$PATH"'


def is_windows() -> bool:
    return os.name == "nt"


def env_python() -> Path:
    if is_windows():
        return ENV_DIR / "python.exe"
    return ENV_DIR / "bin" / "python"


def find_conda_command() -> str | None:
    for name in ("mamba", "conda"):
        path = shutil.which(name)
        if path:
            return path
    return None


def windows_conda_candidate_roots() -> list[Path]:
    roots: list[Path] = []

    def add(path: Path | None) -> None:
        if path is None:
            return
        resolved = path.expanduser()
        if resolved not in roots:
            roots.append(resolved)

    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", "")) if os.environ.get("LOCALAPPDATA") else None
    program_data = Path(os.environ.get("ProgramData", "")) if os.environ.get("ProgramData") else None

    for base in (home, local_app_data, program_data):
        if base is None:
            continue
        add(base / "miniforge3")
        add(base / "mambaforge")
        add(base / "Miniconda3")
        add(base / "Anaconda3")
        add(base / "miniconda3")
        add(base / "anaconda3")

    return roots


def windows_conda_path_entries(root: Path) -> list[Path]:
    return [
        root,
        root / "condabin",
        root / "Scripts",
        root / "Library" / "bin",
    ]


def update_windows_user_path(paths: list[Path]) -> None:
    import winreg

    normalized = [str(path) for path in paths if path.exists()]
    if not normalized:
        return

    current_path = os.environ.get("PATH", "")
    current_entries = [entry for entry in current_path.split(";") if entry]
    merged_current = current_entries[:]
    for entry in reversed(normalized):
        if entry not in merged_current:
            merged_current.insert(0, entry)
    os.environ["PATH"] = ";".join(merged_current)

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        try:
            existing_path, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            existing_path, value_type = "", winreg.REG_EXPAND_SZ
        entries = [entry for entry in existing_path.split(";") if entry]
        for entry in reversed(normalized):
            if entry not in entries:
                entries.insert(0, entry)
        winreg.SetValueEx(key, "Path", 0, value_type, ";".join(entries))


def ensure_windows_conda_on_path() -> str | None:
    manager = find_conda_command()
    if manager:
        return manager

    for root in windows_conda_candidate_roots():
        if not root.exists():
            continue
        update_windows_user_path(windows_conda_path_entries(root))
        manager = find_conda_command()
        if manager:
            return manager
    return None


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(ROOT_DIR), text=True, check=check)


def ensure_environment(manager: str) -> Path:
    python_bin = env_python()
    packages = ["python=3.11", "pythonocc-core", "pip"]
    extra_packages = [] if is_windows() else ["fzf", "fd-find"]

    if not python_bin.exists():
        print("[1/4] Creating project environment")
        run([manager, "create", "-y", "-p", str(ENV_DIR), *packages, *extra_packages])
    else:
        print("[1/4] Project environment already exists")

    print("[2/4] Verifying pythonOCC")
    verify = subprocess.run([str(python_bin), "-c", "import OCC"], cwd=str(ROOT_DIR))
    if verify.returncode != 0:
        run([manager, "install", "-y", "-p", str(ENV_DIR), "pythonocc-core", "pip", *extra_packages])
        run([str(python_bin), "-c", "import OCC"])

    if not is_windows():
        fzf_bin = ENV_DIR / "bin" / "fzf"
        fd_bin = ENV_DIR / "bin" / "fd"
        fdfind_bin = ENV_DIR / "bin" / "fdfind"
        if not fzf_bin.exists() or (not fd_bin.exists() and not fdfind_bin.exists()):
            run([manager, "install", "-y", "-p", str(ENV_DIR), "fzf", "fd-find"])

    return python_bin


def ensure_unix_launcher() -> None:
    print("[3/4] Installing terminal launcher")
    user_bin = Path.home() / ".local" / "bin"
    user_bin.mkdir(parents=True, exist_ok=True)
    link_path = user_bin / "run"
    if link_path.exists() or link_path.is_symlink():
        link_path.unlink()
    link_path.symlink_to(ROOT_DIR / "run")

    for profile_name in (".zshrc", ".zprofile", ".bashrc", ".profile"):
        profile = Path.home() / profile_name
        profile.touch(exist_ok=True)
        content = profile.read_text()
        if PATH_LINE not in content:
            with profile.open("a") as handle:
                if content and not content.endswith("\n"):
                    handle.write("\n")
                handle.write(PATH_LINE + "\n")

    os.environ["PATH"] = f"{user_bin}{os.pathsep}{os.environ.get('PATH', '')}"


def _windows_cmd_wrapper() -> str:
    cli_script = ROOT_DIR / "src" / "dfm_cli.py"
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f"set \"CLI_SCRIPT={cli_script}\"\r\n"
        "where python >nul 2>nul\r\n"
        "if %ERRORLEVEL% EQU 0 (\r\n"
        "  python \"%CLI_SCRIPT%\" %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "where py >nul 2>nul\r\n"
        "if %ERRORLEVEL% EQU 0 (\r\n"
        "  py -3 \"%CLI_SCRIPT%\" %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "echo Python 3 is required to run cnc-dfm.\r\n"
        "exit /b 1\r\n"
    )


def _windows_ps1_wrapper() -> str:
    cli_script = ROOT_DIR / "src" / "dfm_cli.py"
    return (
        '$ErrorActionPreference = "Stop"\r\n'
        f'$cliScript = "{cli_script}"\r\n'
        "if (Get-Command python -ErrorAction SilentlyContinue) {\r\n"
        "    & python $cliScript @args\r\n"
        "    exit $LASTEXITCODE\r\n"
        "}\r\n"
        "if (Get-Command py -ErrorAction SilentlyContinue) {\r\n"
        "    & py -3 $cliScript @args\r\n"
        "    exit $LASTEXITCODE\r\n"
        "}\r\n"
        'Write-Host "Python 3 is required to run cnc-dfm."\r\n'
        "exit 1\r\n"
    )


def ensure_windows_path(user_bin: Path) -> None:
    update_windows_user_path([user_bin])


def ensure_windows_launcher() -> None:
    print("[3/4] Installing terminal launcher")
    user_bin = Path.home() / ".local" / "bin"
    user_bin.mkdir(parents=True, exist_ok=True)
    (user_bin / "run.cmd").write_text(_windows_cmd_wrapper(), newline="")
    (user_bin / "run.ps1").write_text(_windows_ps1_wrapper(), newline="")
    ensure_windows_path(user_bin)


def main() -> int:
    print("Checking package manager tooling")
    manager = ensure_windows_conda_on_path() if is_windows() else find_conda_command()
    if manager is None:
        if is_windows():
            print("Miniforge/Conda is required. Install it, then re-run this script.")
            print("The installer checked common Miniforge, Mambaforge, Miniconda, and Anaconda locations but did not find a usable conda or mamba executable.")
        else:
            print("Mamba or Conda is required. Install Miniforge or Conda, then re-run this script.")
        return 1

    ensure_environment(manager)
    if is_windows():
        ensure_windows_launcher()
        shell_hint = "Open a new PowerShell window if 'run' is not visible yet."
    else:
        ensure_unix_launcher()
        shell_hint = "Run 'source ~/.zshrc' if 'run' is not visible yet."

    print("[4/4] Final checks")
    print("Install complete.")
    print(shell_hint)
    print("Use:")
    print("  run config")
    print("  cd /path/to/parts")
    print("  run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
