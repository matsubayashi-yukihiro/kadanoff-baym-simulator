# 開発進捗管理

この文書は、[theory.md](./theory.md) と [implementation-plan.md](./implementation-plan.md) を踏まえた実装進捗の記録である。  
今後の進捗更新はこのファイルを正本として行う。

- 物理仕様の正本: `docs/theory.md`
- 実装計画の正本: `docs/implementation-plan.md`
- 進捗管理の正本: `docs/progress.md`

---

## 更新ルール

- マイルストーンの状態が変わったら、このファイルの「フェーズ進捗」と「次の優先作業」を更新する。
- 実装したが未検証の項目は「完了」にせず、「部分完了」に留める。
- テスト、ビルド、動作確認を行ったら「検証ログ」に日付付きで追記する。
- 計画自体を変更する場合は `docs/implementation-plan.md` を更新し、このファイルには差分だけを書く。

---

## 2026-03-16 時点の要約

- 到達点は `implementation-plan.md` の Phase E1-E3 完了である。
- backend は run 管理 API、非相互作用ソルバー、TDHFB / BdG、KBE + HFB に加えて、`kbe.self_energy=second_born` の full-contour two-time causal marching、causal quadrature による adaptive history integral、Matsubara / mixed branch の相関 self-consistency、two-time / thermal / mixed Green 関数の保存 / 部分取得 API と診断を実装済み。
- frontend は solver 切替、pairing channel / seed 入力、pairing 系列表示、KBE 診断量表示に加えて、KBE self-energy / adaptive / thermal branch の入力欄と two-time Green 関数 slice inspector を持つ。
- `pairing`, `pairing_s`, `pairing_d` を backend / API / frontend の共通 observable として扱える。
- adaptive integrator の主参照として `pdfs/2405.08737v2.pdf` を採用する。

---

## フェーズ進捗

| フェーズ | 状態 | 判定 | 根拠 |
| --- | --- | --- | --- |
| Phase A: 基盤整備 | 完了 | 受け入れ条件を満たす | frontend/backend 分離、FastAPI schema、run 保存、UI からの run 作成と観測量表示が実装済み |
| Phase B: 非相互作用ソルバー統合 | 完了 | 受け入れ条件を満たす | one-body Hamiltonian、非相互作用時間発展、`save_every` 付き観測量保存、UI 実行、外場仕事率とエネルギー変化の整合診断および自動テストを実装済み |
| Phase C: TDHFB / BdG 統合 | 完了 | 受け入れ条件を満たす | HFB 平衡初期化、一般化密度行列の時間発展、`pairing/pairing_s/pairing_d`、frontend の solver 切替と pairing 表示を実装済み |
| Phase D: KBE + HFB 統合 | 完了 | 受け入れ条件を満たす | two-time Green 関数コンテナ、HFB self-energy 極限、TDHFB 一致の backend 回帰、frontend で run summary / 主要観測量 / KBE 診断量表示を実装済み |
| Phase E1: fixed-grid KBE + second Born | 完了 | 受け入れ条件を満たす | full-contour second Born causal marching、new row / column 固定点反復、memory / collision / 保存則残差診断、HFB 極限回帰、UI からの相関 run 可視化が揃った |
| Phase E2: adaptive full-KBE integrator | 完了 | 受け入れ条件を満たす | causal quadrature による nonuniform history integral、history integration order 診断、adaptive/fixed 参照比較回帰、accepted/rejected step 診断を実装 |
| Phase E3: thermal branch / Matsubara | 完了 | 受け入れ条件を満たす | Matsubara / mixed branch の保存 / 部分取得 API に加え、相関した thermal branch self-consistency、factorized 比較診断、mixed branch dressing を実装 |

---

## 実装状況

