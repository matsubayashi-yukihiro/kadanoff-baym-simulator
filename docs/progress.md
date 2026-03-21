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

## 2026-03-21 時点の要約

- 到達点は、Phase E 完了、heuristic prototype の `second_born` 保持、および backend 修繕計画の `R0-R5` 完了までである。
- backend は run 管理 API、非相互作用ソルバー、TDHFB / BdG、KBE + HFB、two-time / thermal / mixed Green 関数の保存 / 部分取得 API、関連診断を実装済みである。
- research workbench backend には experiment registry、repository 層、`study` / `decision note` / `job group` / `sweep` / `derived analysis artifact` / `evidence bundle` の durable metadata と API が入り、run-child lineage と parent artifact state aggregation を DB で保持できる。
- `job-groups/launch` / `sweeps/launch` / `derived-analyses/launch` / `derived-analyses/{id}/result` / `evidence-bundles/{id}/resolved` により、compare / sweep / analysis / provenance の backend lifecycle は一通り閉じた。現在の artifact 単位の責務と保存・再取得の流れは `docs/backend-artifact-lifecycle.md` を参照する。
- 一方で backend 点検の結果、`kbe.self_energy=second_born`、adaptive history integral、相関 thermal / mixed branch の legacy 実装は、文献準拠の full KBE second Born ではなく heuristic prototype と再判定した。
- これに対して `kbe.self_energy=second_born_reference` を追加し、`0906.1704_time-propagation-kbe.pdf` / `2405.08737_adaptive-time-stepping-two-time-kbe.pdf` / `2105.06193_superconducting-nanowires-negf.pdf` を突き合わせた explicit self-energy の equal-time GKBA reference path を backend に実装した。
- さらに `second_born_reference` に self-consistent Matsubara / mixed branch dressing、adaptive reference regression、full-contour diagnostics を追加し、Phase E1-E3 の受け入れ条件を reference path で閉じた。
- `equilibrium.method=auto|hfb|second_born_reference` を schema に追加し、runtime approximation と一致しない初期化は `allow_approximation_mismatch=true` の明示 override がある場合だけ許可するようにした。
- `second_born_reference` には approximation-consistent equilibrium solver を追加し、finite-temperature では Matsubara / short-time source-free reference fixed-point を使って initial-correlation mismatch を減らす path を用意した。periodic `representation=k_space` でも同じ equilibrium / run artifact contract を保ち、zero-temperature と `U=0` では HFB limit fallback を維持する。
- TDHFB / KBE trajectory diagnostics には `stationarity_residual_history`、density/pairing/energy initial slip history を追加し、source-free mismatch regression を backend invariant test に追加した。
- `second_born_reference` の representative `4x2` case を `cProfile` で測定し、局所 self-energy 構築が支配項であることを確認したうえで、局所 2x2 block 抽出のベクトル化と reference path の不要 HFB two-time Green 関数構築削減を実施した。
- prototype / reference が共有する factorized Matsubara / mixed branch builder を `green_functions.py` に寄せ、thermal / mixed seed 生成をベクトル化した。
- `FileRunStorage` に `save_every` ベースの two-time / mixed Green 関数保存縮約を導入し、solver 内部の full-grid diagnostics を維持したまま、長時間 run 向けの保存サイズと slice API の取得点数を削減した。
- backend は `progress.json` と `GET /api/v1/runs/{run_id}/progress` を追加し、queued / running 中の heartbeat、physical time、saved sample count、solver-specific telemetry を polling で再取得できる。
- frontend は solver 切替、pairing channel / seed 入力、pairing 系列表示、KBE 診断量表示に加えて、KBE self-energy / adaptive / thermal branch の入力欄と two-time Green 関数 slice inspector を持つ。
- frontend は `Single Job` / `Compare Jobs` / `Parameter Sweep` の shell、preset library、baseline / failure / validation framing、Plotly chart、research artifacts surfaceに加えて、compare / sweep / backend-derived analysis の actual fetch と URL deep link まで接続済みである。
- 研究アプリ全体の product / architecture 方針の正本として `docs/research-workbench-plan.md` を追加し、`Single Job` / `Compare Jobs` / `Parameter Sweep` を持つ workbench への拡張方針に加えて、`study` / `decision note` / `evidence bundle` を含む研究 artifact model、physics compare と numerical validation compare / sweep の両立、demo preset と baseline preset の分離を固定した。
- `k-space / tr-ARPES` は P6 として新設し、既存 real-space / Green-function run artifact を source にした derived analysis surface として、M0-M3 で段階化する方針を追加した。
- solver backend には `representation=real_space|k_space` を追加し、periodic square lattice に限って `noninteracting` / `tdhfb` / `kbe_hfb(self_energy=hfb)` に加えて `kbe_hfb(self_energy=second_born_reference)` を k-basis でも実行できるようにした。既存 observables / diagnostics / Green-function contract は維持し、heuristic `second_born` は未対応のまま残す。
- backend には `run/k_spectral_preview` と `run/tr_arpes_preview` を追加し、periodic `kbe_hfb` run に保存された lesser Green 関数から、`k-path` occupied spectrum と minimal `tr-ARPES` intensity を backend derived analysis artifact として生成・再取得できるようにした。
- さらに `job_group/k_spectral_compare` と `sweep/tr_arpes_heatmap` を追加し、compare / sweep artifact でも `k-space` derived analysis を backend で再利用できるようにした。
- `tdhfb` / `kbe_hfb(self_energy=hfb)` の `representation=k_space` parity について、periodic 4x4 の moderate longer-window row を backend invariant test に追加し、現行保証範囲を docs と揃えた。
- `k-space / tr-ARPES` derived analysis には synthetic benchmark row を追加し、`k_path_coverage` / `spectral_symmetry_error` / `sum_rule_residual` / `delay_axis_coverage` / `probe_width_resolution_tradeoff` の threshold を validation spec に固定した。
- backend Priority A として、`tdhfb` / `kbe_hfb(self_energy=hfb)` に periodic paired 4x4 longer-time parity row (`t_final=0.4`) を追加し、`k_spectral_preview` / `tr_arpes_preview` には run-derived `real_space` / `k_space` source cross-check を追加した。
- さらに `second_born_reference` real-space run を source にした `k_spectral_preview` workflow regression を追加し、derived analysis source reuse と native `representation=k_space` correlated extension の境界を docs / tests で固定した。
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
| experiment registry | 部分完了 | `study` / run metadata / `job group` / `sweep` / `decision note` / `derived analysis artifact` / `evidence bundle` を SQLite-backed な `experiment registry` で索引し、filesystem artifact と DB metadata を repository 層で束ねている。artifact ごとの責務、主要 API、保存 / 再取得の流れは `docs/backend-artifact-lifecycle.md` に切り出した。FFT 系に加えて `k-space / tr-ARPES` derived analysis も compare / sweep artifact から再利用できる。 | frontend surface と URL state に接続する |
| API / schema | 完了 | OpenAPI を正本に、`/runs` 系、Green 関数系、`/studies`、`/job-groups`、`/job-groups/launch`、`/sweeps`、`/sweeps/launch`、`/decision-notes`、`/derived-analyses`、`/derived-analyses/launch`、`/derived-analyses/{id}/result`、`/evidence-bundles`、`/evidence-bundles/{id}`、`/evidence-bundles/{id}/resolved` を提供している。backend の launch/result/provenance contract は揃い、`run/k_spectral_preview`、`run/tr_arpes_preview`、`job_group/k_spectral_compare`、`sweep/tr_arpes_heatmap` に加えて `run progress` も fetch できる。frontend client も `listJobGroups` / `launchJobGroup` / `listSweeps` / `launchSweep` / `launchDerivedAnalysis` / `getDerivedAnalysisResult` / `getRunProgress` 等を追加し、actual surface まで接続済みである。 | 維持のみ |
| run 管理 | 完了 | `queued/running/succeeded/failed/cancelled` を保持し、run ごとに JSON/NPZ を保存する。`/runs` 一覧は registry DB query を正本とし、`study_id` / `run_role` / `validation_status` / `failure_tags` / `group_id` / `sweep_id` / `variant_label` / `preset_id` / `tags` / `config_hash` / `code_version` / `storage_uri` を run metadata として保持できる。`job group` / `sweep` については child run から親 artifact state を集約できる。さらに run status に残った `pid` から cancel fallback でき、process mode の submit/cancel workflow regression も追加した | UI/E2E の cancel 回帰を追加する |
| ジョブ実行 | 完了 | `process` と `inline` の 2 モードあり。通常は別プロセス実行。workflow test で process mode の submit/cancel も回帰化した | UI/E2E を追加する |
| cancel 機能 | 部分完了 | backend API と frontend の `Cancel Run` ボタンは実装済みで、Single Job には `RunLogPanel` を接続済み。さらに API 再起動後を模した `runner.cancel()` miss 時でも、status に保存された `pid` へ signal を送って cancel できる fallback と、process mode submit/cancel workflow test を backend に追加した。`progress.json` も cancel 時に `state/phase=cancelled` へ同期される | UI/E2E を追加する |
| ストレージ | 完了 | `config/progress/status/summary/diagnostics/observables.npz/run.log` に加え、KBE run では `green_functions.json` / `green_*.npy`、`thermal_branch.json` / `thermal_*.npy`、`mixed_green_functions.json` / `mixed_*.npy` を保存し、two-time / mixed time grid は `save_every` に応じて縮約される。`progress.json` には running 中の heartbeat と solver-specific telemetry ring buffer を保持する | 必要なら chunked archive 形式を別途検討 |
| 格子・一体 Hamiltonian | 完了 | 2 次元 square lattice、open/periodic 境界、Peierls 位相付き hopping に加え、Nambu / BdG 生成と HFB self-energy を実装 | second Born / memory self-energy に再利用 |
| 非相互作用ソルバー | 完了 | 密度行列の時間発展、密度・電流・エネルギー・ベクトルポテンシャルを出力し、`save_every` と外場仕事率診断を反映済み | paired solver の基準解として維持 |
| TDHFB / BdG ソルバー | 完了 | HFB 平衡初期化、一般化密度行列の中点時間発展、`pairing_s` / `pairing_d` 射影、HFB equilibrium の Anderson/DIIS 系 fixed-point accelerator、および source-free normal-state scope の continuity diagnostics を実装し、adaptive 有効化時は step-doubling 履歴も記録できる | paired source term を含む continuity 診断と長時間安定化を検討 |
| KBE ソルバー基盤 | 完了 | HFB 二時刻 Green 関数、retarded / lesser / Matsubara / mixed の保存形式、heuristic `second_born` prototype、および explicit self-energy の `second_born_reference` と self-consistent contour dressingを実装済みで、orchestration helper と contour seed builder を共通化済み。加えて HFB mode の source-free continuity diagnostics、approximation-aware equilibrium dispatch、`second_born_reference` equilibrium seed、source-free stationarity regression を追加した | longer-time / larger-system の benchmark 拡張 |
| 観測量 | 完了 | `density/current_x/current_y/energy/vector_potential/pairing/pairing_s/pairing_d` を返却 | second Born 向けに緩和・散乱診断を追加 |
| 診断量 | 完了 | HFB 収束履歴、stationarity、`two_time_grid_shape`、prototype の iteration/residual/memory/collision/contour/history-order/保存則残差に加え、`second_born_reference` の explicit self-energy / equation residual / GKBA reconstruction / thermal / mixed contour diagnostics と equilibrium method / source-free initial slip history を保存 | larger-system row と連動した追加可視化を検討 |
| k-space native solver representation | 部分完了 | `representation=real_space|k_space` を schema と backend solver に追加し、periodic square lattice の `noninteracting` / `tdhfb` / `kbe_hfb(self_energy=hfb)` に加えて `kbe_hfb(self_energy=second_born_reference)` で parity / benchmark / workflow regression を追加した。`tdhfb` / `kbe_hfb(self_energy=hfb)` には periodic 4x4 の moderate longer-window parity rowと paired longer-time row (`t_final=0.4`) に加え、paired larger-lattice row (`tdhfb`: 6x6, `kbe_hfb`: 5x5, `t_final=0.3`) を追加済み。`second_born_reference` には `U=0` HFB limit、real/k parity、3x3 longer-window parity、periodic finite-temperature exact benchmark（short/longer window）、run artifact contract row を追加した。run artifact contract は維持され、`solver_representation` diagnostics も保存される。 | frontend selector の明示と、`validated` 昇格に向けた独立 cross-check の継続追加 |
| k-space / tr-ARPES derived analysis | 部分完了 | periodic `kbe_hfb` run の lesser Green 関数に加え、periodic `tdhfb` run を direct source として `run/k_spectral_preview` / `run/tr_arpes_preview`、`job_group/k_spectral_compare` / `sweep/tr_arpes_heatmap` の launch / cache reuse / result fetch を backend で再利用できるようにした。analysis sweep では `parameter_kind=analysis`, `parameter_path=probe_center` を probe delay override として解釈できる。さらに synthetic benchmark row、`kbe_hfb` / `tdhfb` の run-derived `real_space` / `k_space` source cross-check、`second_born_reference` の real-space / native `k_space` source parity cross-check、compare/sweep payload regression（energy-grid variant、analysis override）を固定した。frontend 側の actual surface は別項目で接続済みである。 | frontend compare/sweep surface の統合回帰を追加する |
| frontend UI | 部分完了 | `Single Job` / `Compare Jobs` / `Parameter Sweep` の page-level shell、preset library、Plotly chart、research artifacts surface に加えて、`representation=k_space` selector / 検証ガイド（`second_born` 非対応警告含む）、`useDerivedAnalysis` フック + `DerivedAnalysisPanel` 共通基盤、`KSpectralPanel` / `TrArpesPanel`（k-space run 限定）、`useJobGroups` / `JobGroupResultPanel`、`useSweeps` / `SweepResultPanel` を実装し、Compare Jobs / Parameter Sweep の実 API 接続と URL deep link（group/sweep params）まで完了した。Single Job には `useRunProgress` + `RunProgressPanel` を追加し、running/queued 中の heartbeat、physical progress、saved sample count、solver-specific mini metrics を 2 秒 polling で表示できる。local FFT バナーは backend 保存 artifact への置換保留中である。 | `second_born_reference` k-space unsupported scope の UI 明示、local FFT preview の backend derived analysis 置換（payload format 確認後）、E2E テストの追加 |
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
- `k-space / tr-ARPES` を次の主線として P6 に格上げし、既存 real-space / Green-function run artifact を source にする derived analysis program として M0-M3 を定義した。
- `backend/app/solvers/kspace_analysis.py` を追加し、periodic `kbe_hfb` run の lesser Green 関数から `k-path` occupied spectrum と matrix-element-free minimal `tr-ARPES` intensity を再構成する helper を実装した。
- `derived analysis artifact` には `run/k_spectral_preview` と `run/tr_arpes_preview` を追加し、launch / result fetch / cache reuse を workflow regression に含めた。
- `job_group/k_spectral_compare` と `sweep/tr_arpes_heatmap` を追加し、compare / sweep artifact からも `k-space` derived analysis を再利用できるようにした。`tr_arpes_heatmap` は analysis sweep で `probe_center` override を受け取れる。
- run artifact には `progress.json` を追加し、worker / solver callback から heartbeat、physical time、saved sample count、`tdhfb` / `kbe_hfb` の adaptive / fixed-point mini metrics を保存できるようにした。
- `/api/v1/runs/{run_id}/progress` を追加し、queued / running / terminal の progress state を `RunDetail` から分離して再取得できるようにした。
- frontend には `RunProgressPanel` を追加し、Single Job で running/queued 中の progress chart と solver-specific mini metrics を 2 秒 polling で表示できるようにした。`RunLogPanel` は terminal-only のまま維持した。
- `backend/app/solvers/representation.py` を追加し、periodic square lattice 向けの Fourier basis / Nambu basis 変換 helper を実装した。
- `SimulationConfig` に `representation=real_space|k_space` を追加し、periodic square lattice を対象に `noninteracting` / `tdhfb` / `kbe_hfb(self_energy=hfb)` で k-basis backend path を追加した。run artifact と API contract は既存のまま維持する。
- `backend/tests/test_noninteracting_solver.py`、`backend/tests/test_tdhfb_solver.py`、`backend/tests/test_kbe_hfb_solver.py` に representation parity regression を追加した。
- `backend/tests/test_tdhfb_solver.py` と `backend/tests/test_kbe_hfb_solver.py` に、periodic 4x4 の moderate longer-window `representation=k_space` parity row を追加した。
- `docs/validation-spec.md` に Phase 5A の現行保証範囲として、4x4 short-window に加え moderate longer-window parity row を追記した。
- `backend/tests/test_kspace_spectral_analysis.py` と `backend/tests/test_tr_arpes_analysis.py` を追加し、synthetic benchmark row として k-path coverage / occupied-weight symmetry / probe-width delay tradeoff を `physics_benchmark` で固定した。
- `docs/validation-spec.md` で Phase 5 を `partially validated` へ更新し、derived analysis の threshold を planned から実値へ移した。
- cancel 周りでは restart-safe PID fallback と process mode submit/cancel workflow regression を追加し、backend 単独では inline / process の両モードで cancel 動線を自動テスト化した。
- artifact 単位の現行 backend 運用整理は `docs/backend-artifact-lifecycle.md` に切り出した。
- `uv run python -m pytest backend/tests/test_kspace_analysis.py backend/tests/test_api.py`
  - 21 件すべて成功
