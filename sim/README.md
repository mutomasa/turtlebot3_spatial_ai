# 部屋のシミュレーター（Gazebo Harmonic）

実機で作った地図（`maps/turtlebot3_map.yaml` と `.pgm`）から壁を立ち上げ、Gazebo 上で TurtleBot3 Burger を動かす。

## 起動

```bash
scripts/run_room_sim.sh                  # GUI あり
scripts/run_room_sim.sh headless:=true   # サーバーのみ
scripts/run_room_sim.sh x:=0.5 y:=0.0    # 出現位置（map 座標）
```

- 起動のたびに、地図からワールド（`worlds/scanned_room.sdf`）を作り直す。
- **ROS_DOMAIN_ID=77、このマシン内だけで通信する**。実機のドメイン 30 では起動できない（launch ファイル側でも拒否する）。
- トピック名は実機と同じ：`/cmd_vel`、`/odom`、`/scan`、`/tf`、`/imu`、`/joint_states`、`/clock`。

## 地図からワールドへの変換

```bash
uv run room-sim-world maps/turtlebot3_map.yaml -o worlds/scanned_room.sdf --wall-height 0.5
uv run pytest
```

占有セル（map_server と同じ判定）を長方形にまとめて、高さ 0.5m の壁として置く。ワールドの原点は地図の `map` 座標と一致する。
