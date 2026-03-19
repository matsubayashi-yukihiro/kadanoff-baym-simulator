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

## 2026-03-20 時点の要約

- 到達点は、Phase E 完了、heuristic prototype の `second_born` 保持、および backend 修繕計画の `R0-R5` 完了までである。
- backend は run 管理 API、非相互作用ソルバー、TDHFB / BdG、KBE + HFB、two-time / thermal / mixed Green 関数の保存 / 部分取得 API、関連診断を実装済みである。
- research workbench の `P1.5` 足場として、SQLite-backed な experiment registry、filesystem artifact と DB metadata を束ねる repository 層、`study` / `decision note` / `evidence bundle` API、run metadata patch、および既存 run の backfill utility を追加した。
- compare / sweep の backend 足場として、`job group` / `sweep` / `derived analysis artifact` の registry table / schema / API を追加し、run-child lineage と parent artifact state aggregation を registry DB で保持できるようにした。
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
| experiment registry | 部分完了 | SQLite-backed な `experiment registry`、`ExperimentRepository`、DB-backed `/runs` list、`study` / `decision note` / `evidence bundle` API、run metadata patch、backfill utility に加えて、`job group` / `sweep` / `derived analysis artifact` の registry table / API / relation schema を追加し、run-child lineage と parent artifact state aggregation を DB 側で保持できる | compare / sweep / analysis の launch・再計算・result payload を backend artifact lifecycle へ広げる |
| API / schema | 部分完了 | `/health`, `/schema/simulation`, `/presets`, `/runs`, `/runs/{id}`, `/runs/{id}/metadata`, `/runs/{id}/log`, `/runs/{id}/observables`, `/runs/{id}/green-functions`, `/runs/{id}/thermal-branch`, `/runs/{id}/mixed-green-functions`, `/studies`, `/job-groups`, `/sweeps`, `/decision-notes`, `/derived-analyses`, `/evidence-bundles` が実装済みで、`kbe` / `adaptive` / `thermal_branch` 設定と research artifact schema を API から取得できる。`/presets` には provisional な `square-4x4-higgs-demo-kbe-hfb` を追加し、`kbe_hfb + hfb + bond_d` の long-window Gaussian pulse demo draft を API から取得できる | launch semantics を持つ compare / sweep API、analysis payload 再取得面、enriched `presets`、study-aware URL state を追加する |
| run 管理 | 完了 | `queued/running/succeeded/failed/cancelled` を保持し、run ごとに JSON/NPZ を保存する。`/runs` 一覧は registry DB query を正本とし、`study_id` / `run_role` / `validation_status` / `failure_tags` / `group_id` / `sweep_id` / `variant_label` / `preset_id` / `tags` / `config_hash` / `code_version` / `storage_uri` を run metadata として保持できる。`job group` / `sweep` については child run から親 artifact state を集約できる | restart-safe cancel を追加する |
| ジョブ実行 | 完了 | `process` と `inline` の 2 モードあり。通常は別プロセス実行 | 再起動後の cancel 継続性、プロセスモードのテスト追加 |
| cancel 機能 | 部分完了 | backend API と frontend の `Cancel Run` ボタンは実装済みで、Single Job には `RunLogPanel` を接続済み | API 再起動後の cancel 継続性、process mode test を追加する |
| ストレージ | 完了 | `config/status/summary/diagnostics/observables.npz/run.log` に加え、KBE run では `green_functions.json` / `green_*.npy`、`thermal_branch.json` / `thermal_*.npy`、`mixed_green_functions.json` / `mixed_*.npy` を保存し、two-time / mixed time grid は `save_every` に応じて縮約される | 必要なら chunked archive 形式を別途検討 |
| 格子・一体 Hamiltonian | 完了 | 2 次元 square lattice、open/periodic 境界、Peierls 位相付き hopping に加え、Nambu / BdG 生成と HFB self-energy を実装 | second Born / memory self-energy に再利用 |
| 非相互作用ソルバー | 完了 | 密度行列の時間発展、密度・電流・エネルギー・ベクトルポテンシャルを出力し、`save_every` と外場仕事率診断を反映済み | paired solver の基準解として維持 |
| TDHFB / BdG ソルバー | 完了 | HFB 平衡初期化、一般化密度行列の中点時間発展、`pairing_s` / `pairing_d` 射影を実装し、adaptive 有効化時は step-doubling 履歴も記録できる | 長時間安定化とより高次の積分器を検討 |
| KBE ソルバー基盤 | 完了 | HFB 二時刻 Green 関数、retarded / lesser / Matsubara / mixed の保存形式、heuristic `second_born` prototype、および explicit self-energy の `second_born_reference` と self-consistent contour dressing を実装済みで、orchestration helper と contour seed builder を共通化済み | longer-time / larger-system の benchmark 拡張 |
| 観測量 | 完了 | `density/current_x/current_y/energy/vector_potential/pairing/pairing_s/pairing_d` を返却 | second Born 向けに緩和・散乱診断を追加 |
| 診断量 | 完了 | HFB 収束履歴、stationarity、`two_time_grid_shape`、prototype の iteration/residual/memory/collision/contour/history-order/保存則残差に加え、`second_born_reference` の explicit self-energy / equation residual / GKBA reconstruction / thermal / mixed contour diagnostics を保存 | larger-system row と連動した追加可視化を検討 |
| frontend UI | 部分完了 | 設定入力、solver 切替、pairing channel / seed、run 一覧、polling、診断量、時系列プロット、KBE self-energy / adaptive / thermal branch 入力、retarded / lesser slice inspector、Run Log、top-level navigation shell、preset library、baseline / failure / validation framing、および local FFT preview を実装済みで、`Single Job` / `Compare Jobs` / `Parameter Sweep` を page-level surface として整理した。さらに 2026-03-18 時点で、docs 的な説明 panel を frontend から外し、`Workbench Pages` navigation を page 上部へ移し、Single Job は left sidebar に preset + config stack と run registry rail を置き、main canvas では validation + baseline/failure framing の summary band、observable-first の primary evidence path、real-time / thermal / mixed contour の切替式 advanced surface、および sticky diagnostics / artifact support rail を読む構成へ再整理した。`Compare Jobs` / `Parameter Sweep` は left rail の planning controls と main planning panel に絞り、説明的な context column は置かない構成へ戻した。加えて preset library に Higgs demo quick start を追加し、`Stage Demo` / `Launch Demo` で provisional な `kbe_hfb + hfb + bond_d` long-window Gaussian pulse preset を流し、`pairing_d` を主読 observable として priming できるようにし、local FFT preview は pairing 系で `magnitude` を既定に選び mean-subtracted preview を返すようにした。さらに `Compare Jobs` は left rail に variant / baseline / `comparison_kind` framing と active variant 編集導線を置き、main 冒頭に summary table、その下に planning state / reserved result stack / empty state を置く summary-first design surface へ整理した。2026-03-19 時点で、チャートを custom SVG から Plotly インタラクティブプロットへ移行し、ConfigPanel を CollapsibleSection で折り畳み式に改善し、`Parameter Sweep` に SweepRailPanel（sweep 軸定義・parameter_kind 推定・値範囲・baseline 値・fixed axes）を追加し、全 surface の sidebar 最下部に sticky launch/cancel action bar を追加し、OpenAPI 再生成後の stricter nested config 型に追従するよう frontend type usage を整理した。さらに `studies` / `decision-notes` / `evidence-bundles` の client 関数・`useResearchArtifacts` hook・`ResearchArtifactsPanel` の実動 surface 接続（linked study 表示・study selector・run notes 一覧・note 作成フォーム・evidence bundles 読み取り・study 作成フォーム）を追加し、`SingleJobPage` と `App` の両面で有効にした。2026-03-20 時点で backend には `job group` / `sweep` / `derived analysis artifact` API が入り、frontend はこれらへ接続可能な下地を得たが、actual surface 接続と URL deep link は未実装である | `job group` / `sweep` / `derived analysis artifact` の actual surface 接続と URL deep link を拡張する |
| テスト | 部分完了 | KBE second Born の HFB 極限回帰、full-contour/adaptive/thermal self-consistency 回帰、Green / thermal / mixed branch 部分取得 API、Phase E schema 回帰、2x2 exact diagonalization benchmark、非相互作用 `\Delta t` 収束、Phase 1 continuity residual regression、short-window prototype / reference benchmark、thermal branch 比較、adaptive tolerance 比較、memory window dependence row、`save_every` 付き Green / mixed 保存縮約回帰、pytest marker による validation 層の分類に加えて、experiment registry workflow として `study` / `job group` / `sweep` / `derived analysis artifact` の API 回帰および parent artifact state aggregation 回帰を追加 | E2E、プロセスジョブ、cancel、保存データ回帰の追加 |
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