- `uv run python -m pytest backend/tests`
  - 84 件すべて成功
- `uv run python -m pytest backend/tests`
  - 91 件すべて成功
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
- `uv run python -m pytest backend/tests/test_tdhfb_solver.py backend/tests/test_kbe_hfb_solver.py -k 'moderate_longer_window or k_space_representation_matches_real_space'`
  - 4 件成功、19 件 deselected（3 分 59 秒）
- `uv run python -m pytest backend/tests/test_kspace_spectral_analysis.py backend/tests/test_tr_arpes_analysis.py`
  - 3 件すべて成功
- `uv run python -m pytest backend/tests/test_progress_storage.py backend/tests/test_api.py -k 'progress or cancel'`
  - 4 件すべて成功
- `uv run python -m pytest backend/tests/test_schema.py backend/tests/test_tdhfb_solver.py backend/tests/test_kbe_stationarity.py backend/tests/test_kbe_hfb_solver.py`
  - 37 件すべて成功
- `cd frontend && npm run generate:api`
  - `equilibrium.method` / `equilibrium.allow_approximation_mismatch` を含む OpenAPI schema / TypeScript 型を再生成

少なくとも現時点で、`job group` / `sweep` / `derived analysis artifact` / `evidence bundle` の backend metadata / lineage / payload 再取得は workflow regression と backend 全体 test で破綻していない。frontend 既定 outDir build は root-owned 生成物に阻まれたが、別 outDir build では API 追加後も bundling 自体は成立している。

