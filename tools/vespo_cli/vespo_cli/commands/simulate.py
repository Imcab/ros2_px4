"""
`vespo simulate`: runs PX4 SITL with Gazebo Harmonic, i.e.
`make px4_sitl gz_<model>` inside PX4-Autopilot.

    vespo simulate --minimum                      x500 in the default world
    vespo simulate --default                      what `vespo config` says (sim_*)
    vespo simulate --custom x500_depth            any PX4 Gazebo model
    vespo simulate --custom x500_mono_cam --world aruco
    vespo simulate --minimum --world tmr_field    a world from this workspace
    vespo simulate --show                         list models and worlds

--world, --pose, --follow, --no-follow and --headless also apply on top of
--default, overriding the configured value for that run.

Models are the PX4 airframes named *_gz_<model>, or workspace models: a
share/<pkg>/models/<model>/ folder holding model.sdf and its PX4 airframe
file <SYS_AUTOSTART>_gz_<model>. Worlds are PX4's own
(Tools/simulation/gz/worlds, passed through PX4_GZ_WORLD) or ones installed
by a workspace package under share/<pkg>/worlds.

PX4 only loads worlds, models and airframes from its own tree, so when a
workspace world or model is involved Gazebo is started here first, with the
same environment PX4 would give it, and PX4 attaches to the running world.
A workspace model's airframe is linked into the SITL build, and PX4 is run
directly with PX4_GZ_MODELS pointing at the workspace models.
"""

import difflib
import math
import os
import shlex
import signal
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.markup import escape
from rich.table import Table

from .. import config, system, ui
from ..procs import capture, ros_cmd, run

MINIMUM_MODEL = "x500"

# One-line descriptions for the models most used in the team; the rest are
# listed without one.
MODEL_NOTES = {
    "x500": "Quadrotor, no extra sensors",
    "x500_depth": "x500 + depth camera (OAK-D Lite)",
    "x500_mono_cam": "x500 + forward monocular camera",
    "x500_mono_cam_down": "x500 + downward monocular camera",
    "x500_lidar_2d": "x500 + 2D lidar",
    "x500_lidar_down": "x500 + downward range lidar",
    "x500_lidar_front": "x500 + forward range lidar",
    "x500_gimbal": "x500 + camera on a 3-axis gimbal",
    "x500_flow": "x500 + optical flow",
    "x500_vision": "x500 set up for external vision (no GPS)",
    "standard_vtol": "Quadplane VTOL",
    "rc_cessna": "Fixed wing",
    "advanced_plane": "Fixed wing, detailed aerodynamics",
    "r1_rover": "Ground rover",
}


def _px4_tree(cfg):
    px4_path = cfg.get("px4.path")
    if not px4_path or not system.is_px4_tree(px4_path):
        ui.abort("No valid PX4-Autopilot path configured. Set it with: vespo config edit px4_path")
    return Path(px4_path)


def px4_models(px4):
    """Model names PX4 has a gz_<model> make target for, sorted."""
    airframes = px4 / "ROMFS" / "px4fmu_common" / "init.d-posix" / "airframes"
    return sorted(f.name.split("_gz_", 1)[1] for f in airframes.glob("*_gz_*"))


def px4_worlds(px4):
    return sorted(f.stem for f in (px4 / "Tools" / "simulation" / "gz" / "worlds").glob("*.sdf"))


def workspace_worlds(ws):
    """{world name: (package, .sdf path)} for worlds installed by workspace packages."""
    found = {}
    for sdf in sorted((ws / "install").glob("*/share/*/worlds/**/*.sdf")):
        package = sdf.relative_to(ws / "install").parts[0]
        found.setdefault(sdf.stem, (package, sdf))
    return found


def workspace_models(ws):
    """{model name: (package, model folder, airframe file)} for workspace models PX4 can fly."""
    found = {}
    for sdf in sorted((ws / "install").glob("*/share/*/models/**/model.sdf")):
        folder = sdf.parent
        airframes = sorted(folder.glob(f"[0-9]*_gz_{folder.name}"))
        if airframes:
            package = sdf.relative_to(ws / "install").parts[0]
            found.setdefault(folder.name, (package, folder, airframes[0]))
    return found


def running_gz_world():
    """Name of a Gazebo world already running on this PC, or None."""
    code, out = capture(["gz", "topic", "-l"], timeout=10)
    if code != 0:
        return None
    for line in out.splitlines():
        if line.startswith("/world/") and line.endswith("/clock"):
            return line.split("/")[2]
    return None


