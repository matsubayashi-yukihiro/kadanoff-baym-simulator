# Backend Validation Spec

この文書は、backend solver 検証の正本である。  
役割は、`docs/theory.md` にある理論要求を
`どの自動テストと数値閾値を通れば、何を validated と呼べるか`
へ翻訳することにある。

- 物理仕様の正本: [theory.md](./theory.md)
- backend 修繕計画: [backend-remediation-plan.md](./backend-remediation-plan.md)
- 研究アプリ全体方針: [research-workbench-plan.md](./research-workbench-plan.md)
- 実装進捗: [progress.md](./progress.md)

この文書が扱うのは backend solver validation のみである。  
API / frontend / E2E の test は継続するが、physics validation の根拠には数えない。

---

## 1. 用語と判定ラベル

### `validated`

- 宣言したスコープが明確である
- 受け入れ基準が数値閾値で固定されている
- 受け入れ基準を支える自動テストが存在する
- docs / code / diagnostics の意味づけが一致している

### `partially validated`

- 重要な極限や拘束条件の自動テストはある
- ただし benchmark のスコープ、閾値、または未検証項目が残る

### `prototype only`

- コードパスと診断は存在する
- ただし文献準拠の physics claim を支えるには不十分である
- regression が通っても、それ自体を physics validation と呼ばない

### `not validated`

- 自動テストまたは受け入れ基準が未整備
- 現時点では研究上の主張に使わない

### 研究 workflow metadata との境界

`docs/research-workbench-plan.md` では、
研究運用のために `study`, `run_role`, `validation_status`, `comparison_kind`, `parameter_kind`, `evidence bundle`
を導入する。  
これらは workflow metadata であり、
本書の physics validation label を置き換えない。

最低限の整理:

- `study`
  - 研究問いと baseline を束ねる research campaign artifact
  - physics validation label そのものではない
- `run_role`
  - `baseline` / `candidate` / `control` / `numerical_check` などの研究文脈
  - solver path の validated 判定を意味しない
- `validation_status`
  - `unchecked` / `screening` / `accepted` / `rejected` などの study 局所の判断
  - `validated` / `partially validated` / `prototype only` / `not validated` と別物である
- `comparison_kind`
  - `physics_hypothesis` / `numerical_validation` / `regression` などの比較目的
  - physics claim の保証範囲は本書の phase gate で判断する
- `parameter_kind`
  - `physics` / `numerical` / `analysis` などの sweep 分類
  - numerical sweep を first-class に扱っても、それだけで validated label は上がらない
- `evidence bundle`
  - run / analysis / validation scope を束ねる証跡整理 artifact
  - それ自体は physics claim の自動承認機構ではない

---

## 2. テスト分類

backend solver validation は次の 4 層を主軸にする。

| 層 | pytest marker | 目的 | 現在の代表 suite |
| --- | --- | --- | --- |
| unit | `physics_unit` | schema / numerics / Hamiltonian / local self-energy の局所構造を固定する | `test_schema.py`, `test_numerics.py`, `test_hamiltonian.py`, `test_self_energy_second_born.py`, `test_benchmark_profiling.py` |
| invariant | `physics_invariant` | 保存則、Hermiticity、limit matching、equal-time consistency を固定する | `test_noninteracting_solver.py`, `test_tdhfb_solver.py`, `test_kbe_hfb_solver.py` |
| benchmark | `physics_benchmark` | exact benchmark と収束行で solver の物理的信頼性を評価する | `test_exact_diagonalization_benchmark.py` |
| workflow | `workflow` | API / run lifecycle / slice 取得など開発動線を守る | `test_api.py` |

運用上の原則:

- physics の validated 判定は `physics_unit` + `physics_invariant` + `physics_benchmark` で行う
- `workflow` は公開 API と開発動線の回帰であり、physics validation の根拠には含めない
- `workflow` には将来 `study` / `decision note` / `evidence bundle` の lifecycle が入っても、それ自体を physics validation の根拠には含めない
- まず小さい benchmark と保存則で正しさを固定し、その後に長時間・大規模化へ進む

実行例:

```bash
uv run python -m pytest backend/tests -m physics_unit
uv run python -m pytest backend/tests -m physics_invariant
uv run python -m pytest backend/tests -m physics_benchmark
```

---

## 3. Phase Gate Matrix

### Phase 1: Noninteracting One-Body Solver

現在の判定: `validated`  
ただし、保証範囲は現在の reference problem に限る。

