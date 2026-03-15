# 実装計画

## 1. 目的

`docs/theory.md` で定義した非平衡超伝導ソルバー基盤を、

- `frontend`: React + TypeScript
- `backend`: FastAPI

の二層構成で実装する。

初期目標は、

1. パラメーターをブラウザから入力できる
2. バックエンドでシミュレーションを実行できる
3. 観測量を取得して時系列プロットできる

という最小研究基盤を作ることである。

本書は、理論ロードマップを Web アプリケーション構成へ落とし込んだ実装計画である。

---

## 2. 初期スコープ

初期実装で扱う範囲は以下とする。

- 単一ユーザーのローカル研究環境
- 2 次元格子系の baseline 実装
- 非相互作用ソルバーから開始し、TDHFB / BdG までを優先
- 実行履歴の保存
- 粒子密度、電流、エネルギー、pairing などの観測量表示

初期段階では以下を対象外とする。

- 認証、権限管理、マルチテナント
- 分散ジョブキューやクラスタ連携
- full two-time KBE の大規模実行最適化
- 高度な可視化比較 UI

---

## 3. 全体構成

### 3.1 アーキテクチャ方針

- フロントエンドは入力、実行制御、可視化に専念する
- バックエンドは物理モデル、検証、ジョブ実行、結果保存を担う
- 理論・数値実装の中核は backend 内の Python パッケージとして保持する
- API 契約は FastAPI の OpenAPI を正とし、frontend の型定義はこれに追従させる

### 3.2 想定構成

```text
TDKB/
├─ frontend/
│  ├─ src/
│  │  ├─ app/
│  │  ├─ components/
│  │  ├─ features/
│  │  │  ├─ config/
│  │  │  ├─ runs/
│  │  │  └─ plots/
│  │  ├─ api/
│  │  └─ types/
│  └─ public/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ jobs/
│  │  ├─ solvers/
│  │  ├─ observables/
│  │  └─ storage/
│  ├─ tests/
│  └─ data/
│     └─ runs/
└─ docs/
```

### 3.3 データフロー

1. frontend でパラメーターを入力する
2. frontend が backend に実行要求を送る
3. backend が設定を検証し、run を生成する
4. backend のジョブ実行層がソルバーを起動する
5. backend が観測量と診断量を保存する
6. frontend が run 状態と観測量を取得し、プロットする

---

## 4. frontend の責務

frontend は研究用ダッシュボードとして設計する。

### 4.1 主要機能

- パラメーター入力フォーム
- solver 種別の選択
- 実行開始、停止、再実行
- 実行状態の表示
- 観測量の時系列プロット
- 実行条件と結果メタデータの表示

### 4.2 画面構成

初期版は単一ページ構成でよい。

- `ConfigPanel`
  - 格子サイズ、境界条件、時間刻み
  - 相互作用パラメーター
  - 光パルス設定
  - 初期状態設定
- `RunControlPanel`
  - 実行開始
  - 実行中表示
  - 直近 run の選択
- `ObservablePanel`
  - 観測量の選択
  - 複数系列の重ね描き
  - 軸切替、凡例、時刻カーソル
- `DiagnosticsPanel`
  - 保存則残差
  - 対称性残差
  - 計算メタ情報

### 4.3 frontend 実装方針

- 入力フォームは backend schema に対応したセクション分割にする
- フォーム検証は frontend 側でも行うが、最終判定は backend に置く
- run 状態取得は初期版では polling を採用する
- 可視化対象は backend が返す整形済み観測量データに限定する

初期段階で frontend が直接 solver 内部データへ依存しないようにする。

---

## 5. backend の責務

backend は API 層と数値計算層を同居させるが、責務を分離して設計する。

### 5.1 API 層

- リクエスト受理
- パラメーター検証
- run 管理
- 観測量取得 API
- ログと診断情報の提供

### 5.2 数値計算層

- 格子、bond、Nambu 表現の基盤
- one-body Hamiltonian builder
- TDHFB / BdG ソルバー
- 将来の KBE ソルバー
- 観測量評価
- 保存則、対称性、収束性の記録

