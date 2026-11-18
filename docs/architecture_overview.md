# 全体像とROS 2の仕組み

最終更新日：2026年11月18日

この文書は、デモのゴールに向けたシステムの全体像と、その土台にあるROS 2、Gazebo、TurtleBot3 Burger、Meta Quest 3の仕組みを図で説明する。詳しい仕様は [design_doc.md](design_doc.md)、作業の順番は [todo.md](todo.md) にある。

## 目指すデモ

1. ロボットが部屋を走り、2D LiDARのSLAMで地図を作る
2. RGB-DカメラとYOLOで机・椅子・植物などを見つけ、`map`座標での位置を推定する
3. 同じ物体を何度見ても1つのノードにまとめ、`NEAR`（近い）と`IN_ROOM`（どの部屋にあるか）の関係をNeo4jに保存する
4. 「観葉植物の近くの椅子に行って」と頼むと、LLMがグラフを検索して対象を特定する
5. Nav2が安全に到達できるゴールを確かめてから移動する
6. 最後に、地図・物体・関係・経路をMeta Quest 3のMR表示で重ねて見る

---

## 1. 全体像

実機とGazeboは、**同じトピック名・同じ型**でデータを出すように揃える。上位の処理（SLAM、認識、グラフ、Nav2）は、どちらにつながっているかを意識しない。

```mermaid
flowchart LR
    subgraph SRC["データ源（どちらか一方を使う）"]
        direction TB
        subgraph REAL["実機 TurtleBot3 Burger<br/>ROS 2 Humble / ROS_DOMAIN_ID=30"]
            LDS["LDS-03<br/>2D LiDAR"]
            OPENCR["OpenCR<br/>IMU・モータ制御"]
            DXL["DYNAMIXEL ×2<br/>車輪・エンコーダ"]
            RS["RealSense<br/>RGB-D（追加予定）"]
            TBN["turtlebot3_node<br/>ld08/hlds ドライバ"]
            LDS --> TBN
            OPENCR <--> TBN
            DXL <--> OPENCR
        end
        subgraph SIM["Gazebo シミュレーター<br/>ROS_DOMAIN_ID=77"]
            GZ["gz sim<br/>scanned_room.sdf"]
            BR["ros_gz_bridge"]
            GZ <--> BR
        end
    end

    subgraph PC["Ubuntu ワークステーション（ROS 2 Jazzy）"]
        direction TB
        SLAM["SLAM Toolbox / Cartographer<br/>→ /map, map→odom"]
        DET["object_detector_node<br/>YOLO"]
        LOC["object_localizer_node<br/>Depth投影 + TF"]
        TRK["object_tracker_node<br/>同一物体の統合"]
        SG["scene_graph_node<br/>NEAR / IN_ROOM"]
        QA["graph_query_node<br/>型付きGraph API"]
        LLM["LLMエージェント<br/>LangGraph・読み取り専用"]
        SN["semantic_nav_node<br/>ゴール候補の検証"]
        NAV["Nav2"]
        RVIZ["RViz2"]
        XRB["xr_bridge_node<br/>rosbridge / WebSocket"]
    end

    DB[("Neo4j<br/>Spatial Scene Graph")]
    Q3["Meta Quest 3<br/>WebXR + Three.js"]
    USER(["ユーザー<br/>「植物の近くの椅子に行って」"])

    TBN -- "/scan /odom /imu /tf" --> SLAM
    BR -- "/scan /odom /imu /tf /clock" --> SLAM
    RS -- "/camera/*" --> DET
    BR -- "/camera/*" --> DET
    DET -- "Detection2DArray" --> LOC
    LOC -- "/spatial/observations" --> TRK
    SLAM -- "/map + TF" --> LOC
    TRK -- "/spatial/tracked_objects" --> SG
    SG --> DB
    USER --> LLM
    LLM -- "ツール呼び出し" --> QA
    QA --> DB
    LLM -- "検証済みの物体ID" --> SN
    SN -- "NavigateToPose" --> NAV
    NAV -- "/cmd_vel" --> TBN
    NAV -- "/cmd_vel" --> BR
    SLAM --> RVIZ
    SG -- "MarkerArray" --> RVIZ
    NAV --> RVIZ
    DB --> XRB
    SLAM --> XRB
    NAV --> XRB
    XRB <-- "WebSocket" --> Q3
```

### 処理の分担

