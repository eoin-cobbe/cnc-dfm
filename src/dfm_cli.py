#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT_DIR / ".conda-env"


def env_python() -> Path:
    if os.name == "nt":
        return ENV_DIR / "python.exe"
    return ENV_DIR / "bin" / "python"


def ensure_env_python() -> Path:
    python_bin = env_python()
    if python_bin.exists():
        return python_bin
    install_hint = "powershell -ExecutionPolicy Bypass -File .\\scripts\\install.ps1" if os.name == "nt" else "./scripts/install.sh"
    raise SystemExit(
        f"Environment not found at {python_bin}.\n"
        f"Run {install_hint} from the repo root first."
    )


def run_env_command(*args: str) -> int:
    python_bin = ensure_env_python()
    cmd = [str(python_bin), *args]
    return subprocess.call(cmd, cwd=str(ROOT_DIR))


def load_saved_config_args() -> list[str]:
    python_bin = ensure_env_python()
    cmd = [str(python_bin), str(ROOT_DIR / "src" / "dfm_config.py"), "--print-args"]
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, check=True)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines


def has_qty_arg(args: list[str]) -> bool:
    return any(arg == "--qty" or arg.startswith("--qty=") for arg in args)


def prompt_qty() -> list[str]:
    if not sys.stdin.isatty():
        return []
    while True:
        raw = input("qty: ").strip()
        if raw.isdigit() and int(raw) >= 1:
            return ["--qty", raw]
        print("Please enter a whole number >= 1.")


def _find_fzf_binary() -> str | None:
    env_fzf = ENV_DIR / "bin" / "fzf"
    if env_fzf.exists():
        return str(env_fzf)
    system_fzf = shutil.which("fzf")
    if system_fzf:
        return system_fzf
    return None


def _find_fd_binary() -> str | None:
    for candidate in (ENV_DIR / "bin" / "fd", ENV_DIR / "bin" / "fdfind"):
        if candidate.exists():
            return str(candidate)
    for name in ("fd", "fdfind"):
        system_fd = shutil.which(name)
        if system_fd:
            return system_fd
    return None


def _pick_step_file_with_fzf() -> str | None:
    fzf_bin = _find_fzf_binary()
    if not fzf_bin:
        return None

    fd_bin = _find_fd_binary()
    if fd_bin:
        finder = subprocess.run(
            [fd_bin, "--type", "f", "--extension", "step", "--extension", "stp", ".", str(Path.cwd())],
            capture_output=True,
            text=True,
            check=True,
        )
        candidates = finder.stdout
    else:
        candidates = "\n".join(
            sorted(
                str(path)
                for path in Path.cwd().rglob("*")
                if path.is_file() and path.suffix.lower() in {".step", ".stp"}
            )
        )

    if not candidates.strip():
        return None

    result = subprocess.run(
        [fzf_bin, "--height=50%", "--layout=reverse", "--border", "--prompt=Select STEP file > "],
        input=candidates,
        capture_output=True,
        text=True,
        check=False,
    )
    selection = result.stdout.strip()
    return selection or None


def pick_step_file() -> str | None:
    if os.name != "nt":
        selection = _pick_step_file_with_fzf()
        if selection:
            return selection

    candidates = sorted(
        str(path)
        for path in Path.cwd().rglob("*")
        if path.is_file() and path.suffix.lower() in {".step", ".stp"}
    )
    if not candidates:
        return None
    print("Select STEP file:")
    for idx, candidate in enumerate(candidates, start=1):
        print(f"  {idx}) {candidate}")
    raw = input("Enter number: ").strip()
    if not raw.isdigit():
        return None
    selected = int(raw)
    if selected < 1 or selected > len(candidates):
        return None
    return candidates[selected - 1]


def maybe_expand_step_arg(args: list[str]) -> list[str]:
    if args:
        return args
    if not sys.stdin.isatty():
        raise SystemExit("Usage: run /path/to/file.step [extra dfm args]")
    selection = pick_step_file()
    if not selection:
        raise SystemExit("No STEP file selected.")
    return [selection]


def dispatch(argv: list[str]) -> int:
    if argv and argv[0] in {"config", "configure", "init"}:
        return run_env_command(str(ROOT_DIR / "src" / "dfm_config.py"), "--wizard", *argv[1:])

    if argv and argv[0] == "show-config":
        return run_env_command(str(ROOT_DIR / "src" / "dfm_config.py"), "--show", *argv[1:])

    argv = maybe_expand_step_arg(argv)
    step_file = Path(argv[0]).expanduser().resolve()
    extra_args = argv[1:]

    if not step_file.is_file():
        raise SystemExit(f"STEP file not found: {step_file}")

    cmd = [
        str(ensure_env_python()),
        str(ROOT_DIR / "src" / "dfm_check.py"),
        str(step_file),
        *load_saved_config_args(),
    ]
    if not has_qty_arg(extra_args):
        cmd.extend(prompt_qty())
    cmd.extend(extra_args)
    return subprocess.call(cmd, cwd=str(ROOT_DIR))


def main() -> int:
    return dispatch(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
