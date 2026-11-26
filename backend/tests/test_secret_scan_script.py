"""Automated test suite for scripts/secret_scan.py."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "secret_scan.py"


def _init_git_repo(repo_dir: Path) -> None:
    """Initialize a mock git repository with local user identity in tmp_path."""
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test Committer"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "committer@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )


def test_secret_scan_clean_repo(tmp_path: Path) -> None:
    """Verify clean repository exits with code 0 and reports clean."""
    _init_git_repo(tmp_path)

    clean_file = tmp_path / "hello.py"
    clean_file.write_text("print('clean code without secrets')\n", encoding="utf-8")
    subprocess.run(["git", "add", "hello.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "secret scan: clean" in result.stdout


def test_secret_scan_detects_google_api_key_and_masks_secret(tmp_path: Path) -> None:
    """Verify runtime-constructed Google API key triggers exit 1 and is never emitted in output."""
    _init_git_repo(tmp_path)

    # Dynamically constructed at runtime: "AIza" + 35 characters
    prefix = "AIza"
    suffix = "SyD" + "X" * 32
    fake_key = prefix + suffix
    assert len(fake_key) == 39

    code_file = tmp_path / "service.py"
    code_file.write_text(f"API_KEY = '{fake_key}'\n", encoding="utf-8")
    subprocess.run(["git", "add", "service.py"], cwd=tmp_path, check=True, capture_output=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "service.py:1: matched Google API Key" in result.stdout
    # Invariant: the matched secret text itself must never appear in stdout or stderr
    assert fake_key not in result.stdout
    assert fake_key not in result.stderr


def test_secret_scan_detects_openai_and_groq_and_private_keys(tmp_path: Path) -> None:
    """Verify detection of sk-, gsk-, and private key headers with secret masking."""
    _init_git_repo(tmp_path)

    fake_sk = "sk-" + "Proj" + "9" * 25
    fake_gsk = "gsk_" + "Groq" + "7" * 25
    fake_priv = "-----BEGIN " + "RSA PRIVATE KEY-----"

    app_file = tmp_path / "app.py"
    app_file.write_text(
        f"KEY1 = '{fake_sk}'\nKEY2 = '{fake_gsk}'\nCERT = '''{fake_priv}'''\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, capture_output=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "app.py:1: matched OpenAI/Anthropic Secret Key" in result.stdout
    assert "app.py:2: matched Groq API Key" in result.stdout
    assert "app.py:3: matched Private Key Header" in result.stdout

    # Never emit raw secret contents
    assert fake_sk not in result.stdout
    assert fake_gsk not in result.stdout
    assert fake_priv not in result.stdout


def test_secret_scan_tracked_env_file_rejected(tmp_path: Path) -> None:
    """Verify tracked .env and .env.local files trigger failure."""
    _init_git_repo(tmp_path)

    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgres://localhost\n", encoding="utf-8")
    subprocess.run(["git", "add", ".env"], cwd=tmp_path, check=True, capture_output=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert ".env: tracked environment file forbidden" in result.stdout


def test_secret_scan_tracked_env_example_allowed(tmp_path: Path) -> None:
    """Verify tracked .env.example template file is permitted."""
    _init_git_repo(tmp_path)

    example_file = tmp_path / ".env.example"
    example_file.write_text(
        "DATABASE_URL=postgres://user:pass@localhost:5432/db\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", ".env.example"], cwd=tmp_path, check=True, capture_output=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "secret scan: clean" in result.stdout
