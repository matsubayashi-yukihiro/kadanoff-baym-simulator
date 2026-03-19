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

validated features:

- HFB limit regression
- short-window benchmark row
- adaptive / memory-window convergence row
- self-consistent thermal / mixed contour dressing
- reference full-contour diagnostics within equal-time GKBA scope
- prototype / reference path の docs 上の意味分離

not yet validated:

- full contour second Born を文献準拠 implementation として主張すること
- longer-time / larger-system benchmark
- 独立 benchmark との cross-check

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

明示的に除外するもの:

- API / frontend test の成功を physics validation に数えること
- `second_born` prototype を文献準拠 second Born と呼ぶこと
- `second_born_reference` を full two-time contour solver と同一視すること
- `validation_status=accepted/rejected` を physics validation label と同一視すること
- `evidence bundle` の存在を physics validation の根拠に数えること

---

## 5. 未保証項目と次の追加検証

次に優先する検証は以下である。

1. larger lattice と longer-time の stability / convergence row を追加する
2. paired state と source term を含む continuity diagnostics を整理する
3. process mode / cancel / E2E を workflow 層として補完する

この順序により、

- physics claim を支える test
- 開発動線を守る test

を混同せずに拡張できる。
