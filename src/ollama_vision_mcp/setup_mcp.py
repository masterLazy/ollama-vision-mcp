"""Interactive MCP setup for ollama-vision-mcp.

Detects the local environment — this repo's virtualenv and the Ollama models
already on the machine — then interactively walks through each bridge setting
and writes a ready-to-use ``mcp.json`` for VS Code Copilot (project-local,
user-global, or both). Existing ``mcp.json`` files are merged, so any other MCP
servers you already registered are left untouched.

Pure standard library: the only network access is a read-only HTTP probe of the
local Ollama server (``/v1/models``, then ``/api/tags``), with ``ollama list``
as a fallback when the server is down.

Run any of:

    python setup_mcp.py                     # from the repo root (pre-install)
    python -m ollama_vision_mcp.setup_mcp   # installed package
    ollama-vision-setup                     # installed console script

Non-interactive (CI / scripting):

    ollama-vision-setup --yes --project --model qwen2.5vl:7b
    ollama-vision-setup --print             # show the JSON, write nothing
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SERVER_NAME_DEFAULT = "ollama-vision"
PACKAGE = "ollama_vision_mcp"

# Keep in sync with config.py defaults (and .env.example / README).
DEFAULTS = {
    "base_url": "http://localhost:11434/v1",
    "model": "qwen2.5vl:7b",
    "inbox": ".ai/inbox",
    "max_tokens": 2048,
    "compress": True,
    "think": False,
    "api_key": "",
}

# Substrings that usually mean an Ollama model can understand images.
VISION_HINTS = (
    "vl", "vision", "llava", "bakllava", "moondream", "minicpm",
    "gemma3", "phi3", "llama3.2-vision", "gpt-4o", "pixtral",
)


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    # Source checkout: <repo>/src/ollama_vision_mcp/setup_mcp.py -> parents[2].
    candidates = (here.parents[2], Path.cwd())
    for cand in candidates:
        if (cand / "src" / PACKAGE).is_dir():
            return cand
    return here.parents[2]


REPO_ROOT = _find_repo_root()


def detect_python() -> Path:
    """Prefer this repo's virtualenv, else the interpreter running this script."""
    for cand in (
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "bin" / "python",
    ):
        if cand.is_file():
            return cand
    return Path(sys.executable)