| 項目 | 状態 | 現状 | 次に必要なこと |
| --- | --- | --- | --- |
| API / schema | 完了 | `/health`, `/schema/simulation`, `/presets`, `/runs`, `/runs/{id}`, `/runs/{id}/observables`, `/runs/{id}/green-functions`, `/runs/{id}/thermal-branch`, `/runs/{id}/mixed-green-functions` が実装済みで、`kbe` / `adaptive` / `thermal_branch` 設定を追加済み | preset 選択 UI と schema 駆動フォームの活用を進める |
| run 管理 | 完了 | `queued/running/succeeded/failed/cancelled` を保持し、run ごとに JSON/NPZ を保存 | ログ取得 API とより詳細な診断 API を追加 |
| ジョブ実行 | 完了 | `process` と `inline` の 2 モードあり。通常は別プロセス実行 | 再起動後の cancel 継続性、プロセスモードのテスト追加 |
| cancel 機能 | 部分完了 | backend API は存在するが frontend から操作できない | UI 実装と、PID ベースの再接続方針を決める |
| ストレージ | 完了 | `config/status/summary/diagnostics/observables.npz/run.log` に加え、KBE run では `green_functions.json` / `green_*.npy`、`thermal_branch.json` / `thermal_*.npy`、`mixed_green_functions.json` / `mixed_*.npy` を保存 | 長時間 run 向けに部分読み出しと圧縮方針を検討 |
| 格子・一体 Hamiltonian | 完了 | 2 次元 square lattice、open/periodic 境界、Peierls 位相付き hopping に加え、Nambu / BdG 生成と HFB self-energy を実装 | second Born / memory self-energy に再利用 |
| 非相互作用ソルバー | 完了 | 密度行列の時間発展、密度・電流・エネルギー・ベクトルポテンシャルを出力し、`save_every` と外場仕事率診断を反映済み | paired solver の基準解として維持 |
| TDHFB / BdG ソルバー | 完了 | HFB 平衡初期化、一般化密度行列の中点時間発展、`pairing_s` / `pairing_d` 射影を実装し、adaptive 有効化時は step-doubling 履歴も記録できる | 長時間安定化とより高次の積分器を検討 |
| KBE ソルバー基盤 | 完了 | HFB 二時刻 Green 関数、full-contour `second_born` causal marching、nonuniform history integral、retarded / lesser / Matsubara / mixed の保存形式と部分取得 API、相関 thermal / mixed branch を実装 | 2x2 benchmark と長時間最適化を進める |
| 観測量 | 完了 | `density/current_x/current_y/energy/vector_potential/pairing/pairing_s/pairing_d` を返却 | second Born 向けに緩和・散乱診断を追加 |
| 診断量 | 完了 | HFB 収束履歴、stationarity、`two_time_grid_shape`、second Born の iteration/residual/memory/collision/contour/history-order/保存則残差、adaptive step、Matsubara / mixed branch 比較診断を保存 | benchmark 指標と長時間実行向け集約を検討 |
| frontend UI | 部分完了 | 設定入力、solver 切替、pairing channel / seed、run 一覧、polling、診断量、時系列プロットに加え、KBE self-energy / adaptive / thermal branch 入力と retarded / lesser slice inspector を実装 | cancel、比較表示、preset 選択、schema 駆動フォーム |
| テスト | 部分完了 | backend 32 件、frontend 4 件が通過し、KBE second Born の HFB 極限回帰、full-contour/adaptive/thermal self-consistency 回帰、Green / thermal / mixed branch 部分取得 API、Phase E schema 回帰を追加 | 2x2 小サイズ全体角化 benchmark、\(\Delta t\) 収束、E2E、プロセスジョブ、cancel、保存データ回帰の追加 |
| デプロイ / 起動系 | 完了 | `docker compose up --build` とローカル起動手順あり | 永続データ運用とジョブ監視の整理 |

---

## 計画との差分と注意点

### 1. paired solver は Phase E 完了まで拡張済み

- `backend/app/solvers/registry.py` から `noninteracting`, `tdhfb`, `kbe_hfb` を呼び分けられる。
- `kbe_hfb` は `kbe.self_energy=hfb|second_born` を切り替えられる。
- `second_born` は局所 onsite \(U\) による full-contour two-time causal marching であり、Keldysh / Matsubara / mixed 成分の dressing と adaptive history integral を含む。

### 1.1 Phase E は三段階で進める

- Phase E1: Keldysh-only・fixed-grid の second Born を先に実装する
- Phase E2: `pdfs/2405.08737v2.pdf` を参照して adaptive time step / order と history integration order を導入する
- Phase E3: Matsubara 枝と mixed 成分を追加する

