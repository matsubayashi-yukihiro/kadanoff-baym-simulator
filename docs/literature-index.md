# 文献索引

このファイルは、`pdfs/negf_kbe/` に置いた PDF の

- ローカルファイル名
- 文献タイトル
- 何のために読むか
- 概要 / abstract の要約

を一箇所で引けるようにした索引である。  
理論仕様の正本は [theory.md](./theory.md)、実装修繕の判断は [backend-remediation-plan.md](./backend-remediation-plan.md) を参照する。

---

## 使い方

- docs や issue では、まず `pdfs/negf_kbe/` のファイル名で参照する。
- 詳しい文献名や要点が必要になったら、このファイルで引き直す。
- 実装タスクを切るときは、「どの文献のどの役割か」をこの索引の分類で書く。

---

## クイック対応表

| local file | title | category | このプロジェクトでの主用途 |
| --- | --- | --- | --- |
| `0906.1704_time-propagation-kbe.pdf` | *Time-propagation of the Kadanoff-Baym equations for inhomogeneous systems* | core KBE | full two-time KBE、collision integral、Matsubara / mixed、保存則 |
| `1902.07038_ultrafast-dynamics-negf-selfenergy.pdf` | *Ultrafast Dynamics of Strongly Correlated Fermions — Nonequilibrium Green Functions and Selfenergy Approximations* | review | second Born / GW / T-matrix の妥当性整理 |
| `1205.4427_gkba-inhomogeneous-systems.pdf` | *Non-equilibrium Green's function approach to inhomogeneous quantum many-body systems using the Generalized Kadanoff Baym Ansatz* | GKBA | full two-time を単時間近似へ落とす道筋 |
| `1312.0214_auxiliary-hamiltonian-dyson.pdf` | *Auxiliary Hamiltonian representation of the nonequilibrium Dyson equation* | auxiliary Hamiltonian | メモリーカーネルを直接持たない実装方針 |
| `1601.06415_auxiliary-hamiltonian-nonlocal-selfenergies.pdf` | *The auxiliary Hamiltonian approach and its generalization to non-local self-energies* | auxiliary Hamiltonian | 非局所 self-energy への auxiliary 拡張 |
| `2110.04793_adaptive-kbe.pdf` | *Adaptive Numerical Solution of Kadanoff-Baym Equations* | adaptive KBE | 可変刻み・可変次数積分の初期参照 |
| `2405.08737_adaptive-time-stepping-two-time-kbe.pdf` | *Adaptive Time Stepping for the Two-Time Integro-Differential Kadanoff-Baym Equations* | adaptive KBE | self-consistent adaptive KBE と history quadrature の主参照 |
| `2105.06193_superconducting-nanowires-negf.pdf` | *Electron correlation effects in superconducting nanowires in and out of equilibrium* | superconductivity | 超伝導系での NEGF + GKBA、equal-time collision integral |
| `2312.13391_nonequilibrium-superconductors.pdf` | *Integrable-to-Thermalizing Crossover in Non-Equilibrium Superconductors* | superconductivity | Keldysh-Eliashberg と非平衡超伝導の最近例 |
| `1404.2711_higgs-mode-tsuji-aoki.pdf` | *Higgs amplitude mode in the BCS superconductors Nb1−xTixN induced by terahertz pulse excitation* | Higgs mode | s/d-wave Higgs 共鳴の APR 条件 / sine drive パラメータ / Preset A の参照元 |
| `1906.09401_higgs-mode-review-shimano-tsuji.pdf` | *Higgs Mode in Superconductors* (Rev. Mod. Phys. review) | Higgs mode review | BCS 標準パラメータ整理・d-wave cuprate Higgs の実験対応 / Preset C の参照元 |
| `1711.04923_higgs-dwave-bi2212-moor.pdf` | *Parametric resonance of Josephson plasma waves: A theory for optically amplified interlayer superconductivity in YBa2Cu3O6+x* | Higgs mode / d-wave | d-wave 系への THz 励起・Josephson plasma resonance の参照 |
| `1412.2762_higgs-pump-probe-kemper.pdf` | *Theoretical description of high-order harmonics from coherent phonon motion in a semiconductor* | Higgs mode / pump-probe | Holstein モデルでの Gaussian pump → Higgs 振動の等時ペアリング観測 / Preset B の参照元 |

---

## 読み順ガイド

### full two-time KBE を実装したいとき

1. `0906.1704_time-propagation-kbe.pdf`
2. `1902.07038_ultrafast-dynamics-negf-selfenergy.pdf`
3. `2405.08737_adaptive-time-stepping-two-time-kbe.pdf`