| claim | observable / diagnostic | threshold | reference config | automated test |
| --- | --- | --- | --- | --- |
| 閉鎖系 no-drive で粒子数とエネルギーが保存される | `particle_number_drift`, `energy_drift`, `max_hermiticity_error` | `<1e-10`, `<1e-10`, `<1e-12` | `2x2`, periodic, `dt=0.1`, no drive | `backend/tests/test_noninteracting_solver.py::test_noninteracting_solver_conserves_particle_number_without_drive` |
| 外場仕事率とエネルギー変化が一致する | `max_energy_work_mismatch`, `final_energy_work_mismatch` | `<1e-4`, `<1e-5` | `2x2`, periodic, driven, `dt=0.01` | `backend/tests/test_noninteracting_solver.py::test_noninteracting_solver_tracks_energy_work_balance_under_drive` |
| ゲージ整合的 bond current が局所 continuity equation を満たす | `max_continuity_residual`, `final_continuity_residual` | `<1e-12`, `<1e-12` | `2x2`, open, driven, `dt=0.05` | `backend/tests/test_noninteracting_solver.py::test_noninteracting_solver_tracks_local_continuity_equation_under_drive` |
| exact benchmark に一致する | density / `current_x` / `current_y` max abs error | `<1e-12` | `2x2`, open, driven, `dt=0.05` | `backend/tests/test_exact_diagonalization_benchmark.py::test_exact_diagonalization_matches_noninteracting_solver_in_normal_limit` |
| `dt` を半減すると誤差が減少する | `current_x` error ratio | fine error `<` coarse error, かつ `<0.3 * coarse` | coarse `dt=0.1`, fine `dt=0.05` | `backend/tests/test_exact_diagonalization_benchmark.py::test_noninteracting_solver_shows_dt_convergence_against_exact_diagonalization_reference` |

validated features:

- 時間依存 one-body Hamiltonian の伝播
- gauge-consistent bond current
- continuity residual の自動監視
- energy-work balance
- 2x2 exact benchmark と `dt` 収束

not yet validated:

- 2x2 を超える系サイズでの exact benchmark
- longer-time での系統的収束表
- workflow test を除いた CLI / process mode の運用検証

### Phase 2: TDHFB / BdG

現在の判定: `partially validated`

| claim | observable / diagnostic | threshold | reference config | automated test |
| --- | --- | --- | --- | --- |
| paired stationary state を保持する | `hfb_converged`, `particle_number_drift`, `energy_drift` | `True`, `<1e-8`, `<1e-8` | `paired_config` | `backend/tests/test_tdhfb_solver.py::test_tdhfb_solver_emits_pairing_projections_and_preserves_stationary_state` |
| generalized density の構造拘束を保つ | idempotency residual, `max_generalized_hermiticity_error`, `max_density_bound_violation` | `<1e-10`, `==0.0`, `==0.0` | `paired_config` | `backend/tests/test_tdhfb_solver.py::test_tdhfb_preserves_generalized_density_constraints_over_time` |
| 非相互作用極限で exact one-body solver に戻る | density/current/energy/vector potential mismatch | `<1e-12` | `2x2`, periodic, driven, `U=V=0` | `backend/tests/test_tdhfb_solver.py::test_tdhfb_matches_exact_noninteracting_limit_under_drive` |
| source-free normal-state driven case で continuity equation を満たす | `max_continuity_residual`, `final_continuity_residual` | `<1e-11`, `<1e-11` | `2x2`, open, driven, `pairing_channel=none`, `U=-0.8` | `backend/tests/test_tdhfb_solver.py::test_tdhfb_tracks_local_continuity_equation_in_source_free_normal_state` |
| weak-coupling longer window で exact benchmark に近い | density / `current_x` / `current_y` max abs error | density `<1e-12`, `current_x <2e-3`, `current_y <1e-3` | `2x2`, open, weak interaction, `t_final=0.4` | `backend/tests/test_exact_diagonalization_benchmark.py::test_tdhfb_and_kbe_hfb_track_exact_diagonalization_on_longer_window_weak_interaction` |
| weak-coupling exact benchmark に対する `dt` row が改善する | `current_x` max abs error row | coarse `>` fine `>` finer, かつ finer `<0.25 * coarse` | `2x2`, open, weak interaction `U=-0.1`, `t_final=0.2` | `backend/tests/test_exact_diagonalization_benchmark.py::test_tdhfb_and_kbe_hfb_show_dt_convergence_against_longer_window_exact_reference` |

validated features:

- paired stationary state の回帰
- pairing observable の射影出力
- generalized density の構造保存
- 非相互作用極限への連続接続
- source-free normal-state scope の continuity residual
- weak-coupling exact benchmark の longer-window regression
- weak-coupling exact benchmark に対する `dt` row

not yet validated:

- paired interacting benchmark の longer-time 比較
- anomalous source term を含む局所 continuity diagnostics
- larger lattice / longer-time の stability row

