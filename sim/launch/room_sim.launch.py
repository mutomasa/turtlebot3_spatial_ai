"""Gazebo (gz sim Harmonic) with the scanned room and a TurtleBot3 Burger.

Refuses to start on ROS_DOMAIN_ID=30, the real robot's domain: the simulator
publishes /odom, /scan and /tf and listens on /cmd_vel, which must never mix
with the real TurtleBot3. Use scripts/run_room_sim.sh, which sets an isolated
domain.
"""
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (AppendEnvironmentVariable, DeclareLaunchArgument,
                            IncludeLaunchDescription)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node

SIM_DIR = Path(__file__).resolve().parent.parent
REAL_ROBOT_DOMAIN = "30"


def _refuse_real_robot_domain() -> None:
    if os.environ.get("ROS_DOMAIN_ID", "0") == REAL_ROBOT_DOMAIN:
        raise RuntimeError(
            f"ROS_DOMAIN_ID={REAL_ROBOT_DOMAIN} is the real TurtleBot3; "
            "run the simulator on another domain (scripts/run_room_sim.sh uses 77)")


def _arguments():
    return [
        DeclareLaunchArgument("world", default_value=str(SIM_DIR / "worlds" / "scanned_room.sdf")),
        DeclareLaunchArgument("headless", default_value="false", description="server only, no GUI"),
        DeclareLaunchArgument("x", default_value="0.0"),
        DeclareLaunchArgument("y", default_value="0.0"),
        DeclareLaunchArgument("yaw", default_value="0.0"),
    ]


def _resource_paths():
    share = Path(get_package_share_directory("turtlebot3_description")).parent
    return [
        AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", str(share)),
        AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", str(SIM_DIR / "models")),
    ]


def _gazebo():
    gz_launch = os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")
    world = LaunchConfiguration("world")
    headless = LaunchConfiguration("headless")
    gz_args = PythonExpression(["'-r -v 2 ' + ('-s ' if '", headless, "' == 'true' else '') + '", world, "'"])
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_launch),
        launch_arguments={"gz_args": gz_args, "on_exit_shutdown": "true"}.items(),
    )


def _spawn_robot():
    return Node(
        package="ros_gz_sim", executable="create", output="screen",
        arguments=["-name", "burger", "-file", str(SIM_DIR / "models" / "burger" / "model.sdf"),
                   "-x", LaunchConfiguration("x"), "-y", LaunchConfiguration("y"),
                   "-z", "0.01", "-Y", LaunchConfiguration("yaw")],
    )


def _bridge():
    return Node(
        package="ros_gz_bridge", executable="parameter_bridge", output="screen",
        parameters=[{"config_file": str(SIM_DIR / "config" / "burger_bridge.yaml"),
                     "use_sim_time": True}],
    )


def _robot_state_publisher():
    urdf = os.path.join(get_package_share_directory("turtlebot3_description"),
                        "urdf", "turtlebot3_burger.urdf")
    description = Command(["xacro ", urdf, " namespace:=''"])
    return Node(
        package="robot_state_publisher", executable="robot_state_publisher", output="screen",
        parameters=[{"robot_description": description, "use_sim_time": True}],
    )


def generate_launch_description():
    _refuse_real_robot_domain()
    return LaunchDescription(
        _arguments() + _resource_paths()
        + [_gazebo(), _spawn_robot(), _bridge(), _robot_state_publisher()]
    )
