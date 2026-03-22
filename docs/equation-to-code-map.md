# 式とコードの対応表

このファイルは、`docs/theory.md` に出てくる理論量が、実際にどの module / function / diagnostics に対応しているかを引くための表である。

- 理論仕様の正本: [theory.md](./theory.md)
- 用語集: [glossary.md](./glossary.md)
- 文献索引: [literature-index.md](./literature-index.md)

---

## 使い方

- 理論側からコードを探すときは、このファイルで quantity 名から module を引く。
- コード側から理論的意味を確認したいときは、このファイル経由で `theory.md` と文献索引へ戻る。
- ここでは「主要な対応」だけを管理し、全関数一覧にはしない。

---

## 1. 基本設定と一体部分

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| 格子 `i,j`、bond、境界条件 | `backend/app/solvers/lattice.py` | `SquareLattice`, `Bond`, `build_square_lattice` |
| 一体 Hamiltonian `H_el^{(1)}(t)` | `backend/app/solvers/hamiltonian.py` | `build_one_body_hamiltonian` |
| 外場ベクトルポテンシャル `A(t)` | `backend/app/solvers/hamiltonian.py` | `vector_potential`, `vector_potential_derivative` |
| 時間格子 `t_n` | `backend/app/schemas/simulation.py` | `TimeGridConfig.time_points`, adaptive は `tdhfb.py` 側で生成 |
| 保存対象の sample index | `backend/app/solvers/nambu.py` | `saved_step_indices`, `saved_step_indices_from_count` |

---

## 2. Nambu / BdG / 一般化密度行列

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| Nambu 行列 | `backend/app/solvers/nambu.py` | `ComplexMatrix` を共通型として使う |
| 一般化密度行列 `\mathcal R` | `backend/app/solvers/nambu.py` | `_assemble_generalized_density`, `extract_density_blocks` |
| normal density | `backend/app/solvers/nambu.py` | `extract_density_blocks` の第 1 戻り値 |
| pairing tensor | `backend/app/solvers/nambu.py` | `extract_density_blocks` の第 2 戻り値 |
| Hartree potential | `backend/app/solvers/nambu.py` | `compute_hartree_potential` |
| pairing field `\Delta` | `backend/app/solvers/nambu.py` | `compute_pairing_field` |
| BdG Hamiltonian | `backend/app/solvers/nambu.py` | `assemble_bdg_hamiltonian`, `build_bdg_hamiltonian` |
| thermal generalized density | `backend/app/solvers/nambu.py` | `thermal_generalized_density` |
| BdG propagator | `backend/app/solvers/nambu.py` | `propagator_from_hamiltonian`, `propagate_generalized_density` |
| pairing 射影 | `backend/app/solvers/nambu.py` | `pairing_projections`, `PairingProjections` |

---

## 2.1 `k` 空間表示とフーリエ変換規約（theory §7.3.1 / §8.2.1 / §14.3.1）

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| 離散フーリエ基底 `c_i \leftrightarrow c_k` | `backend/app/solvers/representation.py` | `build_momentum_space_context`, `site_to_momentum_matrix`, `momentum_to_site_matrix` |
| Nambu 基底変換（site/k） | `backend/app/solvers/representation.py` | `site_to_momentum_nambu`, `momentum_to_site_nambu` |
| `k` ブロック行列化 / 逆変換 | `backend/app/solvers/representation.py` | `nambu_from_k_blocks`, `extract_k_blocks_from_k_nambu_matrix`, `extract_k_blocks_from_generalized_density` |
| `\xi_k(t)`（一体項の `k` 対角成分） | `backend/app/solvers/hamiltonian.py` | `build_one_body_momentum_diagonal` |
| `\mathbf H_{\mathrm{BdG}}(k,t)` ブロック構築 | `backend/app/solvers/nambu.py` | `build_kspace_bdg_blocks` |
| `\rho_k(t)` block 伝播 | `backend/app/solvers/nambu.py` | `propagate_kspace_density_blocks`, `enforce_kspace_density_block_constraints` |
| `k` 空間時間発展（block / full fallback） | `backend/app/solvers/tdhfb.py` | `_propagate_generalized_densities_kspace`, `_resolve_kspace_path_mode`, `_advance_generalized_density_step_kspace_blocks` |

---

