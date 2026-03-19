# 開発進捗管理

この文書は、[theory.md](./theory.md) と [research-workbench-plan.md](./research-workbench-plan.md) を踏まえた実装進捗の記録である。  
今後の進捗更新はこのファイルを正本として行う。

- 物理仕様の正本: `docs/theory.md`
- backend validation の正本: `docs/validation-spec.md`
- 研究アプリ全体方針の正本: `docs/research-workbench-plan.md`
- 進捗管理の正本: `docs/progress.md`
- bakend 修繕計画: `docs/backend-remediation-plan.md`
- 文献索引: `docs/literature-index.md`

---

## 更新ルール

- マイルストーンの状態が変わったら、このファイルの「フェーズ進捗」と「次の優先作業」を更新する。
- 実装したが未検証の項目は「完了」にせず、「部分完了」に留める。
- テスト、ビルド、動作確認を行ったら「検証ログ」に日付付きで追記する。
- 研究アプリ全体方針を変更する場合は `docs/research-workbench-plan.md` を更新する。
- 作業が完了したら、進捗状況を加筆する。
- 「作業が完了したら、進捗状況を加筆して、この指示自体も md に書き込んでおく」という運用指示は、このファイルに明示的に残す。

---

## 2026-03-19 時点の要約

- 到達点は、Phase E 完了、heuristic prototype の `second_born` 保持、および backend 修繕計画の `R0-R5` 完了までである。
- backend は run 管理 API、非相互作用ソルバー、TDHFB / BdG、KBE + HFB、two-time / thermal / mixed Green 関数の保存 / 部分取得 API、関連診断を実装済みである。
- research workbench の `P1.5` 足場として、SQLite-backed な experiment registry、filesystem artifact と DB metadata を束ねる repository 層、`study` / `decision note` / `evidence bundle` API、run metadata patch、および既存 run の backfill utility を追加した。
- 一方で backend 点検の結果、`kbe.self_energy=second_born`、adaptive history integral、相関 thermal / mixed branch の legacy 実装は、文献準拠の full KBE second Born ではなく heuristic prototype と再判定した。
- これに対して `kbe.self_energy=second_born_reference` を追加し、`0906.1704_time-propagation-kbe.pdf` / `2405.08737_adaptive-time-stepping-two-time-kbe.pdf` / `2105.06193_superconducting-nanowires-negf.pdf` を突き合わせた explicit self-energy の equal-time GKBA reference path を backend に実装した。
- さらに `second_born_reference` に self-consistent Matsubara / mixed branch dressing、adaptive reference regression、full-contour diagnostics を追加し、Phase E1-E3 の受け入れ条件を reference path で閉じた。
- `second_born_reference` の representative `4x2` case を `cProfile` で測定し、局所 self-energy 構築が支配項であることを確認したうえで、局所 2x2 block 抽出のベクトル化と reference path の不要 HFB two-time Green 関数構築削減を実施した。
- prototype / reference が共有する factorized Matsubara / mixed branch builder を `green_functions.py` に寄せ、thermal / mixed seed 生成をベクトル化した。
- `FileRunStorage` に `save_every` ベースの two-time / mixed Green 関数保存縮約を導入し、solver 内部の full-grid diagnostics を維持したまま、長時間 run 向けの保存サイズと slice API の取得点数を削減した。
- frontend は solver 切替、pairing channel / seed 入力、pairing 系列表示、KBE 診断量表示に加えて、KBE self-energy / adaptive / thermal branch の入力欄と two-time Green 関数 slice inspector を持つ。
- frontend の P1 着手として、`Single Job` / `Compare Jobs` / `Parameter Sweep` の top-level navigation shell、preset library、baseline / failure / validation framing panel、および local FFT preview を追加し、compare / sweep を single-job 面から切り離した page-level surface 再編を進めた。さらに 2026-03-18 時点で、docs 的な説明 panel は frontend から外し、runtime state / controls / evidence に絞った surface へ整理した。`Single Job` は command deck + validation scope + evidence canvas、`Compare Jobs` / `Parameter Sweep` は left rail controls と main planning panel に集約している。
- 研究アプリ全体の product / architecture 方針の正本として `docs/research-workbench-plan.md` を追加し、`Single Job` / `Compare Jobs` / `Parameter Sweep` を持つ workbench への拡張方針に加えて、`study` / `decision note` / `evidence bundle` を含む研究 artifact model、physics compare と numerical validation compare / sweep の両立、demo preset と baseline preset の分離を固定した。
- `pairing`, `pairing_s`, `pairing_d` を backend / API / frontend の共通 observable として扱える。
- adaptive integrator の主参照として [2405.08737_adaptive-time-stepping-two-time-kbe.pdf](../pdfs/negf_kbe/2405.08737_adaptive-time-stepping-two-time-kbe.pdf) を採用する。
- 修繕計画の正本として `docs/backend-remediation-plan.md` を追加し、参考文献束を `pdfs/negf_kbe/` に集約した。
- backend solver validation の正本として `docs/validation-spec.md` を追加し、phase gate、test mapping、validated / not yet validated の判定を一本化した。
- ローカルファイル名と文献タイトル、要約の対応は `docs/literature-index.md` を正本として引く。
- 修繕計画の R0-R2 足場として、`scipy` 導入、`numerics.py` / `equilibrium.py` / `contour.py` / `green_functions.py` / `self_energy_second_born_prototype.py` の追加、および `kbe_hfb.py` の orchestration 層への整理を実施した。
- 修繕計画の R3 を閉じ、2x2 系の固定粒子数 exact diagonalization benchmark helper、benchmark 比較 utility、`dt` / adaptive tolerance / 系サイズ row の docs 収束表、および `second_born_reference` を含む short-window benchmark を追加した。
- pytest marker として `physics_unit` / `physics_invariant` / `physics_benchmark` / `workflow` を追加し、Phase 1 の欠けていた continuity residual regression を `noninteracting` solver に導入した。