### Phase 3: KBE + HFB

現在の判定: `partially validated`

| claim | observable / diagnostic | threshold | reference config | automated test |
| --- | --- | --- | --- | --- |
| equal-time 極限で TDHFB と一致する | `max_equal_time_tdhfb_mismatch`, `max_lesser_hermiticity_error`, `max_retarded_equal_time_error` | `<1e-10`, `<1e-10`, `<1e-10` | `paired_config` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables` |
| retarded causality を守る | `max_retarded_causality_error` | `==0.0` | `paired_config` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables` |
| 非相互作用極限で exact one-body solver に戻る | density/current/energy/vector potential mismatch | `<1e-12` | `2x2`, periodic, driven, `U=V=0` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_exact_noninteracting_limit_under_drive` |
| weak-coupling short window で exact benchmark に近い | density / current error | density `<1e-12`, current `<1e-3` | `2x2`, open, weak interaction, `t_final=0.2` | `backend/tests/test_exact_diagonalization_benchmark.py::test_tdhfb_and_kbe_hfb_track_exact_diagonalization_for_short_time_weak_interaction` |
| source-free HFB mode で continuity equation を満たす | `max_continuity_residual`, `final_continuity_residual` | `<1e-11`, `<1e-11` | `2x2`, open, driven, `pairing_channel=none`, `self_energy=hfb`, `U=-0.8` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_tracks_local_continuity_equation_in_source_free_normal_state` |
| weak-coupling longer window で exact benchmark に近い | density / `current_x` / `current_y` max abs error | density `<1e-12`, `current_x <2e-3`, `current_y <1e-3` | `2x2`, open, weak interaction, `t_final=0.4`, `self_energy=hfb` | `backend/tests/test_exact_diagonalization_benchmark.py::test_tdhfb_and_kbe_hfb_track_exact_diagonalization_on_longer_window_weak_interaction` |
| weak-coupling exact benchmark に対する `dt` row が改善する | `current_x` max abs error row | coarse `>` fine `>` finer, かつ finer `<0.25 * coarse` | `2x2`, open, weak interaction `U=-0.1`, `t_final=0.2`, `self_energy=hfb` | `backend/tests/test_exact_diagonalization_benchmark.py::test_tdhfb_and_kbe_hfb_show_dt_convergence_against_longer_window_exact_reference` |

validated features:

- equal-time TDHFB matching
- retarded / lesser の拘束条件
- 非相互作用極限
- short-window weak-coupling benchmark
- source-free HFB mode の continuity residual
- weak-coupling exact benchmark の longer-window regression
- weak-coupling exact benchmark に対する `dt` row

not yet validated:

- self-energy=`hfb` を超える相関 path の continuity residual
- paired interacting benchmark の longer-time 比較
- larger lattice / longer-time benchmark

### Phase 4: KBE + second Born

現在の判定:

- `second_born`: `prototype only`
- `second_born_reference`: `validated` within equal-time GKBA contour-dressed scope

