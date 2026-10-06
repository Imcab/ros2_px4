"""
`vespo init`: sets up this machine for the workspace.

Detects the host, asks for its role and the values that role needs, writes
vespo.local.toml, optionally clones, installs dependencies and builds, and
finishes with `vespo doctor`. Safe to run again: previous answers become the
defaults. Every question has a flag, so `--yes` runs it unattended.
"""

import re
import shlex
from pathlib import Path
from typing import Annotated, Optional

import typer

from .. import config, fx, system, ui
from ..procs import run
from ..settings import SETTINGS, confirm
from .build import build_workspace
from .doctor import run_doctor

BASHRC = Path.home() / ".bashrc"
BLOCK_BEGIN = "# >>> vespo >>>"
BLOCK_END = "# <<< vespo <<<"

ROSDEP_SOURCES = Path("/etc/ros/rosdep/sources.list.d")
ROSDEP_CACHE = Path.home() / ".ros" / "rosdep" / "sources.cache"


# ---------------------------------------------------------------------------
# Setup steps
# ---------------------------------------------------------------------------

def setup_workspace(cfg):
    """Clones the pinned repos, installs dependencies and builds. False on failure."""
    ui.header("Cloning repositories")
    if run(["vcs", "import", "--input", str(cfg.repos_path), "--skip-existing", "src"], cwd=cfg.ws):
        ui.fail("vcs import failed")
        return False

    ui.header("Installing dependencies")
    if not ROSDEP_SOURCES.is_dir():
        ui.fail("rosdep is not initialised. Run once: sudo rosdep init && rosdep update")
        return False
    if not ROSDEP_CACHE.is_file() and run(["rosdep", "update", "--rosdistro", cfg.distro]):
        ui.fail("rosdep update failed")
        return False
    if run(["rosdep", "install", "--from-paths", "src", "--ignore-src", "-r", "-y",
            "--rosdistro", cfg.distro], cwd=cfg.ws):
        ui.warn("Some dependencies could not be installed, continuing with the build")

    ui.header("Building")
    if build_workspace(cfg):
        ui.fail("Build failed")
        return False
    return True


def bashrc_block(cfg):
    setup = shlex.quote(str(cfg.ws / "install" / "setup.bash"))
    return "\n".join([
        BLOCK_BEGIN,
        "# Managed by `vespo init`, changes inside this block are overwritten.",
        f"if [ -f {setup} ]; then",
        f"  source {setup}",
        "else",
        f"  source /opt/ros/{cfg.distro}/setup.bash",
        "fi",
        f"export ROS_DOMAIN_ID={cfg.get('ros.domain_id', 0)}",
        BLOCK_END,
    ])


def has_bashrc_block():
    return BASHRC.is_file() and BLOCK_BEGIN in BASHRC.read_text()


def write_bashrc(block):
    """Adds the block to ~/.bashrc, replacing a previous one instead of duplicating it."""
    text = BASHRC.read_text() if BASHRC.is_file() else ""
    pattern = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END), re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(lambda _: block, text)
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    BASHRC.write_text(text)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

def init(
    role: Annotated[Optional[str], typer.Option(help="sim, companion or ground.")] = None,
    px4_path: Annotated[Optional[Path], typer.Option(help="PX4-Autopilot checkout (sim role).")] = None,
    flight_controller: Annotated[Optional[str], typer.Option(help="Flight controller id from vespo.toml, e.g. pixhawk6c_mini.")] = None,
    serial: Annotated[Optional[str], typer.Option(help="Serial device to the flight controller (companion role).")] = None,
    baud: Annotated[Optional[int], typer.Option(help="Serial baud rate (companion role).")] = None,
    domain_id: Annotated[Optional[int], typer.Option(min=0, max=232, help="ROS_DOMAIN_ID for this machine.")] = None,
    setup: Annotated[Optional[bool], typer.Option("--setup/--no-setup", help="Clone, install dependencies and build.")] = None,
    bashrc: Annotated[Optional[bool], typer.Option("--bashrc/--no-bashrc", help="Source the workspace from ~/.bashrc.")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Accept every default without asking.")] = False,
):
    """Set up this machine: role, paths, dependencies and build."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    board = system.board()
    fx.logo()
    ui.header("vespo init")
    ui.info(f"Workspace  {cfg.ws}")
    ui.info(f"Platform   {system.describe_platform()}")
    ui.info(f"ROS 2      {', '.join(system.installed_ros_distros()) or 'not installed'}")
    ui.info(f"Gazebo     {system.gz_version() or 'not installed'}")
    if cfg.local:
        ui.info(f"Using the current {config.LOCAL_FILE} as defaults")

    # Each setting is asked only if the chosen role uses it
    explicit = {
        "role": role, "domain_id": domain_id, "flight_controller": flight_controller,
        "px4_path": px4_path, "serial": serial, "baud": baud,
    }
    local = {"machine": {"board": board}}
    for setting in SETTINGS.values():
        if not setting.applies(cfg, role):
            continue
        value = setting.ask(cfg, explicit.get(setting.name), yes)
        if setting.name == "role":
            role = value
        if value is not None:
            config.set_key(local, setting.key, value)
            # later questions see this answer (the sim menus need px4_path)
            config.set_key(cfg.data, setting.key, value)

    # A Raspberry Pi runs out of memory compiling several packages at once
    build_args = cfg.get("build.args", ["--executor", "sequential"] if board == "raspberry" else [])
    if build_args:
        local["build"] = {"args": build_args}

    config.write_local(cfg.ws, local)
    ui.ok(f"Wrote {cfg.local_path}")
    cfg = config.load(cfg.ws)

    if confirm("Clone repositories, install dependencies and build now?", setup, yes, True):
        if not setup_workspace(cfg):
            ui.warn("Setup stopped. Fix the error above and run `vespo init` again.")

    if confirm(f"Source the workspace automatically from {BASHRC}?", bashrc, yes, not yes):
        write_bashrc(bashrc_block(cfg))
        ui.ok(f"Updated {BASHRC}, open a new terminal to use it")

    ui.header("vespo doctor")
    ui.info("Checks about the sourced environment only pass in a new terminal")
    run_doctor(cfg)