---

## backend 修繕フェーズ進捗

| 修繕フェーズ | 状態 | 現在の到達点 | 残作業 |
| --- | --- | --- | --- |
| Phase R0: 凍結とラベリング | 完了 | Phase E 実装を heuristic prototype として docs / diagnostics に反映済み | 維持のみ |
| Phase R1: numerical utility の整理 | 完了 | `scipy` 導入、数値 utility の共通化を実施済み | Anderson / Broyden 系の評価を継続 |
| Phase R2: solver 構造の再編 | 完了 | `kbe_hfb.py` を orchestration 層へ整理し、helper module 群を分離済み | reference path 実装に向けた self-energy 分離を継続 |
| Phase R3: benchmark と収束検証 | 完了 | 2x2 exact benchmark、prototype / reference short-window benchmark、`dt` / adaptive tolerance / 系サイズ row の docs 整理まで反映済み | 維持のみ |
| Phase R4: KBE reference path の再実装 | 完了 | `second_born_reference` の explicit self-energy + equal-time GKBA causal marching と self-consistent thermal / mixed contour dressing を実装し、prototype と分離済み | 維持のみ |
| Phase R5: 高速化と長時間実行 | 完了 | reference/prototype/thermal/mixed path の profiling、factorized contour seed の共通ベクトル化、`kbe_hfb` orchestration の整理、`save_every` ベースの Green 関数保存縮約を実施済み | 維持のみ |

現時点の到達点は `R5 完了` である。

---

## フェーズ進捗

| フェーズ | 状態 | 判定 | 根拠 |
| --- | --- | --- | --- |
| Phase A: 基盤整備 | 完了 | 受け入れ条件を満たす | frontend/backend 分離、FastAPI schema、run 保存、UI からの run 作成と観測量表示が実装済み |
| Phase B: 非相互作用ソルバー統合 | 完了 | 受け入れ条件を満たす | one-body Hamiltonian、非相互作用時間発展、`save_every` 付き観測量保存、UI 実行、外場仕事率とエネルギー変化の整合診断および自動テストを実装済み |
| Phase C: TDHFB / BdG 統合 | 完了 | 受け入れ条件を満たす | HFB 平衡初期化、一般化密度行列の時間発展、`pairing/pairing_s/pairing_d`、frontend の solver 切替と pairing 表示を実装済み |
| Phase D: KBE + HFB 統合 | 完了 | 受け入れ条件を満たす | two-time Green 関数コンテナ、HFB self-energy 極限、TDHFB 一致の backend 回帰、frontend で run summary / 主要観測量 / KBE 診断量表示を実装済み |
| Phase E1: fixed-grid KBE + second Born | 完了 | 受け入れ条件を満たす | `second_born_reference` の fixed-grid explicit self-energy + equal-time GKBA causal marching、HFB 極限回帰、保存則 / 収束 / equation residual 診断、および two-time Green 関数 API を backend で検証済み |
| Phase E2: adaptive full-KBE integrator | 完了 | 受け入れ条件を満たす | adaptive time step / history integration order が `second_born_reference` と `second_born` の双方で diagnostics 化され、tight/loose tolerance 比較と fixed-grid 参照比較で reference path を含む回帰を追加済み |
| Phase E3: thermal branch / Matsubara | 完了 | 受け入れ条件を満たす | `second_born_reference` の self-consistent Matsubara / mixed branch dressing、factorized 差分診断、thermal / mixed branch 保存 / 部分取得 API、および finite-temperature short-window benchmark を backend で検証済み |

---

## 実装状況

