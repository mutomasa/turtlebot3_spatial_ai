# 作業履歴

最終更新日：2026年11月13日

この文書は、開発作業の記録（開発ログ）と、TurtleBot3 Burgerの起動、遠隔操作、RViz2での可視化、地図作成の調査で行った設定変更を記録する。

## 開発ログ

新しい記録を上に追記する。書き方は次のとおり。

```markdown
### YYYY-MM-DD：<作業の名前>

- ブランチ：`feature/...`
- PR：#番号
- やったこと：
- わかったこと・残った課題：
```

### 2026-11-13：開発方針とテストの整備

- ブランチ：`chore/dev-workflow`、`feature/scenario-tests`
- やったこと：
  - `CLAUDE.md` に開発方針（機能ごとのブランチ、PR、Claude レビューボット、マージはオーナーが判断）を書いた
  - `docs/todo.md` に全3回の作業ステップをまとめた
  - GitHub Actions にテスト実行（`test.yml`）と Claude レビュー（`claude-review.yml`）を追加した
  - `tests/scenarios/` に、実機の地図から Gazebo ワールドを作る流れのシナリオテストを追加した
  - ファイル名の誤記 `work_hisotry.md` を `work_history.md` に直した
- わかったこと・残った課題：
  - Claude レビューを動かすには、リポジトリの Secrets に `ANTHROPIC_API_KEY` を登録する必要がある
  - レビューのワークフローは、`main` にマージされるまで動かない

## TurtleBot3の設定記録（2026年11月9日）

### まず確認すること

1. TurtleBot3本体ではROS 2 Humble、UbuntuワークステーションではROS 2 Jazzyを使っている
2. 両方の端末で`ROS_DOMAIN_ID=30`を設定する
3. モーターを有効にする前に、`/cmd_vel`へ停止指令を送る
4. 地図作成用のSLAMは現在停止しており、地図ファイルはまだ保存できていない

### 現在の構成

| 機器 | OS・ROS 2 | 用途 |
|---|---|---|
| TurtleBot3 Burger | Ubuntu・ROS 2 Humble | Bringup、キーボード操作、LiDAR、オドメトリ、モーター制御 |
| Ubuntuワークステーション | Ubuntu 24.04・ROS 2 Jazzy | ROS 2トピックの受信、RViz2での可視化、地図保存 |
| Mac | ROS 2なし | TurtleBot3へのSSH接続、Ubuntuワークステーションの遠隔デスクトップ操作 |

TurtleBot3とUbuntuワークステーションは、同じネットワーク上でDDS通信を行う。TurtleBot3にUbuntuワークステーションのIPアドレスを個別設定する構成にはしていない。

### TurtleBot3本体の起動設定

TurtleBot3本体の端末で、次の環境変数を設定した。

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-03
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
```

Bringupは次のコマンドで起動した。

```bash
ros2 launch turtlebot3_bringup robot.launch.py
```

起動後、次のトピックをUbuntuワークステーションから確認できた。

- `/battery_state`
- `/cmd_vel`
- `/imu`
- `/joint_states`
- `/odom`
- `/robot_description`
- `/scan`
- `/sensor_state`
- `/tf`
- `/tf_static`

### キーボード操作

TurtleBot3本体の別端末で、次のコマンドを実行した。

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30

ros2 run turtlebot3_teleop teleop_keyboard
```

キーボード操作は動作確認済み。停止には`s`またはスペースキーを使う。

#### モーターを有効にするときの注意

`/motor_power`を有効にした直後、以前の`/cmd_vel`が残っていたため、TurtleBot3が意図せず動いた。モーターを有効にする前に、テレオペレーションを停止させるか、速度ゼロを送る。

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.0}}"

ros2 service call /motor_power std_srvs/srv/SetBool "{data: true}"
```

予期しない動作が続く場合は、本体の電源を切る。

### UbuntuワークステーションのROS 2設定

Ubuntuワークステーションでは、次の設定でTurtleBot3のトピックを受信した。

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=0
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

次のパッケージがインストールされている。

- `ros-jazzy-turtlebot3-description`
- `slam_toolbox`
- `nav2_map_server`

### Ubuntuの画面ロックとサスペンド

Macから遠隔デスクトップを継続して使えるように、UbuntuワークステーションのGNOME設定を変更した。

| 設定 | 現在値 |
|---|---|
| アイドル状態になるまでの時間 | `0` |
| 画面ロック | 無効 |
| アイドル時の画面ロック | 無効 |
| AC電源使用時のアイドル動作 | `nothing` |
| バッテリー使用時のアイドル動作 | `nothing` |

再起動後の自動ログインは設定していない。

### RViz2の設定

RViz2はUbuntuワークステーションで起動した。設定ファイルは次の場所に保存した。

```text
/home/mutomasa/turtlebot3/turtlebot3.rviz
```

確認した設定は次のとおり。

- Fixed Frame：`odom`
- RobotModelのDescription Topic：`/robot_description`
- RobotModelのDurability：`Transient Local`
- LaserScanのTopic：`/scan`
- LaserScanのReliability：`Best Effort`
- ロボットを追従表示するときのTarget Frame：`base_link`

ロボットが小さく表示された場合は、ビューのDistanceを約2まで小さくする。ロボットがグリッド外に見える場合は、Target Frameを`base_link`にする。

RViz2は、ユーザーサービス`codex-turtlebot-rviz.service`として起動した。

### 地図作成と保存の調査

Ubuntuワークステーションで、SLAM Toolboxを使った地図作成を試した。`/scan`、`/odom`、`/tf`、`/tf_static`は受信できたが、`/map`には地図データが配信されなかった。

この状態で次のコマンドを実行したため、地図保存は失敗した。

```bash
ros2 run nav2_map_server map_saver_cli -f ~/turtlebot3/turtlebot3_map
```

エラーは次のとおり。

```text
Failed to spin map subscription
```

SLAM Toolboxのログでは、次の二つを確認した。

- `base_scan`のメッセージがTF待ちのキュー満杯で破棄された
- LaserScanは400点だが、SLAM Toolboxは401点を期待していた

ネットワーク遅延対策として、スキャン待ちキューとTF待機時間を一時的に変更した。LaserScanを補正するノードも試作したが、標準構成としては複雑になるため採用しなかった。

実験用に起動した`codex-turtlebot-slam.service`は停止済み。試作した設定ファイルと補正スクリプトも削除済みで、リポジトリには残していない。

### 現在の状態

| 項目 | 状態 |
|---|---|
| TurtleBot3のBringup | 動作確認済み |
| キーボード操作 | 動作確認済み |
| UbuntuワークステーションでのROS 2トピック受信 | 動作確認済み |
| RViz2でのRobotModel表示 | 動作確認済み |
| RViz2でのLaserScan表示 | 設定済み |
| SLAM | 停止中 |
| `/map`の配信 | 未確認 |
| 地図ファイルの保存 | 未完了 |

### 次に行うこと

次回は、ROS 2 Humbleが動くTurtleBot3本体でTurtleBot3公式の地図作成パッケージを起動する。`/map`の配信を確認してから、Ubuntuワークステーションで`map_saver_cli`を実行する。

実行前に、TurtleBot3本体で次のコマンドを使い、地図作成パッケージが入っているか確認する。

```bash
ros2 pkg list | grep turtlebot3_cartographer
```

パッケージが見つかった場合の起動候補は次のコマンド。これはまだ実行していない。

```bash
ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=False
```