| claim | observable / diagnostic | threshold | reference config | automated test |
| --- | --- | --- | --- | --- |
| `second_born` は `U=0` で HFB limit に戻る | observable mismatch, `max_second_born_memory_norm` | observable mismatch `<1e-12`, memory norm `==0.0` | `2x2`, periodic, driven, `U=0` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reduces_to_hfb_when_onsite_u_zero` |
| `second_born_reference` は `U=0` で HFB limit に戻る | observable mismatch, `second_born_reference_implementation` | observable mismatch `<1e-12`, implementation `True` | `2x2`, periodic, driven, `U=0` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero` |
| prototype path の stationary conservation residual が監視される | `max_particle_conservation_residual`, `max_energy_work_mismatch` | `<1e-10`, `<1e-8` | `paired_config`, prototype mode | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_tracks_conservation_residuals_for_stationary_state` |
| prototype path は short-window exact benchmark に比較可能である | density / current error | density `<1e-6`, current `<1e-3` | `2x2`, open, `t_final=0.2` | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_prototype_remains_comparable_to_exact_benchmark_on_short_window` |
| reference path は short-window exact benchmark に比較可能である | density / current error | density `<5e-4`, current `<1e-3` | `2x2`, open, `t_final=0.2` | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_reference_remains_comparable_to_exact_benchmark_on_short_window` |
| adaptive tolerance を tightening すると final error が改善する | benchmark final abs error | tight `<` loose | `2x2`, short window | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_adaptive_tolerance_improves_final_error_against_fine_fixed_reference` |
| reference path でも adaptive tolerance を tightening すると final error が改善する | benchmark final abs error | tight `<` loose | `2x2`, short window, reference mode | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_reference_adaptive_tolerance_improves_final_error_against_fine_fixed_reference` |
| memory-window row が full-memory へ収束する | convergence row | full-memory row error `==0.0` | `2x2`, short window | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_memory_window_rows_converge_to_full_memory_reference` |
| reference thermal / mixed contour dressing は factorized seed から分離される | `thermal_branch_factorized_difference`, `mixed_branch_factorized_difference`, implementation flags | `>0.0`, `>0.0`, `True` | `2x2`, periodic, finite temperature | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_builds_correlated_thermal_and_mixed_branches` |
| reference full-contour path は finite-temperature short-window benchmark に比較可能である | density / current error | `<5e-3` | `2x2`, periodic, finite temperature | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_reference_thermal_branch_remains_close_to_exact_density_benchmark` |
| reference full-contour path は adaptive 実行でも fixed-grid 参照と整合する | final density / energy mismatch | density `<2e-3`, energy `<5e-3` | `2x2`, periodic, finite temperature | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_supports_adaptive_history_against_fixed_reference` |
| HFB-seeded source-free reference path では initial slip が可視化される | `max_stationarity_residual`, `max_density_initial_slip`, `max_energy_initial_slip` | `>1e-3`, `>1e-4`, `>1e-3` | `2x2`, periodic, finite temperature, `equilibrium.method=hfb` | `backend/tests/test_kbe_stationarity.py::test_second_born_reference_hfb_seed_source_free_shows_initial_slip` |
| correlated contour dressing は factorized seed と異なる source-free stationarity history を与える | `thermal_branch_factorized_difference`, `mixed_branch_factorized_difference`, stationarity/slip history | contour differences `>0.0`, history differs | `2x2`, periodic, finite temperature, `equilibrium.method=hfb` | `backend/tests/test_kbe_stationarity.py::test_second_born_reference_correlated_contour_changes_source_free_stationarity_metrics` |
| approximation-consistent reference equilibrium seed は HFB seed より source-free slip を下げる regression case を持つ | `max_stationarity_residual`, `max_density_initial_slip`, `max_energy_initial_slip`, `particle_number_drift` | reference seed `<` HFB seed | `2x2`, periodic, finite temperature, `dt=0.1` | `backend/tests/test_kbe_stationarity.py::test_second_born_reference_equilibrium_seed_is_more_stationary_than_hfb_seed` |

validated features:

- HFB limit regression
- short-window benchmark row
- adaptive / memory-window convergence row
- self-consistent thermal / mixed contour dressing
- reference full-contour diagnostics within equal-time GKBA scope
- prototype / reference path の docs 上の意味分離
- source-free stationarity mismatch の regression exposure
- approximation-aware equilibrium method dispatch

not yet validated:

- full contour second Born を文献準拠 implementation として主張すること
- longer-time / larger-system benchmark
- 独立 benchmark との cross-check
- HFB-seeded source-free stationary baseline を physics validation claim に含めること
- mismatch exposure regression をもって validated label を昇格させること

注記:

- `equilibrium.method=hfb` の source-free slip 検出は、initialization mismatch を露出する regression であり、
  `second_born_reference` の physics validation 昇格根拠ではない。
- source-free stationary claim を validation に含めるのは、
  `equilibrium.method=second_born_reference` の回帰と benchmark row が十分に拡張された後とする。
- 収束判定には2種類が存在する:
  - `strict`: `last_residual <= tolerance` かつ `last_equation_residual <= tolerance / dt`
  - `relaxed_5x`: 上記 strict 判定を満たさないが、`5x` 緩和基準（residual/equation residual）で収束
  - diagnostics には `second_born_convergence_criterion`（`"strict"` / `"relaxed_5x"`）を保存する。
- run state 昇格は `second_born_converged` のみではなく、以下を合成して判定する:
  - `second_born_convergence_criterion=="strict"`
  - `thermal_branch_enabled=True` のとき `thermal_branch_converged=True`
  - `mixed_components_included=True` のとき `mixed_branch_converged=True`
  - いずれか未達なら `succeeded_with_warnings` に昇格する。

---

### Phase 5A: k-space native solver representation

現在の判定:

- `noninteracting(representation=k_space)`: `validated`
- `tdhfb(representation=k_space)`: `partially validated`
- `kbe_hfb(self_energy=hfb, representation=k_space)`: `partially validated`
- `kbe_hfb(self_energy=second_born_reference, representation=k_space)`: `partially validated`

この phase は `k-space / tr-ARPES` derived analysis とは別であり、
solver の内部表現を `real_space` から `k_space` に切り替えても、
既存 observables / diagnostics / Green-function contract を保てるかを検証する話である。

現行 backend 実装では、
`representation=k_space` は periodic square lattice に限定し、
`noninteracting`、`tdhfb`、`kbe_hfb(self_energy=hfb)` に加えて、
`kbe_hfb(self_energy=second_born_reference)` を対象にする。
`second_born` heuristic prototype は未対応である。

`second_born_reference(representation=k_space)` は
correlated native extension の初期公開として扱う。  
ただし判定は `validated` ではなく
`partially validated` に留める。  
公開スコープの前提は次の通り:

- periodic square lattice に限定する
- existing run artifact contract を維持する
- `k-space / tr-ARPES` derived analysis source として再利用可能にする
- reduced-Nambu equal-time GKBA contour-dressed scope を維持し、
  full two-time contour second Born と同一視しない

| claim | observable / diagnostic | threshold | reference config | automated test |
| --- | --- | --- | --- | --- |
| periodic one-body dynamics は `real_space` / `k_space` で同値に実行できる | `density/current/energy/vector_potential` parity, `max_energy_work_mismatch`, `max_continuity_residual` | existing real-space row と同等 | `noninteracting`, periodic 2x2 / 4x4 | `backend/tests/test_noninteracting_solver.py` |
| equal-time HFB dynamics は basis mode を変えても observables parity を保つ | `density/energy/pairing/pairing_s/pairing_d` parity | `abs <= 1e-8` | `tdhfb`, periodic paired 4x4 scope, short and moderate longer windows | `backend/tests/test_tdhfb_solver.py` |
| HFB two-time path は basis mode を変えても Green-function contract を保つ | equal-time parity, `max_lesser_hermiticity_error`, `max_retarded_equal_time_error` | `abs <= 1e-8` | `kbe_hfb(self_energy=hfb)`, periodic paired 4x4 scope, short and moderate longer windows | `backend/tests/test_kbe_hfb_solver.py` |
| paired 4x4 longer window でも basis parity を保つ | `density/energy/pairing/pairing_s/pairing_d` parity | `abs <= 1e-8` | `tdhfb`, `kbe_hfb(self_energy=hfb)`, periodic paired 4x4, driven, `t_final=0.4` | `backend/tests/test_tdhfb_solver.py::test_tdhfb_k_space_representation_matches_real_space_on_longer_window`, `backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_k_space_representation_matches_real_space_on_longer_window` |
| paired interacting larger-lattice row でも basis parity を保つ | `density/energy/pairing/pairing_s/pairing_d` parity | `abs <= 1e-8` | `tdhfb`, periodic paired 6x6, driven, `t_final=0.3`; `kbe_hfb(self_energy=hfb)`, periodic paired 5x5, driven, `t_final=0.3` | `backend/tests/test_tdhfb_solver.py::test_tdhfb_k_space_representation_matches_real_space_on_larger_lattice`, `backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_k_space_representation_matches_real_space_on_larger_lattice` |
| native k-space block path は supported scope で real-space parity を保ち、条件外は full-matrix fallback できる | `k_space_path_mode`, parity (`density/energy/current_x/current_y`) | mode=`block_diagonal`, parity `abs<=1e-8` | `tdhfb`, periodic, finite temperature, `pairing_channel=none`, `nearest_neighbor_v=0` | `backend/tests/test_kspace_native_path.py::test_tdhfb_kspace_native_block_path_matches_real_space_for_supported_scope` |
| k-space block path の propagation kernel は forced full-matrix baseline より高速である | median wall-time ratio (`full/block`) | `>=2.0` | `tdhfb 6x6`、`kbe_hfb(self_energy=second_born_reference) 6x6` | `backend/tests/test_kspace_native_path.py::test_kspace_block_path_is_at_least_twice_as_fast_as_forced_full_matrix_path`, `backend/tests/test_kspace_native_path.py::test_kspace_block_path_is_at_least_twice_as_fast_for_second_born_reference_propagation_kernel` |
| `second_born_reference` は `U=0` で `k_space` basis でも HFB limit に戻る | observable parity, `max_second_born_memory_norm`, implementation flag | observable mismatch `<1e-12`, memory norm `==0.0`, implementation `True` | `kbe_hfb(self_energy=second_born_reference)`, periodic 2x2, driven, `U=0` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_reduces_to_hfb_when_onsite_u_zero` |
| `second_born_reference` full-contour path は basis mode を変えても observables parity と Green-function contract を保つ | `density/energy/pairing/pairing_s/pairing_d` parity, `max_lesser_hermiticity_error`, `max_retarded_equal_time_error` | parity `abs <= 1e-8`, diagnostics `<1e-8` | `kbe_hfb(self_energy=second_born_reference)`, periodic paired 4x4, driven, finite temperature, `t_final=0.2` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_matches_real_space` |
| `second_born_reference` larger-system / longer-window row でも basis parity と Green-function contract を保つ | `density/energy/pairing/pairing_s/pairing_d` parity, `max_lesser_hermiticity_error`, `max_retarded_equal_time_error` | parity `abs <= 1e-8`, diagnostics `<1e-8` | `kbe_hfb(self_energy=second_born_reference)`, periodic paired 3x3, driven, finite temperature, `t_final=0.3` | `backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_matches_real_space_on_larger_system_longer_window` |
| `second_born_reference` periodic finite-temperature short window は `k_space` basis でも exact benchmark に比較可能である | density / `current_x` / `current_y` max abs error | `<5e-3` | `kbe_hfb(self_energy=second_born_reference)`, periodic 2x2, finite temperature | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_reference_k_space_thermal_branch_remains_close_to_exact_density_benchmark` |
| `second_born_reference` periodic finite-temperature longer window でも exact benchmark と同程度に比較可能である | density / `current_x` / `current_y` max abs error | `<5e-3` | `kbe_hfb(self_energy=second_born_reference)`, periodic 2x2, finite temperature, `t_final=0.3` | `backend/tests/test_exact_diagonalization_benchmark.py::test_second_born_reference_k_space_thermal_branch_longer_window_remains_close_to_exact_density_benchmark` |
| `second_born_reference` `k_space` run は既存 artifact contract を保つ | run detail diagnostics, Green-function catalog | workflow regression | `kbe_hfb(self_energy=second_born_reference)`, periodic 2x2, `representation=k_space` | `backend/tests/test_api.py::test_api_accepts_k_space_second_born_reference_runs_and_keeps_existing_artifact_contracts` |