| 場所 | 担当すること | 担当しないこと |
|---|---|---|
| TurtleBot3（Raspberry Pi 4） | センサーの読み取り、モータへの速度指令 | 物体認識、SLAMの重い計算、LLM |
| ワークステーション | SLAM、物体認識、グラフ構築、Nav2、LLM | モータの直接制御 |
| Neo4j | 物体・関係・観測履歴の保存と検索 | 推論 |
| LLM | 質問を構造化し、Graph APIで対象を探す | `/cmd_vel`の発行、DBへの書き込み |
| Quest 3 | 状態の表示、のちに物体の選択と移動の承認 | ロボットの直接操作 |

### デモの流れ（ステップ4〜6）

```mermaid
sequenceDiagram
    autonumber
    actor U as ユーザー
    participant L as LLMエージェント
    participant G as Graph API
    participant N as Neo4j
    participant S as semantic_nav_node
    participant V as Nav2
    participant R as TurtleBot3
    participant Q as Quest 3

    U->>L: 「観葉植物の近くの椅子に行って」
    L->>G: find_objects_near(target=chair, anchor=plant)
    G->>N: Cypherで検索
    N-->>G: chair_02（根拠：NEAR plant_01, 観測5回）
    G-->>L: 候補と根拠
    L->>L: Pydanticで出力を検証（失敗なら停止）
    L->>S: object_id=chair_02
    S->>S: 物体の周りにゴール候補を作り、costmapで判定
    alt 到達できる候補がある
        S->>Q: 計画経路を表示
        Q-->>S: ユーザーが承認
        S->>V: NavigateToPose(goal)
        loop 走行中
            V->>R: /cmd_vel
            R-->>V: /odom /scan
        end
        V-->>S: SUCCEEDED / FAILED と理由
    else 候補がない
        S-->>L: 移動しない理由を返す
    end
    L-->>U: 結果を説明
```

---

## 2. ROS 2の仕組み

### 2.1 レイヤー構造

ROS 2は、自前で通信を実装していない。下の**DDS**という通信規格のミドルウェアに通信を任せ、`rmw`という層で差し替えられるようにしている。

```mermaid
flowchart TB
    APP["自分のノード<br/>例：object_localizer_node"]
    CL["クライアントライブラリ<br/>rclpy（Python） / rclcpp（C++）"]
    RCL["rcl<br/>C言語の共通実装：ノード・パラメータ・時刻"]
    RMW["rmw<br/>ミドルウェアの抽象化"]
    IMPL["rmw_fastrtps_cpp（既定） / rmw_cyclonedds_cpp / rmw_zenoh"]
    DDS["DDS / RTPS<br/>発見・シリアライズ・QoS・再送"]
    NET["UDP（マルチキャスト / ユニキャスト）・共有メモリ"]

    APP --> CL --> RCL --> RMW --> IMPL --> DDS --> NET
```

- このリポジトリの実機設定では `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`（Fast DDS）を使っている。
- 送受信する両側で同じRMWを使うのが安全。混ぜると発見はできても通信が不安定になることがある。

### 2.2 ノードの発見（Discovery）とROS_DOMAIN_ID

ROS 2には、ROS 1の`roscore`のような中央サーバーがない。各ノードがネットワークに「自分はここにいて、このトピックを出している」と告知し合い、互いを見つける。

```mermaid
sequenceDiagram
    participant A as TurtleBot3<br/>turtlebot3_node
    participant NET as LAN（マルチキャスト）
    participant B as ワークステーション<br/>slam_toolbox

    Note over A,B: 両方とも ROS_DOMAIN_ID=30
    A->>NET: SPDP：参加者の告知（UDP 14900番）
    B->>NET: SPDP：参加者の告知
    NET-->>B: A を発見
    NET-->>A: B を発見
    A->>B: SEDP：/scan を LaserScan型・BEST_EFFORTで出す
    B->>A: SEDP：/scan を LaserScan型で購読したい
    Note over A,B: 型名とQoSが合えば接続成立
    A-)B: /scan のデータ（ユニキャストUDP）
```

- **ROS_DOMAIN_ID** は、使うUDPポート番号を変える。発見用マルチキャストのポートは `7400 + 250 × ドメインID` で、30なら14900番、77なら26650番。**ドメインIDが違うノード同士は互いに見えない**。実機（30）とシミュレーター（77）を分けているのはこのため。
- `ROS_LOCALHOST_ONLY=0` は自分のPCの外とも通信するという設定（Humble）。Jazzyでは代わりに `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` を使う。今の構成は両方を設定しているので、HumbleとJazzyのどちらの側でも意図どおりに動く。
- マルチキャストを通さないWi-Fiルーターでは発見に失敗する。その場合はFast DDSのDiscovery Serverか、ピアのIPアドレスの明示指定を使う。

