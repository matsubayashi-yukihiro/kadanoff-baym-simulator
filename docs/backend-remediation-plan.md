# バックエンド修繕計画

この文書は、2026-03-16 の backend 点検を受けて作成した修繕計画である。  
対象は主に `backend/app/solvers/` とその検証系であり、特に `kbe_hfb.py` の Phase E 相当実装を再設計する。

- 進捗の正本: [progress.md](./progress.md)
- 物理仕様の正本: [theory.md](./theory.md)
- backend validation の正本: [validation-spec.md](./validation-spec.md)
- 研究アプリ全体方針: [research-workbench-plan.md](./research-workbench-plan.md)
- 参考文献束: [../pdfs/negf_kbe/README.md](../pdfs/negf_kbe/README.md)
- 文献索引: [literature-index.md](./literature-index.md)

この文書は「何を validated と呼ぶか」の正本ではなく、
validation-spec に対して未達項目をどう埋めるかの作業計画である。

運用メモ:
- 作業が完了したら、進捗状況を加筆する。
- 「作業が完了したら、進捗状況を加筆して、この指示自体も md に書き込んでおく」という指示は `docs/progress.md` に保持する。

### 2026-03-16 実施済み基盤作業

- R0 に対応して、現行 `second_born` / thermal / mixed branch を heuristic prototype として docs / diagnostics 上で明示した。
- R1 に対応して、`scipy` を導入し、累積 trapezoid と root finding を共通 utility に寄せた。
- R2 の足場として、`contour.py`、`green_functions.py`、`self_energy_second_born_prototype.py` を追加し、`kbe_hfb.py` を orchestration 層へ整理した。
- ただし、reference second Born self-energy 自体は未実装であり、R3-R5 は引き続き未完である。

### 2026-03-17 R3 進展

- 2x2 系の固定粒子数 exact diagonalization benchmark helper を追加した。
- 非相互作用 benchmark、一つの \(\Delta t\) 収束回帰、および短時間の TDHFB / KBE-HFB / `second_born` prototype benchmark を backend test に追加した。
- benchmark 比較用 utility を追加し、`second_born` + thermal branch の exact density/current 比較、adaptive tolerance の fine fixed-step 参照に対する最終誤差比較、および memory window 依存の convergence row を backend test に追加した。
- ただし、\(\Delta t\) / adaptive tolerance / 系サイズの収束表を docs 上で整理する作業と、reference second Born path を基準にした benchmark は未完である。

### 2026-03-17 R4 完了

- `backend/app/solvers/self_energy_hfb.py` と `backend/app/solvers/self_energy_second_born.py` を追加し、`second_born_reference` mode を実装した。
- 実装の主参照は `0906.1704_time-propagation-kbe.pdf` の KBE / second Born self-energy、`2405.08737_adaptive-time-stepping-two-time-kbe.pdf` の fixed-point + history integration、`2105.06193_superconducting-nanowires-negf.pdf` の equal-time GKBA collision integral である。
- 現行 backend の reduced-Nambu 基底に合わせて、reference path は explicit self-energy を用いた equal-time GKBA causal marching として実装し、legacy の `second_born` heuristic path は prototype として残した。
- `second_born_reference` は short-window exact benchmark、HFB 極限、reference diagnostics を backend test に追加済みであり、R3 の docs 収束表も本書に反映した。
- 当初 factorized HFB seed に留めていた thermal / mixed branch については、後続の contour dressing 実装で self-consistent reference path へ拡張した。

### 2026-03-17 R5 完了

