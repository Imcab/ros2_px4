"""
`vespo config`: show or change this machine's settings without re-running
init. Changes go to vespo.local.toml; vespo.toml is never touched.

    vespo config                       show every setting and where it comes from
    vespo config set NAME VALUE        change one, validated
    vespo config edit [NAME]           ask one again, interactively
"""

from typing import Annotated, Optional

import typer
from rich.markup import escape
from rich.table import Table

from .. import config, ui
from ..settings import SETTINGS, choose, confirm, missing_for_role
from .init import bashrc_block, has_bashrc_block, write_bashrc

app = typer.Typer(
    help="Show or change this machine's settings.",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _load():
    try:
        return config.load()
    except config.ConfigError as e:
        ui.abort(str(e))


def _source(cfg, key):
    section, _, name = key.partition(".")
    if name in cfg.local.get(section, {}):
        return "machine"
    return "project" if cfg.get(key) is not None else ""


def show(cfg):
    role = cfg.role
    table = Table(box=None, pad_edge=False, header_style="bold dim")
    table.add_column("Setting", style="bold cyan", no_wrap=True)
    table.add_column("Value", overflow="fold")
    table.add_column("From", style="dim")
    for setting in SETTINGS.values():
        used = setting.applies(cfg, role)
        value = escape(setting.describe(cfg))
        if not used:
            value = f"[dim]{value}  (not used by role {role})[/]"
        elif cfg.get(setting.key) is None:
            value = f"[yellow]{value}[/]"
        table.add_row(setting.name, value, _source(cfg, setting.key))

    ui.console.print(table)
    ui.console.print(
        f"\n[dim]machine = {escape(str(cfg.local_path))}, project = {escape(str(cfg.ws / config.PROJECT_FILE))}[/]"
    )
    ui.console.print("[dim]Change one with[/] vespo config edit [dim]or[/] vespo config set <setting> <value>")


def _after_change(cfg, setting, interactive):
    """Follow-ups a change can need: new role settings, the ~/.bashrc export."""
    cfg = config.load(cfg.ws)

    if setting.name == "role":
        for missing in missing_for_role(cfg, cfg.role):
            if interactive:
                ui.info(f"Role {cfg.role} also needs {missing.label}")
                value = missing.ask(cfg, None, False)
                config.save_local_key(cfg, missing.key, value)
                cfg = config.load(cfg.ws)
            else:
                ui.warn(f"Role {cfg.role} also needs {missing.name}: vespo config edit {missing.name}")

    if setting.name == "domain_id" and has_bashrc_block():
        write_bashrc(bashrc_block(cfg))
        ui.ok("Updated ROS_DOMAIN_ID in ~/.bashrc, open a new terminal to use it")


@app.callback()
def main(ctx: typer.Context):
    """Show or change this machine's settings."""
    if ctx.invoked_subcommand is None:
        show(_load())


@app.command("set")
def set_(
    name: Annotated[str, typer.Argument(help=f"One of: {', '.join(SETTINGS)}.")],
    value: Annotated[str, typer.Argument(help="New value.")],
):
    """Change one setting to VALUE."""
    cfg = _load()
    setting = SETTINGS.get(name)
    if setting is None:
        ui.abort(f"Unknown setting '{name}'. Settings: {', '.join(SETTINGS)}")
    try:
        parsed = setting.parse(cfg, value)
    except ValueError as e:
        ui.abort(str(e))

    config.save_local_key(cfg, setting.key, parsed)
    ui.ok(f"{setting.name} = {config.load(cfg.ws).get(setting.key)}")
    if not setting.applies(cfg, cfg.role):
        ui.info(f"Saved, but role {cfg.role} does not use it")
    _after_change(cfg, setting, interactive=False)


@app.command()
def edit(
    name: Annotated[Optional[str], typer.Argument(help="Setting to change; omit to pick from a list.")] = None,
):
    """Ask one setting again, interactively."""
    cfg = _load()
    while True:
        if name is None:
            options = [
                (s.name, f"{s.label}: {s.describe(cfg)}")
                for s in SETTINGS.values() if s.applies(cfg, cfg.role)
            ]
            name = choose("Which setting?", options, None, None, False, "setting")
        setting = SETTINGS.get(name)
        if setting is None:
            ui.abort(f"Unknown setting '{name}'. Settings: {', '.join(SETTINGS)}")

        value = setting.ask(cfg, None, False)
        if value is None:
            ui.info(f"{setting.name} left unchanged")
        else:
            config.save_local_key(cfg, setting.key, value)
            ui.ok(f"{setting.name} = {setting.describe(config.load(cfg.ws))}")
            _after_change(cfg, setting, interactive=True)

        cfg = config.load(cfg.ws)
        name = None
        if not confirm("Change another setting?", None, False, False):
            break