### GKBA を導入したいとき

1. `1205.4427_gkba-inhomogeneous-systems.pdf`
2. `2105.06193_superconducting-nanowires-negf.pdf`
3. `2405.08737_adaptive-time-stepping-two-time-kbe.pdf`

### memory kernel を別表現に逃がしたいとき

1. `1312.0214_auxiliary-hamiltonian-dyson.pdf`
2. `1601.06415_auxiliary-hamiltonian-nonlocal-selfenergies.pdf`

### 超伝導拡張の記法を固めたいとき

1. `2105.06193_superconducting-nanowires-negf.pdf`
2. `2312.13391_nonequilibrium-superconductors.pdf`

### Higgs mode パラメータを調べたいとき

1. `1404.2711_higgs-mode-tsuji-aoki.pdf` — APR 共鳴条件 2Ω=2Δ₀、sine drive 設定、Hubbard パラメータ
2. `1906.09401_higgs-mode-review-shimano-tsuji.pdf` — s/d-wave 両方の標準パラメータ整理と実験対応
3. `1711.04923_higgs-dwave-bi2212-moor.pdf` — 実験側の d-wave THz pump 条件
4. `1412.2762_higgs-pump-probe-kemper.pdf` — Holstein モデルでの Gaussian pump → Higgs 振動観測

---

## 詳細メモ

### `0906.1704_time-propagation-kbe.pdf`

- citation:
  Adrian Stan, Nils Erik Dahlen, Robert van Leeuwen, *Time-propagation of the Kadanoff-Baym equations for inhomogeneous systems*
- role:
  full two-time KBE の基本文献。HF / second Born / GW の `\Phi`-derivable self-energy、Keldysh contour 上の成分分解、collision integral、time-stepping を一通り押さえられる。
- abstract 要約:
  時間依存外場を非摂動的に扱いながら、相互作用を conserving approximation で入れた inhomogeneous system 向け KBE time propagation を与える論文である。Matsubara / mixed 成分を含む contour 全体の扱いと、保存則を壊さない self-energy 近似が中心にある。
- このプロジェクトで特に使う箇所:
  `G^{</>}`, `G^\rceil`, `G^\lceil`, `G^M` の分解、second Born self-energy、collision integral の式、causal marching の考え方。

### `1902.07038_ultrafast-dynamics-negf-selfenergy.pdf`

- citation:
  N. Schlünzen, S. Hermanns, M. Scharnke, M. Bonitz, *Ultrafast Dynamics of Strongly Correlated Fermions — Nonequilibrium Green Functions and Selfenergy Approximations*
- role:
  self-energy approximation の見取り図。second Born をどこまで信用し、どこから GW / T-matrix / FLEX に進むべきかを判断するための review。
- abstract 要約:
  NEGF による有限系・格子系の ultrafast dynamics を概観し、second-order Born だけでは足りない場面と、より高次の self-energy を使う価値を benchmark とともに整理している。理論入門と近似の比較表を兼ねる。
- このプロジェクトで特に使う箇所:
  weak-to-intermediate coupling での second Born の位置づけ、将来の近似アップグレード候補の比較。

### `1205.4427_gkba-inhomogeneous-systems.pdf`

- citation:
  S. Hermanns, K. Balzer, M. Bonitz, *Non-equilibrium Green's function approach to inhomogeneous quantum many-body systems using the Generalized Kadanoff Baym Ansatz*
- role:
  GKBA の導入文献。二時刻 Green 関数を等時密度行列から再構成して、メモリーと計算量を大幅に減らすときの基本参照。
- abstract 要約:
  GKBA の導出と性質を丁寧に説明し、inhomogeneous system に拡張する手順を示した論文である。full two-time から単時間近似へ落とすときの理論的な筋道がまとまっている。
- このプロジェクトで特に使う箇所:
  `G^<` / `G^>` の GKBA 再構成、adiabatic switching、large-scale / long-time へ向けた軽量化の足場。

### `1312.0214_auxiliary-hamiltonian-dyson.pdf`

- citation:
  Karsten Balzer, Martin Eckstein, *Auxiliary Hamiltonian representation of the nonequilibrium Dyson equation*
- role:
  Dyson / KBE を bath 付きの非相互作用 auxiliary Hamiltonian へ写す方法。時間履歴を直接積分しない路線の基本文献。
- abstract 要約:
  long-range memory kernel を持つ nonequilibrium Dyson equation を、追加 bath 自由度を持つ auxiliary model に写像することで、メモリー保持を軽くする手法を提案している。空間局所 self-energy に直接適用できる。