> **注意：** 実機はHumble、ワークステーションはJazzyで、ディストリビューションが違う。ROS 2はディストリビューションをまたぐ通信を公式にはサポートしていない。`LaserScan`や`Odometry`のような変更のない標準メッセージは通じることが多いが、型の定義が変わったメッセージは通じない。うまくいかないときは、まずこの差を疑う。

### 2.3 通信の4つの形

```mermaid
flowchart LR
    subgraph T["Topic：一方向に流し続ける"]
        P1["turtlebot3_node"] -- "/scan" --> S1["slam_toolbox"]
        P1 -- "/scan" --> S2["rviz2"]
    end
    subgraph SV["Service：1回だけ頼んで返事をもらう"]
        C1["ros2 service call"] -- "/motor_power<br/>SetBool" --> SR1["turtlebot3_node"]
        SR1 -- "success" --> C1
    end
    subgraph AC["Action：時間のかかる仕事。途中経過と取り消しあり"]
        C2["semantic_nav_node"] -- "ゴール" --> SR2["Nav2 bt_navigator<br/>navigate_to_pose"]
        SR2 -- "フィードバック：残り距離" --> C2
        SR2 -- "結果：成功・失敗" --> C2
    end
    subgraph PA["Parameter：ノードごとの設定値"]
        Y["YAMLファイル"] --> N1["ノード"]
        CLI["ros2 param set"] --> N1
    end
```

| 形 | 使う場面 | このプロジェクトでの例 |
|---|---|---|
| Topic | センサー値や速度指令のように、流し続けるもの | `/scan`、`/odom`、`/cmd_vel`、`/map` |
| Service | すぐ終わる要求と応答 | `/motor_power`、地図の保存 |
| Action | 時間がかかり、途中経過や取り消しが要るもの | Nav2の`navigate_to_pose` |
| Parameter | 起動時や実行中に変える設定 | SLAMの解像度、Nav2の速度上限 |

### 2.4 QoS（通信品質の設定）

送信側と受信側のQoSが合わないと、**エラーも出ずにデータが届かない**。RViz2で何も表示されないときの典型的な原因。

| 項目 | 選択肢 | 使い分け |
|---|---|---|
| Reliability | `RELIABLE`：届くまで再送する<br/>`BEST_EFFORT`：落ちても再送しない | センサーは`BEST_EFFORT`。古い値を再送するより新しい値が大事なため |
| Durability | `VOLATILE`：後から来た購読者には過去分を送らない<br/>`TRANSIENT_LOCAL`：最後の値を取っておき、後から来た購読者にも送る | `/map`と`/robot_description`は`TRANSIENT_LOCAL`。1回しか出さないことがあるため |
| History / Depth | 何件まで溜めるか | 画像は小さく、制御は1〜10程度 |

組み合わせの規則：送信側が`BEST_EFFORT`で受信側が`RELIABLE`だと接続しない。逆なら接続する。Durabilityも同じで、受信側が`TRANSIENT_LOCAL`を求めて送信側が`VOLATILE`だと接続しない。RViz2でLaserScanのReliabilityを`Best Effort`に、RobotModelのDurabilityを`Transient Local`にしたのはこの規則のため。

確認するコマンド：

```bash
ros2 topic info -v /scan    # 送信側と受信側のQoSが両方見える
```

### 2.5 TF2（座標変換）

ロボットの各部品の位置関係と、ロボットが地図のどこにいるかを、**時刻つきの木構造**で管理する。

```mermaid
flowchart TB
    MAP["map<br/>地図の原点"]
    ODOM["odom<br/>走り始めの位置"]
    BL["base_footprint / base_link<br/>ロボット本体"]
    SCAN["base_scan<br/>LiDAR"]
    IMU["imu_link"]
    WL["wheel_left_link"]
    WR["wheel_right_link"]
    CAM["camera_link"]
    OPT["camera_color_optical_frame"]
    XR["xr_origin（P3）<br/>Quest 3の空間"]

    MAP -- "SLAM / AMCL が出す<br/>（オドメトリのずれを補正）" --> ODOM
    ODOM -- "turtlebot3_node が出す<br/>車輪の回転から計算" --> BL
    BL -- "robot_state_publisher<br/>URDFの固定値" --> SCAN
    BL --> IMU
    BL -- "joint_states から" --> WL
    BL --> WR
    BL -- "取り付け位置を手で測る" --> CAM
    CAM --> OPT
    MAP -. "対応点から推定" .-> XR
```