validated features:

- periodic `noninteracting` の `k_space` parity

partially validated features:

- periodic `tdhfb` の `k_space` parity
- periodic `kbe_hfb(self_energy=hfb)` の `k_space` parity
- periodic paired larger-lattice / longer-time parity (`4x4` + `5x5/6x6`)
- periodic `kbe_hfb(self_energy=second_born_reference)` の HFB-limit / parity / benchmark / workflow gate (`2x2/3x3`, short/longer windows)

not yet validated:

- frontend からの representation 切替 surface

conditions before considering `validated`:

- 追加の independent benchmark または cross-check を蓄積する
- derived-analysis source consistency を threshold 付きで固定する

---

### Phase 5: k-space / tr-ARPES derived analysis

現在の判定: `partially validated`

この phase は backend solver を k-space native に置き換える話ではなく、
既存 real-space / Green-function run artifact から派生解析を作る話である。
現行 backend 実装では、two-time lesser Green 関数を保存する
periodic `kbe_hfb(self_energy=hfb)` run と periodic `tdhfb` run を
mean-field source として扱い、後続で `second_born_reference` を
correlated extension の source にする。

運用上の境界:

- P6 では derived analysis contract の threshold / benchmark row を先に固定する
- `second_born_reference` source 対応は P7 相当の correlated native extension / validation expansion と連動して進める
- derived analysis と native `representation=k_space` solver path を同一能力として扱わない

