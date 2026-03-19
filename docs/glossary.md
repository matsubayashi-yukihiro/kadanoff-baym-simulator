# 用語集

このファイルは、`docs/theory.md`、`docs/backend-remediation-plan.md`、`backend/app/solvers/` で繰り返し出てくる語を同じ意味で読むための最小用語集である。

- 理論仕様の正本: [theory.md](./theory.md)
- 文献索引: [literature-index.md](./literature-index.md)
- 式とコードの対応: [equation-to-code-map.md](./equation-to-code-map.md)

---

## 基本枠組み

### NEGF

Nonequilibrium Green's Function。  
非平衡多体系を Green 関数で記述する枠組み全体を指す。

### KBE

Kadanoff-Baym equations。  
Keldysh contour 上の Green 関数に対する運動方程式。`docs/theory.md` では理論上の基準形として扱う。

### Keldysh contour

実時間の往路・復路と、必要なら虚時間枝を合わせた時間経路。  
このプロジェクトでは、

- real-time branch
- Matsubara branch
- mixed branch

を明示的に区別する。

### conserving approximation

`\Phi`-derivable self-energy に基づく近似。  
粒子数やエネルギーなどの保存則を壊しにくい近似を指す。

---

## 研究 workflow artifact

### study

研究問い、baseline、対象 observable、acceptance check を束ねる最上位 artifact。  
このプロジェクトでは collaboration suite ではなく、solo researcher の research campaign 単位として使う。

### baseline preset

現在の validation scope と benchmark に照らして、
研究の出発点として使う preset。  
demo preset と同義ではない。

### decision note

観察、失敗理由、棄却判断、次アクションを短文で残す軽量 artifact。  
`observation` / `failure` / `decision` / `todo` を最小単位とする。

### evidence bundle

figure、table、claim candidate を支える run / analysis / validation scope を束ねる artifact。  
証跡整理の単位であり、validated 判定そのものではない。

### claim candidate

まだ最終 claim として確定していない主張候補。  
`evidence bundle` で source artifact と validation scope を束ねて管理する。

### run role

研究文脈でその run をどう読むかを表す metadata。  
v1 では `baseline`, `candidate`, `control`, `numerical_check` を使う。

### validation status

study 局所での run や artifact の扱いを示す metadata。  
v1 では `unchecked`, `screening`, `accepted`, `rejected` を使う。

重要:
- これは `docs/validation-spec.md` の `validated` / `partially validated` / `prototype only` / `not validated` と別物である。
- `accepted` な run が、solver path 全体として `validated` であることを意味しない。

### comparison kind

`job group` が何を比較しているかを表す metadata。  
v1 では `physics_hypothesis`, `numerical_validation`, `regression` を使う。

### parameter kind

`sweep` がどの種の parameter を走査しているかを表す metadata。  
v1 では `physics`, `numerical`, `analysis` を使う。

---

## 行列と基底

### Nambu 表現

粒子と hole をまとめた表現。  
このコードベースでは site basis を使い、`2 * site_count` 次元の Nambu 行列を使う。

### normal density

一般化密度行列の左上ブロック。  
通常の一体密度行列に対応する。

### pairing tensor

一般化密度行列の右上ブロック。  
異常平均 `\langle c c \rangle` に対応する。

### generalized density

normal density と pairing tensor をまとめた Nambu 行列。  
TDHFB / KBE の等時情報として実装上もっともよく使う。

### pairing field

pairing tensor から self-consistency で決まる anomalous field。  
on-site と bond の両方を取りうる。

### BdG Hamiltonian

normal Hamiltonian と pairing field をまとめた Nambu 一体ハミルトニアン。  
コードでは `bdg_hamiltonian` の名前で出てくる。

---

## Green 関数成分

### lesser Green 関数 `G^<`

等時極限から density を再構成する成分。  
このコードでは `-1j * G^<(t,t)` が generalized density に対応する。

### greater Green 関数 `G^>`