| 項目 | 状態 | 現状 | 次に必要なこと |
| --- | --- | --- | --- |
| experiment registry | 部分完了 | SQLite-backed な `experiment registry`、`ExperimentRepository`、DB-backed `/runs` list、`study` / `decision note` / `evidence bundle` API、run metadata patch、backfill utility を追加し、既存 run directory を起動時に再索引できる | `job group` / `sweep` / `derived analysis artifact` の table / API / lineage を追加し、compare / sweep surface の primary resource へ広げる |
| API / schema | 部分完了 | `/health`, `/schema/simulation`, `/presets`, `/runs`, `/runs/{id}`, `/runs/{id}/metadata`, `/runs/{id}/log`, `/runs/{id}/observables`, `/runs/{id}/green-functions`, `/runs/{id}/thermal-branch`, `/runs/{id}/mixed-green-functions`, `/studies`, `/decision-notes`, `/evidence-bundles` が実装済みで、`kbe` / `adaptive` / `thermal_branch` 設定と research artifact schema を API から取得できる。`/presets` には provisional な `square-4x4-higgs-demo-kbe-hfb` を追加し、`kbe_hfb + hfb + bond_d` の long-window Gaussian pulse demo draft を API から取得できる | `job group` / `sweep` / `derived analysis artifact`、enriched `presets`、study-aware URL state を追加する |
| run 管理 | 完了 | `queued/running/succeeded/failed/cancelled` を保持し、run ごとに JSON/NPZ を保存する。`/runs` 一覧は registry DB query を正本とし、`study_id` / `run_role` / `validation_status` / `failure_tags` / `group_id` / `sweep_id` / `variant_label` / `preset_id` / `tags` / `config_hash` / `code_version` / `storage_uri` を run metadata として保持できる | `job group` / `sweep` 実装時の lineage 更新と、restart-safe cancel を追加する |
| ジョブ実行 | 完了 | `process` と `inline` の 2 モードあり。通常は別プロセス実行 | 再起動後の cancel 継続性、プロセスモードのテスト追加 |
| cancel 機能 | 部分完了 | backend API と frontend の `Cancel Run` ボタンは実装済みで、Single Job には `RunLogPanel` を接続済み | API 再起動後の cancel 継続性、process mode test を追加する |
| ストレージ | 完了 | `config/status/summary/diagnostics/observables.npz/run.log` に加え、KBE run では `green_functions.json` / `green_*.npy`、`thermal_branch.json` / `thermal_*.npy`、`mixed_green_functions.json` / `mixed_*.npy` を保存し、two-time / mixed time grid は `save_every` に応じて縮約される | 必要なら chunked archive 形式を別途検討 |
| 格子・一体 Hamiltonian | 完了 | 2 次元 square lattice、open/periodic 境界、Peierls 位相付き hopping に加え、Nambu / BdG 生成と HFB self-energy を実装 | second Born / memory self-energy に再利用 |
| 非相互作用ソルバー | 完了 | 密度行列の時間発展、密度・電流・エネルギー・ベクトルポテンシャルを出力し、`save_every` と外場仕事率診断を反映済み | paired solver の基準解として維持 |
| TDHFB / BdG ソルバー | 完了 | HFB 平衡初期化、一般化密度行列の中点時間発展、`pairing_s` / `pairing_d` 射影を実装し、adaptive 有効化時は step-doubling 履歴も記録できる | 長時間安定化とより高次の積分器を検討 |
| KBE ソルバー基盤 | 完了 | HFB 二時刻 Green 関数、retarded / lesser / Matsubara / mixed の保存形式、heuristic `second_born` prototype、および explicit self-energy の `second_born_reference` と self-consistent contour dressing を実装済みで、orchestration helper と contour seed builder を共通化済み | longer-time / larger-system の benchmark 拡張 |
| 観測量 | 完了 | `density/current_x/current_y/energy/vector_potential/pairing/pairing_s/pairing_d` を返却 | second Born 向けに緩和・散乱診断を追加 |
| 診断量 | 完了 | HFB 収束履歴、stationarity、`two_time_grid_shape`、prototype の iteration/residual/memory/collision/contour/history-order/保存則残差に加え、`second_born_reference` の explicit self-energy / equation residual / GKBA reconstruction / thermal / mixed contour diagnostics を保存 | larger-system row と連動した追加可視化を検討 |
| frontend UI | 部分完了 | 設定入力、solver 切替、pairing channel / seed、run 一覧、polling、診断量、時系列プロット、KBE self-energy / adaptive / thermal branch 入力、retarded / lesser slice inspector、Run Log、top-level navigation shell、preset library、baseline / failure / validation framing、および local FFT preview を実装済みで、`Single Job` / `Compare Jobs` / `Parameter Sweep` を page-level surface として整理した。さらに 2026-03-18 時点で、docs 的な説明 panel を frontend から外し、`Workbench Pages` navigation を page 上部へ移し、Single Job は left sidebar に preset + config stack と run registry rail を置き、main canvas では validation + baseline/failure framing の summary band、observable-first の primary evidence path、real-time / thermal / mixed contour の切替式 advanced surface、および sticky diagnostics / artifact support rail を読む構成へ再整理した。`Compare Jobs` / `Parameter Sweep` は left rail の planning controls と main planning panel に絞り、説明的な context column は置かない構成へ戻した。加えて preset library に Higgs demo quick start を追加し、`Stage Demo` / `Launch Demo` で provisional な `kbe_hfb + hfb + bond_d` long-window Gaussian pulse preset を流し、`pairing_d` を主読 observable として priming できるようにし、local FFT preview は pairing 系で `magnitude` を既定に選び mean-subtracted preview を返すようにした。さらに `Compare Jobs` は left rail に variant / baseline / `comparison_kind` framing と active variant 編集導線を置き、main 冒頭に summary table、その下に planning state / reserved result stack / empty state を置く summary-first design surface へ整理した。2026-03-19 時点で、チャートを custom SVG から Plotly インタラクティブプロットへ移行し、ConfigPanel を CollapsibleSection で折り畳み式に改善し、`Parameter Sweep` に SweepRailPanel（sweep 軸定義・parameter_kind 推定・値範囲・baseline 値・fixed axes）を追加し、全 surface の sidebar 最下部に sticky launch/cancel action bar を追加し、OpenAPI 再生成後の stricter nested config 型に追従するよう frontend type usage を整理した | `studies` / `decision-notes` / `evidence-bundles` を actual surface へ接続し、`job group` / `sweep` / `derived analysis artifact` を registry-backed resource として露出する |
| テスト | 部分完了 | KBE second Born の HFB 極限回帰、full-contour/adaptive/thermal self-consistency 回帰、Green / thermal / mixed branch 部分取得 API、Phase E schema 回帰、2x2 exact diagonalization benchmark、非相互作用 `\Delta t` 収束、Phase 1 continuity residual regression、short-window prototype / reference benchmark、thermal branch 比較、adaptive tolerance 比較、memory window dependence row、`save_every` 付き Green / mixed 保存縮約回帰、および pytest marker による validation 層の分類を追加 | E2E、プロセスジョブ、cancel、保存データ回帰の追加 |
| デプロイ / 起動系 | 完了 | `docker compose up --build` とローカル起動手順あり | 永続データ運用とジョブ監視の整理 |

