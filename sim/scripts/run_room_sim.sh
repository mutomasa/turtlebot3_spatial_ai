#!/usr/bin/env bash
# Start Gazebo with the scanned room and a simulated TurtleBot3 Burger.
#
# The simulator runs on an isolated ROS domain (default 77, this host only) so it
# can never exchange /cmd_vel, /odom or /tf with the real robot on domain 30.
#
# usage: scripts/run_room_sim.sh [headless:=true] [x:=0.0 y:=0.0 yaw:=0.0]
set -euo pipefail

SIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAP_YAML="${MAP_YAML:-$SIM_DIR/maps/turtlebot3_map.yaml}"
WORLD="$SIM_DIR/worlds/scanned_room.sdf"

export ROS_DOMAIN_ID="${SIM_ROS_DOMAIN_ID:-77}"
if [[ "$ROS_DOMAIN_ID" == "30" ]]; then
  echo "refusing to run the simulator on ROS_DOMAIN_ID=30 (real robot)" >&2
  exit 1
fi
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_LOCALHOST_ONLY ROS_STATIC_PEERS
export GZ_IP=127.0.0.1           # keep gz-transport traffic on this host too
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

(cd "$SIM_DIR" && uv run --quiet room-sim-world "$MAP_YAML" -o "$WORLD")

set +u
source /opt/ros/jazzy/setup.bash
set -u
echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID (localhost only)"
exec ros2 launch "$SIM_DIR/launch/room_sim.launch.py" world:="$WORLD" "$@"