## 3. HFB / TDHFB

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| HFB 平衡自己無撞着解 | `backend/app/solvers/nambu.py` | `solve_hfb_equilibrium`, `HFBEquilibriumState` |
| `k_space` native HFB 平衡（条件付き） | `backend/app/solvers/nambu.py` | `_solve_hfb_equilibrium_kspace`, `_kspace_native_equilibrium_supported`, `solver_mode=hfb_kspace_native` |
| 化学ポテンシャル調整 | `backend/app/solvers/nambu.py` | `_solve_thermal_state_for_particle_target`, `_thermal_state_for_shift` |
| TDHFB 時間発展 | `backend/app/solvers/tdhfb.py` | `simulate_hfb_dynamics` |
| adaptive TDHFB time step | `backend/app/solvers/tdhfb.py` | `_adaptive_step_factor`, step-doubling |
| `k_space` block 伝播 path | `backend/app/solvers/tdhfb.py` | `_advance_generalized_density_step_kspace_blocks`, diagnostics `k_space_path_mode` |
| TDHFB observables | `backend/app/solvers/tdhfb.py` | `_build_observables`, `_complex_observable` |
| HFB self-energy の明示表現 | `backend/app/solvers/self_energy_hfb.py` | `build_hfb_self_energy`, `HFBSelfEnergy` |
| `second_born_reference` equilibrium seed | `backend/app/solvers/equilibrium_solvers.py` | `solve_second_born_reference_equilibrium`, `_reference_equilibrium_dt` |

---

## 4. Green 関数成分

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| 二時刻 Green 関数 container | `backend/app/solvers/green_functions.py` | `TwoTimeGreenFunctionContainer` |
| Matsubara branch container | `backend/app/solvers/green_functions.py` | `MatsubaraBranchContainer` |
| mixed branch container | `backend/app/solvers/green_functions.py` | `MixedBranchContainer` |
| `G^R`, `G^<` の構築 | `backend/app/solvers/green_functions.py` | `build_two_time_green_functions` |
| equal-time / Hermiticity / causality 診断 | `backend/app/solvers/green_functions.py` | `green_function_diagnostics` |
| API に返す Green 関数 data | `backend/app/solvers/base.py` | `TwoTimeGreenFunctionData`, `ThermalBranchGreenFunctionData`, `MixedGreenFunctionData` |
| Green 関数 API schema | `backend/app/schemas/green_functions.py` | catalog / slice response 群 |

---

## 5. KBE orchestration

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| `kbe_hfb` solver 全体 | `backend/app/solvers/kbe_hfb.py` | `solve` が orchestration 層 |
| mode 分岐 `hfb/second_born/second_born_reference` | `backend/app/solvers/kbe_hfb.py` | `KBESelfEnergyMode` に従って分岐 |
| KBE observables / diagnostics 再計算 | `backend/app/solvers/kbe_hfb.py` | `_analyze_trajectory` |
| 保存則 diagnostics | `backend/app/solvers/kbe_hfb.py` | `_conservation_diagnostics` |
| external work 積分 | `backend/app/solvers/kbe_hfb.py` | `cumulative_trapezoid` を使用 |
| second Born 無効時の診断キー固定 | `backend/app/solvers/kbe_hfb.py` | `_disabled_second_born_diagnostics`（`second_born_convergence_criterion` など） |

---

## 6. Prototype second Born path

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| heuristic `second_born` | `backend/app/solvers/self_energy_second_born_prototype.py` | `apply_second_born_corrections` |
| prototype の dissipative collision | `backend/app/solvers/self_energy_second_born_prototype.py` | `dissipative_collision` |
| prototype Matsubara branch | `backend/app/solvers/self_energy_second_born_prototype.py` | `build_matsubara_branch` |
| prototype mixed branch | `backend/app/solvers/self_energy_second_born_prototype.py` | `build_factorized_mixed_branch`, `build_mixed_branch` |
| prototype diagnostics seed | `backend/app/solvers/self_energy_second_born_prototype.py` | `_base_second_born_diagnostics` |

読み方:
- ここは理論基準の second Born ではなく、legacy prototype である。
- docs 上では `second_born` と書くときに prototype / reference を必ず区別する。

---

## 7. Reference second Born path

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| reference mode 本体 | `backend/app/solvers/self_energy_second_born.py` | `apply_reference_second_born_corrections` |
| explicit local second Born self-energy | `backend/app/solvers/self_energy_second_born.py` | `_build_local_second_born_self_energy` |
| equal-time GKBA row data 再構成 | `backend/app/solvers/self_energy_second_born.py` | `_build_gkba_row_data` |
| reference `G^R`, `G^<` 再構成 | `backend/app/solvers/self_energy_second_born.py` | `build_reference_green_functions` |
| reference Matsubara branch | `backend/app/solvers/self_energy_second_born.py` | `build_matsubara_branch_reference` |
| reference mixed branch | `backend/app/solvers/self_energy_second_born.py` | `build_mixed_branch_reference` |
| reference diagnostics seed | `backend/app/solvers/self_energy_second_born.py` | `_base_second_born_diagnostics` |
| strict / relaxed 収束判定 | `backend/app/solvers/self_energy_second_born.py` | `second_born_convergence_criterion`, `second_born_equation_residual_history`, `max_second_born_equation_residual` |