### 5.3 ジョブ実行層

数値計算は CPU バウンドであり、HTTP リクエスト処理と分離する。

初期版では以下を採用する。

- API は run 設定を保存してジョブを登録する
- ジョブ本体は別プロセスで実行する
- run 状態は `queued/running/succeeded/failed/cancelled` を持つ

`FastAPI BackgroundTasks` に直接長時間計算を載せず、
プロセス分離された実行方式を最初から採用する。

---

## 6. backend の内部構成

### 6.1 `schemas/`

Pydantic で以下を定義する。

- `SimulationConfig`
- `LatticeConfig`
- `TimeGridConfig`
- `DriveConfig`
- `InteractionConfig`
- `InitialStateConfig`
- `ObservableRequest`
- `RunSummary`
- `RunDiagnostics`

### 6.2 `solvers/`

理論ドキュメントのフェーズに対応して実装する。

- `noninteracting/`
- `tdhfb/`
- `kbe_hfb/`
- `kbe_second_born/`

共通部品として以下を切り出す。

- `lattice.py`
- `nambu.py`
- `hamiltonian.py`
- `propagators.py`
- `self_energy.py`
- `observables.py`

### 6.3 `storage/`

結果保存は run 単位のディレクトリ構成にする。

```text
backend/data/runs/{run_id}/
├─ config.json
├─ status.json
├─ summary.json
├─ diagnostics.json
├─ observables.npz
└─ run.log
```

初期版では

- メタデータは JSON
- 時系列配列は `npz`

とし、frontend には API 経由で必要部分のみ返す。

---

## 7. API 設計の初期案

### 7.1 run 管理

- `POST /api/v1/runs`
  - 実行要求を登録する
- `GET /api/v1/runs`
  - 実行履歴一覧を返す
- `GET /api/v1/runs/{run_id}`
  - 単一 run の状態とメタデータを返す
- `POST /api/v1/runs/{run_id}/cancel`
  - 実行中 run を停止する

### 7.2 観測量取得

- `GET /api/v1/runs/{run_id}/observables`
  - 利用可能な観測量一覧を返す
- `GET /api/v1/runs/{run_id}/observables/{name}`
  - 指定観測量の時系列データを返す

### 7.3 補助 API

- `GET /api/v1/health`
- `GET /api/v1/presets`
- `GET /api/v1/schema/simulation`

`/schema/simulation` を用意しておくと、
frontend のフォーム生成やバリデーション同期に使いやすい。

---

## 8. 観測量データの扱い

frontend で直接扱うデータは、
グラフ描画に必要な形へ backend 側で整形して返す。

返却形式の最小単位は以下とする。

```json
{
  "name": "pairing_dwave",
  "time": [0.0, 0.1, 0.2],
  "series": [
    {
      "label": "real",
      "values": [0.0, 0.02, 0.03]
    },
    {
      "label": "imag",
      "values": [0.0, 0.00, -0.01]
    }
  ],
  "units": null,
  "metadata": {
    "solver": "tdhfb"
  }
}
```

複素量は初期版では `real/imag` に分解して返す。
将来的に振幅・位相表示を追加してよい。

---

## 9. 理論ロードマップとの対応

`docs/theory.md` の Phase 0-5 を、Web アプリ実装では以下のように再構成する。

### Phase A: 基盤整備

- `frontend/` と `backend/` の雛形作成
- backend schema と OpenAPI の確立
- run 保存ディレクトリ設計
- mock 観測量 API の実装

完了条件:

- frontend から mock run を作成できる
- 観測量プロットが UI 上で表示される

### Phase B: 非相互作用ソルバー統合

- one-body Hamiltonian builder
- 非相互作用時間発展
- 粒子密度、電流、エネルギー出力
- run 実行と結果保存

完了条件:

- UI から非相互作用 run を実行できる
- エネルギー変化と外場仕事率の基本整合を確認できる

### Phase C: TDHFB / BdG 統合

