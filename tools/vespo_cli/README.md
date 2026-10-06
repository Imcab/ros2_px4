# vespo CLI

Command line tool for the VespoUAV ROS 2 + PX4 workspace. It sets up a
machine, builds what that machine needs and tells you what is broken.

## Fresh machine

From the workspace root:

```bash
./bootstrap.sh
```

It checks Python and ROS, installs missing system tools (`colcon`, `vcs`,
`rosdep`), installs this CLI with `pip install --user -e`, and runs
`vespo init`.

Unattended, e.g. a Jetson over SSH:

```bash
./bootstrap.sh --role companion --serial /dev/ttyTHS1 --yes
```

## Commands

| Command | What it does |
|---|---|
| `vespo init` | Asks the role of the machine and what that role needs, writes `vespo.local.toml`, optionally clones, installs dependencies, builds and adds the workspace to `~/.bashrc`. Re-run it any time: previous answers are the defaults. |
| `vespo doctor [--live]` | Checks ROS, the workspace, the pinned repos, PX4, Gazebo and the link to the flight controller, with a fix for each problem. `--live` also looks for `/fmu` topics. Exits 1 if anything failed. |
| `vespo build [PKG...] [--role R]` | `colcon build --symlink-install`, skipping the packages the role does not need. |
| `vespo clean PKG... [-r]` / `vespo clean --all` | Deletes `build/` and `install/` of those packages (or `build/`, `install/`, `log/` entirely); `-r` rebuilds. `vespo build` suggests it when a failure comes from an old non-symlink build. |
| `vespo agent [--serial DEV] [--udp] [-b BAUD] [-p PORT]` | Runs the Micro XRCE-DDS Agent: UDP for `sim`, the configured serial port for `companion`. The flags override the role, e.g. a Pixhawk on the bench from the sim PC. |
| `vespo simulate --minimum \| --default \| --custom MODEL \| --show [--world W] [--headless]` | Runs PX4 SITL in Gazebo Harmonic (`make px4_sitl gz_<model>`). `--minimum` flies the x500 in PX4's default world, `--default` uses the machine's `sim_*` settings (see `vespo config`), `--custom` any PX4 Gazebo model, `--show` lists models and worlds. `--world` takes a PX4 world or one installed by a workspace package (e.g. `tmr_field`), which vespo starts in Gazebo before PX4 attaches to it. `--custom` also takes workspace models: a `share/<pkg>/models/<model>/` folder with `model.sdf` and its PX4 airframe `<id>_gz_<model>` (e.g. `qav250`). `--pose X,Y[,Z[,YAW]]` sets the spawn point (default: `spawn.yaml` next to a workspace world); `--follow METRES` / `--no-follow` set the camera. |
| `vespo config` | Shows every machine setting and where its value comes from. |
| `vespo config set NAME VALUE` | Changes one setting, validated, without re-running init. |
| `vespo config edit [NAME]` | Asks one setting again from a menu. Changing the role asks for whatever the new role needs; changing `domain_id` updates `~/.bashrc`. |
| `vespo px4 update [REF \| --main \| --release] [--dry-run]` | Moves PX4-Autopilot to a version and px4_msgs to the newest commit with exactly the same messages (compared by git blob hash), pins both in `vespo.toml` / `vespo.repos` and rebuilds px4_msgs and its dependents. Without arguments it offers a menu. |
| `vespo flash [--no-upload] [--target T]` | `make <target> upload` in PX4-Autopilot for the configured flight controller. `--no-upload` only builds. |

## Roles

Defined in `vespo.toml` under `[roles.*]`:

| Role | Machine | Agent link | Simulation |
|---|---|---|---|
| `sim` | Development PC | UDP 8888 | PX4 SITL + Gazebo Harmonic |
| `companion` | Jetson / Raspberry Pi on the drone | Serial to the Pixhawk | No |
| `ground` | Monitoring laptop | None | No |

## Configuration

| File | Committed | Holds |
|---|---|---|
| `vespo.toml` | Yes | Project defaults: ROS distro, PX4 commit, ports, roles |
| `vespo.local.toml` | No | This machine: role, PX4 path, serial port, domain ID |
| `vespo.repos` | Yes | Third-party repos pinned to exact commits |

Local values override project values key by key.

Settings (`vespo config` names): `role`, `domain_id`, `flight_controller`,
`px4_path`, `serial`, `baud`, and for simulation `sim_model`, `sim_world`,
`sim_pose`, `sim_follow`, `sim_headless` (what `vespo simulate --default` runs;
team defaults in `vespo.toml` under `[simulation]`). They are defined once in `vespo_cli/settings.py`
and shared by `init` and `config`.

Flight controllers are listed in `vespo.toml` under `[flight_controllers]`,
each with the PX4 make target `vespo flash` builds. Adding a board is one line.

## Adding a command

1. Create `vespo_cli/commands/<name>.py` with a function named after the command.
2. Register it in `vespo_cli/main.py` with `app.command()(<module>.<function>)`.
3. Read settings with `config.load()` and print through `ui`, like the others.
