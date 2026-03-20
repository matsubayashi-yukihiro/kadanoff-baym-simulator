# 開発進捗管理

この文書は、[theory.md](./theory.md) と [research-workbench-plan.md](./research-workbench-plan.md) を踏まえた実装進捗の記録である。  
今後の進捗更新はこのファイルを正本として行う。

- 物理仕様の正本: `docs/theory.md`
- backend validation の正本: `docs/validation-spec.md`
- 研究アプリ全体方針の正本: `docs/research-workbench-plan.md`
- backend artifact 運用整理: `docs/backend-artifact-lifecycle.md`
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

## 2026-03-20 時点の要約

- 到達点は、Phase E 完了、heuristic prototype の `second_born` 保持、および backend 修繕計画の `R0-R5` 完了までである。
- backend は run 管理 API、非相互作用ソルバー、TDHFB / BdG、KBE + HFB、two-time / thermal / mixed Green 関数の保存 / 部分取得 API、関連診断を実装済みである。
- research workbench backend には experiment registry、repository 層、`study` / `decision note` / `job group` / `sweep` / `derived analysis artifact` / `evidence bundle` の durable metadata と API が入り、run-child lineage と parent artifact state aggregation を DB で保持できる。
- `job-groups/launch` / `sweeps/launch` / `derived-analyses/launch` / `derived-analyses/{id}/result` / `evidence-bundles/{id}/resolved` により、compare / sweep / analysis / provenance の backend lifecycle は一通り閉じた。現在の artifact 単位の責務と保存・再取得の流れは `docs/backend-artifact-lifecycle.md` を参照する。
- 一方で backend 点検の結果、`kbe.self_energy=second_born`、adaptive history integral、相関 thermal / mixed branch の legacy 実装は、文献準拠の full KBE second Born ではなく heuristic prototype と再判定した。
- これに対して `kbe.self_energy=second_born_reference` を追加し、`0906.1704_time-propagation-kbe.pdf` / `2405.08737_adaptive-time-stepping-two-time-kbe.pdf` / `2105.06193_superconducting-nanowires-negf.pdf` を突き合わせた explicit self-energy の equal-time GKBA reference path を backend に実装した。
- さらに `second_born_reference` に self-consistent Matsubara / mixed branch dressing、adaptive reference regression、full-contour diagnostics を追加し、Phase E1-E3 の受け入れ条件を reference path で閉じた。
- `second_born_reference` の representative `4x2` case を `cProfile` で測定し、局所 self-energy 構築が支配項であることを確認したうえで、局所 2x2 block 抽出のベクトル化と reference path の不要 HFB two-time Green 関数構築削減を実施した。
- prototype / reference が共有する factorized Matsubara / mixed branch builder を `green_functions.py` に寄せ、thermal / mixed seed 生成をベクトル化した。
- `FileRunStorage` に `save_every` ベースの two-time / mixed Green 関数保存縮約を導入し、solver 内部の full-grid diagnostics を維持したまま、長時間 run 向けの保存サイズと slice API の取得点数を削減した。
- frontend は solver 切替、pairing channel / seed 入力、pairing 系列表示、KBE 診断量表示に加えて、KBE self-energy / adaptive / thermal branch の入力欄と two-time Green 関数 slice inspector を持つ。
- frontend は `Single Job` / `Compare Jobs` / `Parameter Sweep` の shell、preset library、baseline / failure / validation framing、Plotly chart、research artifacts surface まで進んだが、compare / sweep / backend-derived analysis の actual fetch と URL deep link は未接続である。
- 研究アプリ全体の product / architecture 方針の正本として `docs/research-workbench-plan.md` を追加し、`Single Job` / `Compare Jobs` / `Parameter Sweep` を持つ workbench への拡張方針に加えて、`study` / `decision note` / `evidence bundle` を含む研究 artifact model、physics compare と numerical validation compare / sweep の両立、demo preset と baseline preset の分離を固定した。
- `pairing`, `pairing_s`, `pairing_d` を backend / API / frontend の共通 observable として扱える。
- adaptive integrator の主参照として [2405.08737_adaptive-time-stepping-two-time-kbe.pdf](../pdfs/negf_kbe/2405.08737_adaptive-time-stepping-two-time-kbe.pdf) を採用する。
- 修繕計画の正本として `docs/backend-remediation-plan.md` を追加し、参考文献束を `pdfs/negf_kbe/` に集約した。
- backend solver validation の正本として `docs/validation-spec.md` を追加し、phase gate、test mapping、validated / not yet validated の判定を一本化した。
- ローカルファイル名と文献タイトル、要約の対応は `docs/literature-index.md` を正本として引く。
- 修繕計画の R0-R2 足場として、`scipy` 導入、`numerics.py` / `equilibrium.py` / `contour.py` / `green_functions.py` / `self_energy_second_born_prototype.py` の追加、および `kbe_hfb.py` の orchestration 層への整理を実施した。
- 修繕計画の R3 を閉じ、2x2 系の固定粒子数 exact diagonalization benchmark helper、benchmark 比較 utility、`dt` / adaptive tolerance / 系サイズ row の docs 収束表、および `second_born_reference` を含む short-window benchmark を追加した。
- `fixed_point.py` に Anderson/Broyden 候補評価 utility を追加し、HFB equilibrium の固定点反復には Anderson/DIIS 系 accelerator を採用した。一方で Phase E contour fixed-point は既存 validation row を維持するため linear mixing を保持した。
- pytest marker として `physics_unit` / `physics_invariant` / `physics_benchmark` / `workflow` を追加し、Phase 1 の continuity residual regression に加えて、Phase 2-3 の source-free continuity residual、weak-coupling `dt` row、2x2 exact benchmark の longer-time / larger-window regression を追加した。