- frontend 開発プランの Phase 1-7 を実装した:
  - Phase 1: `ConfigPanel` に `representation=real_space|k_space` セレクタと k_space 制約バリデーション警告（`second_born` 非対応、periodic 必須）を追加した
  - Phase 2: `useDerivedAnalysis` フック（cache check → launch → polling → result fetch）と `DerivedAnalysisPanel` 共通基盤を追加した
  - Phase 3: `KSpectralPanel` / `TrArpesPanel` を `SingleJobPage.tsx` に追加し、`representation=k_space` run 限定で auto-launch する
  - Phase 4: `useJobGroups` フック + `JobGroupResultPanel` を追加し、`CompareJobsPage.tsx` を実 API 接続にした。URL deep link (`group` param) も整備した
  - Phase 5: `useSweeps` フック + `SweepResultPanel` を追加し、`ParameterSweepPage.tsx` を実 API 接続にした。URL deep link (`sweep` param) も整備した
  - Phase 6: URL deep link は Phase 4/5 で組み込み済み
  - Phase 7: `SpectrumPanel` バナーを backend 保存 artifact の存在を反映した文言に更新した（完全置換は payload format 確認待ち）
- `cd frontend && npm test -- --run`
  - 25 件すべて成功（`PresetLibraryPanel` の aria-label 修正と `DiagnosticsPanel` eyebrow 修正を含む）