---

## 計画との差分と注意点

### 0. 2026-03-16 backend 点検で legacy Phase E を再判定

- `backend/app/solvers/kbe_hfb.py` の `second_born` / adaptive / thermal / mixed branch は、自動テスト上は成立している。
- ただし実装は明示的な `Phi`-derivable contour self-energy ではなく、密度平均・envelope・対角 `gamma` に基づく heuristic dissipative closure を含む。
- したがって、legacy `second_born` / adaptive / thermal / mixed branch は「受け入れ条件を満たす文献準拠実装」ではなく、「API と診断を備えた prototype 実装」として扱う。
- 修繕計画は `docs/backend-remediation-plan.md`、参考文献束は `pdfs/negf_kbe/README.md` を参照する。

### 0.1 2026-03-17 `second_born_reference` で Phase E gate を閉じた

- `second_born_reference` に self-consistent Matsubara / mixed branch dressing を追加し、factorized seed との差分診断を reference path で保存するようにした。
- real-time の equal-time GKBA causal marching は contour branch 由来の correction と adaptive history-order diagnostics を保持しつつ、`second_born_reference_scope=equal_time_gkba_full_contour` を返す。
- これにより Phase E1-E3 の完了判定は legacy prototype ではなく `second_born_reference` を基準に行う。

### 1. paired solver は Phase E 完了まで拡張済み

- `backend/app/solvers/registry.py` から `noninteracting`, `tdhfb`, `kbe_hfb` を呼び分けられる。
- `kbe_hfb` は `kbe.self_energy=hfb|second_born|second_born_reference` を切り替えられる。
- `second_born` は局所 onsite \(U\) に基づく Phase E prototype 実装であり、Keldysh / Matsubara / mixed 成分の heuristic dressing と adaptive history integral を含む。
- `second_born_reference` は explicit self-energy を用いた equal-time GKBA reference path であり、self-consistent Matsubara / mixed branch dressing と adaptive/full-contour diagnostics を含めて legacy prototype と診断上も分離した。

### 1.1 Phase E は三段階で進める

- Phase E1: Keldysh-only・fixed-grid の second Born を先に実装する
- Phase E2: `2405.08737_adaptive-time-stepping-two-time-kbe.pdf` を参照して adaptive time step / order と history integration order を導入する
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

- `kbe.self_energy=second_born` は Phase E prototype として有効
- `kbe.self_energy=second_born_reference` は remediation R4 の reference path として有効
- `adaptive.enabled` は `second_born_reference` では adaptive equal-time GKBA reference path として有効
- `thermal_branch.enabled` は `second_born_reference` では self-consistent Matsubara / mixed branch dressing と factorized 比較診断に有効

である。一方、full two-time contour second Born そのものは引き続き将来拡張である。

### 3. cancel は backend 先行実装

- `/api/v1/runs/{run_id}/cancel` は存在する。
- frontend には `Cancel Run` ボタンがあるが、API 再起動後の cancel 継続性と registry-backed な queue / log 導線は未整備である。
- `ProcessJobRunner` はプロセス管理をメモリ上の辞書で保持しているため、API プロセス再起動後の cancel 継続性はない。

### 3.1 frontend は P1 shell に着手したが compare / sweep はまだ placeholder

- frontend は `Single Job` / `Compare Jobs` / `Parameter Sweep` の top-level navigation shell、preset library、baseline / failure / validation framingを持つ workbench 骨格へ着手し、single-job と compare / sweep を page-level surface として分離した。
- 2026-03-18 の layout refresh では、docs 的な説明 panel を frontend から外し、Single Job を command deck / validation scope / evidence canvas に、Compare / Sweep を left rail controls + main planning panel に再編した。
- ただし `Compare Jobs` / `Parameter Sweep` は backend 管理の `job group` / `sweep` API が未実装のため、現時点では planning placeholder に留まる。
- `Compare Jobs` については planning placeholder のままでも、left rail に active variant / baseline / comparison framing を置き、main 冒頭で summary table を先に読む summary-first design surface までは整理した。
- `Single Job` には FFT preview を追加したが、これは backend 保存の `derived analysis artifact` ではなく local preview である。
- したがって derived analysis の durable metadata / lineage / bundle 接続は引き続き未実装である。

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
- solver unit test には厳密極限、構造保存、2x2 exact diagonalization による短時間 benchmark、非相互作用の `\Delta t` 収束回帰、thermal branch の exact density/current 比較、adaptive tolerance の fine fixed-step 参照比較、および memory window dependence row を追加した。一方で、長時間安定性、系サイズ依存、second Born reference path の benchmark、独立 benchmark との比較は未整備である。
- backend test suite には `physics_unit` / `physics_invariant` / `physics_benchmark` / `workflow` の marker を付与し、validation-spec の test matrix と対応づけた。

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

少なくとも現時点で、Phase E1-E3 の prototype 実装については backend の自動テストでコードパスが破綻していない。

- backend 点検を実施
  - `kbe_hfb.py` の Phase E 実装を heuristic prototype と再判定
  - `docs/backend-remediation-plan.md` を新設
  - `pdfs/negf_kbe/` に KBE / GKBA / adaptive / superconducting NEGF の文献束を集約