---

## backend 修繕フェーズ進捗

| 修繕フェーズ | 状態 | 現在の到達点 | 残作業 |
| --- | --- | --- | --- |
| Phase R0: 凍結とラベリング | 完了 | Phase E 実装を heuristic prototype として docs / diagnostics に反映済み | 維持のみ |
| Phase R1: numerical utility の整理 | 完了 | `scipy` 導入、数値 utility の共通化に加えて、fixed-point 候補評価 utility と HFB equilibrium の Anderson/DIIS 系 accelerator を導入済み | contour fixed-point への適用は validation row を見ながら継続検討 |
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
| experiment registry | 部分完了 | `study` / run metadata / `job group` / `sweep` / `decision note` / `derived analysis artifact` / `evidence bundle` を SQLite-backed な `experiment registry` で索引し、filesystem artifact と DB metadata を repository 層で束ねている。artifact ごとの責務、主要 API、保存 / 再取得の流れは `docs/backend-artifact-lifecycle.md` に切り出した。 | compare / sweep 系 artifact を frontend surface と URL state に接続する |
| API / schema | 部分完了 | OpenAPI を正本に、`/runs` 系、Green 関数系、`/studies`、`/job-groups`、`/job-groups/launch`、`/sweeps`、`/sweeps/launch`、`/decision-notes`、`/derived-analyses`、`/derived-analyses/launch`、`/derived-analyses/{id}/result`、`/evidence-bundles`、`/evidence-bundles/{id}`、`/evidence-bundles/{id}/resolved` を提供している。backend の launch/result/provenance contract は揃ったが、frontend 側の actual fetch と deep link は未完である。 | frontend actual surface 接続と URL deep link を追加する |
| run 管理 | 完了 | `queued/running/succeeded/failed/cancelled` を保持し、run ごとに JSON/NPZ を保存する。`/runs` 一覧は registry DB query を正本とし、`study_id` / `run_role` / `validation_status` / `failure_tags` / `group_id` / `sweep_id` / `variant_label` / `preset_id` / `tags` / `config_hash` / `code_version` / `storage_uri` を run metadata として保持できる。`job group` / `sweep` については child run から親 artifact state を集約できる。さらに run status に残った `pid` から cancel fallback でき、process mode の submit/cancel workflow regression も追加した | UI/E2E の cancel 回帰を追加する |
| ジョブ実行 | 完了 | `process` と `inline` の 2 モードあり。通常は別プロセス実行。workflow test で process mode の submit/cancel も回帰化した | UI/E2E を追加する |
| cancel 機能 | 部分完了 | backend API と frontend の `Cancel Run` ボタンは実装済みで、Single Job には `RunLogPanel` を接続済み。さらに API 再起動後を模した `runner.cancel()` miss 時でも、status に保存された `pid` へ signal を送って cancel できる fallback と、process mode submit/cancel workflow test を backend に追加した | UI/E2E を追加する |
| ストレージ | 完了 | `config/status/summary/diagnostics/observables.npz/run.log` に加え、KBE run では `green_functions.json` / `green_*.npy`、`thermal_branch.json` / `thermal_*.npy`、`mixed_green_functions.json` / `mixed_*.npy` を保存し、two-time / mixed time grid は `save_every` に応じて縮約される | 必要なら chunked archive 形式を別途検討 |
| 格子・一体 Hamiltonian | 完了 | 2 次元 square lattice、open/periodic 境界、Peierls 位相付き hopping に加え、Nambu / BdG 生成と HFB self-energy を実装 | second Born / memory self-energy に再利用 |
| 非相互作用ソルバー | 完了 | 密度行列の時間発展、密度・電流・エネルギー・ベクトルポテンシャルを出力し、`save_every` と外場仕事率診断を反映済み | paired solver の基準解として維持 |
| TDHFB / BdG ソルバー | 完了 | HFB 平衡初期化、一般化密度行列の中点時間発展、`pairing_s` / `pairing_d` 射影、HFB equilibrium の Anderson/DIIS 系 fixed-point accelerator、および source-free normal-state scope の continuity diagnostics を実装し、adaptive 有効化時は step-doubling 履歴も記録できる | paired source term を含む continuity 診断と長時間安定化を検討 |
| KBE ソルバー基盤 | 完了 | HFB 二時刻 Green 関数、retarded / lesser / Matsubara / mixed の保存形式、heuristic `second_born` prototype、および explicit self-energy の `second_born_reference` と self-consistent contour dressingを実装済みで、orchestration helper と contour seed builder を共通化済み。加えて HFB mode の source-free continuity diagnostics と 2x2 exact benchmark の longer-window row を追加した | longer-time / larger-system の benchmark 拡張 |
| 観測量 | 完了 | `density/current_x/current_y/energy/vector_potential/pairing/pairing_s/pairing_d` を返却 | second Born 向けに緩和・散乱診断を追加 |
| 診断量 | 完了 | HFB 収束履歴、stationarity、`two_time_grid_shape`、prototype の iteration/residual/memory/collision/contour/history-order/保存則残差に加え、`second_born_reference` の explicit self-energy / equation residual / GKBA reconstruction / thermal / mixed contour diagnostics を保存 | larger-system row と連動した追加可視化を検討 |
| frontend UI | 部分完了 | `Single Job` / `Compare Jobs` / `Parameter Sweep` の page-level shell、preset library、Plotly chart、research artifacts surface までは接続済みで、Single Job は run / diagnostics / Green 関数 / note / bundle を読める。compare / sweep / backend-derived analysis の actual result surface と URL deep link は未実装で、local FFT preview も backend 保存 artifact への置換前である。 | `job group` / `sweep` / `derived analysis artifact` の actual surface 接続と URL deep link を追加する |
| テスト | 部分完了 | solver validation row、Green / thermal / mixed API、`save_every` 保存縮約、experiment registry workflow、restart-safe cancel、process mode submit/cancel、bundle migration / restart persistence まで backend 回帰化した。workflow 層は artifact lifecycle の backend 整合確認に寄っており、frontend E2E と URL deep link の自動テストは未整備である。 | E2E の追加 |
| デプロイ / 起動系 | 完了 | `docker compose up --build` とローカル起動手順あり | 永続データ運用とジョブ監視の整理 |