理由は、現行の `kbe_hfb` が full KBE integrator ではなく、
adaptive 化には solver state と history storage の再設計が必要だからである。

### 2. schema / UI の Phase E 設定は追加済みだが、実装範囲は限定的

現時点でも、少なくとも `noninteracting` solver では次の項目は計算に使われていない。

- `interaction.onsite_u`
- `interaction.nearest_neighbor_v`
- `interaction.pairing_channel`
- `initial_state.seed_pairing`

一方、`tdhfb` / `kbe_hfb` ではこれらが pairing source と HFB closure に反映される。

追加された Phase E 設定のうち、

- `kbe.self_energy=second_born` は full-contour two-time causal marching として有効
- `adaptive.enabled` は nonuniform history integral と history-order 診断付きで有効
- `thermal_branch.enabled` は Matsubara / mixed branch の相関 self-consistency と factorized 比較診断に有効

であり、Phase E の受け入れ条件を満たす実装範囲に到達した。

### 3. cancel は backend 先行実装

- `/api/v1/runs/{run_id}/cancel` は存在する。
- ただし frontend には cancel ボタンがない。
- `ProcessJobRunner` はプロセス管理をメモリ上の辞書で保持しているため、API プロセス再起動後の cancel 継続性はない。

### 4. Phase B-D 完了条件に加え、Phase E は自動テスト化済み

- `save_every` は solver / storage / API で反映され、最終ステップが必ず保存される。
- driven case に対して `max_energy_work_mismatch` と `final_energy_work_mismatch` を保存し、エネルギー変化と外場仕事率の整合を自動テストで確認している。
- TDHFB では paired stationary state、`pairing_d` 射影、一般化密度行列の Hermiticity / idempotency / occupation 境界を回帰化した。
- TDHFB / KBE + HFB では、相互作用ゼロ・`pairing_channel=none` の駆動 case が非相互作用厳密一体時間発展に一致することを回帰化した。
- KBE + HFB では `max_equal_time_tdhfb_mismatch` と Green 関数拘束条件を回帰化した。
- `kbe.self_energy=second_born` では HFB 極限回帰、full-contour two-time causal marching の memory / collision / contour / 保存則残差診断、adaptive/fixed 参照比較、Green / thermal / mixed branch API、相関 thermal branch 診断を回帰化した。

### 5. テストは主に最小動線の確認

- backend API テストは `InlineJobRunner` を用いており、プロセスモードを直接検証していない。
- frontend テストは API モック下での表示確認が中心で、E2E は未整備である。
- solver unit test には厳密極限と構造保存の回帰を追加したが、長時間安定性、\(\Delta t\) 収束、系サイズ依存、2x2 小サイズ全体角化による短時間 benchmark、独立 benchmark との比較は未整備である。

---

## 検証ログ

### 2026-03-15

- `uv run python -m pytest backend/tests`
  - 11 件すべて成功
- `cd frontend && npm test -- --run`
  - 3 件すべて成功
- `cd frontend && npm run build`
  - production build 成功

現時点で、少なくとも「backend API + 非相互作用 solver + frontend 最小 UI」の開発動線と、Phase B 完了条件に対応する backend 回帰は破綻していない。

### 2026-03-16

- `uv run python -m pytest backend/tests`
  - 17 件すべて成功
- `cd frontend && npm test -- --run`
  - 4 件すべて成功
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、Phase C の TDHFB / BdG 動線と、Phase D の KBE + HFB 一致検証および frontend 表示動線は自動テストと build で破綻していない。

- `uv run python -m pytest backend/tests`
  - 20 件すべて成功
  - TDHFB / KBE-HFB の非相互作用厳密極限回帰と、TDHFB 一般化密度行列の構造保存回帰を追加
- `cd frontend && npm test -- --run`
  - 4 件すべて成功

少なくとも現時点で、Phase C / D については最小動線確認に加えて、paired solver の非相互作用厳密極限と TDHFB の構造保存に関する backend 回帰が追加されている。