- `uv run python` + `cProfile` で representative な `4x2`, `t_final=0.6`, `dt=0.05`, `second_born_reference` case を計測し、総実行時間 `0.894 s` のうち `_build_local_second_born_self_energy` が cumulative `0.796 s` を占めることを確認した。
- `backend/app/solvers/self_energy_second_born.py` の局所 2x2 Nambu block 抽出を `np.ix_` 依存の site loop からベクトル化実装へ置き換え、reference path で不要な HFB two-time Green 関数の先行構築を止めた。
- 同一ケースの再計測では総実行時間が `0.223 s`、`_build_local_second_born_self_energy` の cumulative time が `0.132 s` まで低下した。
- 再利用可能な profiling helper として `backend/app/solvers/benchmarks/profiling.py` を追加した。
- `green_functions.py` に factorized Matsubara / mixed branch builder を共通化し、prototype / reference の双方から同じベクトル化 seed 生成経路を使うように整理した。
- `kbe_hfb.py` の solver path 選択、contour seed 構築、artifact packaging を helper 化し、Phase E prototype / reference の orchestration を branch 単位で差し替え可能な形へ整理した。
- `FileRunStorage` で `save_every` に基づく two-time / mixed Green 関数の保存縮約を導入し、observables を `np.savez_compressed` へ切り替えた。これにより solver 内部の full grid diagnostics を維持したまま、長時間 run の保存サイズと API の読み出し点数を削減した。
- representative な `4x2`, `t_final=0.6`, `dt=0.05`, `second_born` + thermal / mixed prototype case を `profile_callable` で再計測し、wall time `0.164 s`、支配項が `apply_second_born_corrections` / `dissipative_collision` 側へ寄ること、および factorized branch builder が上位支配項から外れたことを確認した。

### 2026-03-17 Phase E closure

- `second_born_reference` の Matsubara branch を factorized seed から self-consistent dressing へ拡張し、`thermal_branch_reference_implementation=True` を返すようにした。
- `second_born_reference` の mixed branch を corrected density に基づく self-consistent dressing へ拡張し、`mixed_branch_reference_implementation=True` と memory / residual / history-order diagnostics を追加した。
- real-time equal-time GKBA path には thermal / mixed contour correction を接続し、`second_born_contour_mode=full_contour` と `second_born_reference_scope=equal_time_gkba_full_contour` を返すようにした。
- backend validation には reference adaptive row、reference thermal benchmark、reference full-contour API diagnostics を追加し、Phase E の受け入れ条件を reference path で閉じた。

---

## 0. 修繕フェーズ進捗

| 修繕フェーズ | 状態 | 現在の到達点 | 残作業 |
| --- | --- | --- | --- |
| Phase R0: 凍結とラベリング | 完了 | Phase E 実装を heuristic prototype として docs / diagnostics / progress に反映済み | 維持のみ |
| Phase R1: numerical utility の整理 | 完了 | `scipy` 導入、cumulative trapezoid / root finding の共通 utility 化を実施済み | Anderson / Broyden 系の評価は R4 以降と連動 |
| Phase R2: solver 構造の再編 | 完了 | `contour.py`、`green_functions.py`、`self_energy_second_born_prototype.py` などを追加し、`kbe_hfb.py` を orchestration 層へ整理済み | reference path 実装時に `self_energy_hfb.py` / `self_energy_second_born.py` へ分離を継続 |
| Phase R3: benchmark と収束検証 | 完了 | 2x2 exact diagonalization benchmark、短時間 TDHFB / KBE-HFB / prototype / reference 比較、`dt` / adaptive tolerance / 系サイズ row の docs 整理まで反映済み | 維持のみ |
| Phase R4: KBE reference path の再実装 | 完了 | `second_born_reference` として explicit self-energy + equal-time GKBA causal marching を実装し、self-consistent thermal / mixed contour dressing まで完了 | 維持のみ |
| Phase R5: 高速化と長時間実行 | 完了 | reference/prototype/thermal/mixed path の profiling、factorized contour seed の共通ベクトル化、`kbe_hfb` orchestration の整理、`save_every` ベースの Green 関数保存縮約まで完了 | 維持のみ |

現時点の要約:
- 完了しているのは `R0-R5` までである。
- `R3` は docs 上の収束表整理と reference-path benchmark を含めて閉じた。
- `R4` は reduced-Nambu backend の現在スコープとして、`second_born_reference` の explicit self-energy path を導入した。
- `R5` は reference/prototype の hot path profiling、thermal / mixed seed の共通ベクトル化、`save_every` による保存縮約、API 回帰まで含めて閉じた。
- `second_born_reference` の thermal / mixed contour dressing は self-consistent reference path として閉じた。