---

## 検証ログ

### 2026-03-15 から 2026-03-19 の圧縮要約

- Phase B-D の backend / frontend 最小動線を確立し、非相互作用、TDHFB / BdG、KBE + HFB の基本回帰を継続的に通した。
- Phase E prototype を経て、`second_born_reference` の導入により Phase E1-E3 の reference path を閉じた。
- 修繕計画 R0-R5 を完了し、2x2 exact benchmark、adaptive / memory-window row、thermal / mixed contour dressing、profiling による高速化、`save_every` 付き保存縮約を backend 回帰付きで入れた。
- `docs/validation-spec.md` を正本として整備し、`physics_unit` / `physics_invariant` / `physics_benchmark` / `workflow` の marker 運用を固定した。
- frontend は workbench shell、Single Job / Compare Jobs / Parameter Sweep の page-level surface、Higgs demo preset、Plotly chart、SweepRailPanel、research artifacts surface を追加し、Node 20 系の検証環境では test / typecheck / build を通した。
- experiment registry foundation として `study` / `decision note` / `evidence bundle`、run metadata patch、OpenAPI 再生成、frontend client 接続を追加し、P1.5 の受け入れ条件を満たした。
- frontend の検証では、ホスト既定 Node `v12.22.9` と root-owned な `frontend/dist` が繰り返し阻害要因になったため、Node 20 環境または代替 outDir で確認した。