- `uv run python -m pytest backend/tests`
  - 35 件すべて成功
  - `scipy` 導入、共通 numerical utility、KBE helper 分割、prototype diagnostics の明示化を追加

少なくとも現時点で、修繕計画の R0-R2 に相当する基盤整備と責務分離は backend 回帰を保ったまま実施済みである。

### 2026-03-17

- `uv run python -m pytest backend/tests`
  - 39 件すべて成功
  - 2x2 exact diagonalization benchmark helper、非相互作用 benchmark、\(\Delta t\) 収束回帰、短時間 TDHFB / KBE-HFB / `second_born` prototype benchmark を追加

少なくとも現時点で、修繕計画の R3 については 2x2 小サイズ exact benchmark と最初の収束回帰が backend test として追加され、TDHFB / KBE-HFB / `second_born` prototype の短時間比較基盤が整った。

- `uv run python -m pytest backend/tests`
  - 42 件すべて成功
  - benchmark 比較 utility、thermal branch の exact density/current 比較、adaptive tolerance の fine fixed-step 参照比較、memory window dependence row を追加

少なくとも現時点で、修繕計画の R3 については 2x2 exact benchmark を `second_born` / thermal branch / adaptive tolerance / memory window の比較へ広げる基盤と backend 回帰が追加されている。一方で、系サイズ依存と docs 上の収束表整理、および reference second Born path を基準にした benchmark は未完である。

- 作業完了後の進捗加筆ルールを `docs/progress.md` に追記

今後は、作業完了時の進捗反映そのものも `docs/progress.md` の運用ルールとして扱う。