### 0.1 R3/R4 benchmark tables

#### `dt` 収束: 2x2 非相互作用 exact benchmark に対する max abs error

| `dt` | `current_x` | `density(mean)` |
| --- | --- | --- |
| `0.10` | `2.11e-4` | `1.55e-15` |
| `0.05` | `4.53e-5` | `2.50e-15` |
| `0.025` | `9.15e-6` | `2.72e-15` |

#### adaptive tolerance row: `second_born` prototype の fine fixed-step 参照比較

| adaptive setting | accepted steps | `current_x` final abs error | `current_x` max abs error |
| --- | --- | --- | --- |
| `loose` (`rtol=1e-2`, `atol=1e-4`) | `4` | `2.13e-5` | `7.51e-5` |
| `tight` (`rtol=1e-4`, `atol=1e-6`) | `7` | `7.60e-6` | `1.08e-4` |

#### system-size row: `second_born_reference` の short-window stability diagnostics

| lattice | sites | particle drift | max density bound violation | max collision norm |
| --- | --- | --- | --- | --- |
| `2x2` | `4` | `1.12e-3` | `0.0` | `3.79e-2` |
| `3x2` | `6` | `1.27e-3` | `0.0` | `3.02e-2` |
| `4x2` | `8` | `1.75e-3` | `0.0` | `3.06e-2` |

#### reference-path short-window benchmark: 2x2 exact benchmark に対する max abs error

| mode | density(mean) | `current_x` | `current_y` | max collision norm |
| --- | --- | --- | --- | --- |
| `hfb` | `3.11e-15` | `6.72e-4` | `3.37e-4` | `0.0` |
| `second_born` (prototype) | `1.28e-8` | `6.72e-4` | `3.37e-4` | `1.70e-4` |
| `second_born_reference` | `1.53e-4` | `8.03e-4` | `4.03e-4` | `2.73e-2` |

注記:
- `second_born_reference` は reduced-Nambu backend 上で `0906.1704_time-propagation-kbe.pdf` / `2405.08737_adaptive-time-stepping-two-time-kbe.pdf` / `2105.06193_superconducting-nanowires-negf.pdf` を突き合わせた equal-time GKBA reference path である。
- thermal / mixed branch は self-consistent contour dressing を持ち、real-time Keldysh collision integral と contour diagnostics を reference path へ接続した。

---

## 1. 背景

backend 点検の結果、`noninteracting` と `tdhfb` は比較的筋がよい一方、`kbe_hfb` の `second_born` / adaptive / thermal / mixed branch の相関実装は次の問題を持つことが分かった。

1. `second_born` が文献準拠の `Phi`-derivable contour self-energy を明示的に解いておらず、密度平均・envelope・対角 `gamma` を用いた heuristic dissipative closure になっている。
2. thermal / mixed branch も同様に heuristic dressing を行っており、full-contour second Born と同一視できない。
3. root finding、累積積分、固定点反復、adaptive 制御などの generic numerical primitive を手書きしている箇所があり、数値実装の見通しと再利用性を下げている。
4. 現在の自動テストは「コードパスが破綻していない」ことの確認としては有効だが、「物理的に正しい KBE second Born を解いている」ことの保証にはなっていない。

したがって、現状の Phase E 実装は「研究プロトタイプとしては動くが、文献準拠の reference implementation としては未完」と再評価する。

---

## 2. 修繕の目的

修繕の目的は次の 5 点である。

1. 非相互作用、HFB 平衡、TDHFB の既存基盤を壊さずに維持する。
2. generic numerical routine を既存ライブラリへ寄せ、重複した手書き実装を減らす。
3. `kbe_hfb` の heuristic Phase E 実装を、docs と code の意味が揃った reference path へ段階的に移行する。
4. 小サイズ厳密 benchmark と収束試験を追加し、物理・数値の両面で再検証可能にする。
5. 将来の GKBA や auxiliary-Hamiltonian などの計算量削減路線に耐える設計へ整理する。