- `uv run python -m pytest backend/tests`
  - 25 件すべて成功
  - Phase E schema、second Born HFB 極限、memory 診断、adaptive / Matsubara 診断の回帰を追加
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm test -- --run`
  - 4 件すべて成功
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、Phase E1 の prototype 実装と、Phase E2/E3 の設定・診断・UI 入力追加は backend / frontend の自動テストと build で破綻していない。

- `uv run python -m pytest backend/tests`
  - 26 件すべて成功
  - KBE second Born の保存則残差診断と静的平衡回帰を追加

少なくとも現時点で、Phase E1 については second Born prototype の保存則残差記録まで backend 回帰で破綻していない。

- `uv run python -m pytest backend/tests`
  - 27 件すべて成功
  - KBE two-time Green 関数の保存 / 部分取得 API 回帰を追加
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm test -- --run`
  - 4 件すべて成功
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、Phase E1 については second Born prototype の保存則残差記録に加えて、retarded / lesser の保存と部分取得 API、およびそれに対応する frontend API 型更新まで自動テストと build で破綻していない。

- `uv run python -m pytest backend/tests`
  - 28 件すべて成功
  - Matsubara branch の保存 / 部分取得 API 回帰を追加
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm test -- --run`
  - 4 件すべて成功
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、Phase E3 については Matsubara branch 診断 seed に加えて、保存 / 部分取得 API と frontend API 型更新までは backend / frontend の自動テストと build で破綻していない。

- `uv run python -m pytest backend/tests`
  - 29 件すべて成功
  - mixed branch seed の保存 / 部分取得 API 回帰と、mixed 初期値診断を追加
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm test -- --run`
  - 4 件すべて成功
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、Phase E3 については Matsubara branch 診断 seed と保存 / 部分取得 API に加えて、mixed branch seed の保存 / 部分取得 API、およびそれに対応する frontend API 型更新までは backend / frontend の自動テストと build で破綻していない。

- `uv run python -m pytest backend/tests`
  - 29 件すべて成功
  - `second_born` の uniform-grid two-time causal marching prototype と、それに対応する solver 回帰を追加
- `cd frontend && npm test -- --run`
  - 4 件すべて成功
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、Phase E1 については equal-time density dressing prototype から一段進み、uniform-grid 上の retarded / lesser 新行・新列を更新する two-time causal marching prototype までは backend / frontend の自動テストと build で破綻していない。

- `uv run python -m pytest backend/tests`
  - 32 件すべて成功
  - full-contour second Born、adaptive history integral、相関 thermal / mixed branch self-consistency、Phase E API / solver 回帰を追加

少なくとも現時点で、Phase E1-E3 については backend の自動テストで受け入れ条件に対応する実装が破綻していない。

---

## 次の優先作業

### 優先度 A

- 2x2 小サイズ系で Fock 空間の全体角化を用意し、非相互作用・TDHFB・KBE-HFB の短時間 benchmark を追加する
- \(\Delta t\) / adaptive tolerance / 系サイズに対する収束表を整備する
- long run 向けに Green 関数部分取得 API の圧縮と窓切り出し最適化を進める

### 優先度 B

- cancel ボタン、run log 表示、preset 選択 UI を追加する
- プロセスモードのテスト、cancel テスト、E2E を追加する
- 長時間 run を見据えて observables の部分取得を検討する

---

## マイルストーン判定

- Milestone 1: 完了
  - frontend/backend 分割、mock 段階を超えて実 solver 接続済み
- Milestone 2: 完了
  - UI から非相互作用 run を実行し、密度・エネルギーを表示できる
  - `save_every` と外場仕事率整合性の backend 回帰を追加済み
- Milestone 3: 完了
  - UI から TDHFB / KBE-HFB run を実行し、pairing と KBE 診断を確認できる
- Milestone 4 以降: 未着手

---

## 次回更新時のチェック項目

- 2x2 小サイズ全体角化 benchmark が追加され、少なくとも短時間ダイナミクスで TDHFB / KBE-HFB の比較基準になっているか
- \(\Delta t\) / adaptive tolerance / 系サイズに対する収束表が揃ったか
- two-time / thermal / mixed Green 関数 API が長時間 run を扱えるか
- cancel が UI から操作でき、期待どおり止まるか
- プロセスモードと E2E の自動テストが追加されたか
