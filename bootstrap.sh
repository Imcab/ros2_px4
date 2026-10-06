#!/usr/bin/env bash
#
# First step on a fresh machine: checks the base system, installs the vespo
# CLI and hands over to `vespo init`. Safe to run again.
#
#   ./bootstrap.sh
#   ./bootstrap.sh --role companion --serial /dev/ttyTHS1 --yes
#
# Every argument is passed through to `vespo init`.

set -euo pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISTRO="$(sed -n 's/^ros_distro *= *"\([^"]*\)".*/\1/p' "$WS/vespo.toml" | head -n1)"
DISTRO="${DISTRO:-humble}"
APT_PKGS=(git python3-pip python3-colcon-common-extensions python3-vcstool python3-rosdep)

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

ASSUME_YES=0
for arg in "$@"; do
  [[ "$arg" == "--yes" || "$arg" == "-y" ]] && ASSUME_YES=1
done

say "Workspace: $WS"

command -v python3 >/dev/null || die "python3 not found"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
  || die "Python 3.10+ is required, found $(python3 --version)"

[[ -f "/opt/ros/$DISTRO/setup.bash" ]] \
  || die "ROS 2 $DISTRO is not installed: https://docs.ros.org/en/$DISTRO/Installation.html"

missing=()
for pkg in "${APT_PKGS[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if (( ${#missing[@]} )); then
  say "Missing system packages: ${missing[*]}"
  answer=y
  (( ASSUME_YES )) || read -rp "Install them with sudo apt now? [Y/n] " answer
  case "${answer:-y}" in
    [Yy]*) sudo apt-get update && sudo apt-get install -y "${missing[@]}" ;;
    *) die "Install them and run this script again." ;;
  esac
fi

# Ubuntu 22.04 ships pip 22.0, which cannot do editable installs from a
# pyproject.toml-only project. Upgrade it for this user only.
if ! python3 -c 'import sys, pip; sys.exit(int(pip.__version__.split(".")[0]) < 23)'; then
  say "Upgrading pip for $USER (the system pip is too old for editable installs)"
  python3 -m pip install --user --quiet --upgrade "pip>=23"
fi

say "Installing the vespo CLI"
python3 -m pip install --user --quiet -e "$WS/tools/vespo_cli"

case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) say "~/.local/bin is not on PATH yet. Log out and back in, or run: python3 -m vespo_cli" ;;
esac

exec python3 -m vespo_cli init "$@"
