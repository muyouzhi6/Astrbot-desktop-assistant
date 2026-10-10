"""Linux checkout and virtual environment regressions (#22)."""

from pathlib import Path
import shlex
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["start.sh", "install.sh", "quick_install.sh", "update.sh"])
def test_shell_checkout_uses_lf_and_parses(name):
    path = ROOT / name
    assert b"\r" not in path.read_bytes()
    subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True)
    attributes = subprocess.check_output(
        ["git", "check-attr", "eol", "--", name], cwd=ROOT, text=True
    )
    assert attributes.strip().endswith(": lf")


@pytest.mark.parametrize("script", ["start.sh", "install.sh"])
@pytest.mark.parametrize("existing", [(), ("venv",), (".venv",), ("venv", ".venv")])
def test_installer_and_launcher_reuse_environment(tmp_path, script, existing):
    project = tmp_path / "project with spaces"
    project.mkdir()
    for name in existing:
        bin_dir = project / name / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").touch()
        (bin_dir / "activate").write_text(":\n")
    # Execute the actual setup function without invoking install/autostart/launch.
    definitions = (ROOT / script).read_text().rsplit("\nmain", 1)[0]
    command = definitions + f'''\n
SCRIPT_DIR={shlex.quote(str(project))}
PYTHON_CMD={shlex.quote(sys.executable)}
setup_venv
test -f "$VENV_DIR/bin/python"
echo "SELECTED=$VENV_DIR"
'''
    result = subprocess.run(
        ["bash", "-c", command], cwd=project, input="1\n", text=True,
        capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    expected = "venv" if "venv" in existing or not existing else ".venv"
    assert f"SELECTED={project / expected}" in result.stdout
    assert sorted(p.name for p in project.iterdir()) == sorted(existing or ("venv",))


@pytest.mark.parametrize("script", ["quick_install.sh", "update.sh"])
@pytest.mark.parametrize("existing", [("venv",), (".venv",), ("venv", ".venv")])
def test_quick_install_and_update_reuse_environment(tmp_path, script, existing):
    project = tmp_path / "project with spaces"
    project.mkdir()
    for name in existing:
        bin_dir = project / name / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").touch()
    source = (ROOT / script).read_text()
    # Execute environment selection, excluding network and desktop registration.
    if script == "quick_install.sh":
        selection = source[source.index('VENV_DIR="$PROJECT_DIR/venv"'):]
        selection = selection.split('echo -e "${CYAN}[5/6]', 1)[0]
    else:
        selection = source.split("# 检测 Python\n", 1)[1]
        selection = selection.split('if [[ -z "$PYTHON_CMD" ]]', 1)[0]
    command = f"PROJECT_DIR={shlex.quote(str(project))}\n" + selection
    command += '\necho "SELECTED=$PYTHON_CMD"\n'
    result = subprocess.run(["bash", "-c", command], text=True, capture_output=True, check=True)
    expected = "venv" if "venv" in existing else ".venv"
    assert f"SELECTED={project / expected / 'bin/python'}" in result.stdout
    assert sorted(p.name for p in project.iterdir()) == sorted(existing)


@pytest.mark.parametrize("option, code", [("--help", 0), ("--unknown", 1)])
def test_launcher_options(option, code):
    result = subprocess.run(["bash", str(ROOT / "start.sh"), option], capture_output=True, text=True)
    assert result.returncode == code
    assert "用法:" in result.stdout


@pytest.mark.parametrize("name", ["venv", ".venv"])
def test_reinstall_uses_selected_environment(tmp_path, name):
    bin_dir = tmp_path / name / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").touch()
    (bin_dir / "activate").write_text(":\n")
    (tmp_path / name / ".installed").touch()
    source = (ROOT / "start.sh").read_text().rsplit("\nmain", 1)[0]
    command = source + f'''
SCRIPT_DIR={shlex.quote(str(tmp_path))}
check_python() {{ :; }}
check_linux_deps() {{ :; }}
check_config() {{ :; }}
install_dependencies() {{ test "$NEED_INSTALL" = true; echo "SELECTED=$VENV_DIR"; }}
main --reinstall --check
'''
    result = subprocess.run(["bash", "-c", command], text=True, capture_output=True, check=True)
    assert f"SELECTED={tmp_path / name}" in result.stdout