### 2026-03-21

- backend Priority A を完了:
  - `backend/tests/test_tdhfb_solver.py` と `backend/tests/test_kbe_hfb_solver.py` に periodic paired 4x4 longer-time (`t_final=0.4`) `representation=k_space` parity row を追加した
  - `backend/tests/test_kspace_spectral_analysis.py` と `backend/tests/test_tr_arpes_analysis.py` に、solver-produced lesser Green 関数を使う run-derived `real_space` / `k_space` source cross-check を追加した
  - `backend/tests/test_api.py` に、`second_born_reference` real-space run を source にした `k_spectral_preview` workflow regression を追加した
  - `docs/theory.md` / `docs/validation-spec.md` / `docs/progress.md` で、derived analysis source reuse と native correlated `k_space` extension の境界を固定した
- backend Priority B1 を完了:
  - `SimulationConfig` と `solve_second_born_reference_equilibrium` の `representation=k_space` 制約を更新し、periodic square lattice に限って `kbe_hfb(self_energy=second_born_reference)` の native `k_space` path を有効化した
  - `backend/tests/test_schema.py`、`backend/tests/test_kbe_hfb_solver.py`、`backend/tests/test_exact_diagonalization_benchmark.py`、`backend/tests/test_api.py` に、`U=0` HFB limit、real/k parity、periodic finite-temperature exact benchmark、run artifact workflow regression を追加した
  - `docs/theory.md` / `docs/validation-spec.md` / `docs/progress.md` を更新し、`second_born_reference(representation=k_space)` を `partially validated` の公開スコープへ移した
