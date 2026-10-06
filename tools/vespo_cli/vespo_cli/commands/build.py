"""`vespo build`: colcon build restricted to the packages this machine's role needs."""

import shlex
from typing import Annotated, Optional

import typer

from .. import config, ui
from ..procs import capture, ros_cmd, run


def colcon_packages(cfg):
    """Package names colcon finds under src/, or None if colcon is unavailable."""
    code, out = capture(
        ros_cmd(cfg.distro, "colcon list --names-only --base-paths src"), cwd=cfg.ws, timeout=60,
    )
    return out.split() if code == 0 else None


def stale_packages(cfg):
    """
    Packages whose last build failed because an old copy blocks a symlink,
    the error colcon gives after switching to --symlink-install.
    """
    stale = []
    for log in (cfg.ws / "log" / "latest_build").glob("*/stdout_stderr.log"):
        if "existing path cannot be removed" in log.read_text(errors="ignore"):
            stale.append(log.parent.name)
    return sorted(stale)


def build_workspace(cfg, packages=None, role=None, above=None):
    """
    Runs colcon build and returns its exit code. `packages` builds only those;
    `above` builds those plus every package that depends on them.
    """
    role = role or cfg.role
    cmd = ["colcon", "build", "--symlink-install", "--base-paths", "src", *cfg.get("build.args", [])]

    if packages:
        cmd += ["--packages-select", *packages]
    elif above:
        cmd += ["--packages-above", *above]
    skip_regex = cfg.get("build.skip_regex", [])
    if not packages and skip_regex:
        cmd += ["--packages-skip-regex", *skip_regex]
    if not packages and role:
        # Only pass names that exist: colcon warns about unknown ones
        known = set(colcon_packages(cfg) or [])
        skip = [p for p in cfg.role_spec(role).get("skip", []) if p in known]
        if skip:
            cmd += ["--packages-skip", *skip]
            ui.info(f"Role '{role}' skips: {', '.join(skip)}")
    elif not packages:
        ui.warn("No role set for this machine, building everything. Run `vespo init` to set one.")

    ui.info(shlex.join(cmd))
    return run(ros_cmd(cfg.distro, shlex.join(cmd)), cwd=cfg.ws)


def build(
    packages: Annotated[
        Optional[list[str]], typer.Argument(help="Build only these packages.")
    ] = None,
    role: Annotated[
        Optional[str], typer.Option(help="Build for this role instead of the machine's own.")
    ] = None,
):
    """Build the workspace with the packages this machine's role needs."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    if role and role not in cfg.roles():
        ui.abort(f"Unknown role '{role}'. Roles: {', '.join(cfg.roles())}")

    code = build_workspace(cfg, packages, role)
    if code != 0:
        stale = stale_packages(cfg)
        if stale:
            ui.warn("Left over from a build without --symlink-install: " + ", ".join(stale))
            ui.info(f"Fix it with: vespo clean {' '.join(stale)} --rebuild")
        ui.abort("Build failed", code)
    ui.ok(f"Build finished. Source it with: source {cfg.ws / 'install' / 'setup.bash'}")
