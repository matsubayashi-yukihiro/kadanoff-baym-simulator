# バックエンド修繕計画

この文書は、2026-03-16 の backend 点検を受けて作成した修繕計画である。  
対象は主に `backend/app/solvers/` とその検証系であり、特に `kbe_hfb.py` の Phase E 相当実装を再設計する。

- 進捗の正本: [progress.md](./progress.md)
- 物理仕様の正本: [theory.md](./theory.md)
- 既存の実装計画: [implementation-plan.md](./implementation-plan.md)
- 参考文献束: [../pdfs/negf_kbe/README.md](../pdfs/negf_kbe/README.md)

運用メモ:
- 作業が完了したら、進捗状況を加筆する。
- 「作業が完了したら、進捗状況を加筆して、この指示自体も md に書き込んでおく」という指示は `docs/progress.md` に保持する。

### 2026-03-16 実施済み基盤作業

- R0 に対応して、現行 `second_born` / thermal / mixed branch を heuristic prototype として docs / diagnostics 上で明示した。
- R1 に対応して、`scipy` を導入し、累積 trapezoid と root finding を共通 utility に寄せた。
- R2 の足場として、`contour.py`、`green_functions.py`、`self_energy_second_born_prototype.py` を追加し、`kbe_hfb.py` を orchestration 層へ整理した。
- ただし、reference second Born self-energy 自体は未実装であり、R3-R5 は引き続き未完である。

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
3. `kbe_hfb` の heuristic Phase E 実装を、文献準拠の reference path へ置き換える。
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

- 文献準拠の full two-time KBE + second Born を Nambu 表現で実装する。
- 小サイズと短中時間を主対象にし、正しさの基準にする。
- 主参照:
  - `0906.1704`
  - `1902.07038`
  - `2405.08737`

### Track B: scalable solver

- reference solver の検証後に GKBA もしくは auxiliary-Hamiltonian 系を導入する。
- 長時間・大きめの系はこちらで扱う。
- 主参照:
  - `1205.4427`
  - `1312.0214`
  - `1601.06415`

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
- adaptive history integration は `2405.08737` を主参照にする。

重要な判断:
- 現行の heuristic `second_born` を残す場合は `prototype` 扱いに落とす。
- `second_born` の名前を reference implementation に予約することを推奨する。

受け入れ条件:
- short-time benchmark で exact / reference の比較が可能になる。
- `second_born` の数式上の意味が docs と code で一致する。

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