- `uv run python -m pytest backend/tests`
  - 46 件すべて成功
  - `second_born_reference` schema、HFB 極限回帰、reference diagnostics、2x2 exact benchmark 回帰を追加
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm test -- --run`
  - 4 件すべて成功
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、修繕計画の R3-R4 については docs 上の収束表整理、`second_born_reference` の backend / frontend 露出、reference benchmark 回帰、および既存 prototype 動線の互換維持まで自動テストと build で破綻していない。

- `uv run python -m pytest backend/tests`
  - 48 件すべて成功
  - `second_born_reference` の局所 self-energy hot loop ベクトル化、reference path の不要 HFB two-time Green 関数構築削減、profiling helper、および対応 unit test を追加
- `uv run python - <<'PY' ...`
  - representative `4x2`, `t_final=0.6`, `dt=0.05`, `second_born_reference` case を `cProfile` で再計測
  - 総実行時間 `0.894 s -> 0.223 s`
  - `_build_local_second_born_self_energy` cumulative time `0.796 s -> 0.132 s`

少なくとも現時点で、修繕計画の R5 については `second_born_reference` の支配項 profiling と first optimization が backend 回帰を保ったまま入っており、同一 representative case で約 4 倍の短縮を確認した。

- `uv run python -m pytest backend/tests`
  - 49 件すべて成功
  - `docs/validation-spec.md` を追加し、pytest marker による validation 層の分類、README / docs の役割分担整理、および `noninteracting` solver の continuity residual 回帰を追加

少なくとも現時点で、backend solver validation については `validation-spec` を正本として参照できる状態になり、Phase 1 の continuity equation は自動テストと診断量で first-class に監視されている。

- `uv run python -m pytest backend/tests/test_api.py`
  - 11 件すべて成功
  - `save_every` 付き KBE two-time / mixed Green 関数保存縮約の API 回帰を追加
- `uv run python -m pytest backend/tests/test_kbe_hfb_solver.py`
  - 12 件すべて成功
- `uv run python -m pytest backend/tests`
  - 51 件すべて成功
- `uv run python - <<'PY' ...`
  - representative `4x2`, `t_final=0.6`, `dt=0.05`, `second_born` + thermal / mixed prototype case を `profile_callable` で再計測
  - wall time `0.164 s`
  - 上位支配項は `apply_second_born_corrections` / `dissipative_collision` であり、factorized branch builder は上位支配項から外れた

少なくとも現時点で、修繕計画の R5 については prototype / thermal / mixed path の profiling、factorized contour seed の共通ベクトル化、`kbe_hfb` orchestration の整理、および `save_every` ベースの保存縮約が backend 回帰を保ったまま完了している。

### 2026-03-17

- `uv run python -m pytest backend/tests/test_self_energy_second_born.py backend/tests/test_kbe_hfb_solver.py backend/tests/test_exact_diagonalization_benchmark.py backend/tests/test_api.py`
  - 37 件すべて成功
  - `second_born_reference` の self-consistent thermal / mixed contour dressing、adaptive reference regression、reference full-contour API diagnostics を追加
- `uv run python -m pytest backend/tests`
  - 56 件すべて成功

少なくとも現時点で、Phase E 完了判定に必要な reference path の invariant / benchmark / workflow 回帰は backend 自動テストで破綻していない。

### 2026-03-18

- `cd frontend && npm test -- --run`
  - 5 件すべて成功
  - top-level navigation shell、preset library、baseline framing、local FFT preview の rendering regression を更新
- `cd frontend && npm run build`
  - production build 成功

少なくとも現時点で、frontend の workbench shell 着手と `Single Job` 面の再編は自動テストと build で破綻していない。

- `cd frontend && ./node_modules/.bin/vitest run`
  - この環境の Node `v12.22.9` が optional chaining / modern ESM 構文に追従しておらず、`Unexpected token '?'` で実行不能
- `cd frontend && ./node_modules/.bin/vite build`
  - この環境の Node `v12.22.9` が top-level `await` を解釈できず、`Unexpected reserved word` で実行不能

今回の frontend page-level surface 再編については、コード更新までは完了したが、この環境では Node runtime 制約のため frontend 自動検証を再実行できていない。

- `cd frontend && ./node_modules/.bin/vitest run`
  - frontend visual realignment 後も再試行したが、この環境の Node `v12.22.9` が optional chaining / modern ESM 構文に追従しておらず、`Unexpected token '?'` で実行不能
- `cd frontend && ./node_modules/.bin/tsc --noEmit -p tsconfig.json && ./node_modules/.bin/tsc --noEmit -p tsconfig.node.json && ./node_modules/.bin/vite build`
  - frontend visual realignment 後も再試行したが、この環境の Node `v12.22.9` が `typescript` 自体の nullish coalescing を解釈できず、`Unexpected token '?'` で停止

少なくとも現時点で、frontend shell / panel / chart の visual realignment はコード差分として反映済みだが、Node runtime 制約のため自動テストと build による再検証は未完了である。

- Single Job の情報設計を再編
  - launch 面を preset / config / run registry の 3 列 band へ整理
  - evidence 面を observable-first の主読 path と support rail に分離
  - `RunContextPanel` を spectrum の隣へ移し、`ValidationScopePanel` は draft / selected summary を残しつつ solver ladder / guardrails を開閉式に圧縮
  - real-time / thermal / mixed contour は縦積みではなく切替式 advanced surface へ変更
- `cd frontend && ./node_modules/.bin/vitest run`
  - 上記再編後も、この環境の Node `v12.22.9` が optional chaining / modern ESM 構文に追従しておらず、`Unexpected token '?'` で実行不能
- `cd frontend && ./node_modules/.bin/vite build`
  - 上記再編後も、この環境の Node `v12.22.9` が top-level `await` を解釈できず、`Unexpected reserved word` で停止

少なくとも現時点で、Single Job の hierarchy simplification はコード差分として反映済みだが、Node runtime 制約のため frontend 自動テストと build による再検証は未完了である。

- support rail の情報設計を再調整
  - `DiagnosticsPanel` は groups / metrics / anomalies の要約と異常ハイライトを先頭に出し、full diagnostic matrix は disclosure に下げた
  - `ResearchArtifactsPanel` は current artifact surface を常時表示し、derived analysis / decision note / evidence bundle backlog を disclosure に下げた
- `cd frontend && ./node_modules/.bin/vitest run`
  - 上記 support rail 再調整後も、この環境の Node `v12.22.9` が optional chaining / modern ESM 構文に追従しておらず、`Unexpected token '?'` で実行不能
- `cd frontend && ./node_modules/.bin/vite build`
  - 上記 support rail 再調整後も、この環境の Node `v12.22.9` が top-level `await` を解釈できず、`Unexpected reserved word` で停止

少なくとも現時点で、support rail の hierarchy compression もコード差分として反映済みだが、Node runtime 制約のため frontend 自動テストと build による再検証は未完了である。

- Higgs demo preset と quick start を追加
  - backend `/presets` に provisional な `square-4x4-higgs-demo-kbe-hfb` を追加
  - frontend preset library に `Stage Demo` / `Launch Demo` quick action を追加し、`pairing_d` を主読 observable として priming する導線を追加
  - demo preset は `kbe_hfb + hfb + bond_d + pulsed drive` の illustrative draft として扱い、validated baseline とは分離した
- `uv run python -m pytest backend/tests`
  - 56 件すべて成功
- `cd frontend && ./node_modules/.bin/vitest run`
  - demo quick start 追加後も、この環境の Node `v12.22.9` が optional chaining / modern ESM 構文に追従しておらず、`Unexpected token '?'` で実行不能
- `cd frontend && ./node_modules/.bin/vite build`
  - demo quick start 追加後も、この環境の Node `v12.22.9` が top-level `await` を解釈できず、`Unexpected reserved word` で停止

少なくとも現時点で、Higgs demo の provisional preset と quick-start 導線は backend 回帰を保ったままコード差分に反映済みだが、frontend 自動テストと build による再検証は Node runtime 制約のため未完了である。

- Higgs demo preset を長窓・ガウスパルス読取向けに再調整
  - backend / frontend の `square-4x4-higgs-demo-kbe-hfb` を `t_final=20.0`, `dt=0.05`, `center=3.0`, `width=1.2` の long-window Gaussian pulse へ揃え、pre-pulse baseline と post-pulse 観測窓を確保した
  - local FFT preview は pairing 系 observable で `magnitude` を既定系列に選び、mean-subtracted spectrum を返して DC 成分に引っ張られにくい読取へ寄せた
  - demo preset は引き続き illustrative draft であり、validated baseline ではない
- `uv run python -m pytest backend/tests`
  - 57 件すべて成功

- Compare Jobs design surface を再編
  - left rail に variant slots、working baseline、`comparison_kind` framing、preset / active variant 編集導線を集約
  - main 冒頭に `job group` を先に読む summary table を置き、その下に planning state、reserved result stack、empty state を配置
  - compare 面へ Single Job の evidence surface を逆流させず、child-run progress / accepted-rejected / failure note は将来の compare artifact 側へ留める構成に揃えた
- `docker run --rm -v /home/matsubayashi/TDKB:/work -w /work/frontend node:20 bash -lc 'npm test -- --run'`
  - 4 file、18 test すべて成功
  - compare summary-first surface と contour tab 切替後の rendering regression を更新
- `docker run --rm -v /home/matsubayashi/TDKB:/work -w /work/frontend node:20 bash -lc 'npm run build'`
  - production build 成功

少なくとも現時点で、Compare Jobs の summary-first design surface 改善は Docker 上の Node 20 検証では frontend test と build で破綻していない。一方でホスト環境の Node `v12.22.9` には `npm` がなく modern ESM toolchain を直接起動できないため、frontend 検証は container 経由で行った。
- `cd frontend && ./node_modules/.bin/vitest run`
  - 上記 Higgs demo / spectrum 調整後も、この環境の Node `v12.22.9` が optional chaining / modern ESM 構文に追従しておらず、`Unexpected token '?'` で実行不能
- `cd frontend && ./node_modules/.bin/vite build`
  - 上記 Higgs demo / spectrum 調整後も、この環境の Node `v12.22.9` が top-level `await` を解釈できず、`Unexpected reserved word` で停止

少なくとも現時点で、Higgs demo の長窓化と local FFT 読取改善は backend 回帰を保ったままコード差分に反映済みだが、frontend 自動テストと build による再検証は Node runtime 制約のため未完了である。

- frontend layout refresh を再実施
  - docs 的な説明 panel を frontend から外し、runtime state / controls / evidence に寄せた
  - `Single Job` を command deck / validation scope / evidence canvas の 3 層へ組み替え、sticky run registry rail と sticky support rail を導入
  - `Compare Jobs` / `Parameter Sweep` は left rail controls と main planning panel に絞った
  - `vite.config.ts` は `VITEST_CACHE_DIR` を受けて vitest cache 先を切り替えられるようにした
- `cd frontend && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH VITEST_CACHE_DIR=.vitest-local npm test -- --run`
  - 4 file、18 test すべて成功
- `cd frontend && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH ./node_modules/.bin/tsc --noEmit -p tsconfig.json && ./node_modules/.bin/tsc --noEmit -p tsconfig.node.json && ./node_modules/.bin/vite build --outDir dist-check --emptyOutDir`
  - production build 相当の型検査 + build 成功
  - 既存 `dist/` 配下が root-owned だったため、等価な `dist-check/` 出力で検証

少なくとも現時点で、surface-first な frontend 再構成は Node 20 環境下の test / typecheck / build で破綻していない。一方でホスト既定の Node `v12.22.9` と root-owned な frontend 生成物は引き続きローカル検証の阻害要因である。

- single-job page layout を再調整
  - `Workbench Pages` navigation を shell 上部へ移し、top-level surface switch を page 先頭で読めるようにした
  - `Single Job` は left sidebar に launch / config / run control を戻し、main canvas を run framing / primary evidence / advanced evidence の順序へ再構成した
  - validation scope と baseline / failure framing を summary band へ寄せ、observables + spectrum を primary evidence、contour surface を独立した advanced section へ分離した
- `cd frontend && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH VITEST_CACHE_DIR=.vitest-local npm test -- --run`
  - 4 file、18 test すべて成功
- `cd frontend && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH ./node_modules/.bin/tsc --noEmit -p tsconfig.json && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH ./node_modules/.bin/tsc --noEmit -p tsconfig.node.json && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH ./node_modules/.bin/vite build --outDir dist-check --emptyOutDir`
  - 型検査 + production build 相当が成功

少なくとも現時点で、Workbench Pages の上部移動と Single Job の reading-order 再編は Node 20 環境下の test / typecheck / build で破綻していない。

### 2026-03-19

- cmp-mp ライクな UI 改善を実施
  - ObservablePanel / SpectrumPanel のチャートを custom SVG LineChart から Plotly インタラクティブプロットへ移行し、ズーム / パン / ホバー / クリップボードコピーを有効化した
  - Parameter Sweep ページに SweepRailPanel を追加し、sweep 軸定義（パラメータパス選択、値範囲入力、parameter_kind 自動推定、baseline 値表示、fixed axes 要約）を planning surface として配置した
  - ConfigPanel の各設定グループ（Lattice / Time Grid / Drive / Interaction / Observables / KBE Extensions）を CollapsibleSection で折り畳み可能にし、sidebar の情報密度を改善した
  - 全 surface の Sidebar 最下部に sticky action bar を追加し、Single Job は Launch Run / Cancel Run、Compare Jobs は Launch Compare Group（disabled）、Parameter Sweep は Launch Sweep（disabled）を配置した
  - テスト内の SVG role="img" 依存を Plotly 移行に合わせて更新した
- `cd frontend && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH npx tsc --noEmit -p tsconfig.json`
  - 型検査成功
- `cd frontend && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH VITEST_CACHE_DIR=.vitest-local npm test -- --run`
  - 4 file、18 test すべて成功
- `cd frontend && PATH=/tmp/tdkb-node/node-v20.20.1-linux-x64/bin:$PATH npx vite build --outDir dist-check --emptyOutDir`
  - production build 成功

少なくとも現時点で、Plotly チャート移行、SweepRailPanel 追加、ConfigPanel 折り畳み、sticky action bar 追加は Node 20 環境下の typecheck / test / build で破綻していない。

- experiment registry foundation を実施
  - SQLite-backed な `ExperimentRegistry` と `ExperimentRepository` を追加し、`/runs` 一覧を directory scan ではなく DB query 正本へ切り替えた
  - `study` / `decision note` / `evidence bundle` schema と `/studies` / `/decision-notes` / `/evidence-bundles` API を追加した
  - run metadata patch (`/runs/{id}/metadata`) を追加し、`study_id` / `run_role` / `validation_status` / `failure_tags` / `group_id` / `sweep_id` / `variant_label` / `preset_id` / `tags` / `config_hash` / `code_version` / `storage_uri` を保持できるようにした
  - `backend/scripts/backfill_experiment_registry.py` を追加し、既存 run directory の再索引 utility を用意した
  - frontend OpenAPI を再生成し、strict 化された nested config 型に合わせて `ConfigPanel` / `workbench` helper / `App.test.tsx` の type usage を補正した
- `uv run python -m pytest backend/tests`
  - 60 件すべて成功
- `cd frontend && node ./scripts/generate-openapi.mjs`
  - OpenAPI schema を再生成
- `cd frontend && /home/matsubayashi/.vscode-server/bin/ce099c1ed25d9eb3076c11e4a280f3eb52b4fbeb/node ./node_modules/openapi-typescript/bin/cli.js ./openapi.json --output ./src/api/generated.ts`
  - `frontend/src/api/generated.ts` を再生成
- `cd frontend && /home/matsubayashi/.vscode-server/bin/ce099c1ed25d9eb3076c11e4a280f3eb52b4fbeb/node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
  - 型検査成功
