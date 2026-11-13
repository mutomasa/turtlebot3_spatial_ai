# TODO

最終更新日：2026年11月13日

全3回（勉強会・テックブログ）の構成に沿って、作業をステップに分けた。各ステップは1つのブランチ・1つのPRで進める（[CLAUDE.md](../CLAUDE.md)）。詳しい仕様は [design_doc.md](design_doc.md) の9節と13節にある。

チェックはPRがマージされてから付ける。

## Step 0：開発基盤

- [ ] 開発方針（CLAUDE.md）、TODO、作業履歴を置く
- [ ] GitHub Actions でテストを自動実行する
- [ ] GitHub Actions の Claude レビューボットを動かす（`ANTHROPIC_API_KEY` の登録が必要）
- [ ] pytest のシナリオテストを `tests/scenarios/` に置く
- [ ] 実機の地図から Gazebo のワールドを作るシミュレーター（`sim/`）をリポジトリに入れる
- [ ] 実機とシミュレーターの差分を `docs/environment.md` に記録する
- [ ] Neo4j を Docker Compose で起動する
- [ ] 机・椅子・植物・部屋のサンプルデータを投入し、`find_objects_near` をLLMなしで実装する

**完了条件：** データ投入、問い合わせ、表示までを README の手順で再現できる。

---

## 第1回：2D LiDAR + RGB-DでつくるSemantic SLAM / Scene Graph

### Step 1-1：TurtleBot3 / ROS 2 / SLAM Toolbox の構成

- [ ] `/map` が配信されることを確認する（Cartographer か SLAM Toolbox）
- [ ] `map_saver_cli` で地図を保存する
- [ ] TFツリー（`map` → `odom` → `base_link` → `base_scan`）を記録する

### Step 1-2：YOLO と Depth による3D物体位置推定

- [ ] RealSense の RGB・Depth・CameraInfo を受信する
- [ ] YOLO で物体を検出する
- [ ] 検出枠の深度から、物体位置を `map` 座標へ投影する（ロジックはROSなしでテストする）

### Step 1-3：同一物体の再観測統合

- [ ] 距離とカテゴリで、新しい観測を既存の物体に対応づける
- [ ] 観測回数と位置の平均・分散を物体ごとに持つ

### Step 1-4：Neo4j で Object と NEAR / IN_ROOM を可視化

- [ ] `upsert_object`、`add_observation`、`upsert_relation`、`expire_relation`、`query_objects` を実装する
- [ ] `NEAR` と `IN_ROOM` を計算して保存する
- [ ] Neo4j Browser でグラフを表示する

### Step 1-5：デモと評価

- [ ] デモ：走行するとグラフに物体と関係が増える
- [ ] rosbag2、手測定した物体座標（GT）、スクリーンショットを保存する
- [ ] 評価：物体位置誤差、関係F1、更新時間

**完了条件：** 同じ記録データを再生すると、同じ物体IDと関係を再現できる。

---

## 第2回：Spatial Knowledge Graph × 生成AIによる意味理解と自律移動

### Step 2-1：LinkML でオントロジーを設計する

- [ ] `ontology/spatial_ai.yaml` に Object、Room、Observation と関係の型を定義する
- [ ] スキーマ検証をテストに入れる

### Step 2-2：Neo4j で対象物体の関係検索

- [ ] 型付き Graph API（`find_objects_near` など）を実装する
- [ ] 存在しない物体・同名の複数候補・不明の応答を返す

### Step 2-3：LangGraph の型付き Tool Calling

- [ ] LLM が呼べるツールを読み取り専用の型付き関数に限定する
- [ ] LLM の出力を Pydantic で検証し、失敗したら停止する

### Step 2-4：Nav2 で安全な到達候補を検証

- [ ] 対象物体の周りから、Costmap 上で到達できるゴールを選ぶ
- [ ] 到達できない場合は移動せず、理由を返す

### Step 2-5：デモと評価

- [ ] デモ：「植物の近くの椅子に行って」
- [ ] 評価：条件A/B/Cの対象特定成功率、移動成功率

**完了条件：** グラフにない物体の位置を作り出さず、認識済みの物体には安全な Nav2 ゴールを出せる。

---

## 第3回：Meta Quest 3で見るロボットのSpatial AI

### Step 3-1：WebXR / Three.js と ROS 2 の状態配信

- [ ] ROS 2 の状態（物体、関係、ロボット位置、経路）をブラウザへ配信する
- [ ] Three.js でグラフを3D表示する

### Step 3-2：map 座標と XR 座標の位置合わせ

- [ ] 対応点から `map` → XR の変換を求める
- [ ] 位置合わせ誤差を測る

### Step 3-3：オブジェクトと関係エッジを MR 空間で表示

- [ ] 物体ノードと `NEAR` / `IN_ROOM` エッジを Quest 3 上に表示する
- [ ] 椅子を動かしたとき、旧位置と新位置の履歴を区別して表示する

### Step 3-4：デモと評価

- [ ] デモ：Quest 3 から対象物体を選び、計画経路を見て移動を承認する
- [ ] 評価：XR位置合わせ誤差、通信遅延

**完了条件：** Quest 上で選んだ物体と、ROS 2 側の物体IDが一致する。