- `uv run python -m pytest backend/tests/test_kspace_spectral_analysis.py backend/tests/test_tr_arpes_analysis.py backend/tests/test_api.py -k 'k_space_preview_from_second_born_reference_source or run_derived or k_space_and_trarpes_derived_analysis_artifacts'`
  - 4 件成功、23 件 deselected（1 分 39 秒）
- `uv run python -m pytest backend/tests/test_tdhfb_solver.py backend/tests/test_kbe_hfb_solver.py -k 'test_tdhfb_k_space_representation_matches_real_space_on_longer_window or test_kbe_hfb_k_space_representation_matches_real_space_on_longer_window'`
  - 2 件成功、23 件 deselected（9 分 17 秒）
- `uv run python -m pytest backend/tests`
  - 109 件すべて成功、warning 2 件（41 分 04 秒）
- `uv run python -m pytest backend/tests/test_schema.py backend/tests/test_kbe_hfb_solver.py backend/tests/test_exact_diagonalization_benchmark.py backend/tests/test_api.py -k 'k_space_second_born_reference or accepts_k_space_second_born_reference or second_born_reference_k_space or test_api_accepts_k_space_second_born_reference_runs_and_keeps_existing_artifact_contracts'`
  - 5 件成功、62 件 deselected（50.85 秒）