- `odom → base_link`はなめらかだが、走るほどずれがたまる。`map → odom`はSLAMが地図との照合でずれを打ち消す。この2段構えにすることで、制御はなめらかなまま、地図上の位置も正しく保てる。
- 物体の位置を`map`座標に直すときは、**画像を撮った時刻のTF**を使う。最新のTFを使うと、走行中に位置がずれる。
- SLAM Toolboxのログに出た「TF待ちのキューが満杯でスキャンを破棄」は、`/scan`の時刻に対応する`odom → base_link`がまだ届いていない、という意味。ネットワークの遅延か、PC同士の時計のずれ（`chrony`で合わせる）が原因の候補になる。

### 2.6 時刻：実時間とシミュレーション時間

- 実機では、各PCのシステム時計を使う。PC同士の時計がずれるとTFの照合に失敗するので、NTP（`chrony`）で揃える。
- Gazeboでは、シミュレーターが`/clock`トピックで時刻を配信する。全ノードを`use_sim_time:=True`で起動し、この時刻に従わせる。実機で`use_sim_time:=True`にすると、時刻が進まずに止まる。

### 2.7 launchとlifecycle

- **launch**：複数のノードを、パラメータやトピック名の付け替え（remap）と一緒にまとめて起動するPythonスクリプト。`ros2 launch turtlebot3_bringup robot.launch.py`がその例。
- **lifecycle node**：`未設定 → 設定済み → 動作中`と状態を持つノード。Nav2の各サーバーはこれで、`lifecycle_manager`が地図やTFの準備ができた順に起動する。Nav2が動かないときは、どのノードが`active`になっていないかを最初に見る。

---

## 3. TurtleBot3 Burgerのセンサー出力と制御

### 3.1 ハードウェアとソフトウェアのつながり

```mermaid
flowchart LR
    subgraph HW["ハードウェア"]
        LDS["LDS-03<br/>360°レーザー距離センサー"]
        IMU["IMU<br/>OpenCR基板に内蔵"]
        ENC["DYNAMIXEL XL430 ×2<br/>モータ + エンコーダ"]
        BAT["LiPoバッテリー<br/>11.1V"]
        OCR["OpenCR 1.0<br/>STM32 マイコン"]
        IMU --- OCR
        ENC <-- "TTL 半二重" --> OCR
        BAT --- OCR
    end

    subgraph PI["Raspberry Pi 4（ROS 2 Humble）"]
        DRV["LiDARドライバ<br/>（robot.launch.py が起動）"]
        TBN["turtlebot3_node"]
        RSP["robot_state_publisher"]
    end

    LDS -- "USB シリアル" --> DRV
    OCR <-- "USB シリアル<br/>DYNAMIXEL Protocol 2.0" --> TBN

    DRV -- "/scan" --> OUT(("ROS 2<br/>ネットワーク"))
    TBN -- "/odom /imu /joint_states<br/>/battery_state /sensor_state<br/>TF: odom→base_footprint" --> OUT
    RSP -- "/tf /tf_static<br/>/robot_description" --> OUT
    TBN -- "/joint_states" --> RSP
    OUT -- "/cmd_vel" --> TBN
    OUT -- "/motor_power（Service）" --> TBN
```

- OpenCRは、Raspberry Piから見ると「DYNAMIXELの1台」のようにふるまう。`turtlebot3_node`は、OpenCRのコントロールテーブル（メモリの番地表）に目標速度を書き込み、エンコーダ値やIMU値を読み出す。
- OpenCRのファームウェアが、モータを決まった周期で制御する。Raspberry PiはROS 2の世界とのつなぎ役。

### 3.2 センサー出力