---

## 3. 基本方針

### 3.1 correctness first

- まず reference implementation を正しく作る。
- 高速化は、その後に profiling に基づいて行う。
- heuristic mode を延命するための機能追加は止める。

### 3.2 物理カーネルと数値ユーティリティを分離する

- contour 構造
- self-energy
- quadrature
- fixed-point / root finding
- storage / API

を別責務として切り分ける。

### 3.3 段階的に置換する

- 既存の `second_born` を一気に複雑化しない。
- 先に benchmark と文書化を整え、その後に実装を入れ替える。

### 3.4 ライブラリ利用は「正当な下請け」に限定する

- `scipy` は積分・最適化・sparse linear algebra のために導入する。
- `numba` は hot loop の最適化に限り、correctness の代替には使わない。
- `qutip` は必要なら benchmark helper としてのみ使い、core solver には入れない。

---

## 4. 推奨する実装方針

推奨方針は二段構えである。

### Track A: reference solver

- 文献準拠の second Born self-energy と causal marching を Nambu 表現で実装する。
- 小サイズと短中時間を主対象にし、正しさの基準にする。
- 主参照:
  - `0906.1704_time-propagation-kbe.pdf`
  - `1902.07038_ultrafast-dynamics-negf-selfenergy.pdf`
  - `2405.08737_adaptive-time-stepping-two-time-kbe.pdf`
- 現行 backend では、まず reduced-Nambu 基底に整合する equal-time GKBA reference (`second_born_reference`) を Track A の第一段として採用する。

### Track B: scalable solver

- reference solver の検証後に GKBA もしくは auxiliary-Hamiltonian 系を導入する。
- 長時間・大きめの系はこちらで扱う。
- 主参照:
  - `1205.4427_gkba-inhomogeneous-systems.pdf`
  - `1312.0214_auxiliary-hamiltonian-dyson.pdf`
  - `1601.06415_auxiliary-hamiltonian-nonlocal-selfenergies.pdf`

現時点では Track A を優先し、Track B はその後に着手する。

---

## 5. 修繕フェーズ

### Phase R0: 凍結とラベリング

目的:
- 現状の `kbe_hfb` を「prototype」として明示し、過大な意味付けを止める。

作業:
- docs 上で、Phase E 実装を heuristic prototype として再判定する。
- `progress.md` に修繕計画へのリンクと再評価内容を追記する。
- 既存実装を壊さず、今後の比較対象として保持する。

受け入れ条件:
- docs 上で現状の意味づけが一貫する。
- Phase E 実装を「文献準拠 second Born」と断定する文言を除去する。

### Phase R1: numerical utility の整理

目的:
- generic routine の手書きを減らし、solver の見通しを改善する。

作業:
- `scipy` を導入する。
- 置換候補:
  - 手書き cumulative trapezoid -> `scipy.integrate.cumulative_trapezoid`
  - 化学ポテンシャル探索の二分法 -> `scipy.optimize.brentq`
  - 固定点混合の候補検討 -> Anderson / Broyden 系
- 共通 numerical utility module を導入する。

対象候補:
- `backend/app/solvers/noninteracting.py`
- `backend/app/solvers/nambu.py`
- `backend/app/solvers/kbe_hfb.py`

受け入れ条件:
- 同等のテストが維持される。
- root finding / quadrature の重複実装が削減される。

### Phase R2: solver 構造の再編

目的:
- `kbe_hfb.py` の責務集中を解消し、置換可能な構造にする。

作業:
- 以下のような分割を行う。
  - `contour.py`
  - `green_functions.py`
  - `self_energy_hfb.py`
  - `self_energy_second_born.py`
  - `quadrature.py`
  - `fixed_point.py`
  - `benchmarks/`
- API / storage / diagnostics と physics kernel を分離する。

受け入れ条件:
- `kbe_hfb.py` が orchestration 層に近い長さまで縮む。
- self-energy と contour marching が単体テスト可能になる。

### Phase R3: benchmark と収束検証