| claim | observable / diagnostic | threshold | reference config | automated test |
| --- | --- | --- | --- | --- |
| k-path occupied spectrum は `Gamma-X-M-Gamma` path を落とさず再構成できる | `k_path_coverage`, `spectral_symmetry_error` | `== 4`, `<1e-10` | synthetic periodic 4x4 Gamma mode on `gamma_x_m_gamma` path | `backend/tests/test_kspace_spectral_analysis.py::test_k_path_preview_covers_gamma_x_m_gamma_with_small_endpoint_symmetry_error` |
| occupied spectrum の occupied-weight 分布は inversion-symmetric mode で対称性と正規化分布を保つ | `spectral_symmetry_error`, `sum_rule_residual` | `<1e-10`, `<5e-2` | synthetic periodic 4x4 `(+k_x,-k_x)` equal-weight mode on discrete BZ | `backend/tests/test_kspace_spectral_analysis.py::test_k_grid_preview_preserves_inversion_symmetric_occupied_weight_distribution` |
| minimal tr-ARPES intensity は narrow probe の方が off-center suppression を強く保つ | `delay_axis_coverage`, `probe_width_resolution_tradeoff` | `>0.99`, `>0.05` | synthetic periodic 2x2 single-packet Gamma mode with matched vs delayed probe centers | `backend/tests/test_tr_arpes_analysis.py::test_trarpes_probe_width_tradeoff_preserves_delay_resolution` |
| run-derived occupied spectrum は source run が `real_space` / `k_space` でも同一 contract を保つ | `source_mode_consistency`, endpoint symmetry, non-negativity | parity `<1e-12`, symmetry `<1e-12`, intensity/weight `>=-1e-14` | `kbe_hfb(self_energy=hfb)`, periodic 2x2, driven | `backend/tests/test_kspace_spectral_analysis.py::test_run_derived_k_path_preview_matches_between_real_space_and_k_space_sources` |
| run-derived minimal tr-ARPES は source run が `real_space` / `k_space` でも同一 contract を保つ | `source_mode_consistency`, non-negativity | parity `<1e-12`, intensity/weight `>=-1e-14` | `kbe_hfb(self_energy=hfb)`, periodic 2x2, driven | `backend/tests/test_tr_arpes_analysis.py::test_run_derived_trarpes_preview_matches_between_real_space_and_k_space_sources` |
| mean-field `tdhfb` direct source でも run-derived occupied spectrum / minimal tr-ARPES が source mode consistency を保つ | `source_mode_consistency`, endpoint symmetry, non-negativity | parity `<1e-12`, symmetry `<1e-12`, intensity/weight `>=-1e-14` | `tdhfb`, periodic 2x2, driven | `backend/tests/test_kspace_spectral_analysis.py::test_run_derived_k_path_preview_matches_between_real_space_and_k_space_tdhfb_sources`, `backend/tests/test_tr_arpes_analysis.py::test_run_derived_trarpes_preview_matches_between_real_space_and_k_space_tdhfb_sources` |
| correlated real-space source でも同一 analysis contract を再利用できる | `source_self_energy`, payload shape, finite non-negative intensity | workflow regression | `second_born_reference` real-space run source | `backend/tests/test_api.py::test_api_launches_k_space_preview_from_second_born_reference_source` |
| correlated source の `real_space` / native `k_space` でも同一 analysis contract を保つ | `source_mode_consistency`, endpoint symmetry, non-negativity | parity `<1e-12`, symmetry `<1e-12`, intensity/weight `>=-1e-14` | `kbe_hfb(self_energy=second_born_reference)`, periodic 2x2, driven | `backend/tests/test_kspace_spectral_analysis.py::test_run_derived_k_path_preview_matches_between_real_space_and_k_space_second_born_reference_sources`, `backend/tests/test_tr_arpes_analysis.py::test_run_derived_trarpes_preview_matches_between_real_space_and_k_space_second_born_reference_sources` |
| compare / sweep artifact でも correlated source consistency と analysis override を保つ | compare parity, heatmap delay override, payload non-negativity | parity `<1e-12`, `probe_centers==values`, intensity `>=0.0` | `second_born_reference` mixed real/k source job-group + analysis sweep | `backend/tests/test_api.py::test_api_launches_second_born_reference_k_space_compare_and_heatmap_with_analysis_override` |
| compare / sweep artifact でも `tdhfb` direct source を再利用できる | payload shape, analysis override, non-negativity | `probe_centers==values`, intensity `>=0.0` | `tdhfb` mixed real/k source job-group + analysis sweep | `backend/tests/test_api.py::test_api_launches_k_space_compare_and_trarpes_heatmap_from_tdhfb_sources` |