- `cd frontend && /home/matsubayashi/.vscode-server/bin/ce099c1ed25d9eb3076c11e4a280f3eb52b4fbeb/node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.node.json`
  - Node-side 型検査成功
- `cd frontend && /home/matsubayashi/.vscode-server/bin/ce099c1ed25d9eb3076c11e4a280f3eb52b4fbeb/node ./node_modules/vitest/vitest.mjs run`
  - 4 file、18 test すべて成功
- `cd frontend && /home/matsubayashi/.vscode-server/bin/ce099c1ed25d9eb3076c11e4a280f3eb52b4fbeb/node ./node_modules/vite/bin/vite.js build --outDir /tmp/tdkb-frontend-build`
  - production build 相当が成功
  - 既存 `frontend/dist/assets/` が root-owned で通常 outDir を空にできないため、一時 outDir で検証

少なくとも現時点で、experiment registry foundation、run metadata patch、research artifact API、OpenAPI 再生成、および frontend 型修正は backend / frontend の test / typecheck / build 相当で破綻していない。一方で `job group` / `sweep` / `derived analysis artifact` の durable lineage と frontend 接続は引き続き未実装である。

- experiment repository の冗長な中間 upsert を削除し、run metadata patch 時の Pydantic serialization warning を解消した
- `cd frontend && openapi-typescript ./openapi.json --output ./src/api/generated.ts`
  - Node 20 環境で OpenAPI 型を再生成
