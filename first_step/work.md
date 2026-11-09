# TurtleBot3の起動とキーボード操作

## 1. TurtleBot3を起動する

TurtleBot3本体に接続したターミナルで、次のコマンドを実行する。

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-03
export ROS_DOMAIN_ID=30

ros2 launch turtlebot3_bringup robot.launch.py
```

## 2. キーボードで操作する

別のターミナルで、次のコマンドを実行する。

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30

ros2 run turtlebot3_teleop teleop_keyboard
```

キーボード操作を終了するときは、`Ctrl+C`を押す。