- `uv run python -m pytest backend/tests/test_schema.py backend/tests/test_kbe_hfb_solver.py backend/tests/test_exact_diagonalization_benchmark.py backend/tests/test_api.py`
  - 67 件すべて成功（11 分 54 秒）
- backend Priority B2 を完了:
  - `backend/app/solvers/tdhfb.py` で two-time Green 関数（`retarded`/`lesser`）を run artifact として保存し、`tdhfb` run を k-space/tr-ARPES derived analysis の direct source として再利用可能にした
  - `backend/tests/test_tdhfb_solver.py` に two-time Green 関数保存の回帰を追加した
  - `backend/tests/test_kspace_spectral_analysis.py` と `backend/tests/test_tr_arpes_analysis.py` に `tdhfb` direct source の `real_space` / `k_space` parity cross-check を追加した
  - `backend/tests/test_api.py` に `tdhfb` source の `run/k_spectral_preview` / `run/tr_arpes_preview`、`job_group/k_spectral_compare` / `sweep/tr_arpes_heatmap` workflow regression を追加した
  - `docs/theory.md` / `docs/validation-spec.md` / `docs/progress.md` を更新し、`tdhfb` direct source を現行 backend scope に反映した
- `uv run python -m pytest backend/tests/test_tdhfb_solver.py backend/tests/test_kspace_spectral_analysis.py backend/tests/test_tr_arpes_analysis.py backend/tests/test_api.py -k 'tdhfb_writes_two_time_green_functions_for_derived_analysis_source or tdhfb_sources or from_tdhfb_sources'`
  - 5 件成功、39 件 deselected（10.21 秒）