- `uv run python -m pytest backend/tests -W error::UserWarning`
  - 60 件すべて成功、UserWarning なし
- `cd frontend && npx tsc --noEmit -p tsconfig.json`
  - 型検査成功
- `cd frontend && npm test -- --run`
  - 4 file、18 test すべて成功
- `cd frontend && npx vite build --outDir dist-check --emptyOutDir`
  - production build 成功

少なくとも現時点で、P1.5 Experiment Registry Foundation の受け入れ条件は backend / frontend の test / typecheck / build で満たされている。

---

## 次の優先作業

### 優先度 A

- `scipy` を入れた前提で、fixed-point mixing を Anderson / Broyden 系へ置き換える候補を評価する
- 2x2 exact diagonalization benchmark を longer-time / larger-window の reference regression へ広げる
- Phase 2-3 の `dt` 収束と continuity residual を validation-spec の gate として追加する

### 優先度 B

- registry を前提に、`job group` / `sweep` / `derived analysis artifact` の table / API / 型 / storage を追加する
- `studies` / `decision-notes` / `evidence-bundles` を frontend の actual surface と URL deep link に接続する
- Higgs demo を基準にした preset 戦略を定め、`kbe_hfb + hfb + bond_d` を軸に単一 run / 比較 / sweep の導線を設計する
- demo preset と baseline preset の分離、および numerical validation compare / sweep の導線を設計する
- local FFT preview を backend 保存の `derived analysis artifact` に置き換え、FFT / peak extraction metadata を再取得可能にする
- run log 表示と、`study` / tab / run / group / sweep を含む URL deep link を拡張する
- compare / sweep placeholder を registry-backed artifact surface に置き換える
- プロセスモードのテスト、cancel テスト、E2E を追加する
- 長時間 run を見据えて observables の部分取得を検討する
- 必要なら two-time / mixed Green 関数の chunked archive 形式を検討する

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

- 追加した 2x2 exact diagonalization benchmark が longer-time の reference regression まで広がったか
- `save_every` 縮約付き two-time / thermal / mixed Green 関数 API が frontend / longer run で十分か
- `job group` / `sweep` / `derived analysis artifact` を置ける registry schema が固まったか
- `study` / `decision note` / `evidence bundle` が frontend surface と deep link に接続されたか
- local FFT preview が backend 保存の derived analysis artifact へ置き換わったか
- compare / sweep placeholder が registry-backed artifact surface へ置き換わったか
- cancel が UI から操作でき、期待どおり止まるか
- プロセスモードと E2E の自動テストが追加されたか
