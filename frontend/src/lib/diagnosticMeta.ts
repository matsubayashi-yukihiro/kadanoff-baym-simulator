type DiagnosticMeta = {
  description: string;
  threshold?: string;
};

const META: Record<string, DiagnosticMeta> = {
  // ── Run info ─────────────────────────────────────────────────────────────
  site_count: {
    description: "格子サイト数。",
  },
  time_steps: {
    description: "時間発展の総ステップ数。",
  },
  saved_samples: {
    description: "出力として保存されたサンプル数。",
  },
  particle_target: {
    description: "平衡計算に使用した目標粒子数（filling）。",
  },
  effective_chemical_potential: {
    description: "目標 filling を再現するために平衡求解で決定した化学ポテンシャル μ。",
  },
  pairing_channel: {
    description: "ペアリング対称性のチャンネル（例: bond_s, bond_d）。",
  },
  two_time_grid_shape: {
    description: "2時間 Green 関数グリッドの形状 [Nt, Nt, Ns, Ns]。",
  },
  kbe_self_energy_mode: {
    description: "KBE で使用している自己エネルギーの近似種別。",
  },
  kbe_two_time_reconstruction: {
    description: "2時間 GF から等時刻密度行列を復元する方式（exact_hfb または equal_time_average）。",
  },
  second_born_solver_mode: {
    description: "Second Born ソルバーの動作モード（hfb_limit / two_time_causal_marching / gkba_causal_marching）。",
  },
  second_born_kspace_block_path: {
    description: "k-space block-diagonal kernel が second_born_reference path で有効だったかどうか。",
    threshold: "true（k-space native block path が有効なとき）",
  },
  second_born_contour_mode: {
    description: "Second Born の輪郭積分モード（keldysh_only / thermal_only / full_contour / hfb_limit）。",
  },
  second_born_memory_window: {
    description: "メモリ積分に含める過去のタイムステップ数（メモリカーネルの切り捨て幅）。",
  },
  time_grid_mode: {
    description:
      "時間刻みの種別（uniform: 等刻み / adaptive: 可変刻み生出力 / uniform_dense_output: 適応刻み→等刻み補間出力）。",
  },
  adaptive_enabled: {
    description: "適応時間刻みが有効かどうか。",
  },
  dense_output_enabled: {
    description:
      "適応刻みの軌道を等刻みグリッドに線形補間して出力しているかどうか。" +
      "有効なとき、FFT ベースのスペクトル解析が adaptive run でも利用可能になる。",
  },
  k_space_path_mode: {
    description: "k-space 伝播カーネルの実行モード（block_diagonal / full_matrix_fallback）。",
  },
  k_space_path_fallback_reason: {
    description: "k-space block path が無効化され full-matrix fallback した理由。",
  },
  k_space_initial_block_structure_error: {
    description: "初期密度の block-diagonal 再構成誤差。大きい場合は block path を使わず fallback する。",
  },
  kbe_reference_solver_available: {
    description: "参照実装のソルバーが利用可能かどうか。",
  },
  second_born_reference_implementation: {
    description: "参照実装（equal-time GKBA contour-dressed）を使用しているかどうか。",
  },
  second_born_enabled: {
    description: "Second Born 自己エネルギーが有効化されているかどうか。",
  },
  thermal_branch_enabled: {
    description: "Matsubara（虚時間）ブランチが有効化されているかどうか。",
  },
  thermal_branch_correlated: {
    description: "熱平衡状態に相関効果を含めているかどうか。",
  },
  second_born_explicit_self_energy: {
    description: "明示的な自己エネルギー計算を使用しているかどうか（参照実装のみ true）。",
  },

  // ── Equilibrium / HFB convergence ────────────────────────────────────────
  hfb_converged: {
    description: "平衡 HFB 自己無撞着計算が収束したかどうか。",
    threshold: "true",
  },
  hfb_iterations: {
    description: "平衡 HFB の自己無撞着反復回数。",
  },
  hfb_self_consistency_error: {
    description: "平衡 HFB の最終反復における自己無撞着誤差。",
  },
  equilibrium_stationarity_residual: {
    description: "HFB 平衡解の静止性残差。時間発展開始前に自己無撞着 HFB 解が真の定常状態にどれだけ近いかを示す。値が大きいほど初期状態が非定常的で、時間発展の立ち上がりに人工的な過渡応答が現れる可能性がある。",
  },
  second_born_converged: {
    description: "Second Born fixed-point 反復が収束したかどうか。",
    threshold: "true",
  },
  thermal_branch_converged: {
    description: "Matsubara ブランチの自己無撞着反復が収束したかどうか。",
    threshold: "true",
  },
  thermal_branch_iterations: {
    description: "Matsubara ブランチの自己無撞着反復回数。",
  },

  // ── Conservation and continuity ──────────────────────────────────────────
  particle_number_drift: {
    description: "max|N(t) − N(0)| — 粒子数の時間変化量。連続方程式（∂ₜρᵢᵢ = Jᵢ）の積分誤差を反映する。非駆動系では厳密に 0 であるべき。",
    threshold: "< 1e-10",
  },
  energy_drift: {
    description: "max|E(t) − E(0)| — 非駆動時のエネルギー保存誤差。外部駆動がない場合は厳密に 0 であるべき。",
    threshold: "< 1e-10",
  },
  max_continuity_residual: {
    description: "max|∂ₜρᵢᵢ − Jᵢ| — サイト連続方程式の残差。密度の時間微分と電流の発散の不一致を測る。",
    threshold: "< 1e-12",
  },
  final_continuity_residual: {
    description: "t_final における連続方程式の残差。",
    threshold: "< 1e-12",
  },
  net_external_work: {
    description: "外部ドライブが系になした仕事の積算値 W_ext = ∫ dt Tr[∂ₜH·ρ]。",
  },
  max_energy_work_mismatch: {
    description: "max|ΔE − W_ext| — エネルギー変化と外部仕事の不一致量。エネルギー保存則のチェック。",
    threshold: "< 1e-4",
  },
  final_energy_work_mismatch: {
    description: "t_final における energy-work balance 誤差。",
    threshold: "< 1e-5",
  },
  max_particle_conservation_residual: {
    description: "max|∂ₜN − 0| — KBE での粒子数保存残差。Kadanoff-Baym 方程式が粒子数を保存しているかを検証する。",
    threshold: "< 1e-10",
  },

  // ── Hermiticity and structural constraints ────────────────────────────────
  max_hermiticity_error: {
    description: "max|ρ − ρ†| — 一体密度行列の Hermiticity 誤差。数値誤差で非 Hermitian 成分が生じた量を測る。",
    threshold: "< 1e-12",
  },
  max_generalized_hermiticity_error: {
    description: "max|G − G†| — Nambu 構造を持つ一般化密度行列の Hermiticity 誤差。TDHFB および KBE で監視される。",
    threshold: "< 1e-10",
  },
  max_density_bound_violation: {
    description: "max(ρᵢᵢ > 1 または ρᵢᵢ < 0) の違反量。占有数が物理的な範囲 [0, 1] を逸脱した大きさを示す。",
    threshold: "== 0.0",
  },
  max_lesser_hermiticity_error: {
    description: "max|G_<(t,s) + G_<†(s,t)| — lesser Green 関数の Hermiticity 制約誤差。G_< は G_<† = −G_< を満たすべき。",
    threshold: "< 1e-10",
  },
  max_retarded_equal_time_error: {
    description: "max|G_ret(t,t) + iI| — 等時刻 retarded GF の規格化誤差。G_ret(t,t) = −iI という厳密な関係からのずれ。",
    threshold: "< 1e-10",
  },
  max_retarded_causality_error: {
    description: "max|G_ret(t>s, s)| — 因果律の違反量。retarded GF は t < s では厳密に 0 でなければならない。",
    threshold: "== 0.0",
  },
  max_equal_time_tdhfb_mismatch: {
    description: "max|G_KBE(t,t) − ρ_TDHFB(t)| — KBE の等時刻密度と独立した TDHFB 密度の不一致。KBE と TDHFB の整合性を検証する。",
    threshold: "< 1e-10",
  },
  max_equal_time_density_reconstruction_error: {
    description: "2時間 GF から等時刻密度行列を再構成したときの誤差。再構成方式（exact_hfb / equal_time_average）の精度を示す。",
    threshold: "< 1e-10",
  },

  // ── Pairing ───────────────────────────────────────────────────────────────
  max_pairing_magnitude: {
    description: "全時間にわたる最大ペアリング振幅 max|Δ(t)|。",
  },
  max_pairing_s_magnitude: {
    description: "s 波成分のペアリング振幅の最大値 max|Δ_s(t)|。",
  },
  max_pairing_d_magnitude: {
    description: "d 波成分のペアリング振幅の最大値 max|Δ_d(t)|。",
  },
  final_pairing_magnitude: {
    description: "t_final におけるペアリング振幅 |Δ(t_final)|。",
  },

  // ── Second Born convergence ───────────────────────────────────────────────
  thermal_branch_factorized_difference: {
    description: "‖G_Matsubara − G_factorized‖ — 完全な Matsubara GF と factorized 近似の差。値が大きいほど factorization 近似の誤差が大きい。",
  },
  mixed_branch_factorized_difference: {
    description: "‖G_mixed − G_factorized‖ — 混合実時間/虚時間 GF と factorized 近似の差。",
  },
  thermal_branch_density_shift: {
    description: "熱平衡計算後の密度シフト量。平衡状態の数値誤差を反映する。",
  },

  // ── Adaptive time stepping ────────────────────────────────────────────────
  accepted_time_steps: {
    description: "適応時間刻みで受理されたステップ数。",
  },
  requested_time_steps: {
    description: "適応時間刻みで要求されたステップ数（受理 + 棄却の合計）。",
  },
  rejected_time_steps: {
    description: "適応時間刻みで棄却されたステップ数。局所誤差推定が許容値を超えてステップを縮小した回数。",
    threshold: "== 0 (理想)",
  },
  adaptive_max_error_estimate: {
    description: "適応刻み制御の全ステップにわたる最大局所誤差推定量。",
  },
  adaptive_min_dt_used: {
    description: "実際に使用された最小タイムステップ。",
  },
  adaptive_max_dt_used: {
    description: "実際に使用された最大タイムステップ。",
  },

  // ── KBE fixed-point ───────────────────────────────────────────────────────
  kbe_fixed_point_tolerance: {
    description: "KBE fixed-point 反復の収束判定閾値。",
  },
  kbe_fixed_point_mixing: {
    description: "KBE fixed-point 反復の mixing パラメータ（線形混合の重み）。",
  },
  kbe_fixed_point_max_iterations: {
    description: "KBE fixed-point 反復の最大反復回数。",
  },
};

export function getDiagnosticMeta(key: string): DiagnosticMeta | null {
  return META[key] ?? null;
}