重要:
- この path は `second_born_reference` mode に対応する。
- 現状の理論的スコープは `equal_time_gkba` を基底にした contour-dressed reference path であり、full two-time contour second Born そのものではない。

---

## 8. Contour / quadrature / numerical utilities

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| 履歴積分重み | `backend/app/solvers/contour.py` | `quadrature_weights`, `composite_simpson_weights`（2点ケースは台形則 `dt/2,dt/2`） |
| causal history rule | `backend/app/solvers/contour.py` | `causal_history_rule`, `CausalHistoryIntegrationRule` |
| 履歴平均 | `backend/app/solvers/contour.py` | `history_average_matrix`, `history_average_rank3`, `tau_average_matrix` |
| quasi-uniform 判定 | `backend/app/solvers/contour.py` | `is_quasi_uniform` |
| cumulative trapezoid | `backend/app/solvers/numerics.py` | `cumulative_trapezoid` |
| bracketed root solve | `backend/app/solvers/numerics.py` | `solve_bracketed_root` |
| linear mixing | `backend/app/solvers/numerics.py` | `linear_mix` |

---

## 9. 観測量と benchmark

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| 密度統計 | `backend/app/solvers/observables.py` | `particle_density_statistics` |
| 電流 | `backend/app/solvers/observables.py` | `bond_current`, `average_current` |
| エネルギー | `backend/app/solvers/nambu.py`, `backend/app/solvers/noninteracting.py` | `effective_energy`, `_expectation_value` |
| exact diagonalization benchmark | `backend/app/solvers/benchmarks/exact_diagonalization.py` | `run_exact_diagonalization_benchmark` |
| benchmark error 集計 | `backend/app/solvers/benchmarks/convergence.py` | `summarize_trajectory_error`, `build_convergence_table` |

---

## 10. Config / mode / API

| 理論量 / 役割 | 主なコード | 補足 |
| --- | --- | --- |
| solver mode enum | `backend/app/schemas/simulation.py` | `SolverKind`, `KBESelfEnergyMode` |
| basis mode enum | `backend/app/schemas/simulation.py` | `SolverRepresentation`（`real_space` / `k_space`） |
| KBE parameters | `backend/app/schemas/simulation.py` | `KBEConfig` |
| equilibrium parameters | `backend/app/schemas/simulation.py` | `EquilibriumConfig`（`method`, `tolerance`, `mixing`） |
| adaptive parameters | `backend/app/schemas/simulation.py` | `AdaptiveConfig` |
| thermal branch parameters | `backend/app/schemas/simulation.py` | `ThermalBranchConfig` |
| observable schema | `backend/app/schemas/observables.py` | frontend との I/O に使う |
| run summary / diagnostics schema | `backend/app/schemas/runs.py` | API surface |
| run state 昇格（warning 含む） | `backend/app/jobs/worker.py` | `second_born_convergence_criterion` + thermal/mixed branch 収束を合成判定 |

---

## 11. 理論からコードを引く最短経路

### HFB の式を見て実装を探すとき

1. [theory.md](./theory.md) の HFB / Nambu 節を読む
2. `backend/app/solvers/nambu.py` の `build_bdg_hamiltonian`
3. `backend/app/solvers/self_energy_hfb.py` の `build_hfb_self_energy`
4. `backend/app/solvers/tdhfb.py` の `simulate_hfb_dynamics`

### second Born を見て実装を探すとき

1. [theory.md](./theory.md) の second Born 節を読む
2. [literature-index.md](./literature-index.md) で `0906.1704_time-propagation-kbe.pdf` と `2105.06193_superconducting-nanowires-negf.pdf` の役割を確認する
3. prototype なら `backend/app/solvers/self_energy_second_born_prototype.py`
4. reference なら `backend/app/solvers/self_energy_second_born.py`

### Green 関数 API を追うとき

1. `backend/app/solvers/green_functions.py`
2. `backend/app/solvers/base.py`
3. `backend/app/schemas/green_functions.py`

### `k` 空間版の式を見て実装を探すとき

1. [theory.md](./theory.md) の `7.3.1` と `8.2.1` を読む
2. `backend/app/solvers/representation.py` で基底変換と block 変換を確認する
3. `backend/app/solvers/nambu.py` の `build_kspace_bdg_blocks` / `propagate_kspace_density_blocks` を確認する
4. `backend/app/solvers/tdhfb.py` の `_propagate_generalized_densities_kspace` と `_resolve_kspace_path_mode` を確認する

---

## 更新ルール

- 新しい理論量を docs に追加したら、このファイルにも 1 行対応を足す。
- 関数名が変わったら、まずこのファイルの表を直す。
- prototype と reference の意味が変わる変更では、`docs/glossary.md` も同時に更新する。