def _unknown(kind, name, options, hint):
    close = difflib.get_close_matches(name, options, n=3)
    suggestion = f" Did you mean: {', '.join(close)}?" if close else ""
    ui.abort(f"Unknown {kind} '{name}'.{suggestion} {hint}")


def show(cfg, px4):
    ui.header("vespo simulate --show")

    models = Table(title="Models", title_justify="left", box=None, pad_edge=False)
    models.add_column("Name", style="bold")
    models.add_column("Description", style="dim")
    for name in px4_models(px4):
        models.add_row(escape(name), MODEL_NOTES.get(name, ""))
    for name, (package, _, _) in workspace_models(cfg.ws).items():
        models.add_row(escape(name), f"workspace: {package}")
    ui.console.print(models)
    ui.console.print()

    worlds = Table(title="Worlds", title_justify="left", box=None, pad_edge=False)
    worlds.add_column("Name", style="bold")
    worlds.add_column("Source", style="dim")
    for name in px4_worlds(px4):
        worlds.add_row(escape(name), "PX4" + (" (used by default)" if name == "default" else ""))
    for name, (package, _) in workspace_worlds(cfg.ws).items():
        worlds.add_row(escape(name), f"workspace: {package}")
    ui.console.print(worlds)
    ui.console.print()

    ui.console.print(
        "[bold]Examples[/]\n"
        "  vespo simulate --minimum\n"
        "  vespo simulate --default                  (set it with: vespo config edit sim_model)\n"
        "  vespo simulate --custom x500_depth --world walls\n"
        "  vespo simulate --custom x500_mono_cam --world aruco --headless"
    )


def _sitl_build(px4):
    return px4 / "build" / "px4_sitl_default"


def _start_gz(cfg, px4, sdf, headless, env):
    """
    Starts the Gazebo server (and GUI) on a world file, with the workspace
    sourced (for its model:// paths) and PX4's gz_env.sh (for PX4's models,
    plugins and server config). Returns the processes.
    """
    gz_env = _sitl_build(px4) / "rootfs" / "gz_env.sh"
    if not gz_env.is_file():
        ui.info("PX4 SITL is not built yet, building it first")
        if run(["make", "px4_sitl"], cwd=px4):
            ui.abort("make px4_sitl failed, see the output above")

    prefix = f"source {shlex.quote(str(gz_env))} && gz sim --verbose=1"
    commands = [f"{prefix} -r -s {shlex.quote(str(sdf))}"]
    if not headless:
        commands.append(f"{prefix} -g")

    full_env = {**os.environ, **env}
    # Own process group each, so the whole gz process tree can be stopped at once
    return [
        subprocess.Popen(ros_cmd(cfg.distro, cmd, cfg.ws), env=full_env, start_new_session=True,
                         stdout=subprocess.DEVNULL if cmd.endswith("-g") else None)
        for cmd in commands
    ]


SPAWN_Z = 0.25   # high enough for any model to drop onto the ground, not into it


def pose_values(text):
    """'x,y[,z[,yaw_deg]]' -> (x, y, z, yaw_deg). ValueError if malformed."""
    try:
        values = [float(v) for v in str(text).split(",")]
    except ValueError:
        values = []
    if not 2 <= len(values) <= 4:
        raise ValueError(f"Expected X,Y[,Z[,YAW]] in metres and degrees, got '{text}'")
    x, y, z, yaw = values + [SPAWN_Z, 0.0][len(values) - 2:]
    return x, y, z, yaw


def follow_value(text):
    """'auto', 'off' or a positive distance in metres. ValueError otherwise."""
    text = str(text).strip().lower()
    if text in ("auto", "off"):
        return text
    try:
        metres = float(text)
    except ValueError:
        metres = 0.0
    if metres <= 0:
        raise ValueError(f"Expected auto, off or a distance in metres, got '{text}'")
    return metres


def _parse_pose(text):
    try:
        return pose_values(text)
    except ValueError as e:
        ui.abort(f"--pose: {e}")


def _world_spawn(world_sdf):
    """
    Default spawn pose of a workspace world, from spawn.yaml next to its .sdf:
        pose: [x, y, z, yaw_deg]   (z and yaw optional)
    """
    if world_sdf is None:
        return None
    path = world_sdf.parent / "spawn.yaml"
    if not path.is_file():
        return None
    try:
        values = (yaml.safe_load(path.read_text()) or {}).get("pose")
        return _parse_pose(",".join(str(v) for v in values))
    except (yaml.YAMLError, AttributeError, TypeError):
        ui.abort(f"{path}: expected 'pose: [x, y, z, yaw_deg]'")


