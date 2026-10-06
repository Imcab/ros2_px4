# qav250_vespo

Autonomous missions for the VespoUAV QAV250.

- **Outside**, the official PX4 way: the mission is an external flight mode
  (`px4-ros2-interface-lib`). It shows up in QGroundControl as "TMR Gates" and
  respects PX4 failsafes. An executor chains PX4's takeoff, the mission and PX4's
  land.
- **Inside**, command-based like FRC/WPILib: the mode runs a `Sequence` of
  commands (`GoTo`, `Wait`, ...) against a `Vehicle` subsystem.

```
TmrExecutor   takeoff (PX4) -> TmrMode -> land (PX4) -> wait disarmed
   TmrMode    updateSetpoint(): mission_->execute(); vehicle_->update();
     Sequence   GoTo -> Wait -> GoTo -> ...
       Vehicle    goto setpoint + local position (px4_ros2)
FieldFrame    field/Gazebo coordinates -> PX4 NED
```

## Layout

| Path | What |
|---|---|
| `include/qav250_vespo/field_frame.hpp` | Field (ENU) to PX4 NED conversion |
| `include/qav250_vespo/vehicle.hpp` | The subsystem: the only thing commands know about the drone |
| `include/qav250_vespo/command.hpp` | Command base: initialize / execute / isFinished / end |
| `include/qav250_vespo/commands/` | GoTo, Wait |
| `include/qav250_vespo/sequence.hpp` | SequentialCommandGroup |
| `include/qav250_vespo/tmr_mode.hpp` | The mission as a PX4 flight mode |
| `include/qav250_vespo/tmr_executor.hpp` | takeoff -> mission -> land |
| `src/tmr_mission_main.cpp` | Executable |
| `config/tmr_field.yaml` | Waypoints, holds, tolerance, speed (field coordinates) |
| `launch/tmr_mission.launch.py` | Runs the node with the config |
| `test/test_framework.cpp` | Tests that need neither PX4 nor Gazebo |

## Order to implement (TODO 1-9)

1. `FieldFrame`, then test it (TODO 9)
2. `Vehicle`
3. `Command`
4. `GoTo` and `Wait`
5. `Sequence`, then test it
6. `TmrMode`
7. `TmrExecutor`
8. `main`

Build and test after each step:

```bash
vespo build qav250_vespo
colcon test --packages-select qav250_vespo && colcon test-result --verbose
```

## Run

```bash
vespo simulate --default        # qav250 in tmr_field
vespo agent
ros2 launch qav250_vespo tmr_mission.launch.py
```

Then select the "TMR Gates" mode in QGroundControl, or send the
mode switch from ROS 2.

`drone_control` keeps the first examples (takeoff, square, listeners) for
reference.