| トピック | 型 | 中身 | 出し手 |
|---|---|---|---|
| `/scan` | `sensor_msgs/LaserScan` | 360°の距離配列（`ranges`）、角度の始点・刻み、測定範囲。実機では400点 | LiDARドライバ |
| `/odom` | `nav_msgs/Odometry` | 位置・姿勢（`pose`）と速度（`twist`）、共分散 | `turtlebot3_node` |
| `/imu` | `sensor_msgs/Imu` | 姿勢の四元数、角速度、加速度 | `turtlebot3_node` |
| `/joint_states` | `sensor_msgs/JointState` | 左右の車輪の回転角と角速度 | `turtlebot3_node` |
| `/battery_state` | `sensor_msgs/BatteryState` | 電圧・残量 | `turtlebot3_node` |
| `/sensor_state` | `turtlebot3_msgs/SensorState` | バンパー、ボタン、エンコーダの生の値など | `turtlebot3_node` |
| `/tf`、`/tf_static` | `tf2_msgs/TFMessage` | 座標変換（2.5節） | `turtlebot3_node`、`robot_state_publisher` |

**SLAMが「401点を期待」と出した件：** `LaserScan`は`angle_min`、`angle_max`、`angle_increment`から点数を計算できる。SLAM Toolboxは`(angle_max − angle_min) / angle_increment + 1`で点数を見積もるため、ドライバの角度設定によって、実際の点数（400）と1点ずれることがある。LDS-03のドライバの設定値と、SLAM Toolboxの対応を確かめる必要がある。

### 3.3 制御：`/cmd_vel`から車輪まで

```mermaid
flowchart LR
    SRC["teleop_keyboard<br/>または Nav2"] -- "/cmd_vel<br/>linear.x [m/s]<br/>angular.z [rad/s]" --> TBN["turtlebot3_node"]
    TBN -- "目標速度を<br/>コントロールテーブルへ" --> OCR["OpenCR"]
    OCR -- "左右の車輪の<br/>目標回転速度" --> M["DYNAMIXEL ×2"]
    M -- "エンコーダ" --> OCR
    OCR -- "車輪の回転量・IMU" --> TBN
    TBN -- "/odom<br/>odom→base_footprint" --> OUT(("ROS 2"))
```

Burgerは差動二輪（左右の車輪の速度差で曲がる）。車輪の半径を r = 0.033 m、左右の車輪の間隔を L = 0.160 m とすると、

```text
指令から車輪の速度へ：
  v_left  = v − ω · L / 2
  v_right = v + ω · L / 2
  （車輪の回転速度 = v_left / r, v_right / r）

車輪の回転からオドメトリへ（短い時間 Δt ごと）：
  v  = (v_right + v_left) / 2
  ω  = (v_right − v_left) / L
  x += v · cos(θ) · Δt
  y += v · sin(θ) · Δt
  θ += ω · Δt
```

- Burgerの速度上限は、直進0.22 m/s、旋回2.84 rad/s。これを超える指令は切り詰められる。
- オドメトリは、タイヤが滑ると誤差がたまる。これを地図との照合で補正するのがSLAMやAMCL（2.5節の`map → odom`）。
- `/cmd_vel`の型は、構成によって`Twist`と`TwistStamped`が分かれる。Jazzy側のNav2が出す型と、Humble側の`turtlebot3_node`が受ける型を、`ros2 topic info -v /cmd_vel`で必ず確かめる。型が合わないと、エラーなしで動かない。
- 安全：`/motor_power`を有効にする前に、速度ゼロの`/cmd_vel`を送る（[work_history.md](../work_history.md)）。

---

## 4. Gazeboシミュレーター

実機のかわりに、同じトピックを出す仮想のロボットを動かす。実機の地図から部屋を作ると（`sim/`）、実機とシミュレーターで同じ部屋を使える。

```mermaid
flowchart LR
    subgraph GZ["Gazebo（gz sim, Harmonic）"]
        W["ワールド<br/>scanned_room.sdf"]
        PHY["物理エンジン"]
        M["Burgerモデル（SDF）"]
        P1["gpu_lidar センサー<br/>360点・5Hz"]
        P2["IMU センサー"]
        P3["DiffDrive プラグイン"]
        P4["RGB-D カメラ<br/>（追加予定）"]
        W --- PHY --- M
        M --- P1
        M --- P2
        M --- P3
        M --- P4
    end

    BR["ros_gz_bridge<br/>gzのメッセージ ⇔ ROS 2"]
    ROS(("ROS 2<br/>ROS_DOMAIN_ID=77"))

    P1 --> BR
    P2 --> BR
    P3 -- "odom, TF" --> BR
    M -- "joint_states" --> BR
    P4 --> BR
    GZ -- "/clock" --> BR
    BR -- "/scan /imu /odom /tf<br/>/joint_states /clock" --> ROS
    ROS -- "/cmd_vel" --> BR
    BR -- "速度指令" --> P3
```