圧縮前の詳細ログは git history を参照する。`docs/progress.md` には、以後は到達点判断に効く要約だけを残す。

### 2026-03-20

- experiment registry を compare / sweep / analysis / bundle まで広げ、`job group` / `sweep` / `derived analysis artifact` / `evidence bundle` の backend lifecycle を durable metadata と file artifact の組み合わせで扱えるようにした。
- `job-groups/launch` / `sweeps/launch` で child run 生成と parent artifact 同期を実装し、`derived analysis artifact` では `run/fft_preview`、`job_group/fft_compare`、`sweep/fft_heatmap` の launch / result fetch / cache reuse を追加した。
- `evidence bundle` には study 整合検証、`supports_bundle_ids` 逆参照同期、`status=draft|ready|superseded`、resolved provenance、patch、status filter を追加し、migration 後方互換と restart persistence も workflow 回帰化した。
- cancel 周りでは restart-safe PID fallback と process mode submit/cancel workflow regression を追加し、backend 単独では inline / process の両モードで cancel 動線を自動テスト化した。
- artifact 単位の現行 backend 運用整理は `docs/backend-artifact-lifecycle.md` に切り出した。
- `uv run python -m pytest backend/tests/test_experiment_registry.py backend/tests/test_api.py`
  - 30 件すべて成功
- `uv run python -m pytest backend/tests`
  - 81 件すべて成功
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm run build`
  - 既存 `frontend/dist/assets` が root-owned のため outDir cleanup で失敗
- `cd frontend && npm exec vite build -- --outDir dist-codex-check`
  - 一時 outDir では production build 成功
- backend Priority A を完了
  - `backend/app/solvers/fixed_point.py` を追加し、Anderson/Broyden 候補評価 utility を `physics_unit` で回帰化した
  - HFB equilibrium の fixed-point iteration に Anderson/DIIS 系 accelerator を適用し、`hfb_fixed_point_accelerator=anderson_diis` diagnostics を追加した
  - `tdhfb` / `kbe_hfb(self_energy=hfb)` に source-free continuity residual diagnostics を追加し、Phase 2-3 gate を `validation-spec` に反映した
  - `backend/tests/test_exact_diagonalization_benchmark.py` に 2x2 exact benchmark の longer-window regression と、Phase 2-3 weak-coupling `dt` row を追加した
- `uv run python -m pytest backend/tests/test_numerics.py backend/tests/test_tdhfb_solver.py backend/tests/test_kbe_hfb_solver.py backend/tests/test_exact_diagonalization_benchmark.py`
  - 37 件すべて成功

少なくとも現時点で、`job group` / `sweep` / `derived analysis artifact` / `evidence bundle` の backend metadata / lineage / payload 再取得は workflow regression と backend 全体 test で破綻していない。frontend 既定 outDir build は root-owned 生成物に阻まれたが、別 outDir build では API 追加後も bundling 自体は成立している。

---

## 次の優先作業

### 優先度 A

- larger lattice / longer-time の stability / convergence row を Phase 2-4 に広げる
- `process` mode / cancel / E2E を workflow 層の回帰として補完する
- `job group` / `sweep` / `derived analysis artifact` を frontend の actual surface と URL state に接続する

### 優先度 B

- `studies` / `decision-notes` / `evidence-bundles` の URL deep link と一覧導線を整理する
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

- larger lattice / longer-time の stability / convergence row が増えたか
- source term を含む paired state continuity diagnostics の整理方針が固まったか
- `save_every` 縮約付き two-time / thermal / mixed Green 関数 API が frontend / longer run で十分か
- `job group` / `sweep` / `derived analysis artifact` の launch / result / frontend surface がつながったか
- `study` / `decision note` / `evidence bundle` が frontend surface と deep link に接続されたか
- local FFT preview が backend 保存の derived analysis artifact へ置き換わったか
- compare / sweep placeholder が registry-backed artifact surface へ置き換わったか
- cancel が UI から操作でき、期待どおり止まるか
- プロセスモードと E2E の自動テストが追加されたか
