"""
`vespo clean`: deletes colcon's build/ and install/ output for some packages,
or everything, and optionally rebuilds.

Needed when a package's previous build is incompatible with the current one,
typically after switching to --symlink-install ("existing path cannot be
removed: Is a directory"). Sources in src/ are never touched.
"""

import re
import shutil
from typing import Annotated, Optional

import typer

from .. import config, ui
from ..settings import confirm
from .build import build_workspace

OUTPUT_DIRS = ("build", "install", "log")
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _size(path):
    total = 0
    for f in path.rglob("*"):
        if f.is_file() and not f.is_symlink():
            total += f.stat().st_size
    return total


def _human(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def clean(
    packages: Annotated[Optional[list[str]], typer.Argument(help="Packages to clean.")] = None,
    all_: Annotated[bool, typer.Option("--all", help="Delete build/, install/ and log/ entirely.")] = False,
    rebuild: Annotated[bool, typer.Option("--rebuild", "-r", help="Build the cleaned packages again.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Do not ask for confirmation.")] = False,
):
    """Delete build output so packages build again from scratch."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    if bool(packages) == all_:
        ui.abort("Name the packages to clean, or use --all")

    if all_:
        targets = [cfg.ws / d for d in OUTPUT_DIRS]
    else:
        bad = [p for p in packages if not PACKAGE_NAME.match(p)]
        if bad:
            ui.abort(f"Not a package name: {', '.join(bad)}")
        targets = [cfg.ws / d / p for p in packages for d in ("build", "install")]

    existing = [t for t in targets if t.exists() or t.is_symlink()]
    for p in packages or []:
        if not any((cfg.ws / d / p).exists() for d in ("build", "install")):
            ui.warn(f"{p} has no build output, nothing to delete")
    if not existing:
        ui.info("Nothing to clean")
    else:
        ui.header("vespo clean")
        for t in existing:
            ui.console.print(f"  {t.relative_to(cfg.ws)}  [dim]{_human(_size(t))}[/]")
        ui.console.print()
        if not confirm("Delete these?", True if yes else None, False, True):
            raise typer.Exit(1)
        for t in existing:
            if t.is_dir() and not t.is_symlink():
                shutil.rmtree(t)
            else:
                t.unlink()
        ui.ok(f"Deleted {len(existing)} folder{'s' if len(existing) != 1 else ''}")
        ui.info("Terminals that sourced the workspace still point at the old install; open a new one")

    if rebuild:
        code = build_workspace(cfg, None if all_ else packages)
        if code:
            ui.abort("Build failed", code)
        ui.ok("Rebuilt")
    elif existing:
        hint = "vespo build" if all_ else f"vespo build {' '.join(packages)}"
        ui.info(f"Build again with: {hint}")
