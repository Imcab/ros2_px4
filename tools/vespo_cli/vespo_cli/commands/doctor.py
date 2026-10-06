"""
`vespo doctor`: checks that this machine can build and run the workspace for
its role, and says how to fix whatever is wrong.

Every check returns a Check; nothing here modifies the system.
"""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.markup import escape
from rich.table import Table

from .. import config, fx, system, ui
from ..procs import capture, ros_cmd
from .build import colcon_packages

TOOLS = [
    ("colcon", "python3-colcon-common-extensions"),
    ("vcs", "python3-vcstool"),
    ("rosdep", "python3-rosdep"),
]


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail | skip
    detail: str = ""
    hint: str = ""  # shown only for warn and fail


def passed(condition, name, detail="", hint="", level="fail"):
    return Check(name, "ok" if condition else level, detail, hint)


# ---------------------------------------------------------------------------
# System and ROS
# ---------------------------------------------------------------------------

def check_system(cfg):
    v = sys.version_info
    return [
        Check("Platform", "ok", system.describe_platform()),
        passed(v >= (3, 10), "Python", f"{v.major}.{v.minor}.{v.micro}", "Python 3.10 or newer is required"),
    ]


def check_ros(cfg):
    distro = cfg.distro
    installed = system.installed_ros_distros()
    env_distro = os.environ.get("ROS_DISTRO")
    want_domain = str(cfg.get("ros.domain_id", 0))
    have_domain = os.environ.get("ROS_DOMAIN_ID", "0")

    checks = [
        passed(
            distro in installed, f"ROS 2 {distro} installed",
            f"/opt/ros: {', '.join(installed) or 'empty'}",
            f"https://docs.ros.org/en/{distro}/Installation.html",
        ),
        passed(
            env_distro == distro, "ROS environment sourced", f"ROS_DISTRO={env_distro or 'unset'}",
            f"source /opt/ros/{distro}/setup.bash, or let `vespo init` add it to ~/.bashrc",
            level="warn",
        ),
        passed(
            have_domain == want_domain, "ROS_DOMAIN_ID", f"shell {have_domain}, config {want_domain}",
            f"export ROS_DOMAIN_ID={want_domain}", level="warn",
        ),
    ]
    for tool, package in TOOLS:
        path = shutil.which(tool)
        checks.append(passed(path, tool, path or "not found", f"sudo apt install {package}"))
    return checks


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

def check_workspace(cfg):
    checks = []

    exported = os.environ.get("VESPO_WS")
    if exported and Path(exported).expanduser().resolve() != cfg.ws:
        checks.append(Check(
            "VESPO_WS", "warn", f"exported as {exported}",
            f"Remove that export from ~/.bashrc, the workspace is {cfg.ws}",
        ))

    role = cfg.role
    if role is None:
        checks.append(Check("Machine role", "fail", f"no {config.LOCAL_FILE}", "vespo init"))
    elif role not in cfg.roles():
        checks.append(Check("Machine role", "fail", f"unknown role '{role}'", "vespo init"))
    else:
        checks.append(Check("Machine role", "ok", f"{role}: {cfg.role_spec().get('description', '')}"))

    return checks + check_repos(cfg) + check_build(cfg)