`G^<` と対になる Keldysh 成分。  
prototype / reference の second Born self-energy では collision integral の構成に使う。

### retarded Green 関数 `G^R`

因果性を持つ propagator。  
上三角がゼロであることが causality diagnostics の対象になる。

### advanced Green 関数 `G^A`

`G^R` の随伴で与えられる成分。  
コードでは明示保存せず、Hermiticity や再構成から扱うことが多い。

### Matsubara branch

虚時間 `\tau` 上の Green 関数。  
熱平衡初期状態を扱うための枝。

### mixed branch

片方が実時間、片方が虚時間の Green 関数。  
初期相関のメモリーを real-time propagation に渡すために使う。

---

## Self-energy と近似

### HFB self-energy

Hartree と pairing field を合わせた時間局所の自己エネルギー。  
このプロジェクトでは KBE の最小極限であり、TDHFB と整合する。

### second Born self-energy

相互作用の 2 次摂動までを入れた自己エネルギー。  
`docs/theory.md` では理論基準として扱うが、コード上では mode によって意味が分かれる。

### `second_born` prototype

heuristic closure を使う legacy path。  
docs 上では prototype と明示し、reference implementation とは区別する。

### `second_born_reference`

現在の reference path。  
explicit self-energy を使う equal-time GKBA causal marching として実装されている。full contour second Born そのものではない。

### Hartree 項

density に比例する時間局所の対角ポテンシャル。  
コードでは `hartree_potential` や `hartree` の名前で現れる。

### Fock 項

交換に由来する項。  
このプロジェクトでは一般論として理論文書に出てくるが、現状の格子実装では on-site / nearest-neighbor の closure に応じて陽な実装範囲が限定される。

### collision integral

KBE の右辺に現れる履歴積分。  
散乱とメモリーを表す。

### causal marching

過去時刻だけを使って新しい時間行・列を前進更新するやり方。  
prototype / reference ともにこの語を diagnostics に使う。

### memory window

履歴積分で過去をどこまで保持するかの窓。  
長時間計算の近似や高速化で重要になる。

### history integration order

履歴積分の数値積分次数。  
adaptive KBE の主要パラメータの一つ。

---

## 単時間近似と thermal 初期化

### GKBA

Generalized Kadanoff-Baym Ansatz。  
二時刻 Green 関数を等時 density と propagator から再構成する単時間近似。

### equal-time GKBA

GKBA を使って等時密度行列の運動方程式へ落とした実装上の扱い。  
`second_born_reference` はこのスコープに属する。

### factorized branch

Matsubara / mixed branch を HFB seed から分離形で作る近似。  
reference path の thermal / mixed branch は現状この扱い。

### thermal branch

Matsubara branch を使って熱平衡初期状態を準備する処理全体を指すこともある。  
config では `thermal_branch.enabled` で制御する。

---

## 観測量と診断

### pairing observable

観測量としての pairing。  
`pairing`, `pairing_s`, `pairing_d` を返す。

### equal-time constraint

`G^<(t,t)` と generalized density が一致する拘束。  
`max_equal_time_density_reconstruction_error` で監視する。

### Hermiticity diagnostics

Green 関数や generalized density の随伴対称性の残差。  
`max_lesser_hermiticity_error` など。

### causality diagnostics

retarded Green 関数の上三角成分がゼロであることの残差。  
`max_retarded_causality_error` で監視する。

### exact diagonalization benchmark

小サイズ系で Fock 空間全体を角化し、solver の short-time benchmark に使う基準解。

---

## 運用ルール

- docs や issue で `second_born` と書くときは、prototype か reference かを必ず明記する。
- `reference` という語だけでは full contour second Born を意味しない。現状は `second_born_reference` を指す。
- `validation status` と `validated` を混同しない。
- `evidence bundle` を作っても physics claim が自動承認されたことにはならない。
- 新しい略語を導入したら、このファイルに 2 行でもよいので足しておく。
