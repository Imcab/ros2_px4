"""
`vespo px4 update`: moves PX4-Autopilot to another version together with
the px4_msgs commit whose messages match it exactly, then pins both and
rebuilds.

px4_msgs is a byte-for-byte copy of PX4's msg/ and msg/versioned/, so a
match is found by comparing git blob hashes of the two trees at candidate
commits. Nothing is checked out until a match is found and confirmed.
"""

import re
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.markup import escape
from rich.table import Table

from .. import config, system, ui
from ..procs import capture, run
from ..settings import choose, confirm
from .build import build_workspace

app = typer.Typer(
    help="Manage the PX4-Autopilot version the workspace uses.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

SYNC_MESSAGE = re.compile(r"Update to PX4 ([0-9a-f]{40})")
STABLE_TAG = re.compile(r"^v\d+\.\d+\.\d+$")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(repo, *args, timeout=60):
    code, out = capture(["git", "-C", str(repo), *args], timeout=timeout)
    return out if code == 0 else None


def resolve(repo, ref):
    """Commit hash for a branch, tag or hash, preferring the remote branch."""
    for candidate in (f"origin/{ref}", ref):
        sha = git(repo, "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}")
        if sha:
            return sha
    return None


def describe(repo, sha):
    """'v1.18.0-beta1-469-g730742b · 2026-08-28' style label for a commit."""
    name = git(repo, "describe", "--tags", "--always", sha) or sha[:12]
    date = git(repo, "log", "-1", "--format=%cs", sha) or ""
    return f"{name} · {date}"


def is_dirty(repo):
    """Tracked files modified. Untracked files and ignored build output are fine."""
    return bool(git(repo, "status", "--porcelain", "--untracked-files=no"))


def msg_blobs(repo, commit, dirs):
    """{file name: blob hash} for the .msg files directly inside `dirs` at `commit`."""
    out = git(repo, "ls-tree", "-r", commit, "--", "msg")
    blobs = {}
    for line in (out or "").splitlines():
        meta, path = line.split("\t", 1)
        parent, _, name = path.rpartition("/")
        if parent in dirs and name.endswith(".msg"):
            blobs[name] = meta.split()[2]
    return blobs


# ---------------------------------------------------------------------------
# Choosing the target and its px4_msgs match
# ---------------------------------------------------------------------------

def msgs_branches(msgs_repo):
    out = git(msgs_repo, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
    return [b for b in (out or "").split() if b == "origin/main" or b.startswith("origin/release/")]


def find_msgs_match(px4, target, msgs_repo):
    """
    Newest px4_msgs commit (main and release branches) defining every message
    of PX4 at `target` identically. Extra messages in px4_msgs are harmless.
    """
    wanted = msg_blobs(px4, target, ("msg", "msg/versioned"))
    if not wanted:
        return None
    commits = git(msgs_repo, "rev-list", "--date-order", *msgs_branches(msgs_repo)) or ""
    for commit in commits.split():
        have = msg_blobs(msgs_repo, commit, ("msg",))
        if all(have.get(name) == blob for name, blob in wanted.items()):
            return commit
    return None


def newest_synced_main(px4, msgs_repo):
    """The PX4 commit named by the newest 'Update to PX4 <sha>' on px4_msgs main."""
    log = git(msgs_repo, "log", "--format=%s", "-50", "origin/main") or ""
    for subject in log.splitlines():
        match = SYNC_MESSAGE.search(subject)
        if match and git(px4, "cat-file", "-e", f"{match.group(1)}^{{commit}}") is not None:
            return match.group(1)
    return None


def latest_stable(px4):
    tags = git(px4, "tag", "-l", "v*", "--sort=-v:refname") or ""
    return next((t for t in tags.split() if STABLE_TAG.match(t)), None)


def pick_target(px4, msgs_repo, ref, main, release, yes):
    """Returns (sha, label) of the PX4 commit to move to."""
    if ref:
        sha = resolve(px4, ref)
        if sha is None:
            ui.abort(f"'{ref}' is not a branch, tag or commit of PX4-Autopilot")
        return sha, ref

    synced = newest_synced_main(px4, msgs_repo)
    stable = latest_stable(px4)
    if main or release:
        if main and synced is None:
            ui.abort("No px4_msgs sync commit on main points to a PX4 commit found locally")
        if release and stable is None:
            ui.abort("No stable vX.Y.Z tag found in PX4-Autopilot")
        return (synced, "main") if main else (resolve(px4, stable), stable)
    if yes:
        ui.abort("Say which version: a REF argument, --main or --release")

    options = []
    if synced:
        options.append(("main", f"Newest main px4_msgs supports: {describe(px4, synced)}"))
    if stable:
        options.append(("release", f"Latest stable release: {stable}"))
    options.append(("other", "Other: type a branch, tag or commit"))
    choice = choose("Move PX4 to", options, options[0][0], None, False, "target")
    if choice == "main":
        return synced, "main"
    if choice == "release":
        return resolve(px4, stable), stable
    return pick_target(px4, msgs_repo, typer.prompt("Branch, tag or commit"), False, False, False)


# ---------------------------------------------------------------------------
# Pins
# ---------------------------------------------------------------------------

def pin_px4(cfg, sha):
    """Rewrites px4.commit in vespo.toml, keeping every comment."""
    path = cfg.ws / config.PROJECT_FILE
    text = path.read_text()
    pattern = re.compile(r'(^\[px4\]$.*?^commit\s*=\s*)"[^"]*"', re.MULTILINE | re.DOTALL)
    new, count = pattern.subn(lambda m: f'{m.group(1)}"{sha}"', text, count=1)
    if count != 1:
        raise RuntimeError(f"No commit = \"...\" under [px4] in {path}")
    path.write_text(new)


def pin_px4_msgs(cfg, sha, px4_sha):
    """Rewrites the px4_msgs version line in vespo.repos, keeping the rest."""
    path = cfg.repos_path
    text = path.read_text()
    pattern = re.compile(r"(^  px4_msgs:\n(?:    .*\n)*?    version: )\S+.*$", re.MULTILINE)
    line = f"{sha}  # matches PX4 {px4_sha[:12]}, found by vespo px4 update"
    new, count = pattern.subn(lambda m: m.group(1) + line, text, count=1)
    if count != 1:
        raise RuntimeError(f"No px4_msgs version line in {path}")
    path.write_text(new)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@app.command()
def update(
    ref: Annotated[Optional[str], typer.Argument(help="PX4 branch, tag or commit. Omit to choose from a menu.")] = None,
    main: Annotated[bool, typer.Option("--main", help="Newest PX4 main that px4_msgs supports.")] = False,
    release: Annotated[bool, typer.Option("--release", help="Latest stable PX4 release.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show the plan, change nothing.")] = False,
    fetch: Annotated[bool, typer.Option("--fetch/--no-fetch", help="Fetch both repos first.")] = True,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Do not ask for confirmation.")] = False,
):
    """Move PX4 and px4_msgs to matching versions, pin them and rebuild."""
    try:
        cfg = config.load()
    except config.ConfigError as e:
        ui.abort(str(e))

    if sum([bool(ref), main, release]) > 1:
        ui.abort("Use only one of: REF, --main, --release")

    px4 = Path(cfg.get("px4.path") or "")
    if not system.is_px4_tree(px4):
        ui.abort("No PX4-Autopilot configured. Set it with: vespo config edit px4_path")
    msgs_repo = cfg.ws / "src" / "px4_msgs"
    if not (msgs_repo / ".git").exists():
        ui.abort("src/px4_msgs is not cloned: vcs import --input vespo.repos --skip-existing src")
    if not dry_run:
        for repo in (px4, msgs_repo):
            if is_dirty(repo):
                ui.abort(f"{repo} has uncommitted changes. Commit or stash them first")

    if fetch:
        ui.header("Fetching")
        for repo in (px4, msgs_repo):
            ui.info(f"git fetch {repo.name}")
            if run(["git", "-C", str(repo), "fetch", "--tags", "origin"]):
                ui.abort(f"git fetch failed in {repo}")

    target, label = pick_target(px4, msgs_repo, ref, main, release, yes)
    ui.info(f"Looking for the px4_msgs commit matching PX4 {target[:12]}…")
    match = find_msgs_match(px4, target, msgs_repo)

    px4_now = system.git_head(px4) or ""
    msgs_now = system.git_head(msgs_repo) or ""
    plan = Table(box=None, pad_edge=False, header_style="bold dim")
    plan.add_column("")
    plan.add_column("Now")
    plan.add_column("After")
    plan.add_row("[bold]PX4-Autopilot", escape(describe(px4, px4_now)), escape(f"{describe(px4, target)} ({label})"))
    plan.add_row(
        "[bold]px4_msgs", escape(describe(msgs_repo, msgs_now)),
        escape(describe(msgs_repo, match)) if match else "[red]no matching commit[/]",
    )
    ui.header("Plan")
    ui.console.print(plan)
    ui.console.print()

    if match is None:
        ui.abort(
            "px4_msgs has no commit with exactly these messages; px4_msgs syncs with PX4 main "
            "a few times a week, so a very recent PX4 commit may not be covered yet. "
            "Try --main, which always has a match"
        )
    if target == px4_now and match == msgs_now:
        ui.ok("Already there, nothing to do")
        return
    if dry_run:
        ui.info("Dry run, nothing changed")
        return
    if not confirm("Apply?", True if yes else None, False, True):
        raise typer.Exit(1)

    ui.header("Checking out PX4")
    if run(["git", "-C", str(px4), "checkout", "--quiet", target]):
        ui.abort("git checkout failed in PX4-Autopilot")
    ui.info("Updating submodules, this can take a while")
    if run(["git", "-C", str(px4), "submodule", "update", "--init", "--recursive"]):
        ui.abort(f"Submodule update failed. PX4 is at {target[:12]}; rerun the command to retry")

    ui.header("Checking out px4_msgs")
    if run(["git", "-C", str(msgs_repo), "checkout", "--quiet", match]):
        ui.abort("git checkout failed in px4_msgs")

    pin_px4(cfg, target)
    pin_px4_msgs(cfg, match, target)
    ui.ok(f"Pinned PX4 {target[:12]} in {config.PROJECT_FILE} and px4_msgs {match[:12]} in {config.REPOS_FILE}")

    ui.header("Rebuilding px4_msgs and everything that uses it")
    if build_workspace(cfg, above=["px4_msgs"]):
        ui.abort("Build failed. If it mentions 'existing path cannot be removed', run: vespo clean px4_msgs -r")

    ui.ok("PX4 and px4_msgs updated and matching")
    ui.console.print(
        "\n[bold]Next[/]\n"
        "  Simulation rebuilds PX4 on its next start (make px4_sitl …)\n"
        "  Real flight controller: vespo flash\n"
        f"[dim]  To go back: vespo px4 update {px4_now[:12]}[/]"
    )
