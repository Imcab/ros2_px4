"""
Launches the TMR mission node with its field configuration.

    ros2 launch qav250_vespo tmr_mission.launch.py
    ros2 launch qav250_vespo tmr_mission.launch.py config:=/path/to/other.yaml

Needs PX4 SITL (vespo simulate --default) and the agent (vespo agent) running.
The node registers the "TMR Gates" mode with PX4; start it from QGroundControl
or by switching to that mode.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_config = Path(get_package_share_directory("qav250_vespo")) / "config" / "tmr_field.yaml"

    return LaunchDescription([
        DeclareLaunchArgument("config", default_value=str(default_config),
                              description="Mission parameters (YAML)"),
        Node(
            package="qav250_vespo",
            executable="tmr_mission",
            name="tmr_mission",   # must match the top key of the YAML
            output="screen",
            emulate_tty=True,
            parameters=[LaunchConfiguration("config")],
        ),
    ])