### 3.1 frontend は P1 shell に着手し、backend も compare / sweep resource を持ったが actual launch surface は未接続

- frontend は `Single Job` / `Compare Jobs` / `Parameter Sweep` の top-level navigation shell、preset library、baseline / failure / validation framingを持つ workbench 骨格へ着手し、single-job と compare / sweep を page-level surface として分離した。
- 2026-03-18 の layout refresh では、docs 的な説明 panel を frontend から外し、Single Job を command deck / validation scope / evidence canvas に、Compare / Sweep を left rail controls + main planning panel に再編した。
- backend には `job group` / `sweep` / `derived analysis artifact` API が入り、child run lineage と parent state aggregation を保持できるようになった。
- ただし `Compare Jobs` / `Parameter Sweep` は、これらの backend resource をまだ launch / fetch / re-read に接続していないため、現時点では planning placeholder に留まる。
- `Compare Jobs` については planning placeholder のままでも、left rail に active variant / baseline / comparison framing を置き、main 冒頭で summary table を先に読む summary-first design surface までは整理した。
- `Single Job` には FFT preview を追加したが、これは backend 保存の `derived analysis artifact` ではなく local preview である。
- `derived analysis artifact` の durable metadata / lineage は実装したが、FFT payload 生成と frontend 再取得面は引き続き未実装である。

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