目的:
- 物理的に正しいかどうかを確認できる最小検証基盤を作る。

作業:
- 2x2 小サイズで Fock 空間全体角化 benchmark を追加する。
- 短時間ダイナミクスについて、非相互作用 / TDHFB / KBE-reference を比較する。
- `dt` 収束、adaptive tolerance 収束、memory window 依存を表で整理する。
- thermal / mixed branch の整合条件を test 化する。

受け入れ条件:
- exact diagonalization benchmark が backend test もしくは benchmark harness に追加される。
- `dt -> 0` に対する収束が少なくとも 1 系で確認される。

### Phase R4: KBE reference path の再実装

目的:
- heuristic closure ではなく、文献準拠の contour self-energy と causal marching を実装する。

作業:
- Nambu/Keldysh/Matsubara/mixed 成分の記法を固定する。
- HFB self-energy と second Born self-energy を明示的に書く。
- equal-time constraint、Hermiticity、causality、保存則を実装内で監視する。
- adaptive history integration は [2405.08737_adaptive-time-stepping-two-time-kbe.pdf](../pdfs/negf_kbe/2405.08737_adaptive-time-stepping-two-time-kbe.pdf) を主参照にする。

重要な判断:
- 現行の heuristic `second_born` を残す場合は `prototype` 扱いに落とす。
- 互換性維持のため、legacy の `second_born` は prototype として残し、reference path は `second_born_reference` として公開する。

受け入れ条件:
- short-time benchmark で exact / reference の比較が可能になる。
- `second_born_reference` と `second_born` prototype の数式上の意味が docs と code で一致する。

### Phase R5: 高速化と長時間実行

目的:
- correctness を維持したまま、長時間 run とやや大きい系へ対応する。

作業:
- profiling を取る。
- `numba` で hot loop を最適化する。
- 必要なら `scipy.sparse.linalg` を使って propagator / linear algebra を見直す。
- Green 関数保存を圧縮・窓切り出し対応にする。
- reference solver 検証後に GKBA / auxiliary-Hamiltonian 路線を検討する。

受け入れ条件:
- profiler で支配項が定量化されている。
- correctness を落とさずに速度改善が確認される。

---

## 6. ライブラリ採用方針

### 採用を推奨

- `scipy`
  - root finding
  - quadrature
  - sparse linear algebra
  - 必要に応じて ODE / nonlinear solver

### 条件付きで採用

- `numba`
  - loop 最適化専用
  - correctness 固定後に導入

### benchmark helper としてのみ検討

- `qutip`
  - 小サイズ exact benchmark 用
  - core solver には入れない

### 当面見送る

- generic quantum dynamics package を core KBE solver の代わりに採用する方針
  - 本プロジェクトの Nambu + contour + superconducting self-energy をそのまま置き換える既製 Python ライブラリは見当たらない

---

## 7. 優先順位

### 優先度 A

1. `progress.md` の再判定と本計画の作成
2. `scipy` 導入と hand-written numerical utility の整理
3. 2x2 exact benchmark の追加
4. `kbe_hfb` の分割と heuristic path の明示的な隔離

### 優先度 B

1. literature-faithful second Born self-energy の reference 実装
2. adaptive full-contour marching の再実装
3. thermal / mixed branch の再実装

### 優先度 C

1. profiling
2. `numba` / sparse 最適化
3. GKBA / auxiliary-Hamiltonian の別 solver 化

---

## 8. 完了条件

この修繕計画は、少なくとも次を満たした時点で第一段階完了とする。

1. `second_born` が heuristic closure ではなく、文献準拠の reference implementation になっている。
2. exact benchmark と `dt` 収束試験が存在する。
3. adaptive/fixed の比較が文書化されている。
4. thermal / mixed branch の整合条件が test で確認されている。
5. docs / code / diagnostics の用語が一致している。

---

## 9. 非目標

現段階では次を非目標とする。

- frontend の大規模改修
- 分散実行やクラスタ連携
- 現実物質向けの定量計算
- Phase E heuristic path の機能追加による延命
