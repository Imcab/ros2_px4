"""
`vespo agent`: runs the Micro XRCE-DDS Agent, the bridge between PX4's
uXRCE-DDS client and ROS 2.

The transport follows the machine's role: UDP for `sim` (PX4 SITL on this
PC), serial for `companion` (wired to the flight controller). --serial or
--udp override it, e.g. to test a Pixhawk on the bench from the sim PC.

The ROS domain is not chosen here: PX4 picks it, from ROS_DOMAIN_ID in SITL
and from the UXRCE_DDS_DOM_ID parameter on a real flight controller.
"""

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from .. import config, system, ui
from ..procs import run


def agent_binary(cfg):
    built = cfg.ws / "install" / "microxrcedds_agent" / "bin" / "MicroXRCEAgent"
    return str(built) if built.is_file() else shutil.which("MicroXRCEAgent")


def agent(
    serial: Annotated[
        Optional[str], typer.Option(help="Use this serial device, whatever the role (e.g. /dev/ttyUSB0).")
    ] = None,
    baud: Annotated[Optional[int], typer.Option("--baud", "-b", help="Serial baud rate. Default: agent.baud.")] = None,
    udp: Annotated[bool, typer.Option("--udp", help="Use UDP, whatever the role.")] = False,
    port: Annotated[Optional[int], typer.Option("--port", "-p", help="UDP port. Default: agent.udp_port.")] = None,
    verbose: Annotated[int, typer.Option("--verbose", "-v", min=0, max=6, help="Agent log level, 0-6.")] = 4,
):
    """Run the Micro XRCE-DDS Agent, over UDP or serial as the role needs."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    if serial and udp:
        ui.abort("Use either --serial or --udp, not both")

    binary = agent_binary(cfg)
    if binary is None:
        ui.abort("MicroXRCEAgent is not built. Build it with: vespo build microxrcedds_agent")

    link = "serial" if serial else "udp" if udp else cfg.role_spec().get("link", "none")
    domain = cfg.get("ros.domain_id", 0)
    summary = Table(box=None, show_header=False, pad_edge=False)
    summary.add_column(style="bold")
    summary.add_column()

    if link == "udp":
        port = port or int(cfg.get("agent.udp_port", 8888))
        if not system.udp_port_free(port):
            ui.abort(f"UDP port {port} is in use, probably by another agent. Stop it or use --port")
        cmd = [binary, "udp4", "-p", str(port), "-v", str(verbose)]
        summary.add_row("Transport", f"UDP {port}")
        summary.add_row("Domain", f"{domain} (PX4 SITL takes it from ROS_DOMAIN_ID)")

    elif link == "serial":
        device = serial or cfg.get("agent.device")
        if not device:
            ui.abort("No serial device configured. Use --serial or: vespo config edit serial")
        if not Path(device).exists():
            found = system.serial_candidates()
            ui.abort(f"{device} does not exist. Serial ports found: {', '.join(found) or 'none'}")
        if not system.in_group("dialout"):
            ui.abort("You are not in the dialout group: sudo usermod -aG dialout $USER, then log in again")
        baud = baud or int(cfg.get("agent.baud", 921600))
        cmd = [binary, "serial", "--dev", device, "-b", str(baud), "-v", str(verbose)]
        summary.add_row("Transport", f"serial {device} @ {baud}")
        summary.add_row("Domain", f"{domain} (set by UXRCE_DDS_DOM_ID on the flight controller)")

    else:
        ui.abort(f"Role {cfg.role} has no agent link. Use --udp or --serial <device>")

    ui.header("vespo agent")
    ui.console.print(summary)
    if link == "serial" and domain != 0:
        ui.warn(f"Your domain is {domain}: set UXRCE_DDS_DOM_ID = {domain} on the flight controller too")
    ui.info("Ctrl+C to stop")
    ui.console.print()

    code = run(cmd)
    # 130 = stopped with Ctrl+C, the normal way to end it
    if code not in (0, 130, -2):
        ui.abort(f"MicroXRCEAgent exited with code {code}", code)