def _px4_world_file(px4, world):
    return px4 / "Tools" / "simulation" / "gz" / "worlds" / f"{world or 'default'}.sdf"


def _run_workspace_model(cfg, px4, ws_model, world_sdf, headless, env):
    """
    Does by hand what `make px4_sitl gz_<model>` does for PX4's own models:
    builds PX4 and its Gazebo plugins, makes the airframe visible to PX4,
    starts Gazebo and runs the PX4 binary from the SITL rootfs.
    """
    _, folder, airframe = ws_model

    if run(["make", "px4_sitl", "px4", "px4_gz_plugins"], cwd=px4):
        ui.abort("make px4_sitl failed, see the output above")

    # PX4 finds airframes by file name in its build; a link keeps the
    # workspace file as the only copy to edit
    link = _sitl_build(px4) / "etc" / "init.d-posix" / "airframes" / airframe.name
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(airframe.resolve())

    run_env = {
        **env,
        "PX4_SIM_MODEL": f"gz_{folder.name}",
        "PX4_GZ_MODELS": str(folder.parent),   # PX4 spawns <this>/<model>/model.sdf
        "GZ_IP": "127.0.0.1",
    }
    run_env.pop("PX4_GZ_WORLD", None)   # PX4 takes the world from the running Gazebo

    gz_procs = _start_gz(cfg, px4, world_sdf, headless, run_env)
    try:
        return run([str(_sitl_build(px4) / "bin" / "px4")], cwd=_sitl_build(px4) / "rootfs", env=run_env)
    finally:
        _stop(gz_procs)