validated features:

- synthetic k-path coverage / endpoint symmetry row
- synthetic inversion-symmetric occupied-weight row
- synthetic probe-width / delay tradeoff row
- run-derived `real_space` / `k_space` source cross-check
- `tdhfb` direct source (`real_space` / `k_space`) cross-check
- `second_born_reference` real-space run source の analysis contract reuse
- `second_born_reference` source の `real_space` / native `k_space` cross-check
- compare / sweep payload regression (`second_born_reference` source, energy-grid variant, analysis sweep override)

not yet validated:

- frontend compare / sweep での k-space surface 表示統合

---

## 4. 現在の保証範囲

| 対象 | 現在の判定 | 根拠 |
| --- | --- | --- |
| noninteracting one-body solver | `validated` | invariant + exact benchmark + `dt` 収束 + continuity residual |
| TDHFB / BdG equal-time dynamics | `partially validated` | stationary paired state, structure constraints, noninteracting limit, source-free continuity residual, weak-coupling exact benchmark row |
| KBE + HFB equal-time path | `partially validated` | TDHFB equal-time match, Green 関数拘束, source-free continuity residual, weak-coupling exact benchmark row |
| heuristic `second_born` path | `prototype only` | regression と diagnostics はあるが文献準拠 full second Born ではない |
| `second_born_reference` equal-time GKBA contour-dressed path | `validated` | HFB limit, short-window benchmark, adaptive row, self-consistent thermal / mixed branch dressing |
| full contour second Born | `not validated` | 未公開 |
| reference thermal / mixed contour dressing | `validated` | factorized 差分診断と exact benchmark を含む self-consistent branch 回帰を追加済み |
| `noninteracting` `k_space` representation | `validated` | periodic parity + energy-work row |
| `tdhfb` / `kbe_hfb(self_energy=hfb)` `k_space` representation | `partially validated` | periodic 4x4 parity と moderate/longer-window parityに加え、paired larger-lattice row (`tdhfb`: 6x6, `kbe_hfb`: 5x5, `t_final=0.3`) を追加したが、frontend representation surface は未了 |
| `second_born_reference` `k_space` representation | `partially validated` | HFB limit、real/k parity、periodic finite-temperature exact benchmark（short/longer window）、run artifact workflow regression、3x3 longer-window parity row を追加したが、`validated` 昇格に向けた独立 cross-check の蓄積は継続中 |
| k-space / tr-ARPES derived analysis | `partially validated` | synthetic benchmark row、run-derived `real_space` / `k_space` source cross-check、`second_born_reference` real/native source cross-check、compare/sweep payload regression（energy-grid variant、analysis sweep override）を固定したが、frontend surface integration は未了 |

