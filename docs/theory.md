# 非平衡超伝導の時間発展ソルバー基盤
## ― 2 次元格子電子系を基準とし、拡張 Hubbard と electron-phonon 系を接続する ―

---

# 1. 研究背景

相関電子系の非平衡ダイナミクスは、超短パルス光実験の発展により重要な研究対象となっている。

代表的な現象として

- 光誘起超伝導
- 非平衡モット転移
- 非平衡秩序パラメータの振動（Higgs mode）
- 光照射後の緩和・熱化
- 高次高調波発生

などが挙げられる。

これらを理論的に記述するには

- 電子相関
- 非平衡時間発展
- 散乱・緩和
- 超伝導秩序
- 必要に応じて格子自由度

を同時に扱う枠組みが必要になる。

ただし、これらすべてを単一の近似で定量的に扱えるわけではない。
特に深い Mott 領域や非摂動的強結合ダイナミクスには、
非平衡 DMFT などのより強力な枠組みが必要になることが多い。

本プロジェクトでは、

- 2 次元格子系
- 光励起後の短中時間 transient
- 弱〜中間結合で制御可能な近似
- 超伝導秩序の時間発展

を主対象とし、その範囲で妥当なソルバーを構築する。

そのための最も体系的な方法の一つが

**非平衡グリーン関数法 (Nonequilibrium Green's Function; NEGF)**  
であり、その運動方程式が

**Kadanoff-Baym 方程式 (KBE)**

である。

---

# 2. 本プロジェクトの目的

本研究の目的は

> 光照射などの時間依存外場を受ける 2 次元格子系に対し、  
> 非平衡超伝導ダイナミクスを扱える汎用的な時間発展ソルバー基盤を構築すること

である。

特に以下を重視する。

- 非平衡多体論を **正面から扱う**
- 超伝導秩序を扱える枠組み
- 弱〜中間結合での散乱と緩和を扱える
- 数値実装として検証可能な構造
- 将来の electron-phonon 拡張に耐える設計

そのために

**Kadanoff-Baym 方程式を理論の基準形とする。**

---

## 2.1 プロジェクトの構造

本プロジェクトは、単一の模型に固定されたコードを書くのではなく、
以下の三層からなる構造として設計する。

### Core platform

- 時間依存一体ハミルトニアン
- Nambu 表現
- TDHFB / BdG
- full two-time KBE
- 観測量評価
- 検証インフラ

を共有する共通基盤。

### Mainline baseline

**2 次元拡張 Hubbard 模型**

- 電子のみの有効模型
- 最近接引力から生じる bond pairing
- 弱〜中間結合
- HFB および自己無撞着 second Born

を、最初の基準問題として実装する。

### Subproject

**electron-phonon 相互作用を起源とする超伝導ダイナミクス**

- Holstein 模型
- SSH 模型
- Hubbard-Holstein 模型

などを用いて、
格子媒介引力や光応答を同じ数値基盤の上で調べる。

したがって、本プロジェクトの主眼は

> 「拡張 Hubbard のみの専用ソルバー」ではなく、  
> 「非平衡超伝導を扱う共通ソルバー基盤を構築し、その最初の具体例として拡張 Hubbard を採用する」

ことにある。

---

## 2.2 本プロジェクトの守備範囲

本プロジェクトが共通基盤として直接に扱うのは、以下の問題である。

- 空間一様な電磁場で駆動される 2 次元格子系
- ポンプ後の短中時間ダイナミクス
- 閉鎖系として扱える時間発展
- Nambu 表現による超伝導秩序の記述
- HFB と摂動的メモリー自己エネルギーの接続

ここで「閉鎖系」とは、各サブプロジェクトで
**明示的にシミュレートする自由度全体**
が閉じているという意味である。

- baseline の拡張 Hubbard では電子系のみが閉鎖系
- electron-phonon サブプロジェクトでは電子 + 格子系全体が閉鎖系

と考える。

一方、以下は初期段階では対象外とする。

- 深い Mott 絶縁体や非摂動的強結合
- 浴やリードにより維持される非平衡定常状態
- 非局所スクリーニングや GW 型補正
- 現実物質に対する定量予測

---

## 2.3 初期実装での優先順位

共通基盤を保ったまま、初期段階では以下を優先する。

1. 非相互作用の時間発展
2. TDHFB / BdG
3. KBE + HFB
4. KBE + second Born
5. 拡張 Hubbard における bond pairing と d-wave 成分

electron-phonon 系はこの主線の上に載るサブプロジェクトとして段階的に追加する。

---

# 3. ソルバー設計思想

KBE ソルバーは実装難度が高く、直接実装すると

- バグ検出が困難
- 数値不安定性
- 初期化問題
- 物理的な切り分けの難しさ

などの問題が起きやすい。

そのため本研究では

**二種類のソルバーを並行して実装する。**

---

## 3.1 平均場ソルバー (TDHFB / BdG)

相互作用を平均場分解し

- Hartree-Fock-Bogoliubov
- time-dependent BdG

として解く。

特徴

- 実装が軽い
- 2 次元系を直接扱える
- 超伝導秩序の時間発展を可視化しやすい
- KBE 実装の検証基準になる

ただし

- 散乱
- 緩和
- 非局所時間メモリー
- フォノン媒介相互作用の本来の遅延性

は基本的に入らない。

---

## 3.2 非平衡多体ソルバー (Kadanoff-Baym)

閉時間経路上の Dyson 方程式から

**Kadanoff-Baym 方程式**

を解く。

特徴

- 散乱と緩和が自然に入る
- conserving approximation が使える
- 非平衡多体論として体系的
- 将来、電子・格子双方の Green 関数へ拡張できる

ただし

- 二時刻関数
- 計算量増大
- 実装が難しい

という重さがある。

本プロジェクトの baseline では、
KBE 側に採用する自己エネルギーはまず HFB、
次に自己無撞着 second Born とする。
したがって baseline の物理的守備範囲は、
平均場に散乱とメモリーを摂動的に付加した
弱〜中間結合ダイナミクスにある。

---

## 3.3 GKBA の位置づけ

**Generalized Kadanoff-Baym Ansatz (GKBA)** は、
二時刻グリーン関数を等時密度行列
\(\rho(t)\equiv -iG^<(t,t)\)
と retarded/advanced propagator から近似的に再構成する
単時間近似である。例えば lesser 成分は
$$
G^<(t,t')
\approx
-G^R(t,t')\rho(t')
+\rho(t)G^A(t,t')
$$
の形で与えられる。

この近似により、full two-time KBE に比べて
メモリー使用量と計算量を大きく削減できるため、
長時間伝播やより大きな系に有利である。
一方で GKBA は、自己エネルギー近似とは別に
二時刻構造そのものに追加近似を導入する方法である。

したがって本プロジェクトでは、

- 理論の基準形
- 実装検証の基準

はあくまで full two-time KBE に置き、
GKBA はその上に載る **計算軽量化の将来拡張**
として位置づける。
特に second Born や将来の electron-phonon 自己エネルギーを用いた
長時間・大規模計算が必要になった段階で導入候補とする。

参考: [Hermanns, Balzer, Bonitz, "Non-equilibrium Green's function approach to inhomogeneous quantum many-body systems using the Generalized Kadanoff Baym Ansatz"](../pdfs/1205.4427v1.pdf)

---

# 4. 共通ソルバーの設計層

将来拡張を見据えると、
ソルバーは「模型ごとの専用実装」ではなく
以下の層に分けて設計するのが自然である。

---

## 4.1 One-body 層

この層では

- 格子形状
- ホッピング
- 境界条件
- 化学ポテンシャル
- Peierls 置換による光照射
- 必要なら格子変位によるホッピング変調

を扱う。

ここは拡張 Hubbard と electron-phonon 系で最大限共有する。

---

## 4.2 Propagator 層

この層では

- 単粒子波動関数の時間発展（TDHFB / BdG）
- 一般化密度行列
- two-time Green 関数
- Nambu 表現

を扱う。

ここがソルバーの中心であり、相互作用の起源に依らず再利用される。

---

## 4.3 Interaction / self-energy 層

この層では、模型ごとの差が最も強く現れる。
例えば

- 拡張 Hubbard の HFB
- 局所 Hubbard \(U\) の second Born
- 遅延有効相互作用 \(V_{\rm eff}(t,t')\)
- electron-phonon 由来の自己エネルギー

を実装する。

したがって、pairing の起源をコード本体に埋め込まず、
**closure を差し替え可能な構造**
にすることが重要である。

---

## 4.4 Boson 層

electron-phonon サブプロジェクトのために、
基盤設計として boson 層を持たせる。

この層には少なくとも三段階がある。

- なし
- 古典格子変位 \(X(t)\) を持つ Ehrenfest 型
- 量子フォノン Green 関数 \(D(z,z')\) を持つ NEGF 型

初期段階では boson 層を空実装または古典場として設計し、
将来の量子フォノン拡張に備える。

---

## 4.5 Observable 層

観測量として

- 粒子密度
- 電流
- エネルギー
- オンサイトおよび bond pairing
- form factor 射影した \(s\)-wave / \(d\)-wave 成分
- ペア相関関数
- フォノン変位やそのエネルギー

を統一的に扱う。

---

# 5. 対象模型の共通記述

模型族全体を包む共通形として、
ハミルトニアンを

$$
H(t)=H_{\rm el}^{(1)}(t)+H_{\rm int}^{\rm (el)}+H_{\rm bos}+H_{\rm el\text{-}bos}
$$

と書く。

ここで

- \(H_{\rm el}^{(1)}\): 電子の時間依存一体部分
- \(H_{\rm int}^{\rm (el)}\): 電子間相互作用
- \(H_{\rm bos}\): 格子や他のボース自由度
- \(H_{\rm el\text{-}bos}\): 電子-ボース結合

である。

このうち baseline の拡張 Hubbard では
\(H_{\rm bos}=H_{\rm el\text{-}bos}=0\) となる。

---

## 5.1 共通の電子一体部分

電子部分は

$$
H_{\rm el}^{(1)}(t)
=
-\sum_{ij,\sigma}
T_{ij}(t)c^\dagger_{i\sigma}c_{j\sigma}
-\mu\sum_{i,\sigma}n_{i\sigma}
$$

とする。

ここで \(T_{ij}(t)\) は

- 外場による Peierls 位相
- 必要なら格子歪みによるホッピング変調

を含めた有効 hopping である。

---

## 5.2 Baseline: 2 次元拡張 Hubbard 模型

最初の具体的な基準模型は

$$
H_{\rm int}^{\rm (el)}
=
U\sum_i n_{i\uparrow}n_{i\downarrow}
+
\frac12\sum_{i\neq j}V_{ij}n_in_j
$$

で与えられる 2 次元拡張 Hubbard 模型である。

標準設定では
$$
V_{ij}
=
\begin{cases}
V_1 & (i,j \text{ が最近接})\\
0 & \text{otherwise}
\end{cases},
\qquad
U\ge 0,\quad V_1<0
$$
とし、最近接引力から生じる spin-singlet bond pairing を主対象とする。

この模型は

- 非平衡超伝導のダイナミクス
- 実空間での bond 秩序
- d-wave form factor
- HFB と second Born の接続

を検証する基準問題として適している。

---

## 5.3 Subproject: electron-phonon 起源模型

pairing の起源そのものを明示したい場合には、
electron-phonon 模型を扱う。

代表例は

- Holstein 模型
- SSH 模型
- Hubbard-Holstein 模型

である。

### Holstein 型

量子フォノンなら
$$
H_{\rm bos}=\Omega\sum_i b_i^\dagger b_i,
\qquad
H_{\rm el\text{-}bos}
=
g\sum_i (b_i+b_i^\dagger)n_i
$$

と書ける。

古典変位なら
$$
H_{\rm bos}
=
\sum_i\left(
\frac{P_i^2}{2M}+\frac{K}{2}X_i^2
\right),
\qquad
H_{\rm el\text{-}bos}=g\sum_i X_i n_i
$$

である。

Holstein 型は自然には on-site \(s\)-wave pairing に結びつきやすい。

### SSH 型

結合やホッピングの変調として
$$
T_{ij}(t)\to T_{ij}(t)+\alpha\,u_{ij}(t)
$$

のように入る模型であり、
bond 秩序や非局所 pairing と相性が良い。
したがって、本プロジェクトの baseline である
bond pairing / d-wave 指標との接続は
Holstein より SSH 型の方が自然な場合がある。

### Hubbard-Holstein 型

電子相関と格子媒介引力を同時に扱うための中間的模型であり、
将来の比較対象として有用である。

---

## 5.4 「超伝導形成」をどう定義するか

electron-phonon サブプロジェクトでは、
「超伝導形成」という言葉を二段階に分けて扱う必要がある。

### A. 有効引力の生成

格子自由度を消去したときに、電子間に実効的な引力が現れること。

### B. 超伝導秩序の形成

その結果として
$$
\Delta(t)=\langle c_\downarrow(t)c_\uparrow(t)\rangle
$$
または対応する bond pairing や pair correlation が成長すること。

baseline の拡張 Hubbard は A を有効模型として仮定し、
B のダイナミクスを扱う。
一方、electron-phonon サブプロジェクトでは
A から B までの接続を視野に入れる。

ただし平均場だけでは、
完全に対称性を保った有限系から
\(\Delta\) が厳密に自発形成するとは限らない。
実務上は

- 微小 seed を入れる
- 既に対称性の破れた枝から始める
- ペア相関の増大を観測する

という形で定義を明確にする。

---

# 6. 光照射の導入

外場は時間ゲージ \(\phi=0\) を仮定し、
空間一様なベクトルポテンシャル \(\mathbf A(t)\) を
Peierls 置換で導入する。

$$
T_{ij}(t)
=
t_{ij}
\exp\left(
-i\frac{e}{\hbar}
\int_{\mathbf r_j}^{\mathbf r_i}
\mathbf A(t)\cdot d\mathbf l
\right)
$$

ここで \(e>0\) は電荷素量であり、
一様場では積分は
\(\mathbf A(t)\cdot(\mathbf r_i-\mathbf r_j)\) に簡約される。
電場は

$$
\mathbf E(t)=-\partial_t\mathbf A(t)
$$

で与えられる。

baseline の拡張 Hubbard では、外場は電子一体部分にのみ入る。
electron-phonon サブプロジェクトでは将来的に

- 電子への Peierls 駆動
- 赤外活性モードの直接駆動
- 光で誘起される格子変位

なども検討対象になりうるが、初期実装ではまず電子駆動を標準とする。

Peierls 置換を用いる以上、
観測量として比較すべき電流は
**ベアな運動量ではなく、Peierls 位相を含んだ hopping から構成される
ゲージ整合的な電流**
である。
したがって、KBE ソルバーの検証では

- ゲージ整合的な bond current の実装
- 連続の式との整合
- パルス後のエネルギー保存

を必須の品質確認項目とする。

---

# 7. 非平衡グリーン関数

## 7.1 閉時間経路

非平衡問題では時間発展を

**Keldysh contour**

上で定義する。

$$
\mathcal C=\mathcal C_+\cup\mathcal C_-\cup\mathcal C_{\rm M}
$$

ここで \(\mathcal C_+\) と \(\mathcal C_-\) は実時間の往復枝、
\(\mathcal C_{\rm M}\) は熱初期状態
\(\rho_0\propto e^{-\beta(H-\mu N)}\)
を表す虚時間枝である。

相関した熱平衡初期状態を使う場合には \(\mathcal C_{\rm M}\) を含める。
一方、初期実装では

- factorized 初期状態
- HFB 熱平衡状態

から開始する Keldysh-only の計算も許す。
この場合、second Born や将来の electron-phonon 自己エネルギーは
\(t_0\) 以降の相関生成を記述するが、
相互作用を含んだ厳密熱平衡初期状態とは一致しない。

---

## 7.2 電子グリーン関数

$$
G_{ij,\sigma\sigma'}(z,z')
=
-i
\langle
T_{\mathcal C}
c_{i\sigma}(z)
c_{j\sigma'}^\dagger(z')
\rangle
$$

実時間成分は

lesser
$$
G^<_{ij,\sigma}(t,t')
=
i
\langle
c_{j\sigma}^\dagger(t')
c_{i\sigma}(t)
\rangle
$$

greater
$$
G^>_{ij,\sigma}(t,t')
=
-i
\langle
c_{i\sigma}(t)
c_{j\sigma}^\dagger(t')
\rangle
$$

retarded
$$
G^R_{ij,\sigma}(t,t')
=
\theta(t-t')
\left(G^>_{ij,\sigma}(t,t')-G^<_{ij,\sigma}(t,t')\right)
$$

advanced
$$
G^A(t,t')=[G^R(t',t)]^\dagger
$$

で与えられる。

---

## 7.3 Nambu 表現

スピン一重項超伝導を扱うため

$$
\Psi_i=
\begin{pmatrix}
c_{i\uparrow}\\
c^\dagger_{i\downarrow}
\end{pmatrix}
$$

を導入し、Nambu グリーン関数

$$
\mathbf G_{ij}(z,z')
=
\begin{pmatrix}
G_{ij,\uparrow}(z,z') & F_{ij}(z,z')\\
\bar F_{ij}(z,z') & \bar G_{ij}(z,z')
\end{pmatrix}
$$

を用いる。

ここで
$$
F_{ij}(z,z')
=
-i\langle T_{\mathcal C}c_{i\uparrow}(z)c_{j\downarrow}(z')\rangle
$$
$$
\bar F_{ij}(z,z')
=
-i\langle T_{\mathcal C}c^\dagger_{i\downarrow}(z)c^\dagger_{j\uparrow}(z')\rangle
$$
$$
\bar G_{ij}(z,z')
=
-i\langle T_{\mathcal C}c^\dagger_{i\downarrow}(z)c_{j\downarrow}(z')\rangle
=
-G_{ji,\downarrow}(z',z)
$$
である。

実時間成分では
$$
\mathbf G^A(t,t')=[\mathbf G^R(t',t)]^\dagger,
\qquad
[\mathbf G^<(t,t')]^\dagger=-\mathbf G^<(t',t)
$$
を満たす。

異常成分 \(F_{ij}\) と異常自己エネルギー \(\Delta_{ij}\) は、
模型と closure に応じて

- オンサイト
- bond
- 遅延カーネルを持つ有効相互作用

のいずれにもなりうる。
したがって共通基盤では、
pairing channel を on-site にも bond にも固定しない。

---

## 7.4 将来のボース Green 関数

electron-phonon の量子的取り扱いに進む場合には、
フォノン変位演算子 \(X_i\) に対して

$$
D_{ij}(z,z')
=
-i\langle T_{\mathcal C}X_i(z)X_j(z')\rangle
$$

を導入する。

初期段階ではこの boson Green 関数は未実装でよいが、
理論上の拡張先として明示しておく。

---

# 8. Dyson 方程式と Kadanoff-Baym 方程式

## 8.1 電子 Dyson 方程式

閉時間経路上の Dyson 方程式は

$$
(i\partial_z-h(z))G(z,z')
=
\delta_{\mathcal C}(z,z')
+
\int_{\mathcal C}
\Sigma(z,\bar z)
G(\bar z,z')
d\bar z
$$

である。

Nambu 表現では

$$
(i\partial_z\tau_0-\mathbf h)\mathbf G
=
\delta
+
\mathbf\Sigma\circ\mathbf G
$$

と書く。

ここで
\((\mathbf A\circ\mathbf B)(z,z')
=
\int_{\mathcal C}d\bar z\,\mathbf A(z,\bar z)\mathbf B(\bar z,z')\)
であり、
標準的な Nambu 一体ハミルトニアンは

$$
\mathbf h_{ij}(t)
=
\begin{pmatrix}
h_{ij\uparrow}(t) & 0\\
0 & -h_{ji\downarrow}(t)
\end{pmatrix}
$$

と書ける。

---

## 8.2 Kadanoff-Baym 方程式

Langreth 分解により、実時間成分は例えば

$$
\begin{aligned}
(i\partial_t-h(t))G^{</>}(t,t')
=&
\int_{t_0}^{t} d\bar t\,
\Sigma^R(t,\bar t)G^{</>}(\bar t,t') \\
&+
\int_{t_0}^{t'} d\bar t\,
\Sigma^{</>}(t,\bar t)G^A(\bar t,t')
+
I^{\rceil}(t,t')
\end{aligned}
$$

$$
\begin{aligned}
G^{</>}(t,t')(-i\overleftarrow{\partial}_{t'}-h(t'))
=&
\int_{t_0}^{t} d\bar t\,
G^R(t,\bar t)\Sigma^{</>}(\bar t,t') \\
&+
\int_{t_0}^{t'} d\bar t\,
G^{</>}(t,\bar t)\Sigma^A(\bar t,t')
+
I^{\lceil}(t,t')
\end{aligned}
$$

$$
(i\partial_t-h(t))G^R(t,t')
=
\delta(t-t')
+
\int_{t'}^{t} d\bar t\,
\Sigma^R(t,\bar t)G^R(\bar t,t')
$$

を満たす。

ここで \(I^{\rceil},I^{\lceil}\) は虚時間枝に由来する初期相関項であり、
factorized 初期状態や平均場初期化では消える。

---

## 8.3 将来のボース Dyson 方程式

量子フォノンまで扱う場合には、
boson Green 関数 \(D\) に対しても contour Dyson 方程式

$$
D=D_0+D_0\circ\Pi\circ D
$$

を解く必要がある。

ここで \(\Pi\) はフォノン自己エネルギーである。
この段階では

- 電子 Green 関数 \(G\)
- フォノン Green 関数 \(D\)
- 電子自己エネルギー \(\Sigma_{\rm ep}\)
- フォノン自己エネルギー \(\Pi\)

が連成する。

これは本プロジェクトの将来拡張であり、
初期版では対象外だが、理論的な到達点として重要である。

---

# 9. 自己エネルギー近似と closure

## 9.1 Baseline: 拡張 Hubbard の HFB

平均場極限では

$$
\Sigma(z,z')=\Sigma^{\rm HFB}(z)\delta_{\mathcal C}(z,z')
$$

とする。

baseline の標準 decoupling では、
常伝導成分は Hartree 項、
異常成分は最近接結合上の singlet pairing 項とする。
具体的には

$$
\Sigma^{\rm H}_{i\sigma}(t)
=
U\,n_{i\bar\sigma}(t)
+
\sum_l V_{il}n_l(t)
$$

$$
\Delta_{ij}(t)
=
-iV_{ij}F_{ij}^<(t,t)
\qquad
((i,j)\text{ は pairing を残す結合})
$$

とし、Nambu 表現では

$$
\mathbf\Sigma^{\rm HFB}_{ij}(t)
=
\begin{pmatrix}
\delta_{ij}\Sigma^{\rm H}_{i\uparrow}(t) & \Delta_{ij}(t)\\
\Delta^\dagger_{ij}(t) & -\delta_{ij}\Sigma^{\rm H}_{i\downarrow}(t)
\end{pmatrix}
$$

と書ける。

将来的に結合 Fock 項を追加する場合には、
左上・右下ブロックは空間的に非局所になる。

---

## 9.2 Baseline: 局所 Hubbard \(U\) の second Born

baseline の beyond-mean-field 第一段階では

$$
\Sigma=\Sigma^{\rm HFB}+\Sigma^{(2)}
$$

とし、\(\Sigma^{(2)}[G]\) は
二次の骨格図から得られる時間非局所なメモリー自己エネルギーとする。
自己無撞着に解けば conserving approximation になる。

ここでは \(\Sigma^{(2)}\) は
局所 Hubbard 相互作用 \(U\) に由来する図のみを採用する。
したがって baseline では

- \(V_{ij}\) はまず HFB レベルで pairing を担う
- \(V_{ij}\) に由来する二次図は入れない
- 非局所スクリーニングや GW 型補正は守備範囲外

とする。

常伝導成分の概形としては

$$
\Sigma_{\sigma}^{(2)}(1,2)
\sim
U^2
G_{\sigma}(1,2)
G_{\bar\sigma}(1,2)
G_{\bar\sigma}(2,1)
$$

であり、超伝導状態ではこれを Nambu 行列表式に拡張する。

この近似が信頼できるのは、
少なくとも deep Mott 極限から離れた弱〜中間結合領域である。

---

## 9.3 Subproject A: 古典格子 + Ehrenfest 連成

最初の electron-phonon サブプロジェクトとしては、
格子変位を古典変数として扱うのが最も現実的である。

例えば Holstein 型なら

$$
M\ddot X_i(t)=-KX_i(t)-g\langle n_i(t)\rangle
$$

を電子ダイナミクスと連成して解く。

この枠組みで見やすいのは

- コヒーレントフォノン
- 電子分布の格子応答
- 既存の超伝導状態の増幅・抑制
- 光照射後の \(\Delta(t)\) と \(X(t)\) の連成振動

である。

ただし重要なのは、
**古典格子変位 \(X_i(t)\) が対角密度結合にしか入らない場合、
それだけでは phonon-mediated pairing の起源を完全には表現しない**
という点である。

したがってこの段階は主として

- 既存または seed 付き秩序の制御
- 格子応答によるパラメータ変調

を見るためのサブプロジェクトとして位置づける。

---

## 9.4 Subproject B: 遅延有効相互作用の観点

格子自由度を積分消去すると、
電子間には遅延を持つ有効相互作用

$$
V_{\rm eff}(t,t')
$$

が現れる。

この観点では pairing field は概念的に

$$
\Delta_i(t)
\sim
\int dt'\,
V_{\rm eff}(t,t')
\langle c_{i\downarrow}(t')c_{i\uparrow}(t')\rangle
$$

のような形になる。

これは BCS 起源により近いが、

- 遅延カーネル
- 二時刻構造
- 初期相関

が本質的になる。

したがって、phonon-mediated attraction を
理論的にきちんと扱う最小拡張としては、
この retarded interaction の導入が重要である。

---

## 9.5 Subproject C: 量子フォノン自己エネルギー

さらに本格的に進む場合には、
量子フォノンを保持して

- 電子自己エネルギー \(\Sigma_{\rm ep}\sim g^2 D G\)
- フォノン自己エネルギー \(\Pi\)
- 必要に応じて異常自己エネルギー

を二時刻で扱う必要がある。

これは非平衡 Migdal-Eliashberg 的な方向に接続する。
一方で計算コストと実装難度は大きく上がるため、
共通基盤の将来拡張と位置づける。

---

# 10. 両ソルバーの関係

本研究では

> **HFB 自己エネルギーを閉時間経路上で時間局所とした KBE の等時極限が TDHFB に一致する**

として位置づける。

具体的には

$$
\Sigma(z,z')=\Sigma^{\rm HFB}(z)\delta_{\mathcal C}(z,z')
$$

とすると、Dyson 方程式は時間局所な有効 BdG ハミルトニアン
\(\mathcal H_{\rm BdG}(z)=h(z)+\Sigma^{\rm HFB}(z)\)
で閉じる。
その等時一般化密度行列

$$
\mathcal R(t)\equiv -i\,\mathbf G^<(t,t)
$$

は

$$
i\partial_t \mathcal R(t)
=
[\mathcal H_{\rm BdG}[\mathcal R(t)],\mathcal R(t)]
$$

を満たし、これが TDHFB 方程式である。

したがって

- TDHFB
- KBE (HFB self-energy)

の一致は、baseline のみならず
将来のサブプロジェクトに対しても
実装検証の中核になる。

ただし、この一致は初期状態も同じ平均場密度行列から構成した場合に限る。
虚時間枝を含む場合には、両者とも同じ HFB 熱平衡状態から初期化する。

---

# 11. 観測量

粒子密度

$$
n_{i\sigma}(t)=-iG_{ii,\sigma}^<(t,t),
\qquad
n_i(t)=\sum_\sigma n_{i\sigma}(t)
$$

粒子電流

$$
J_{i\to j}(t)
=
\frac{2}{\hbar}
\operatorname{Re}
\sum_\sigma
\left[
T_{ij}(t)G_{ji,\sigma}^<(t,t)
\right]
$$

で定義すると、連続の式
$$
\partial_t n_i(t)+\sum_j J_{i\to j}(t)=0
$$
を満たす。
電荷電流は \(j^{\rm ch}_{i\to j}(t)=-e\,J_{i\to j}(t)\) である。

ここで重要なのは、
Peierls 位相を含む \(T_{ij}(t)\) と
equal-time lesser Green 関数の組
\(T_{ij}(t)G_{ji}^<(t,t)\) が
ゲージ整合的な組み合わせになっていることである。
したがって、実装上の電流評価は

- ベアな \(\langle c_i^\dagger c_j\rangle\) 単体ではなく
- 必ず hopping 位相を含んだ bond current

として行う。

空間平均したマクロ電流や光学応答も、
この bond current を集約して定義する。

---

## 11.1 エネルギー

閉鎖系では、全エネルギー

$$
E_{\rm tot}(t)=\langle H(t)\rangle
$$

が重要な検証量である。

baseline の拡張 Hubbard では

$$
E_{\rm tot}(t)=E_{\rm kin}(t)+E_{\rm int}(t)
$$

であり、electron-phonon サブプロジェクトでは

$$
E_{\rm tot}(t)=E_{\rm el}(t)+E_{\rm bos}(t)+E_{\rm el\text{-}bos}(t)
$$

を用いる。

時間依存外場が存在する区間では、
一般にはエネルギーは保存せず、
外場のする仕事
\(\langle \partial_t H(t)\rangle\)
と整合する必要がある。
一方、パルス終了後に \(\mathbf A(t)\) が時間一定となる区間では、
近似に応じた意味で
\(E_{\rm tot}(t)\) が数値誤差の範囲で保存することを
必須検証項目とする。

---

## 11.2 超伝導秩序

超伝導秩序指標は、
closure に応じて複数の形を持つ。

### オンサイト成分

引力的な on-site pairing channel を明示的に持つ場合には

$$
\Delta_i(t)=-iU_{\rm pair}F_{ii}^<(t,t)
$$

で与えられる。

### Bond 成分

拡張相互作用や SSH 型結合から生じる bond 秩序は

$$
\Delta_{ij}(t)=-iV_{ij}^{\rm pair}F_{ij}^<(t,t)
\qquad (i\neq j)
$$

で表す。

### Form factor 射影

\(d\)-wave 成分は例えば

$$
\Delta_d(i,t)
=
\frac14\left[
\Delta_{i,i+\hat x}
+\Delta_{i,i-\hat x}
-\Delta_{i,i+\hat y}
-\Delta_{i,i-\hat y}
\right]
$$

のような線形結合として定義する。

共通基盤では、\(s\)-wave / \(d\)-wave / bond / on-site を
観測量レベルで柔軟に切り替えられるようにする。

---

## 11.3 Pair correlation と boson 量

electron-phonon サブプロジェクトでは、
異常平均だけでなく

- pair correlation
- pairing susceptibility
- 格子変位 \(X_i(t)\)
- フォノンエネルギー

も重要な観測量である。

特に、retarded interaction をまだ明示的に扱っていない段階では、
「秩序パラメータの自然形成」よりも
「ペア相関の増大」や
「既存秩序の増幅」
を主要な指標にするのが現実的である。

---

# 12. 数値実装の基本構造

時間離散化

$$
t_n=t_0+n\Delta t
$$

未知量

$$
G(t_n,t_m)
$$

メモリー積分

$$
\int_{t_0}^{t_n}
\Sigma(t_n,\bar t)
G(\bar t,t_m)
d\bar t
$$

が KBE 側の基本要素である。

共通基盤としては、少なくとも

- 格子サイトや bond のインデックス管理
- Nambu 行列構造
- contour 成分の保存則
- one-body 項の時間依存
- self-energy の差し替え

をモジュール化する。

---

# 13. 検証戦略

以下の一致や保存則を、共通基盤と各サブプロジェクトで段階的に検証する。

---

## 13.1 非相互作用極限

相互作用および boson 結合が無いとき、
KBE は厳密な一体問題に還元される。
異常場が無い場合、TDHFB / BdG も同じ単粒子時間発展を与える。

---

## 13.2 HFB 極限

KBE + HFB self-energy

$$
\Sigma(z,z')=\Sigma^{\rm HFB}(z)\delta_{\mathcal C}(z,z')
$$

に対して、
等時一般化密度行列の発展が TDHFB と一致することを検証する。
加えて二時刻グリーン関数が同じ BdG 伝播子から構成されることも確認する。

---

## 13.3 構造保存則

- 因果律 \(G^R(t,t')=0\ (t<t')\)
- エルミート性 \([G^<(t,t')]^\dagger=-G^<(t',t)\)
- スペクトル和則 \(G^R(t,t^+)-G^A(t,t^-)=-i\)
- conserving approximation における粒子数保存
- ゲージ整合的な bond current の連続の式との整合
- パルス終了後かつ時間依存外場が無い区間での全エネルギー保存

を確認する。

特に KBE ソルバーでは、

- **ゲージ不変あるいは少なくともゲージ整合的な電流評価**
- **閉鎖系での全エネルギー保存チェック**

はほぼ必須の検証項目である。

駆動中については、単純な保存則ではなく
外場の仕事率との整合
\(dE_{\rm tot}/dt=\langle \partial_t H(t)\rangle\)
を確認対象とする。

electron-phonon サブプロジェクトでは、
閉鎖系とみなす自由度全体の
**全エネルギー保存**
を確認対象とする。

---

## 13.4 Baseline の弱〜中間結合極限

second Born を自己無撞着に解いた結果が、
短時間では HFB に連続に接続し、
弱〜中間結合の範囲で散乱による減衰と有効温度化への緩和傾向を
与えることを確認する。

深い強結合極限の熱化や Mott 物理の再現は、
この段階の検証対象としない。

---

## 13.5 Electron-phonon サブプロジェクト固有の検証

### 古典格子段階

- 電子を固定したときの調和振動子極限
- 格子を固定したときの電子のみの時間発展
- 連成系での全エネルギー保存
- 小振幅極限での線形応答

### 有効相互作用段階

- 適切な極限で有効 \(-U\) 模型に還元されること
- seed に対する pairing 増幅の再現

### 量子フォノン段階

- 非相互作用フォノン極限
- 既知の平衡結果への接続
- 電子・フォノン双方の Dyson 方程式の整合性

---

## 13.6 物理的な正当性の追加チェック

保存則を満たすことは必要条件だが、それだけで
計算された非平衡ダイナミクスが物理的に妥当とは限らない。
したがって baseline では、以下の観点を
**保存則とは独立の物理チェック項目**
として明示的に持つ。

### 平衡初期状態の静止性

外場が無く、初期状態が採用した closure に対する
自己無撞着な平衡解である場合には、

- 粒子密度
- 電流
- pairing field
- 全エネルギー

が時間一定であることを確認する。

HFB では少なくとも
$$
[\mathcal H_{\rm BdG}[\mathcal R_0],\mathcal R_0]=0
$$
を満たすことを確認する。

KBE でも、相関した平衡初期状態を用いる場合には
時間並進対称性
\(G(t,t')=G(t-t')\)
への接続を確認する。
一方、Keldysh-only の factorized 初期化で second Born を開始する場合には、
厳密な静止性は要求せず、

- 初期スリップの大きさ
- \(\Delta t\) を変えたときの収束
- Matsubara 枝実装後との比較基準

として記録する。

### 対称性と拘束条件

採用した近似と外場が保存する対称性は、
数値解でも保たれる必要がある。
例えば

- \(0\le n_{i\sigma}(t)\le 1\)
- \(\mathcal R(t)=\mathcal R^\dagger(t)\)
- TDHFB の純粋状態極限では \(\mathcal R^2=\mathcal R\)
- スピン対称条件下で \(n_{i\uparrow}=n_{i\downarrow}\)
- 正常相の対称初期条件から出発した場合に、明示的 seed 無しでは異常成分が機械誤差以上に自発発生しない
- 正方格子と駆動が \(C_4\) や鏡映対称性を保つ場合、それに対応する密度・電流・bond pairing の対称性が破れない

をチェックする。

また Nambu 表現では
$$
\mathbf G^A(t,t')=[\mathbf G^R(t',t)]^\dagger,
\qquad
[\mathbf G^<(t,t')]^\dagger=-\mathbf G^<(t',t)
$$
が各時刻で保たれていることを
常時モニターする。

### 既知極限・既知応答との比較

物理的妥当性の確認には、
既知の解析結果または高精度計算との照合が有効である。
最低限、以下を順に確認する。

- 非相互作用極限での厳密一体時間発展
- 一様弱パルスに対する線形応答が平衡 Kubo 応答に接続すること
- 小サイズ系での短時間ダイナミクスが exact diagonalization や厳密な BdG 計算と整合すること
- 一様 DC 場や長パルスの単純極限で、非相互作用格子の加速定理や Bloch oscillation と整合すること

特に bond current と光学応答は、
Peierls 位相を含む実装になって初めて
これらの極限と整合する。

### 近似の守備範囲判定

second Born を含む baseline の結果を物理的に採用してよいのは、
少なくとも以下が成り立つ範囲に限る。

- \(U\) や散乱率が帯域幅と同程度以上になっていない
- HFB から second Born への補正が連続的で、\(\Delta t\) や系サイズを変えても質的結論が安定
- occupation の範囲逸脱や大きなエネルギードリフトなど、明白な非物理性が現れない
- 深い Mott 極限に特徴的な非摂動的現象を説明対象にしていない

逆に、

- 時間刻みを半減すると結果が大きく変わる
- 系サイズを変えると秩序の有無自体が変わる
- 自己エネルギー補正が平均場の上に乗る摂動として見なせない

場合には、そのパラメータ領域は
baseline の信頼範囲外と判断する。

### 有限サイズ・有限時間窓の切り分け

2 次元実空間計算では、
有限サイズと有限観測時間が物理解釈に直接影響する。
したがって

- 境界条件
- 格子サイズ
- パルス幅
- 観測時間窓

を変えても主要結論が維持されるかを確認する。
特に Higgs-like 振動や秩序の再成長を議論する場合には、
反射や再帰による有限サイズ効果と切り分ける必要がある。

---

# 14. 実装ロードマップ

## 14.1 実装原則

初期実装では

- 正しさ優先
- 小サイズ系での完全検証優先
- TDHFB と KBE の one-body / observable 層を極力共有
- full two-time KBE を基準実装とし、軽量化は後回し

を採る。

したがって最初の版では、
Python 3.12 上での複素数 dense 行列実装を前提にし、
最適化や大規模並列化は
HFB 極限・保存則・既知極限の一致が取れてから着手する。

---

## 14.2 開発フェーズ

### Phase 0

共通インフラの整備

- 格子・bond・境界条件の表現
- Nambu インデックス管理
- Peierls 駆動付き one-body Hamiltonian builder
- 観測量と診断量の共通 API
- 時間刻み依存性を確認するテスト雛形

この段階では、後続の TDHFB と KBE が
同じ `h(t)` と同じ観測量評価を共有できる形にする。

---

### Phase 1

非相互作用 one-body ソルバー

- 時間依存一体ハミルトニアンの伝播
- ゲージ整合的 bond current
- 連続の式
- 外場の仕事率とエネルギー変化の一致

を実装し、
非相互作用極限を以後すべての基準解とする。

---

### Phase 2

TDHFB / BdG

- HFB 平衡状態の自己無撞着解法
- 一般化密度行列 \(\mathcal R(t)\) の時間発展
- on-site / bond pairing の両対応
- \(s\)-wave / \(d\)-wave 射影観測量

を追加する。

---

### Phase 3

KBE + HFB

- two-time Green 関数コンテナ
- row/column marching による因果的時間発展
- HFB self-energy の contour 実装
- 等時極限での TDHFB との一致確認

を行う。

---

### Phase 4

KBE + second Born

- 局所 Hubbard \(U\) の二次骨格自己エネルギー
- 自己無撞着反復
- メモリー積分
- 緩和・散乱の確認

を追加する。

---

### Phase 5

拡張 Hubbard baseline の完成

- 最近接引力 \(V_1\) による bond pairing
- \(d\)-wave form factor 観測量
- パラメータ走査
- finite-size / finite-time の切り分け

を実施する。

---

### Subproject A

古典格子変位を持つ electron-phonon 連成  
Ehrenfest + TDHFB / BdG

主目的

- コヒーレントフォノン
- 光誘起パラメータ変調
- 既存または seed 付き超伝導秩序の増幅・抑制

---

### Subproject B

遅延有効相互作用 \(V_{\rm eff}(t,t')\) を持つ pairing kernel

主目的

- phonon-mediated attraction の時間遅れ
- 有効 \(-U\) 極限との接続
- pairing 起源の明示化

---

### Subproject C

電子 Green 関数 \(G\) とフォノン Green 関数 \(D\) を
同時に扱う非平衡 electron-phonon KBE

主目的

- 量子フォノン媒介散乱
- retardation の明示的扱い
- 非平衡 Migdal-Eliashberg 的拡張

---

### 将来拡張

GKBA による単時間近似を導入し、
second Born や electron-phonon 自己エネルギーを含む
長時間・大規模計算を軽量化する。
ただし検証基準は引き続き full two-time KBE とする。

---

## 14.3 推奨データ構造

実装上は、空間サイトと Nambu 指標をまとめた
複合添字 \(\alpha=(i,a)\) を導入し、
行列を
\((N_{\rm site}\times N_{\rm Nambu})\)
次元の複素行列として扱うのが最も単純である。

初期版で持つべき主要オブジェクトは

- \(\mathbf h_{\alpha\beta}(t_n)\): one-body Hamiltonian
- \(\mathcal R_{\alpha\beta}(t_n)\): TDHFB 用の等時一般化密度行列
- \(\mathbf G^R_{\alpha\beta}(t_n,t_m)\): retarded Green 関数
- \(\mathbf G^<_{\alpha\beta}(t_n,t_m)\): lesser Green 関数
- \(\mathbf\Sigma^{\rm inst}(t_n)\), \(\mathbf\Sigma^{\rm mem}(t_n,t_m)\): 時間局所・時間非局所自己エネルギー

である。

KBE では
\(n\ge m\) の三角領域だけを格納し、
Hermiticity と advanced / retarded 関係で残りを再構成する。
これにより保存則チェックとメモリー削減を同時に行える。

---

## 14.4 TDHFB / BdG ソルバーの実装手順

TDHFB 側では
$$
i\partial_t\mathcal R=[\mathcal H_{\rm BdG}[\mathcal R],\mathcal R]
$$
を直接解く。

実装順序としては、

1. 静的 HFB 方程式を反復して \(\mathcal R_0\) を得る
2. \(\mathcal R_n\) から \(\Sigma^{\rm HFB}_n\) を構成する
3. 中点ハミルトニアン \(\mathcal H_{n+1/2}\) を予測する
4. 行列指数または Crank-Nicolson 型で \(\mathcal R_n\to\mathcal R_{n+1}\) を伝播する
5. 新しい \(\mathcal R_{n+1}\) で \(\Sigma^{\rm HFB}\) を更新し、必要なら predictor-corrector を 1-2 回回す

という流れにするのが扱いやすい。

この方法なら

- 非相互作用極限で厳密一体伝播に戻る
- Hermiticity を保ちやすい
- HFB 極限でのユニタリティ確認が容易

という利点がある。

---

## 14.5 full two-time KBE ソルバーの実装手順

KBE では、新しい時刻 \(t_{n+1}\) に対して
Green 関数の新しい行と列を順次埋める
**causal marching**
を採用する。

初期版の手順は以下で十分である。

1. 初期条件
   \( \mathbf G^<(t_0,t_0)=i\mathcal R_0 \),
   \( \mathbf G^R(t_0,t_0)=-i\mathbf 1 \)
   を与える
2. \(t_{n+1}\) での one-body Hamiltonian と instantaneous self-energy を構成する
3. 既知の過去時刻 \(t_m\le t_{n+1}\) に対して
   \(\mathbf G^R(t_{n+1},t_m)\) を Volterra 型積分方程式として解く
4. 同じ履歴を使って
   \(\mathbf G^<(t_{n+1},t_m)\) を更新する
5. Hermiticity から列成分
   \(\mathbf G^<(t_m,t_{n+1})\)
   を再構成する
6. 等時成分から \(\mathcal R(t_{n+1})\) と観測量を評価する
7. 保存則残差と対称性残差を毎ステップ記録する

時間積分は最初は台形則で十分であり、
長時間伝播の位相誤差が問題になってから
Gregory 型や高次 predictor-corrector に進めばよい。

---

## 14.6 second Born 実装時の反復戦略

second Born は \(\Sigma^{(2)}[G]\) が
二時刻 Green 関数全体に依存するため、
各時刻ステップでの自己無撞着反復が必要になる。

初期版では

- HFB 解を初期推定に使う
- 新しい行・列に対してのみ固定点反復を回す
- 発散を避けるために自己エネルギー更新へ mixing を入れる
- 収束判定は \(\|\Delta G\|\) と \(\|\Delta \Sigma\|\) の双方で行う

のが現実的である。

また、局所 Hubbard \(U\) の second Born から始めることで、

- Nambu 行列表式の実装確認
- メモリー積分の実装確認
- 散乱による減衰の出現

を、非局所相互作用の複雑さを持ち込まずに検証できる。

相関した熱平衡初期状態が必要になった段階で、
Matsubara 枝を導入して
\(I^{\rceil},I^{\lceil}\) を含む版へ拡張する。
したがって、Matsubara 初期化は
second Born 実装後の補助マイルストーンとして
明示的に計画に入れておくべきである。

---

## 14.7 テストと受け入れ基準

各フェーズに対して、少なくとも以下を
完了条件とする。

- 時間刻みを半減したとき、主要観測量の誤差が期待次数で減少する
- Phase 2 と Phase 3 の HFB 極限が数値誤差内で一致する
- 連続の式残差、Hermiticity 残差、エネルギー残差が時系列で監視される
- 小サイズ既知極限との比較が自動テスト化される
- 観測量計算とソルバー本体が同じ one-body / bond 定義を共有する

特に「結果が出た」ことと「物理的に使える」ことを切り分けるために、
各 run では

- 最大保存則残差
- 最大対称性残差
- \(\Delta t\) 収束性
- 系サイズ依存性

をメタデータとして必ず保存する。

---

## 14.8 計算量と拡張戦略

full two-time KBE のメモリー量は概ね
\(O(N_t^2 N_{\rm orb}^2)\)
で増大するため、
初期実装では

- 小格子
- 短中時間
- dense 行列

に限定してよい。

その代わり、

- lower-triangular storage
- observables の逐次書き出し
- self-energy 計算の局所性利用

を最初から設計に織り込む。

最適化の順序としては

1. full two-time KBE の正当性確立
2. プロファイリングによる律速部の特定
3. 行列演算・自己エネルギー計算の高速化
4. 必要なら GKBA への移行

とし、
**軽量化は必ず基準実装との比較可能性を保ったまま進める**
ことを原則とする。

---

# 15. 本研究の位置づけ

本研究は、

- 2 次元実空間
- 非平衡超伝導
- 光励起後の短中時間 transient

に対して、

**Kadanoff-Baym 方程式**

を基盤とする数値ソルバーを構築する試みである。

その中で

- 拡張 Hubbard は最初の基準模型
- bond pairing / d-wave は baseline の主対象
- electron-phonon 系は同じ数値基盤上のサブプロジェクト

と位置づける。

したがって本プロジェクトの狙いは、

- TDHFB / BdG で見える秩序ダイナミクス
- second Born で入る摂動的散乱とメモリー
- 実空間 2 次元での結合秩序の可視化
- 将来の phonon-mediated pairing 研究への拡張性

を同一の実装基盤で接続するところにある。

これは、非平衡 DMFT のような非摂動的強結合理論の代替ではない。
むしろ本プロジェクトの価値は、

- 理論整合性
- 実装検証可能性
- モデル間の比較可能性
- 将来拡張のしやすさ

を初期段階から設計に織り込むことにある。