def check_repos(cfg):
    """Each repo in vespo.repos is cloned and checked out at its pin."""
    try:
        repos = yaml.safe_load(cfg.repos_path.read_text())["repositories"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as e:
        return [Check(config.REPOS_FILE, "fail", f"unreadable: {e}")]

    checks = []
    for name, spec in repos.items():
        label = f"src/{name}"
        path = cfg.ws / "src" / name
        pin = str(spec.get("version", ""))
        if not (path / ".git").exists():
            checks.append(Check(label, "warn", "not cloned", "vcs import --input vespo.repos --skip-existing src"))
            continue
        head = system.git_head(path) or ""
        target = system.git_resolve(path, pin) if pin else head
        if target is None:
            checks.append(Check(label, "warn", f"pin {pin} not found locally", f"git -C {path} fetch --tags origin"))
        elif head == target:
            checks.append(Check(label, "ok", pin[:12]))
        else:
            checks.append(Check(label, "warn", f"at {head[:12]}, pinned {pin[:12]}", f"git -C {path} checkout {pin}"))
    return checks


def check_build(cfg):
    install = cfg.ws / "install"
    setup = install / "setup.bash"
    if not setup.is_file():
        return [Check("Workspace built", "fail", "no install/setup.bash", "vespo build")]

    checks = []
    known = colcon_packages(cfg)
    if known is None:
        checks.append(Check("Workspace built", "warn", "could not list packages, is colcon installed?"))
    else:
        skip = set(cfg.role_spec().get("skip", []))
        missing = [p for p in known if p not in skip and not (install / p).is_dir()]
        checks.append(passed(
            not missing, "Workspace built",
            f"not built: {', '.join(missing)}" if missing else f"{len(known) - len(skip & set(known))} packages",
            "vespo build", level="warn",
        ))

    prefixes = os.environ.get("AMENT_PREFIX_PATH", "").split(":")
    sourced = any(p.startswith(str(install)) for p in prefixes)
    checks.append(passed(sourced, "Workspace sourced", "", f"source {setup}", level="warn"))
    return checks


# ---------------------------------------------------------------------------
# PX4 source and simulation (roles with simulation = true)
# ---------------------------------------------------------------------------

def check_px4(cfg):
    configured = cfg.get("px4.path")
    if not configured:
        return [Check("PX4-Autopilot", "fail", "path not configured", "vespo init")]
    px4 = Path(configured).expanduser()
    if not system.is_px4_tree(px4):
        return [Check("PX4-Autopilot", "fail", f"{px4} is not a PX4 checkout", "vespo init")]

    checks = [Check("PX4-Autopilot", "ok", str(px4))]

    want = cfg.get("px4.commit")
    head = system.git_head(px4) or ""
    if want:
        checks.append(passed(
            bool(head) and head.startswith(want),
            "PX4 commit", f"at {head[:12]}, expected {want[:12]}",
            f"git -C {px4} checkout {want[:12]} && git -C {px4} submodule update --init --recursive",
            level="warn",
        ))

    checks += check_firmware(cfg, px4)

    sitl = px4 / "build" / "px4_sitl_default" / "bin" / "px4"
    checks.append(passed(sitl.is_file(), "PX4 SITL built", str(sitl), f"make -C {px4} px4_sitl", level="warn"))
    checks.append(check_msgs(cfg, px4))
    return checks


def check_firmware(cfg, px4):
    """The configured flight controller has a PX4 target and it can be compiled."""
    fc_id = cfg.get("flight_controller.model")
    fc = cfg.get("flight_controllers", {}).get(fc_id)
    if fc is None:
        return [Check("Flight controller", "warn", "not configured" if fc_id is None else f"unknown '{fc_id}'",
                      "vespo config edit flight_controller")]
    board_file = system.px4_board_file(px4, fc["target"])
    gcc = shutil.which("arm-none-eabi-gcc")
    return [
        passed(board_file.is_file(), "Flight controller", f"{fc['name']} · {fc['target']}",
               f"PX4 has no {board_file}; fix the target in vespo.toml"),
        passed(gcc, "ARM toolchain", gcc or "arm-none-eabi-gcc not found",
               f"bash {px4}/Tools/setup/ubuntu.sh", level="warn"),
    ]


def _msg_fields(path):
    """Field lines of a .msg file, without comments or spacing differences."""
    fields = []
    for line in path.read_text(errors="ignore").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            fields.append(" ".join(line.split()))
    return fields


def _load_msgs(*dirs):
    return {f.name: _msg_fields(f) for d in dirs if d.is_dir() for f in d.glob("*.msg")}


def check_msgs(cfg, px4):
    """
    px4_msgs must define every message exactly as the PX4 checkout does.
    A mismatch does not fail to build: the topic silently never arrives, or
    arrives with garbage in it.
    """
    name = "px4_msgs matches PX4"
    msgs_dir = cfg.ws / "src" / "px4_msgs" / "msg"
    if not msgs_dir.is_dir():
        return Check(name, "skip", "px4_msgs not cloned")

    firmware = _load_msgs(px4 / "msg", px4 / "msg" / "versioned")
    ros = _load_msgs(msgs_dir)
    bad = sorted(n for n in firmware if firmware[n] != ros.get(n))
    if not bad:
        return Check(name, "ok", f"{len(firmware)} messages identical")

    shown = ", ".join(n.removesuffix(".msg") for n in bad[:6])
    if len(bad) > 6:
        shown += f" (+{len(bad) - 6} more)"
    return Check(
        name, "fail", f"{len(bad)} differ: {shown}",
        "Pin px4_msgs and PX4-Autopilot to matching commits, "
        "or copy PX4's msg/ and msg/versioned/ into px4_msgs/msg and rebuild",
    )


def check_simulation(cfg):
    checks = []

    version = system.gz_version()
    if version is None:
        checks.append(Check(
            "Gazebo", "fail", "gz not found", "https://gazebosim.org/docs/harmonic/install_ubuntu",
        ))
    else:
        checks.append(passed(
            version.startswith("8."), "Gazebo", f"gz-sim {version}",
            "PX4 and ros_gz here target Gazebo Harmonic (gz-sim 8)", level="warn",
        ))

    bridge_pkg = "ros-humble-ros-gzharmonic" if cfg.distro == "humble" else f"ros-{cfg.distro}-ros-gz"
    bridge = Path("/opt/ros") / cfg.distro / "share" / "ros_gz_bridge"
    checks.append(passed(
        bridge.is_dir(), "ros_gz_bridge", "", f"sudo apt install {bridge_pkg}", level="warn",
    ))

    return checks + check_resource_path(cfg)


def check_resource_path(cfg):
    """
    GZ_SIM_RESOURCE_PATH includes the project models, has no dead entries,
    and no model name is defined twice (Gazebo silently loads the first).
    """
    entries = [Path(p) for p in os.environ.get("GZ_SIM_RESOURCE_PATH", "").split(":") if p]
    ours = cfg.ws / "install" / "environment_description"
    checks = [passed(
        any(e == ours or ours in e.parents for e in entries),
        "Project models on GZ_SIM_RESOURCE_PATH", "",
        f"source {cfg.ws / 'install' / 'setup.bash'}", level="warn",
    )]

    dead = [str(e) for e in entries if not e.is_dir()]
    if dead:
        checks.append(Check("Dead resource paths", "warn", ", ".join(dead), "Remove them from ~/.bashrc"))

    owners = {}
    for entry in dict.fromkeys(e.resolve() for e in entries if e.is_dir()):
        for child in entry.iterdir():
            if (child / "model.config").is_file():
                owners.setdefault(child.name, []).append(entry)
    dups = {name: dirs for name, dirs in owners.items() if len(dirs) > 1}
    if dups:
        stale = sorted({str(d) for dirs in dups.values() for d in dirs if ours not in d.parents})
        checks.append(Check(
            "Duplicate models", "warn",
            f"{len(dups)} defined twice: {', '.join(sorted(dups)[:5])}",
            f"Remove the old exports from ~/.bashrc: {', '.join(stale)}" if stale
            else "Two resource paths define the same model",
        ))
    return checks


# ---------------------------------------------------------------------------
# Link to the flight controller
# ---------------------------------------------------------------------------

def check_link(cfg):
    link = cfg.role_spec().get("link", "none")
    if link == "none":
        return []

    built = cfg.ws / "install" / "microxrcedds_agent" / "bin" / "MicroXRCEAgent"
    agent = str(built) if built.is_file() else shutil.which("MicroXRCEAgent")
    checks = [passed(agent, "Micro XRCE-DDS Agent", agent or "not built", "vespo build")]

    if link == "udp":
        port = int(cfg.get("agent.udp_port", 8888))
        free = system.udp_port_free(port)
        checks.append(passed(
            free, f"UDP port {port}", "free" if free else "in use",
            "An agent is probably running already; stop it or change agent.udp_port", level="warn",
        ))
    elif link == "serial":
        device = cfg.get("agent.device")
        if not device:
            checks.append(Check("Serial device", "fail", "not configured", "vespo init"))
        else:
            checks.append(passed(
                Path(device).exists(), "Serial device", device,
                "Check the cable and that the UART is enabled",
            ))
        checks.append(passed(
            system.in_group("dialout"), "User in dialout", "",
            "sudo usermod -aG dialout $USER, then log out and back in",
        ))
    return checks


def check_live(cfg):
    code, out = capture(
        ros_cmd(cfg.distro, "ros2 topic list", ws=cfg.ws),
        timeout=30, env={"ROS_DOMAIN_ID": cfg.get("ros.domain_id", 0)},
    )
    if code != 0:
        return [Check("ros2 topic list", "fail", "command failed")]
    topics = [t for t in out.split() if t.startswith("/fmu/")]
    return [passed(
        topics, "PX4 topics", f"{len(topics)} under /fmu",
        "Start PX4 and the agent, with the same ROS_DOMAIN_ID", level="warn",
    )]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

def sections(cfg, live=False):
    """(title, check function) pairs for this machine's role, in display order."""
    out = [("System", check_system), ("ROS 2", check_ros), ("Workspace", check_workspace)]
    if cfg.role_spec().get("simulation"):
        out += [("PX4", check_px4), ("Simulation", check_simulation)]
    out.append(("Flight controller link", check_link))
    if live:
        out.append(("Live", check_live))
    return out


def section_table(title, checks):
    table = Table(title=f"[bold]{title}", title_justify="left", show_header=False, box=None)
    table.add_column(width=1)
    table.add_column(style="bold", no_wrap=True)
    table.add_column(overflow="fold")
    for check in checks:
        icon, colour = ui.STYLES[check.status]
        table.add_row(f"[{colour}]{icon}[/]", escape(check.name), escape(check.detail))
        if check.hint and check.status in ("warn", "fail"):
            table.add_row("", "", f"[dim]→ {escape(check.hint)}[/]")
    return table


def run_doctor(cfg, live=False):
    """
    Runs every section under the breathing status line, printing each one as
    soon as it finishes. Returns the number of failed checks.
    """
    counts = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    with fx.status("Checking") as status:
        for title, check in sections(cfg, live):
            status.update(f"Checking {title}")
            checks = check(cfg)
            if not checks:
                continue
            for c in checks:
                counts[c.status] += 1
            status.print(section_table(title, checks))
            status.print()

    ui.console.print(
        f"[green]{counts['ok']} ok[/]  [yellow]{counts['warn']} warnings[/]  [red]{counts['fail']} failed[/]"
    )
    return counts["fail"]


def doctor(
    live: Annotated[
        bool, typer.Option("--live", help="Also check that PX4 topics are visible right now.")
    ] = False,
):
    """Check this machine can build and run the workspace for its role."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    if run_doctor(cfg, live):
        raise typer.Exit(1)