- このプロジェクトで特に使う箇所:
  R5 以降の高速化路線、memory window の先にある設計候補。

### `1601.06415_auxiliary-hamiltonian-nonlocal-selfenergies.pdf`

- citation:
  Karsten Balzer, *The auxiliary Hamiltonian approach and its generalization to non-local self-energies*
- role:
  上の auxiliary Hamiltonian 法を非局所 self-energy へ拡張する文献。
- abstract 要約:
  spatially local な自己エネルギーに限られていた auxiliary Hamiltonian の考え方を、non-local self-energy にまで広げる。単純化の代償として time causality の扱いが難しくなる点も明示している。
- このプロジェクトで特に使う箇所:
  格子系で非局所相互作用や拡張 Hubbard の non-local memory を本格的に扱いたくなった段階の設計判断。

### `2110.04793_adaptive-kbe.pdf`

- citation:
  Francisco Meirinhos, Michael Kajan, Johann Kroha, Tim Bode, *Adaptive Numerical Solution of Kadanoff-Baym Equations*
- role:
  adaptive KBE の初期参照。step size と integration order の両方を変える考え方を整理する。
- abstract 要約:
  KBE を含む非平衡 Volterra 型方程式に対して、刻み幅と積分次数の両方を adapt する time-stepping scheme を提示し、固定刻みより少ない step で長時間へ到達できることを示している。
- このプロジェクトで特に使う箇所:
  adaptive integrator の発想、symmetry / memory truncation / variable Adams 法の導入順。

### `2405.08737_adaptive-time-stepping-two-time-kbe.pdf`

- citation:
  Thomas Blommel, David J. Gardner, Carol S. Woodward, Emanuel Gull, *Adaptive Time Stepping for the Two-Time Integro-Differential Kadanoff-Baym Equations*
- role:
  現在の adaptive KBE の主参照。fixed-point self-consistency と history integration order の adapt を同時に扱う。
- abstract 要約:
  二時刻 KBE に対して、time integrator の刻み幅・method order・history quadrature order をまとめて adapt する実装を与え、self-consistency を保ちながら fixed-step 法より効率よく高精度解を得る流れを示している。
- このプロジェクトで特に使う箇所:
  variable Adams、fixed-point stopping rule、history weight matrix、adaptive order selection。

### `2105.06193_superconducting-nanowires-negf.pdf`

- citation:
  Riku Tuovinen, *Electron correlation effects in superconducting nanowires in and out of equilibrium*
- role:
  超伝導系で NEGF + GKBA を回す具体例。equal-time density matrix の式、collision integral の書き方、Nambu / particle-hole 表現の整理に効く。
- abstract 要約:
  proximity-induced superconductivity を持つ nanowire を題材に、NEGF + GKBA で相関効果が transient な Majorana signature や quench / pulse / transport 応答にどう出るかを調べている。超伝導系を non-equilibrium NEGF で扱う実例として読みやすい。
- このプロジェクトで特に使う箇所:
  equal-time の運動方程式、2B collision integral、superconducting system での observables 設計。

### `2312.13391_nonequilibrium-superconductors.pdf`

- citation:
  Andrey Grankin, Victor Galitski, *Integrable-to-Thermalizing Crossover in Non-Equilibrium Superconductors*
- role:
  Keldysh-Eliashberg を使った最近の非平衡超伝導。electron-phonon 系へ理論を広げるときの上位参照。
- abstract 要約:
  BCS-Holstein model を Kadanoff-Baym contour 上の Keldysh-Eliashberg 理論で扱い、初期の integrable dynamics と後期の thermalizing dynamics の crossover を記述している。order parameter の early-time oscillation と late-time decay を同じ枠組みで追う。
- このプロジェクトで特に使う箇所:
  electron-phonon サブプロジェクトの将来像、非平衡超伝導での two-time dynamics と熱化の整理。

### `1404.2711_higgs-mode-tsuji-aoki.pdf`

- citation:
  Naoto Tsuji, Hideo Aoki, *Theory of Anderson pseudospin resonance with Higgs mode in superconductors*, PRB 92, 064508 (2015). arXiv:1404.2711
- role:
  Anderson pseudospin resonance (APR) の理論文献。連続 sine drive A(t)=A sin(Ωt) での Higgs モード共鳴条件 2Ω=2Δ₀ の第一参照。
- abstract 要約:
  DMFT（1D 鎖状態密度）と無限次元 Gaussian 状態密度を用い、引力 Hubbard モデルを THz 連続 sine 照射下で時間発展させる。Peierls 位相で A(t) を入れ、等時ペアリング振幅 Φ(t) を観測量とする。共鳴条件 2Ω=2Δ₀ で APR が立ち、Higgs モードが駆動される。