明示的に除外するもの:

- API / frontend test の成功を physics validation に数えること
- `second_born` prototype を文献準拠 second Born と呼ぶこと
- `second_born_reference` を full two-time contour solver と同一視すること
- `validation_status=accepted/rejected` を physics validation label と同一視すること
- `evidence bundle` の存在を physics validation の根拠に数えること

---

## 5. 未保証項目と次の追加検証

次に優先する検証は以下である。

1. `second_born_reference(representation=k_space)` の独立 cross-check を追加蓄積し、`validated` 判定への証跡を増やす
2. frontend compare / sweep で k-space surface を表示統合し、workflow E2E で固定する
3. paired state と source term を含む continuity diagnostics を整理する
4. process mode / cancel / E2E を workflow 層として補完する

この順序により、

- physics claim を支える test
- 開発動線を守る test

---

## 6. RunState 意味境界

run の `state` フィールドは、physics validation label とは独立した run lifecycle 状態を表す。

| RunState | 意味 | 結果アクセス |
| --- | --- | --- |
| `succeeded` | 計算が正常完了し、すべての収束診断が基準を満たした | 可 |
| `succeeded_with_warnings` | 計算は完了し結果は保存済みだが、収束診断が基準未達（`second_born_converged=False` または strict/thermal/mixed 条件未達）| 可（要注意） |
| `failed` | 例外が発生し計算が中断した | 不可 |

### 昇格ルール

- `second_born_converged=False` の run は `succeeded_with_warnings` に昇格する。
- `second_born_convergence_criterion!="strict"` の run は `succeeded_with_warnings` に昇格する。
- `thermal_branch_enabled=True` かつ `thermal_branch_converged=False` の run は `succeeded_with_warnings` に昇格する。
- `mixed_components_included=True` かつ `mixed_branch_converged=False` の run は `succeeded_with_warnings` に昇格する。
- `second_born_converged` フィールドが存在しない solver（noninteracting, tdhfb 等）は `True` と扱い、`succeeded` になる。
- `succeeded_with_warnings` は研究上の参照は可能だが、validated claim の根拠には使わない。
- `job group` / `sweep` の parent artifact lifecycle 集約では、child run の `succeeded_with_warnings` は `succeeded` と同等に扱う（workflow state 互換のため）。

### convergence_criterion の読み方

diagnostics の `second_born_convergence_criterion` フィールドが収束判定の種別を示す。

- `"strict"`: `last_residual <= tolerance` かつ `last_equation_residual <= tolerance/dt` で収束
- `"relaxed_5x"`: 上記 strict 判定を満たさず、`5x` 緩和基準で収束（少なくとも 1 timestep で適用）

`second_born_converged=True` でも `convergence_criterion="relaxed_5x"` なら、tolerance 超過の step が存在することに注意する。

### fallback diagnostics の読み方

second Born 系の diagnostics には、fallback を明示する additive key を持たせる。

- `second_born_applied_fallback`
- `thermal_branch_applied_fallback`
- `mixed_branch_applied_fallback`

値は `None` または固定 reason 文字列（例: `hfb_limit_single_sample`, `hfb_limit_onsite_u_zero`, `second_born_mode_not_selected`）を取る。
`second_born` / `second_born_reference` を選択している run で fallback が発生した場合は backend logger に warning を出し、
run の diagnostics と worker log の双方で事後追跡できるようにする。

を混同せずに拡張できる。