- HFB 平衡初期状態
- 一般化密度行列の時間発展
- pairing 観測量
- `s` / `d` 射影表示

完了条件:

- UI から TDHFB run を実行できる
- pairing 系列と診断量を同一画面で確認できる

### Phase D: KBE + HFB 統合

- two-time Green 関数コンテナ
- HFB self-energy
- 等時極限の TDHFB 一致検証
- 診断量 API の拡張

完了条件:

- backend テストで TDHFB 一致が確認できる
- frontend で run サマリーと主要観測量を表示できる

### Phase E1: fixed-grid KBE + second Born

- uniform time grid 上の memory self-energy
- 新しい行・列に対する自己無撞着固定点反復
- 緩和過程の出力
- 保存則残差、収束履歴、\(\Delta t\) 回帰の記録

完了条件:

- HFB 極限への連続接続が backend テストで確認できる
- 保存則残差と収束情報を run ごとに記録できる
- 少なくとも 1 種の相関効果付き run が UI から可視化できる

### Phase E2: adaptive full-KBE integrator

- 可変 time step / method order
- history integral order の適応
- variable-step history storage と補間重みの管理
- 長時間 run 向けの結果取得最適化

完了条件:

- fixed-grid 参照解に対して同等精度を維持できる
- adaptive step / order / iteration の診断量を run ごとに記録できる
- 長時間 run で fixed-grid より有利な計算条件を示せる

### Phase E3: thermal branch / Matsubara 初期化

- Matsubara および mixed 成分
- 相関した熱平衡初期状態
- factorized 初期化との比較基準整備

完了条件:

- thermal branch 付き run を backend で安定実行できる
- factorized 初期化との差分を比較できる
- finite-temperature superconducting benchmark を再現できる

---

## 10. 開発順序

### 10.1 先に整えるもの

最初に固定すべきものは solver 実装ではなく、以下である。

- パラメーター schema
- run 状態モデル
- 観測量レスポンス形式
- 結果保存形式

特に Phase E1 では `dt` 固定の schema を維持し、
variable-step 用の tolerances や order 制御パラメーターは
Phase E2 で追加する。

これらを先に固定することで、
frontend と backend を並行開発できる。

### 10.2 並行開発の切り分け

- frontend は mock API で先行開発する
- backend は CLI から solver を起動できる状態を先に作る
- API 連携は mock から実 solver へ差し替える

この順序により、solver 完成待ちで UI 開発が止まることを防ぐ。

---

## 11. テスト方針

### 11.1 backend

- schema validation test
- Hamiltonian builder test
- observables test
- solver regression test
- API integration test

### 11.2 frontend

- 入力フォーム validation test
- run 状態遷移の表示 test
- 観測量プロット表示 test

### 11.3 end-to-end

- パラメーター入力
- run 実行
- 完了待ち
- 観測量表示

までの最小動線を自動化する。

---

## 12. 初期マイルストーン

### Milestone 1

リポジトリを `frontend/backend` に分割し、
mock API と仮プロット画面を動かす。

### Milestone 2

非相互作用ソルバーを backend に接続し、
UI から run を実行して粒子密度とエネルギーを表示する。

### Milestone 3

TDHFB / BdG を接続し、
pairing と診断量を表示する。

### Milestone 4

KBE + HFB を backend に追加し、
理論ドキュメントの一致検証を自動テストへ組み込む。

---

## 13. 実装上の重要判断

- physics の正しさは backend で担保する
- frontend は solver の内部表現を知らない
- 長時間計算は API プロセスから分離する
- 観測量と診断量は run と同時に保存する
- `docs/theory.md` を物理仕様の正本、本書を実装仕様の正本とする

---

## 14. 次の作業

この計画に基づく最初の具体作業は以下である。

1. `frontend/` と `backend/` のディレクトリを作る
2. backend に FastAPI 雛形と `SimulationConfig` schema を作る
3. frontend にパラメーター入力画面と mock プロット画面を作る
4. run 作成 API と polling を接続する

この順で進めれば、理論ソルバーの詳細実装と UI 実装を独立に前進させられる。