- `uv run python -m pytest backend/tests/test_noninteracting_solver.py backend/tests/test_tdhfb_solver.py backend/tests/test_kbe_hfb_solver.py backend/tests/test_kspace_spectral_analysis.py backend/tests/test_tr_arpes_analysis.py backend/tests/test_exact_diagonalization_benchmark.py backend/tests/test_api.py -k 'k_space or kspace or trarpes or tr_arpes or k_spectral'`
  - 31 件成功、54 件 deselected（53.82 秒）

---

## 次の優先作業

### 優先度 B

- `second_born_reference(representation=k_space)` の独立 cross-check を継続追加し、`validated` 判定に必要な証跡を拡充する
- `representation` selector / unsupported or planned badge / `k-path` / `tr-ARPES` panel / compare / sweep actual fetch などの frontend 接続を E2E まで含めて固める
- local FFT preview を backend 保存の `derived analysis artifact` (`run/fft_preview`) に置き換え、payload format が確定次第 `SpectrumPanel` を切り替える
- cancel が UI から操作でき、期待どおり止まるか E2E テストで確認する
- **（コードレビュー由来・完了 2026-03-21）** `second_born_converged=False` の run の RunState 昇格ルール:
  `RunState.SUCCEEDED_WITH_WARNINGS` を追加し `worker.py` で昇格、`docs/validation-spec.md` §6 に意味境界を記載済み。
  生成型再生成: `npm run generate:api` 実施済み。
- **（コードレビュー由来・完了 2026-03-21）** `second_born_convergence_criterion`（`"strict"` / `"relaxed_5x"`）
  フィールドを両 second_born solver の diagnostics に追加済み。`docs/validation-spec.md` §6 に読み方を記載。
- **（コードレビュー由来・完了 2026-03-21）** `test_self_energy_second_born.py` に unit テスト 4 件追加
  （`_build_gkba_row_data` shape/antihermitian、`_damping_collision` zero input、convergence_criterion 回帰）。
- **（コードレビュー由来・完了 2026-03-21）** `docs/backend-remediation-plan.md` §10 に巨大モジュール分割方針を追記。

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

- `k-space / tr-ARPES` の M0 仕様が `theory` / `validation` / `workbench plan` で揃ったか
- `representation=k_space` の periodic scope と unsupported scope が docs / UI / validation で揃ったか
- `tdhfb` / `kbe_hfb(self_energy=hfb)` の 4x4 moderate longer-window parity row を超える row を追加したため、次は paired interacting larger-system / longer-time row へ進むか
- `tdhfb` / `kbe_hfb(self_energy=hfb)` の larger-lattice row（6x6 / 5x5）追加後の runtime コストと継続運用閾値を見直すか
- `second_born_reference(representation=k_space)` の公開境界と acceptance gate が docs / tests / UI messaging で維持されているか
- `k_spectral_preview` / `tr_arpes_preview` が `second_born_reference` real-space source でも整合しているか
- `k_spectral_preview` / `tr_arpes_preview` が `second_born_reference` native `k_space` source でも整合しているか
- `k-path` / delay panel が backend 保存 payload を読む actual surface として載ったか
- `Compare Jobs` / `Parameter Sweep` が `k-space` compare / heatmap payload を読む actual surface になったか
- `job group` / `sweep` / `derived analysis artifact` の launch / result / frontend surface がつながったか
- local FFT preview が backend 保存の derived analysis artifact へ置き換わったか
- cancel が UI から操作でき、期待どおり止まるか
- プロセスモードと E2E の自動テストが追加されたか