- registry-backed compare / sweep / analysis metadata foundation を追加
  - `ExperimentRegistry` に `job_groups` / `job_group_runs` / `sweeps` / `sweep_runs` / `derived_analyses` table を追加し、run-child relation と parent artifact state aggregation を保持できるようにした
  - `backend/app/schemas/research.py` に `ComparisonKind` / `ParameterKind` / `ArtifactLifecycleState` / `JobGroup*` / `Sweep*` / `DerivedAnalysisArtifact*` schema を追加した
  - `/job-groups` / `/sweeps` / `/derived-analyses` API を追加し、`ExperimentRepository` 経由で child run の `group_id` / `sweep_id` metadata を storage と registry の両方へ同期するようにした
  - workflow test として `job group` / `sweep` / `derived analysis artifact` API 回帰、および parent artifact state aggregation 回帰を追加した
- `uv run python -m pytest backend/tests/test_experiment_registry.py backend/tests/test_api.py`
  - 18 件すべて成功
- `uv run python -m pytest backend/tests`
  - 62 件すべて成功
- `cd frontend && npm run generate:api`
  - OpenAPI schema / TypeScript 型を再生成
- `cd frontend && npm run build`
  - 既存 `frontend/dist/assets` が root-owned のため outDir cleanup で失敗
- `cd frontend && npm exec vite build -- --outDir dist-codex-check`
  - 一時 outDir では production build 成功

少なくとも現時点で、`job group` / `sweep` / `derived analysis artifact` の backend metadata / lineage / state aggregation は workflow regression と backend 全体 test で破綻していない。frontend 既定 outDir build は root-owned 生成物に阻まれたが、別 outDir build では API 追加後も bundling 自体は成立している。

---

## 次の優先作業

### 優先度 A

- `scipy` を入れた前提で、fixed-point mixing を Anderson / Broyden 系へ置き換える候補を評価する
- 2x2 exact diagonalization benchmark を longer-time / larger-window の reference regression へ広げる
- Phase 2-3 の `dt` 収束と continuity residual を validation-spec の gate として追加する

### 優先度 B

- `job group` / `sweep` / `derived analysis artifact` の backend metadata foundation を、launch / result payload / actual surface 接続へ広げる
- `studies` / `decision-notes` / `evidence-bundles` を frontend の actual surface と URL deep link に接続する（actual surface 接続は完了。URL deep link は未実装）
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
- `job group` / `sweep` / `derived analysis artifact` の launch / result / frontend surface がつながったか
- `study` / `decision note` / `evidence bundle` が frontend surface と deep link に接続されたか
- local FFT preview が backend 保存の derived analysis artifact へ置き換わったか
- compare / sweep placeholder が registry-backed artifact surface へ置き換わったか
- cancel が UI から操作でき、期待どおり止まるか
- プロセスモードと E2E の自動テストが追加されたか