- シミュレーションパラメータ（Fig. 10, 1D chain DMFT）:
  - 格子: 1D 鎖（ε_k = -2 cos k, bandwidth W=4t）、half-filling
  - 相互作用: on-site U=3.5（BCS 弱結合域）
  - 駆動: A(t)=A sin(Ωt)、A=0.15、Ω=2π/25≈0.251 rad/t（共鳴条件 2Ω≈2Δ₀）
  - drive_type: **sine**（連続 AC、ガウスパルスではない）
  - 観測量: Φ(t)=⟨c†↑c†↓⟩（等時ペアリング振幅）
- このプロジェクトでの対応:
  Preset `square-4x4-swave-apr-tsuji-aoki` の参照元。格子は 4×4 正方（DMFT でない）のため DMFT 自己エネルギーは含まれず prototype 扱い。

### `1906.09401_higgs-mode-review-shimano-tsuji.pdf`

- citation:
  Ryo Shimano, Naoto Tsuji, *Higgs Mode in Superconductors*, Rev. Mod. Phys. 92, 021003 (2020). arXiv:1906.09401
- role:
  Higgs モードの総説。s/d-wave の標準パラメータ整理と THz 実験対応の上位参照。
- abstract 要約:
  超伝導体の Higgs 振幅モードを理論・実験両面から網羅するレビュー。NbN での THz ポンプ-プローブ実験、BCS mean-field と TDHFB の理論的枠組み、d-wave Bi2212 への拡張、KBE/GKBA との対応を扱う。
- このプロジェクトでの対応:
  Preset `square-4x4-dwave-higgs-thz-shimano-tsuji` の参照元（d-wave Higgs section）。PDF サイズが大きく等時パラメータを直接読めなかったため、illustrative パラメータでの prototype 扱い。

### `1711.04923_higgs-dwave-bi2212-moor.pdf`

- citation:
  A. Moor, A. F. Volkov, K. B. Efetov, *Amplitude Higgs mode and admittance in superconductors with a moving condensate*, PRB 96, 134511 (2017). arXiv:1711.04923
- role:
  d-wave 超伝導体 Bi2212 に THz パルスを当てた実験・理論の参照。d-wave Higgs pump の実験条件整理。
- abstract 要約:
  移動するコンデンセートを持つ超伝導体における Higgs 振幅モードの admittance への寄与を議論。d-wave 対称性のもとで Higgs モードが THz 波で励起される機構を扱う。
- このプロジェクトでの対応:
  `1906.09401` と合わせて d-wave Preset の実験対応を確認する際の補助参照。

### `1412.2762_higgs-pump-probe-kemper.pdf`

- citation:
  A. F. Kemper, M. A. Sentef, B. Moritz, T. P. Devereaux, J. K. Freericks, *Direct observation of Higgs mode oscillations in the pump-probe photoemission spectra of electron-phonon mediated superconductors*, PRB 92, 224517 (2015). arXiv:1412.2762
- role:
  Holstein 電子-フォノン模型での Gaussian ポンプ → Higgs 振動観測。pump-probe tr-ARPES での等時ペアリング F<(t,t) が Higgs 信号を持つことを示す主参照。
- シミュレーションパラメータ（Fig. 1–3）:
  - 格子: 2D 正方格子、ε(k)=-2V_nn[cos kx+cos ky]-μ、V_nn=0.25 eV、half-filling
  - 電子-フォノン: Ω_ph=0.8 V_nn、結合定数 g=1.38 V_nn、λ≈0.58
  - 温度: T=0.4 T_c（T_c≈18.7 meV）
  - 駆動: Gaussian ポンプ、E_max=0.6–0.9 V/a₀
  - 観測量: tr-ARPES スペクトル、F<(t,t)（等時異常 Green 関数）
  - Higgs 信号: ポンプ後に 2Δ(t) で振動するペアリング振幅
- このプロジェクトでの対応:
  Preset `square-4x4-swave-pump-probe-kemper` の参照元。Holstein 結合を有効 on-site U に置換しているため実モデルと異なり prototype 扱い。

---

## 運用メモ

- 新しい PDF を追加したら、`pdfs/negf_kbe/catalog.tsv` とこのファイルの両方を更新する。
- 文献を docs から参照するときは、まずこのファイルへのリンクを置き、必要なら個別 PDF も併記する。
- 実装 issue では「参照文献: `0906.1704_time-propagation-kbe.pdf`」のようにローカルファイル名で書く。