def _http_get_json(url: str, timeout: float = 4.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _native_tags_url(base_url: str) -> str:
    parts = urllib.parse.urlsplit(base_url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/api/tags", "", ""))


def _ollama_list_models() -> list[str]:
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
    except Exception:
        return []
    models = []
    for line in out.stdout.splitlines()[1:]:  # skip the header row
        if line.strip():
            models.append(line.split(None, 1)[0])
    return models


def detect_ollama_models(base_url: str) -> tuple[bool, list[str], str]:
    """Return (ok, models, error).

    Probes the OpenAI-compatible ``/v1/models`` first (the endpoint this bridge
    uses), then the native ``/api/tags``, then falls back to ``ollama list``.
    """
    data = _http_get_json(base_url.rstrip("/") + "/models")
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        models = [
            m.get("id", "")
            for m in data["data"]
            if isinstance(m, dict) and m.get("id")
        ]
        return True, models, ""
    data = _http_get_json(_native_tags_url(base_url))
    if isinstance(data, dict) and isinstance(data.get("models"), list):
        models = [
            m.get("name", "")
            for m in data["models"]
            if isinstance(m, dict) and m.get("name")
        ]
        return True, models, ""
    cli = _ollama_list_models()
    if cli:
        return True, cli, ""
    return False, [], (
        "Ollama is not reachable (is `ollama serve` running?) and `ollama list` "
        "returned nothing."
    )


def is_likely_vision(model: str) -> bool:
    name = model.lower()
    return any(hint in name for hint in VISION_HINTS)


# ---------------------------------------------------------------------------
# Console styling (ANSI; disabled when piped or NO_COLOR is set)
# ---------------------------------------------------------------------------

_USE_COLOR = False


def _enable_vt_windows() -> bool:
    """Enable ANSI escape processing on the Windows console (Win10+)."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        return True
    except Exception:
        return False


def _init_color() -> None:
    global _USE_COLOR
    if os.environ.get("NO_COLOR"):
        return
    if not (sys.stdout and sys.stdout.isatty()):
        return
    if os.name == "nt" and not _enable_vt_windows():
        return
    _USE_COLOR = True


def style(text: str, *codes: str) -> str:
    """Wrap ``text`` in ANSI SGR codes; returns plain text when color is off."""
    if not _USE_COLOR or not codes:
        return text
    return "\033[" + ";".join(codes) + "m" + text + "\033[0m"


def p_title(text: str) -> None:
    print(style(text, "1", "36"))  # bold cyan


def p_heading(text: str) -> None:
    print(style(text, "1", "4"))  # bold + underline


def p_ok(text: str) -> None:
    print(style(text, "32"))  # green


def p_warn(text: str) -> None:
    print(style(text, "1", "33"))  # bold yellow


def p_error(text: str) -> None:
    print(style(text, "1", "31"))  # bold red


def p_dim(text: str) -> None:
    print(style(text, "90"))  # dim


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def _ask(prompt: str, default: str = "") -> str:
    label = style(f"  {prompt}", "1", "36")
    hint = style(f" [{default}]", "2") if default else ""
    try:
        raw = input(f"{label}{hint}: ").strip()
    except EOFError:  # Ctrl+Z / closed stdin — keep non-interactive use working
        print()
        return default
    return raw or default


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            p_warn(f"    ! '{raw}' is not an integer.")


def _confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    label = style(f"  {prompt}", "1", "36")
    try:
        raw = input(f"{label} [{hint}] ").strip().lower()
    except EOFError:  # Ctrl+Z / closed stdin — keep non-interactive use working
        print()
        return default
    if not raw:
        return default
    return raw in ("y", "yes")


def choose_model(models: list[str], current_default: str) -> str:
    vision = [m for m in models if is_likely_vision(m)]
    if not models:
        p_warn("    (no local models detected — pick a name now and `ollama pull` it later)")
        return _ask("Vision model", current_default)
    if vision:
        p_ok(f"    Vision-capable models found: {len(vision)}")
    else:
        p_warn(
            "    NOTE: none of your local models look vision-capable "
            "(names usually contain 'vl', 'vision', 'llava', ...)."
        )
    pool = vision or models
    for i, m in enumerate(pool, 1):
        tag = style(" (vision)", "32") if m in vision else ""
        print(f"      {i}. {m}{tag}")
    default = vision[0] if vision else (current_default if current_default in pool else pool[0])
    while True:
        raw = _ask("Vision model", default)
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(pool):
                return pool[idx - 1]
            p_warn(f"      ! {idx} is out of range 1..{len(pool)}")
            continue
        return raw


# ---------------------------------------------------------------------------
# Config building / writing
# ---------------------------------------------------------------------------

def build_env(
    base_url: str,
    model: str,
    inbox: str,
    max_tokens: int,
    compress: bool,
    api_key: str,
    think: bool,
) -> dict[str, str]:
    env = {
        "VISION_MCP_BASE_URL": base_url.rstrip("/"),
        "VISION_MCP_MODEL": model,
        "VISION_MCP_INBOX": inbox,
        "VISION_MCP_MAX_TOKENS": str(max_tokens),
        "VISION_MCP_COMPRESS": "1" if compress else "0",
        "VISION_MCP_THINK": "1" if think else "0",
    }
    if api_key:
        env["VISION_MCP_API_KEY"] = api_key
    return env


def build_server_entry(python: Path, env: dict[str, str]) -> dict:
    # as_posix() yields forward slashes on Windows — clean JSON, no escaping.
    return {
        "type": "stdio",
        "command": python.as_posix(),
        "args": ["-m", PACKAGE],
        "env": env,
    }


def user_mcp_path() -> Path:
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Code" / "User" / "mcp.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    return Path.home() / ".config" / "Code" / "User" / "mcp.json"


def _read_mcp_data(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        # utf-8-sig tolerates a UTF-8 BOM (common from Windows editors/tools).
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        p_error(f"    ! Could not parse {path}; it will be recreated from scratch.")
        return {}
    return data if isinstance(data, dict) else {}


def write_mcp_json(path: Path, server_name: str, entry: dict) -> None:
    """Merge ``entry`` into ``path`` under ``server_name``, preserving other servers."""
    data = _read_mcp_data(path)
    servers = data.get("servers")
    if not isinstance(servers, dict):
        servers = {}
        data["servers"] = servers
    action = "updated" if server_name in servers else "added"
    servers[server_name] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    p_ok(f"  Done! {action} '{server_name}' in {path}")


def _choose_target_key(project_path: Path, global_path: Path) -> str:
    print("\n  Where should the config be written?")
    print(f"    1. Project     -> {project_path}")
    print(f"    2. User-global -> {global_path}  (available in every project)")
    print("    3. Both")
    print("    4. Print only  -> no files are changed")
    while True:
        raw = _ask("Choose", "1")
        if raw in ("1", "2", "3", "4"):
            return {"1": "project", "2": "user", "3": "both", "4": "print"}[raw]
        print("    ! Enter 1, 2, 3 or 4.")


def _run_smoke_test(python: Path, env: dict[str, str]) -> None:
    smoke = REPO_ROOT / "examples" / "smoke_test.py"
    if not smoke.is_file():
        p_warn("  ! examples/smoke_test.py not found; skipping.")
        return
    run_env = dict(os.environ)
    src = str(REPO_ROOT / "src")
    run_env["PYTHONPATH"] = src + os.pathsep + run_env.get("PYTHONPATH", "")
    run_env.update(env)
    print(f"\n  Running: {python} examples/smoke_test.py")
    try:
        proc = subprocess.run([str(python), str(smoke)], cwd=REPO_ROOT, env=run_env)
    except OSError as e:
        p_error(f"  ! Could not run the smoke test: {e}")
        return
    if proc.returncode != 0:
        p_error(f"  ! Smoke test exited with code {proc.returncode}.")


def _package_installed_in(python: Path) -> bool:
    """True if ``python`` can import the package the way the generated config
    will launch it (no extra PYTHONPATH on the command line)."""
    code = (
        "import importlib.util; "
        f"print(importlib.util.find_spec('{PACKAGE}') is not None)"
    )
    try:
        out = subprocess.run(
            [str(python), "-c", code],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        return False
    return out.returncode == 0 and out.stdout.strip().endswith("True")


def _install_editable(python: Path) -> bool:
    cmd = [str(python), "-m", "pip", "install", "-e", str(REPO_ROOT)]
    print(f"\n  Running: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd)
    except OSError as e:
        p_error(f"  ! Could not run pip: {e}")
        return False
    return proc.returncode == 0


def _warn_and_offer_install(python: Path) -> bool:
    """Warn that the target interpreter lacks the package and offer to install
    it (editable) into that environment. Returns True if it is installed now."""
    p_error(f"\n  !! '{PACKAGE}' is NOT installed in {python}")
    p_warn("     The generated config will not start until it is installed:")
    p_warn(f"       {python} -m pip install -e {REPO_ROOT}")
    if _confirm("     Install it into this environment now?", False):
        if _install_editable(python):
            p_ok("  Installed — continuing.")
            return True
        p_error("  Install failed. You can install it later with the command above.")
    return False


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _setup_venv(venv_dir: Path) -> bool:
    """Create ``venv_dir`` (if missing) and pip-install the package into it."""
    created = False
    if not _venv_python(venv_dir).is_file():
        print(f"\n  Creating virtualenv: {venv_dir}")
        try:
            proc = subprocess.run([str(Path(sys.executable)), "-m", "venv", str(venv_dir)])
        except OSError as e:
            p_error(f"  ! Could not create the virtualenv: {e}")
            return False
        if proc.returncode != 0:
            p_error("  ! Failed to create the virtualenv.")
            return False
        created = True
    venv_python = _venv_python(venv_dir)
    if _package_installed_in(venv_python):
        if created:
            p_ok("  Virtualenv created.")
        return True
    if not _install_editable(venv_python):
        p_error("  ! Failed to install the package into the virtualenv.")
        return False
    p_ok("  Virtualenv ready — package installed.")
    return True


def _is_base_interpreter(python: Path) -> bool:
    """True if ``python`` is a global/base interpreter (not a virtualenv)."""
    code = "import sys; print(sys.prefix == sys.base_prefix)"
    try:
        out = subprocess.run([str(python), "-c", code], capture_output=True, text=True, timeout=15)
    except Exception:
        return True  # assume base on failure
    return out.returncode == 0 and out.stdout.strip() == "True"


def _ensure_environment(python: Path, interactive: bool, allow_setup: bool = True) -> Path:
    """Return a Python interpreter that has the package installed.

    Prefers an existing repo virtualenv. If the current interpreter is a global/
    base one (even when the package is already installed there), the default is
    to set up a dedicated virtualenv so nothing leaks into the system Python —
    interactive mode asks first, non-interactive mode does it automatically.
    ``allow_setup=False`` (e.g. ``--print``) never touches the environment.
    """
    venv_dir = REPO_ROOT / ".venv"
    venv_python = _venv_python(venv_dir)

    if venv_dir.is_dir() and _package_installed_in(venv_python):
        p_ok(f"  Using existing virtualenv: {venv_python}")
        return venv_python
    if _package_installed_in(python) and not _is_base_interpreter(python):
        return python  # an existing virtualenv already works

    if _package_installed_in(python):
        p_warn(f"\n  {python} is a global interpreter ({PACKAGE} is installed there).")
        p_warn("  Prefer a dedicated virtualenv so the package does not live in your system Python.")
    else:
        p_warn(f"\n  '{PACKAGE}' is not installed in {python}.")

    if interactive:
        if _confirm(
            f"  Create a dedicated virtualenv ({venv_dir}) and install the package into it?",
            True,
        ):
            if _setup_venv(venv_dir):
                return venv_python
            p_error("  Virtualenv setup failed — you can still pick an interpreter manually.")
        p = Path(
            _ask("Python interpreter (must have ollama_vision_mcp installed)", str(python))
        ).expanduser()
        if not _package_installed_in(p):
            _warn_and_offer_install(p)
        return p

    if not allow_setup:
        return python  # preview only (--print)
    p_warn(f"  Creating a dedicated virtualenv: {venv_dir}")
    if _setup_venv(venv_dir):
        return venv_python
    return python


def _configure_io() -> None:
    """Write UTF-8 to the console even under a legacy (GBK/CP1252) code page."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ollama-vision-setup",
        description="Interactive setup for ollama-vision-mcp: detects your local "
                    "Ollama models and writes a ready-to-use mcp.json for VS Code.",
    )
    p.add_argument("--python", help="Python interpreter that has ollama_vision_mcp installed")
    p.add_argument("--base-url", help="OpenAI-compatible Ollama base URL")
    p.add_argument("--model", help="Vision model to use")
    p.add_argument("--api-key", help="API key (Ollama ignores it; empty -> 'ollama')")
    p.add_argument("--inbox", help="Inbox directory, relative to the project")
    p.add_argument("--max-tokens", type=int, help="Max output tokens")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--compress", dest="compress", action="store_true", help="Compress large images (default)")
    grp.add_argument("--no-compress", dest="compress", action="store_false", help="Disable image compression")
    p.add_argument("--server-name", default=SERVER_NAME_DEFAULT, help="MCP server name in mcp.json")
    grp2 = p.add_mutually_exclusive_group()
    grp2.add_argument("--project", dest="target", action="store_const", const="project",
                      help="Write to .vscode/mcp.json in the current folder")
    grp2.add_argument("--user", dest="target", action="store_const", const="user",
                      help="Write to the user-global mcp.json")
    grp2.add_argument("--both", dest="target", action="store_const", const="both",
                      help="Write to both files")
    grp2.add_argument("--print", dest="target", action="store_const", const="print",
                      help="Print the config JSON without writing")
    p.add_argument("--user-mcp", help="Override the user-global mcp.json path")
    p.add_argument("--yes", "-y", action="store_true", help="Accept detected defaults (non-interactive)")
    grp3 = p.add_mutually_exclusive_group()
    grp3.add_argument("--think", dest="think", action="store_true",
                      help="Keep thinking/reasoning enabled (for thinking models)")
    grp3.add_argument("--no-think", dest="think", action="store_false",
                      help="Disable thinking via reasoning_effort=none (default)")
    p.set_defaults(compress=None, think=None)
    return p.parse_args(argv)


def _run(argv: list[str] | None) -> int:
    _configure_io()
    args = _parse_args(argv)
    _init_color()

    p_title("=" * 62)
    p_title("  ollama-vision-mcp — interactive MCP setup")
    p_title("=" * 62)

    python = Path(args.python).expanduser() if args.python else detect_python()
    print()
    p_heading("Detected environment")
    print(f"    Repo root : {REPO_ROOT}")
    print(f"    Python    : {python}")

    base_url = (args.base_url or DEFAULTS["base_url"]).rstrip("/")
    ok, models, err = detect_ollama_models(base_url)
    if models:
        print(f"    Ollama    : {style('reachable', '32')} — {len(models)} model(s):")
        for m in models:
            tag = style(" (vision)", "32") if is_likely_vision(m) else ""
            print(f"      - {m}{tag}")
    else:
        print(f"    Ollama    : {style('NOT reachable', '1', '31')} — {err}")

    # ---- settings ----------------------------------------------------------
    if not args.yes:
        p_heading("Configure the bridge")
        python = _ensure_environment(python, interactive=True)
        installed = _package_installed_in(python)
        base_url = _ask("Base URL", base_url).rstrip("/") or DEFAULTS["base_url"]
        model = args.model or choose_model(models, DEFAULTS["model"])
        inbox = args.inbox or _ask("Inbox dir (screenshots live here)", DEFAULTS["inbox"])
        max_tokens = args.max_tokens or _ask_int("Max tokens", DEFAULTS["max_tokens"])
        compress = args.compress
        if compress is None:
            compress = _confirm("Auto-compress large images (>50KB) to 768px JPEG?", True)
        think = args.think
        if think is None:
            think = not _confirm("Disable thinking for thinking models (faster, avoids empty replies)?", True)
        api_key = args.api_key if args.api_key is not None else _ask("API key (empty = 'ollama')", "")
    else:
        python = _ensure_environment(
            python, interactive=False, allow_setup=(args.target != "print")
        )
        installed = _package_installed_in(python)
        vision = [m for m in models if is_likely_vision(m)]
        model = args.model or (vision[0] if vision else DEFAULTS["model"])
        inbox = args.inbox or DEFAULTS["inbox"]
        max_tokens = args.max_tokens or DEFAULTS["max_tokens"]
        compress = DEFAULTS["compress"] if args.compress is None else args.compress
        think = DEFAULTS["think"] if args.think is None else args.think
        api_key = args.api_key or ""

    env = build_env(base_url, model, inbox, max_tokens, compress, api_key, think)
    entry = build_server_entry(python, env)
    server_name = args.server_name or SERVER_NAME_DEFAULT

    # ---- target selection ---------------------------------------------------
    project_path = Path(os.getcwd()) / ".vscode" / "mcp.json"
    global_path = Path(args.user_mcp).expanduser() if args.user_mcp else user_mcp_path()

    if args.target is None:
        target = "project" if args.yes else _choose_target_key(project_path, global_path)
    else:
        target = args.target
    targets = {
        "project": [project_path],
        "user": [global_path],
        "both": [project_path, global_path],
        "print": [],
    }[target]

    # ---- summary ------------------------------------------------------------
    print()
    p_heading("Summary")
    print(f"    server name : {server_name}")
    print(f"    command     : {entry['command']} -m {PACKAGE}")
    for key, val in env.items():
        print(f"    {key: <22}: {val}")
    if not installed:
        p_warn("    !! package NOT installed in the target interpreter:")
        p_warn(f"       {python} -m pip install -e {REPO_ROOT}")

    if target == "print":
        print()
        p_heading("Config JSON")
        print(json.dumps({"servers": {server_name: entry}}, indent=2, ensure_ascii=False))
    elif args.yes or _confirm("\n  Write the configuration now?", True):
        for path in targets:
            write_mcp_json(path, server_name, entry)
        if len(targets) > 1:
            print("  (other MCP servers in those files were left untouched)")
    else:
        p_warn("  Aborted — nothing was written.")
        return 1

    # ---- next steps ----------------------------------------------------------
    print()
    p_heading("Next steps")
    if not installed:
        print("    0. Install the package first:")
        print(f"         {python} -m pip install -e {REPO_ROOT}")
    print("    1. Reload the VS Code window: Ctrl+Shift+P -> 'Developer: Reload Window'.")
    print("    2. Open Copilot Chat in Agent mode and run:  vision_status")
    print("       Expected: \"ollama\": { \"ok\": true, ... } plus your model list.")
    if not ok:
        print("    3. Start Ollama and pull a vision model:")
        print("         ollama serve")
        print(f"         ollama pull {model}")
    elif model not in models:
        print(f"    3. '{model}' is not installed yet — pull it:")
        print(f"         ollama pull {model}")

    if not args.yes and _confirm("\n  Run the smoke test now (uses these settings)?", False):
        _run_smoke_test(python, env)

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point — turns Ctrl+C into a clean abort instead of a traceback."""
    try:
        return _run(argv)
    except KeyboardInterrupt:
        print()
        p_warn("  Aborted by user (Ctrl+C).")
        return 130


if __name__ == "__main__":
    sys.exit(main())
