"""
`vespo flash`: builds PX4 for this machine's flight controller and uploads it
over USB, i.e. `make <target> upload` inside PX4-Autopilot.

Flashing from the same PX4 checkout the workspace pins is what keeps the
firmware's messages identical to px4_msgs.
"""

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.markup import escape
from rich.table import Table

from .. import config, system, ui
from ..procs import run
from ..settings import confirm


def _abort_config(message, setting):
    ui.abort(f"{message}. Set it with: vespo config edit {setting}")


def flash(
    upload: Annotated[
        bool, typer.Option("--upload/--no-upload", help="Upload over USB after building; --no-upload only builds.")
    ] = True,
    target: Annotated[
        Optional[str], typer.Option(help="PX4 make target, overriding the configured flight controller.")
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Do not ask for confirmation.")] = False,
):
    """Build PX4 for this machine's flight controller and upload it."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    # Where and what to build
    px4_path = cfg.get("px4.path")
    if not px4_path:
        _abort_config("No PX4-Autopilot path configured", "px4_path")
    px4 = Path(px4_path)
    if not system.is_px4_tree(px4):
        _abort_config(f"{px4} is not a PX4-Autopilot checkout", "px4_path")

    fc_id = cfg.get("flight_controller.model")
    fc = cfg.get("flight_controllers", {}).get(fc_id, {})
    if target is None:
        if not fc:
            _abort_config("No flight controller configured", "flight_controller")
        target = fc["target"]

    board_file = system.px4_board_file(px4, target)
    if not board_file.is_file():
        ui.abort(f"PX4 has no target {target} (looked for {board_file})")

    if not shutil.which("arm-none-eabi-gcc"):
        ui.abort(f"ARM toolchain not found. Install it with: bash {px4}/Tools/setup/ubuntu.sh")

    # Firmware messages must match px4_msgs, which is generated from the pinned commit
    head = system.git_head(px4) or ""
    pinned = cfg.get("px4.commit", "")
    matches = bool(head) and head.startswith(pinned)

    summary = Table(box=None, show_header=False, pad_edge=False)
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Flight controller", escape(fc.get("name", "custom target")))
    summary.add_row("Target", escape(target))
    summary.add_row("PX4", escape(f"{px4} @ {head[:12]}"))
    summary.add_row("Action", "build and upload over USB" if upload else "build only")
    ui.header("vespo flash")
    ui.console.print(summary)
    ui.console.print()

    if not matches:
        ui.warn(f"PX4 is at {head[:12]} but the workspace pins {pinned[:12]}: "
                "the firmware's messages may not match px4_msgs")
    if not confirm("Continue?", True if yes else None, False, matches):
        raise typer.Exit(1)

    if upload:
        ui.info("Connect the flight controller over USB and close QGroundControl (it holds the port)")
        ui.info("If the upload keeps waiting for the bootloader, unplug the USB cable and plug it back in")

    code = run(["make", target, *(["upload"] if upload else [])], cwd=px4)
    if code:
        ui.abort("make failed, see the output above", code)

    firmware = px4 / "build" / target / f"{target}.px4"
    ui.ok(f"Firmware: {firmware}")
    if not upload:
        ui.info("Upload it with `vespo flash`, or from QGroundControl as custom firmware")
        return

    ui.ok("Uploaded")
    baud = cfg.get("agent.baud", 921600)
    ui.console.print(
        "\n[bold]For ROS 2 over TELEM2[/] set these in QGroundControl, then reboot:\n"
        f"  UXRCE_DDS_CFG = TELEM 2\n"
        f"  SER_TEL2_BAUD = {baud} 8N1\n"
        "  MAV_1_CONFIG  = Disabled   (if it says TELEM 2)\n"
        f"  UXRCE_DDS_DOM_ID = {cfg.get('ros.domain_id', 0)}   (your ROS_DOMAIN_ID)\n"
        f"[dim]Agent on the other end:[/] MicroXRCEAgent serial --dev /dev/ttyUSB0 -b {baud}"
    )