def _stop(procs):
    for proc in procs:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGINT)
    for proc in procs:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def simulate(
    minimum: Annotated[
        bool, typer.Option("--minimum", help=f"Plain {MINIMUM_MODEL} in PX4's default world, nothing else.")
    ] = False,
    default: Annotated[
        bool, typer.Option("--default", help="Model, world, pose and camera from `vespo config` (sim_*).")
    ] = False,
    custom: Annotated[
        Optional[str], typer.Option("--custom", metavar="MODEL", help="Fly this model (see --show), e.g. x500_depth.")
    ] = None,
    show_: Annotated[bool, typer.Option("--show", help="List the available models and worlds, then exit.")] = False,
    world: Annotated[
        Optional[str], typer.Option("--world", "-w", help="World to load (see --show). Default: PX4's default.")
    ] = None,
    headless: Annotated[bool, typer.Option("--headless", help="Run without the Gazebo window.")] = False,
    pose: Annotated[
        Optional[str],
        typer.Option("--pose", "-p", metavar="X,Y[,Z[,YAW]]",
                     help="Spawn position in metres, yaw in degrees. Default: the world's spawn.yaml, else 0,0."),
    ] = None,
    follow: Annotated[
        Optional[float],
        typer.Option("--follow", metavar="METRES", help="Camera distance behind/beside/above the vehicle. PX4 uses 2."),
    ] = None,
    no_follow: Annotated[bool, typer.Option("--no-follow", help="Free camera instead of following the vehicle.")] = False,
):
    """Run PX4 SITL in Gazebo Harmonic (--minimum, --default, --custom MODEL or --show)."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    px4 = _px4_tree(cfg)

    if sum([minimum, default, custom is not None, show_]) > 1:
        ui.abort("Use only one of --minimum, --default, --custom or --show")
    if show_ or not (minimum or default or custom):
        show(cfg, px4)
        if not show_:
            ui.console.print("\n[dim]Pick one with --minimum, --default or --custom MODEL.[/]")
        return

    if not cfg.role_spec().get("simulation"):
        ui.warn(f"The {cfg.role} role does not run simulation; continuing anyway")

    if follow is not None and no_follow:
        ui.abort("Use either --follow or --no-follow, not both")

    # --default fills in whatever the flags did not give, from vespo config
    pose_source = ""   # shown next to the spawn point: where it came from
    if default:
        custom = cfg.get("simulation.model", MINIMUM_MODEL)
        world = world or cfg.get("simulation.world")
        if not pose and str(cfg.get("simulation.pose", "auto")) != "auto":
            pose = str(cfg.get("simulation.pose"))
            pose_source = "vespo config"
        if follow is None and not no_follow:
            try:
                camera = follow_value(cfg.get("simulation.follow", "auto"))
            except ValueError as e:
                ui.abort(f"sim_follow: {e}. Fix it with: vespo config edit sim_follow")
            no_follow = camera == "off"
            follow = camera if isinstance(camera, float) else None
        headless = headless or bool(cfg.get("simulation.headless", False))
    if world == "default":
        world = None

    # Model: PX4's own, or one from a workspace package
    model = (custom or MINIMUM_MODEL).removeprefix("gz_")
    ws_models = workspace_models(cfg.ws)
    ws_model = ws_models.get(model)
    if ws_model is None and model not in px4_models(px4):
        _unknown("model", model, px4_models(px4) + list(ws_models),
                 "List them with: vespo simulate --show")

    # World: PX4's own, or one from a workspace package
    ws_worlds = workspace_worlds(cfg.ws)
    ws_world = None
    if world is not None:
        if world in ws_worlds:
            ws_world = ws_worlds[world][1]
        elif world not in px4_worlds(px4):
            _unknown("world", world, px4_worlds(px4) + list(ws_worlds),
                     "List them with: vespo simulate --show")

    env = {"ROS_DOMAIN_ID": str(cfg.get("ros.domain_id", 0))}
    if headless:
        env["HEADLESS"] = "1"
    if world and not ws_world:
        env["PX4_GZ_WORLD"] = world

    spawn = _parse_pose(pose) if pose else _world_spawn(ws_world)
    if spawn:
        x, y, z, yaw = spawn
        env["PX4_GZ_MODEL_POSE"] = f"{x},{y},{z},0,0,{math.radians(yaw):.4f}"

    if no_follow:
        env["PX4_GZ_NO_FOLLOW"] = "1"
    elif follow is not None:
        env.update(PX4_GZ_FOLLOW_OFFSET_X=str(-follow), PX4_GZ_FOLLOW_OFFSET_Y=str(-follow),
                   PX4_GZ_FOLLOW_OFFSET_Z=str(follow))

    # PX4 attaches to any world already running instead of starting its own
    already = running_gz_world()
    if already:
        ui.abort(f"Gazebo is already running the world '{already}'. Close it first "
                 "(or: pkill -f 'gz sim')")

    head = system.git_head(px4) or ""
    pinned = cfg.get("px4.commit", "")

    summary = Table(box=None, show_header=False, pad_edge=False)
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Model", escape(model) + (f" [dim]({ws_model[1]})[/]" if ws_model else ""))
    summary.add_row("World", escape(world or "default") + (f" [dim]({ws_world})[/]" if ws_world else ""))
    if spawn:
        source = pose_source if pose else "spawn.yaml"
        summary.add_row("Spawn", f"x={spawn[0]} y={spawn[1]} z={spawn[2]} yaw={spawn[3]}°"
                        + (f" [dim]({source})[/]" if source else ""))
    summary.add_row("Camera", "free" if no_follow else f"follow at {follow} m" if follow else "follow (PX4 default)")
    summary.add_row("GUI", "no (headless)" if headless else "yes")
    summary.add_row("PX4", escape(f"{px4} @ {head[:12]}"))
    summary.add_row("Domain", env["ROS_DOMAIN_ID"])
    ui.header("vespo simulate")
    ui.console.print(summary)
    ui.console.print()
    if head and pinned and not head.startswith(pinned):
        ui.warn(f"PX4 is at {head[:12]} but the workspace pins {pinned[:12]}: "
                "its messages may not match px4_msgs")
    ui.info("In another terminal: vespo agent  (for the /fmu topics in ROS 2)")
    ui.info("Ctrl+C or `shutdown` at the pxh> prompt to stop")
    ui.console.print()

    if ws_model:
        code = _run_workspace_model(cfg, px4, ws_model, ws_world or _px4_world_file(px4, world), headless, env)
    else:
        gz_procs = _start_gz(cfg, px4, ws_world, headless, env) if ws_world else []
        try:
            code = run(["make", "px4_sitl", f"gz_{model}"], cwd=px4, env=env)
        finally:
            _stop(gz_procs)

    # 130 = stopped with Ctrl+C, the normal way to end it
    if code not in (0, 130, -2):
        ui.abort(f"PX4 SITL exited with code {code}", code)
