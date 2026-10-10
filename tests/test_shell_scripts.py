"""Linux checkout and virtual environment regressions (#22)."""

import shlex
import shutil
import stat
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bash():
    if sys.platform == "win32":
        pytest.skip("Shell execution tests require a POSIX environment")
    executable = shutil.which("bash")
    if executable is None:
        pytest.skip("Bash is not installed")
    return executable


@pytest.mark.parametrize(
    "name", ["start.sh", "install.sh", "quick_install.sh", "update.sh"]
)
def test_shell_checkout_uses_lf(name):
    path = ROOT / name
    assert b"\r" not in path.read_bytes()
    attributes = subprocess.check_output(
        ["git", "check-attr", "eol", "--", name], cwd=ROOT, text=True
    )
    assert attributes.strip().endswith(": lf")


@pytest.mark.parametrize(
    "name", ["start.sh", "install.sh", "quick_install.sh", "update.sh"]
)
def test_shell_git_checkout_is_executable(name, tmp_path):
    """A fresh Git checkout must support the documented ./script.sh usage."""
    entry = subprocess.check_output(
        ["git", "ls-files", "--stage", "--", name], cwd=ROOT, text=True
    )
    assert entry.split()[0] == "100755", f"{name} loses +x on checkout"
    if sys.platform == "win32":
        return
    checkout = tmp_path / "fresh checkout"
    checkout.mkdir()
    subprocess.run(
        ["git", "checkout-index", f"--prefix={checkout}/", "--", name],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    assert (checkout / name).stat().st_mode & stat.S_IXUSR


def test_launcher_executes_directly(bash):
    result = subprocess.run(
        [str(ROOT / "start.sh"), "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "用法:" in result.stdout


@pytest.mark.parametrize(
    "name", ["start.sh", "install.sh", "quick_install.sh", "update.sh"]
)
def test_shell_script_parses(bash, name):
    subprocess.run(
        [bash, "-n", str(ROOT / name)], check=True, capture_output=True
    )


@pytest.mark.parametrize("script", ["start.sh", "install.sh"])
@pytest.mark.parametrize(
    "existing", [(), ("venv",), (".venv",), ("venv", ".venv")]
)
def test_installer_and_launcher_reuse_environment(
    bash, tmp_path, script, existing
):
    project = tmp_path / "project with spaces"
    project.mkdir()
    for name in existing:
        bin_dir = project / name / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").touch()
        (bin_dir / "activate").write_text(":\n")
    # Run setup without invoking installation, autostart or launch.
    definitions = (ROOT / script).read_text().rsplit("\nmain", 1)[0]
    command = definitions + f"""\n
SCRIPT_DIR={shlex.quote(str(project))}
PYTHON_CMD={shlex.quote(sys.executable)}
setup_venv
test -f "$VENV_DIR/bin/python"
echo "SELECTED=$VENV_DIR"
"""
    result = subprocess.run(
        [bash, "-c", command],
        cwd=project,
        input="1\n",
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    expected = "venv" if "venv" in existing or not existing else ".venv"
    assert f"SELECTED={project / expected}" in result.stdout
    assert sorted(p.name for p in project.iterdir()) == sorted(
        existing or ("venv",)
    )


@pytest.mark.parametrize("script", ["quick_install.sh", "update.sh"])
@pytest.mark.parametrize(
    "existing", [("venv",), (".venv",), ("venv", ".venv")]
)
def test_quick_install_and_update_reuse_environment(
    bash, tmp_path, script, existing
):
    project = tmp_path / "project with spaces"
    project.mkdir()
    for name in existing:
        bin_dir = project / name / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").touch()
    source = (ROOT / script).read_text()
    # Select the environment without network or desktop registration.
    if script == "quick_install.sh":
        start = source.index('VENV_DIR="$PROJECT_DIR/venv"')
        selection = source[start:]
        selection = selection.split('echo -e "${CYAN}[5/6]', 1)[0]
    else:
        selection = source.split("# 检测 Python\n", 1)[1]
        selection = selection.split('if [[ -z "$PYTHON_CMD" ]]', 1)[0]
    command = f"PROJECT_DIR={shlex.quote(str(project))}\n" + selection
    command += '\necho "SELECTED=$PYTHON_CMD"\n'
    result = subprocess.run(
        [bash, "-c", command], text=True, capture_output=True, check=True
    )
    expected = "venv" if "venv" in existing else ".venv"
    assert f"SELECTED={project / expected / 'bin/python'}" in result.stdout
    assert sorted(p.name for p in project.iterdir()) == sorted(existing)


@pytest.mark.parametrize("option, code", [("--help", 0), ("--unknown", 1)])
def test_launcher_options(bash, option, code):
    result = subprocess.run(
        [bash, str(ROOT / "start.sh"), option],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == code
    assert "用法:" in result.stdout


@pytest.mark.parametrize("name", ["venv", ".venv"])
def test_reinstall_uses_selected_environment(bash, tmp_path, name):
    bin_dir = tmp_path / name / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").touch()
    (bin_dir / "activate").write_text(":\n")
    (tmp_path / name / ".installed").touch()
    source = (ROOT / "start.sh").read_text().rsplit("\nmain", 1)[0]
    command = source + f"""
SCRIPT_DIR={shlex.quote(str(tmp_path))}
check_python() {{ :; }}
check_linux_deps() {{ :; }}
check_config() {{ :; }}
install_dependencies() {{
    test "$NEED_INSTALL" = true
    echo "SELECTED=$VENV_DIR"
}}
main --reinstall --check
"""
    result = subprocess.run(
        [bash, "-c", command], text=True, capture_output=True, check=True
    )
    assert f"SELECTED={tmp_path / name}" in result.stdout


@pytest.mark.parametrize(
    "existing", [("venv",), (".venv",), ("venv", ".venv")]
)
@pytest.mark.parametrize(
    "failure", ["upgrade", "requirements", "missing-requirements"]
)
def test_failed_reinstall_retries_on_next_launch(
    bash, tmp_path, existing, failure
):
    project = tmp_path / "project with spaces"
    project.mkdir()
    for name in existing:
        bin_dir = project / name / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").touch()
        (bin_dir / "activate").write_text(":\n")
        (project / name / ".installed").write_text("old installation\n")
    selected = "venv" if "venv" in existing else ".venv"
    marker = project / selected / ".installed"
    requirements = project / "requirements.txt"
    if failure != "missing-requirements":
        requirements.touch()
    calls = project / "pip-calls.txt"
    source = (ROOT / "start.sh").read_text().rsplit("\nmain", 1)[0]
    command = source + f"""
SCRIPT_DIR={shlex.quote(str(project))}
check_python() {{ :; }}
check_linux_deps() {{ :; }}
check_config() {{ :; }}
pip() {{
    local stage=requirements marker_state=absent
    if [ "$2" = --upgrade ]; then stage=upgrade; fi
    if [ -f "$VENV_DIR/.installed" ]; then marker_state=present; fi
    printf '%s %s\\n' "$stage" "$marker_state" >> "$SCRIPT_DIR/pip-calls.txt"
    if [ "$stage" = "$FAIL_AT" ]; then return 17; fi
}}
"""

    def launch(fail_at, options):
        return subprocess.run(
            [bash, "-c", command + f"\nFAIL_AT={fail_at}\nmain {options}\n"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

    failed = launch(failure, "--reinstall --check")
    assert failed.returncode == (
        1 if failure == "missing-requirements" else 17
    )
    assert not marker.exists(), "Failed reinstall left a stale success marker"
    expected = ["upgrade absent"]
    if failure == "requirements":
        expected.append("requirements absent")
    assert calls.read_text().splitlines() == expected
    for name in set(existing) - {selected}:
        assert (
            project / name / ".installed"
        ).read_text() == "old installation\n"

    # Ordinary launch retries and records success after both pip calls.
    requirements.touch()
    calls.write_text("")
    retried = launch("none", "--check")
    assert retried.returncode == 0, retried.stderr
    assert marker.exists()
    assert calls.read_text().splitlines() == [
        "upgrade absent",
        "requirements absent",
    ]

    calls.write_text("")
    skipped = launch("none", "--check")
    assert skipped.returncode == 0, skipped.stderr
    assert calls.read_text() == ""


def test_shell_tests_without_bash_keep_lf_checks(tmp_path):
    """Without Bash, pytest must check LF and skip script execution."""
    report = tmp_path / "without-bash.xml"
    runner = textwrap.dedent("""
        from pathlib import Path
        import shutil
        import subprocess
        import sys
        from unittest.mock import patch

        import pytest

        real_which = shutil.which
        real_popen = subprocess.Popen

        def without_bash(command, *args, **kwargs):
            if command == "bash":
                return None
            return real_which(command, *args, **kwargs)

        def reject_bash(args, *rest, **kwargs):
            command = args
            if isinstance(args, (list, tuple)):
                command = Path(args[0]).name
            if command in {"bash", "bash.exe"}:
                raise AssertionError("Bash invoked on a host without Bash")
            return real_popen(args, *rest, **kwargs)

        with patch("shutil.which", without_bash), patch(
            "subprocess.Popen", reject_bash
        ):
            raise SystemExit(pytest.main(sys.argv[1:]))
    """)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            runner,
            str(Path(__file__).resolve()),
            "-q",
            "--tb=line",
            "-p",
            "no:cacheprovider",
            "-k",
            "not test_shell_tests_without_bash_keep_lf_checks",
            f"--basetemp={tmp_path / 'without-bash'}",
            f"--junitxml={report}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    cases = ET.parse(report).findall(".//testcase")
    passed = {
        case.attrib["name"] for case in cases if case.find("skipped") is None
    }
    assert passed == {
        f"test_shell_checkout_uses_lf[{name}]"
        for name in ["start.sh", "install.sh", "quick_install.sh", "update.sh"]
    } | {
        f"test_shell_git_checkout_is_executable[{name}]"
        for name in ["start.sh", "install.sh", "quick_install.sh", "update.sh"]
    }
    assert len(cases) > len(
        passed
    ), "Bash execution tests must be collected and skipped"