| | 実機 | Gazebo |
|---|---|---|
| `ROS_DOMAIN_ID` | 30 | 77 |
| 時刻 | システム時計（`use_sim_time:=False`） | `/clock`（`use_sim_time:=True`） |
| `/scan` | LDS-03（実測400点、ノイズあり） | gpu_lidar（`sim/models/burger/model.sdf`で360点・5Hz） |
| オドメトリ | エンコーダから。滑りの誤差あり | DiffDriveプラグインから。ほぼ理想値 |
| `/cmd_vel`の受け手 | `turtlebot3_node` | DiffDriveプラグイン（`Twist`型。`sim/config/burger_bridge.yaml`） |
| カメラ | RealSense（追加予定） | まだモデルにない |

- シミュレーターは誤差が小さいので、うまくいっても実機で同じとは限らない。違いは`docs/environment.md`に記録する（todo Step 0）。
- 今のシミュレーターのLiDARは360点で、実機の400点と違う。点数やノイズを実機に寄せておくと、「401点問題」のようなずれをシミュレーターでも再現できる。

---

## 5. Meta Quest 3との接続（第3回）

```mermaid
flowchart LR
    subgraph WS["ワークステーション"]
        ROS(("ROS 2"))
        XRB["xr_bridge_node<br/>rosbridge_server または foxglove_bridge"]
        DB[("Neo4j")]
        WEB["HTTPSサーバー<br/>WebXRアプリを配信"]
        ROS -- "/map /tf /plan<br/>MarkerArray" --> XRB
        DB -- "物体・関係" --> XRB
    end

    subgraph Q3["Meta Quest 3"]
        BRW["Meta Quest ブラウザ"]
        APP["Three.js + WebXR<br/>immersive-ar セッション"]
        PT["パススルー映像<br/>+ 空間アンカー"]
        BRW --> APP --> PT
    end

    WEB -- "HTTPS（WebXRに必須）" --> BRW
    XRB <-- "WebSocket（JSON）" --> APP
    APP -- "物体の選択<br/>移動の承認" --> XRB
```

### 座標系の違い

| | ROS（REP 103） | WebXR / Three.js |
|---|---|---|
| 手系 | 右手系 | 右手系 |
| 上向き | +Z | +Y |
| 前向き | +X | −Z |
| 単位 | m | m |

`map`座標の点をQuest 3に表示するには、2段の変換をする。

1. **軸の付け替え**：ROSの(x, y, z)を、WebXRの(−y, z, −x)にする（固定の回転）。
2. **位置合わせ**：部屋の中の3点以上の対応点（またはAprilTag）から、`map`とQuest 3の空間の間の回転と平行移動を推定する。誤差は実際に測って記録する（todo Step 3-2）。

最初はQuest 3のブラウザで2D表示を見るところから始め、次にWebXRで現実の部屋に重ねる（[design_doc.md](design_doc.md) 8.2節）。

---

## 6. 今どこにいるか

```mermaid
flowchart LR
    A["Bringup<br/>キーボード操作<br/>RViz2表示"]:::done
    B["/map の配信<br/>地図の保存"]:::now
    C["Gazebo で<br/>同じ構成を再現"]:::done
    D["RealSense<br/>YOLO・Depth投影"]:::todo
    E["Neo4j<br/>Scene Graph"]:::todo
    F["LLM<br/>+ Nav2"]:::todo
    G["Quest 3<br/>MR表示"]:::todo

    A --> B --> D --> E --> F --> G
    B --> C
    C -.-> D

    classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b5e20
    classDef now fill:#fff3c4,stroke:#f9a825,color:#5d4000
    classDef todo fill:#eeeeee,stroke:#9e9e9e,color:#424242
```

| 段階 | 状態 |
|---|---|
| Bringup、キーボード操作、RViz2でのRobotModel表示 | 動作確認済み |
| `/map`の配信と地図の保存 | 止まっている（TFの待ち、LiDARの点数のずれ） |
| Gazebo | 実機の地図からワールドを作るシミュレーター（`sim/`）はPR #2でマージ済み。Nav2はまだ動かしていない |
| 物体認識からQuest 3まで | 未着手 |
