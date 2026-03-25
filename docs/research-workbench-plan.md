# 研究アプリ全体方針
## ― 非平衡超伝導ソルバー基盤を研究加速型 workbench として具体化する ―

この文書は、研究用アプリ全体の product / architecture / implementation 方針の正本である。  
frontend 設計だけでなく、

- 何を研究体験として実現するか
- そのために frontend / backend / storage に何を要求するか
- どの概念を API と UI の共通語彙として固定するか
- どの順序で実装と拡張を進めるか

を定める。

役割分担:

- 物理仕様の正本: [theory.md](./theory.md)
- backend solver validation の正本: [validation-spec.md](./validation-spec.md)
- backend solver remediation の正本: [backend-remediation-plan.md](./backend-remediation-plan.md)
- 研究アプリ全体方針の正本: [research-workbench-plan.md](./research-workbench-plan.md)
- 進捗管理の正本: [progress.md](./progress.md)
- 用語の最小共有語彙: [glossary.md](./glossary.md)

この文書が扱うのは、研究アプリ全体の体験設計、責務分割、データモデル、API 契約、段階的拡張計画である。  
physics validation の判定や理論 claim そのものは扱わない。

---

## 1. Product Goal

### 1.1 目的

本プロジェクトのアプリケーション層の目的は、

> 非平衡超伝導ダイナミクスの simulation、比較、解析、再現を一つの研究 workbench として回せるようにすること

である。

重要なのは、frontend を
「run を投げて結果を眺めるだけの画面」
とみなさないことである。

高品質な研究用 frontend は、

- 研究問いと baseline の固定
- 仮説比較と numerical validation の切り分け
- 解析の再利用
- 実験条件の再現
- 失敗 run と判断理由の保持
- prototype と validated scope の切り分け

を大幅に加速する。

したがって、このアプリは
**可視化の見た目を整えること** だけでなく、
**研究作業そのものを構造化して加速すること**
を目標に置く。

### 1.2 主な研究タスク

初期段階でアプリが支えるべき研究タスクは次の 7 つである。

1. 研究問いと baseline の固定
2. 単一 run の妥当性確認と異常検知
3. 仮説差分の比較
4. parameter dependence と robustness / convergence 評価
5. simulation 後の derived analysis による feature extraction
6. claim candidate の整理と reproducibility bundle 化
7. k-space / tr-ARPES derived analysis による momentum-resolved feature extraction

これらは UI の tab 名ではなく、
**研究判断の単位**
として扱う。  
workbench の tabs / artifact / metadata は、
この 6 つのタスクを支えるために設計する。

対応の正本:

| task | primary surface | roadmap anchor |
| --- | --- | --- |
| 1. 研究問いと baseline の固定 | `study`, baseline preset | `P1.5` |
| 2. 単一 run の妥当性確認と異常検知 | `Single Job` | `P1` |
| 3. 仮説差分の比較 | `Compare Jobs` | `P2` |
| 4. parameter dependence と robustness / convergence 評価 | `Parameter Sweep` | `P3` |
| 5. derived analysis による feature extraction | `derived analysis artifact` | `P4` |
| 6. claim candidate の整理と reproducibility bundle 化 | `evidence bundle` | `P4` |
| 7. k-space / tr-ARPES derived analysis | `derived analysis artifact`, `k-space surface` | `P6` |

特に、

- 時間波形
- フーリエスペクトル
- パラメーター x 時間ヒートマップ
- パラメーター x 周波数ヒートマップ
- convergence row / error surface

を自然に往復できることを重視する。

### 1.3 初期デモ目標

アプリの最初のデモンストレーションは、

> 光パルス照射後の超伝導 Higgs mode の時間プロファイルを可視化すること

とする。

既定デモの基準:

- solver の主軸: `kbe_hfb`
- self-energy の主軸: `hfb`
- pairing の主軸: `bond_d`
- 主観測量: `pairing_d`
- 主解析: 時間波形 + FFT

ただし、数値値を含む最終 preset は benchmark / stability / validation scope を踏まえて後続で確定する。  
このデモ preset は
**validated baseline preset とは区別して扱う**。  
このデモ preset を既定に据えることは、
その physics claim が自動的に validated になることを意味しない。

### 1.4 初期スコープ外

初期段階では次を対象外とする。

- 2D parameter sweep
- cluster / distributed execution
- frontend 側での重い解析の常時計算
- full contour second Born を completed と見なす UI messaging
- p-wave, `second_born_reference` を含む full k-space correlated solver, 不純物効果の本実装
- 共同編集ノートや reviewer workflow

ただし UI / API / storage の抽象は、これらを後から受け入れられるように設計する。

### 1.5 Frontend Reference Posture

この workbench の frontend は、
別プロダクトとして存在する `cmp-mp` の frontend を
**layout / composition の参照元**
として扱う。

ここでいう参照とは、
feature parity や domain 再現ではない。  
真似る対象は主に次である。

- top navigation で page-level surface を分離すること
- 各 surface が fixed-width の左 sidebar と広い main canvas を持つこと
- sidebar 内で collapsible section を積み、最下部に sticky な実行操作を置くこと
- simulation と comparison で shared parameter scaffold を再利用すること
- sweep page では sweep 軸定義を最初に置き、その後ろに fixed parameter 群を並べること
- main 側で page title、短い説明、progress / warning、結果 panel 群、empty state を一定順序で並べること

TDKB における対応関係の正本は次の通りとする。

- `cmp-mp` `Simulation` page → `Single Job`
- `cmp-mp` `Comparison` page → `Compare Jobs`
- `cmp-mp` `Parameter Dependency` / `Erosion Sweep` page → `Parameter Sweep`

一方で、次は意図的に再現対象にしない。

- CMP 固有の物理量、フォーム項目、分析指標
- optimization / study-analysis / admin の feature set
- `cmp-mp` backend contract や job schema そのもの
- 2D sweep を v1 必須とみなすこと

つまり、
**cmp-mp の page grammar は借りるが、
TDKB 固有の physics / validation / artifact model に合わせて再構成する**
という方針を取る。

---

## 2. Current Technical Baseline

### 2.1 実装スタック

現行基盤は次で構成される。

- frontend: React + TypeScript + Vite
- backend: FastAPI
- solver core: backend 内 Python package
- artifact storage: run ごとの JSON / NPZ / NPY

アプリ全体方針はこの現行基盤を出発点にし、
一気に別種の full-stack product へ移行することは前提にしない。

### 2.2 現行の repository shape

```text
TDKB/
├─ frontend/
│  ├─ src/
│  │  ├─ components/
│  │  ├─ api/
│  │  └─ lib/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ jobs/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ solvers/
│  │  └─ storage/
│  └─ tests/
└─ docs/
```

今後も、

- frontend は interaction / composition
- backend は solver / orchestration / persistence

の分離を維持する。

### 2.3 現行データフロー

現行の最小動線は次である。

1. frontend で config を編集する
2. frontend が backend に run 作成要求を送る
3. backend が設定を検証し、run を生成する
4. backend の job runner が solver を起動する
5. backend が observables / diagnostics / Green 関数を保存する
6. frontend が run 状態と artifact を取得して表示する

今後の compare / sweep / analysis は、この run 中心データフローを拡張して構築する。

### 2.4 現行 API の基準面

現時点で存在する主要 API:

- `GET /api/v1/health`
- `GET /api/v1/schema/simulation`
- `GET /api/v1/presets`
- `POST /api/v1/runs`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/progress`
- `POST /api/v1/runs/{run_id}/cancel`
- `GET /api/v1/runs/{run_id}/observables`
- `GET /api/v1/runs/{run_id}/observables/{name}`
- `GET /api/v1/runs/{run_id}/green-functions`
- `GET /api/v1/runs/{run_id}/green-functions/{component}`
- `GET /api/v1/runs/{run_id}/thermal-branch`
- `GET /api/v1/runs/{run_id}/thermal-branch/{component}`
- `GET /api/v1/runs/{run_id}/mixed-green-functions`
- `GET /api/v1/runs/{run_id}/mixed-green-functions/{component}`

今後の拡張でも、
**既存の run API は単一 artifact 取得面として維持しつつ、上位 resource を追加する**
という方針を取る。

### 2.5 現行 storage の基準面

現行 run artifact の基準構成:

```text
backend/data/runs/{run_id}/
├─ config.json
├─ progress.json
├─ status.json
├─ summary.json
├─ diagnostics.json
├─ observables.npz
├─ run.log
├─ green_functions.json
├─ green_*.npy
├─ thermal_branch.json
├─ thermal_*.npy
├─ mixed_green_functions.json
└─ mixed_*.npy
```

今後の上位 artifact でも、

- metadata は JSON
- 配列本体は保存向きの binary format
- frontend は API 経由で必要部分のみ取得

の原則を保つ。

---

## 3. UX / Workflow

### 3.1 Workbench 全体構成

アプリは単一ページの巨大フォームではなく、
**top-level navigation で distinct surface を分ける研究 workbench**
として設計する。

最上位 surface は次の 3 つを正本とする。

- `Single Job`
- `Compare Jobs`
- `Parameter Sweep`

この 3 surface は「同じ run 一覧の別の見え方」ではなく、
研究作業の異なる面を表す。  
一方で、
v1 の研究運用の主資源は `study` であり、
各 surface は同一 `study` の中で
baseline、candidate、numerical check、derived analysis、evidence bundle
を扱う作業面として読む。

実装上は page route を第一候補とし、
`Single Job` / `Compare Jobs` / `Parameter Sweep` を
同一ダッシュボードに貼り込んで情報を混在させないことを優先する。  
tab bar は、
surface 内 submode を切り替えるときにのみ使う。

`cmp-mp` を参照するときの構成対応は次の通りである。

| cmp-mp reference | TDKB surface | 真似るべき構成 | 再現しないもの |
| --- | --- | --- | --- |
| `SimulationPage` | `Single Job` | shared sidebar + page 固有の run launch / preview / result stack | CMP 固有フォーム、断面プロファイル固有 plot |
| `ComparisonPage` | `Compare Jobs` | active variant を左で編集し、中央で summary table と overlay compare を読む構成 | 条件テーブルの細かな inline editing をそのまま写すこと |
| `ParameterDependencyPage` | `Parameter Sweep` | 1 軸 sweep を定義し、主曲線や依存性 plot を読む構成 | CMP 固有の erosion 指標 |
| `ErosionSweepPage` | `Parameter Sweep` | sweep family の中で submode を切り替える tab bar と、heatmap / cross-section 主体の結果面 | 2D sweep を v1 必須とすること |

したがって、
TDKB では route-level surface 分離を第一候補とし、
page 内 tab は sweep family や advanced evidence 切替のような
**surface 内 submode**
に限定する。

### 3.2 共通 UI 骨格

全 surface で共通する骨格は次の通りである。

- 最上位 shell:
  - `cmp-mp` 同様、top navigation で surface を切り替える
  - global shell は軽量に保ち、plot 面積を奪う dashboard KPI row を常設しない
- 左: context-aware sidebar
  - 幅はおおむね 300-360px の固定 rail を基準にする
  - surface 固有の intent 定義を先頭に置く
  - その後ろに shared parameter scaffold を collapsible section で積む
  - 最下部に sticky な launch / run / apply 操作を置く
  - `study` コンテキスト
  - preset 選択
  - config 編集
  - 実行制御
  - 対象 artifact 選択
- 中央: 主可視化領域
  - page title と 1-2 文の surface copy を先頭に置く
  - warning / progress / success を title 直下の status band に集約する
  - その下に primary result stack を置く
  - 時間波形
  - スペクトル
  - heatmap
  - 比較表示
  - convergence / error surface
- 右または下: 補助領域
  - `cmp-mp` は主に main stack 下部へ補助情報を送る
  - TDKB でも wide screen では右 rail を使ってよいが、plot 幅を削りすぎないことを優先する
  - diagnostics
  - metadata
  - decision note
  - derived analysis
  - evidence bundle
  - validation scope / implementation scope

さらに、
cmp-mp から学ぶべき page grammar を次で固定する。

- empty state は「何を設定してどのボタンを押すか」を明示する
- progress state は page 内で結果面と同じ場所に出し、別 modal に逃がさない
- completed state は success banner の直後に primary figure を出す
- sidebar の入力群は surface ごとに全差し替えせず、shared section を再利用しつつ先頭数ブロックだけを変える
- main canvas の panel は「もっとも単純な読み」から「派生・補助」の順に並べる
- advanced / rare artifact は disclosure や secondary row へ逃がし、最初の読みに混在させない

ナビゲーションは top-level surface を明示的に切り替えられる形を採用し、
選択中の `study`、surface、対象 run / group / sweep、選択中 observable、解析条件などの主要 state は URL に反映し、
deep link と session 復元を可能にする。

### 3.3 Single Job

`Single Job` は、
一つの run を観察するだけでなく、
その run を
**baseline / candidate / control / numerical check のどれとして読むか**
を固定する作業面である。

必要機能:

- `study` コンテキスト、`run_role`、`validation_status`、`failure_tags` を明示できる
- preset から draft をロードできる
- config を編集して run を作成 / clone / rerun できる
- run 状態、設定、メタデータ、baseline 情報、diagnostics を同時に確認できる
- 時間波形を複数系列で観察できる
- two-time / thermal / mixed Green 関数の inspector を持つ
- run 完了後に derived analysis を追加生成できる
- 観察・失敗理由・判断理由を `decision note` として残せる
- 有用な run と analysis を `evidence bundle` に追加できる

主表示:

- page header + study / preset / baseline framing
- launch band
  - preset / study context
  - editable config
  - run selection / run control
- primary evidence row
  - observable 時系列
  - FFT spectrum
- secondary evidence row
  - run framing / baseline relation
  - diagnostics summary
- advanced evidence surface
  - two-time / thermal / mixed contour
  - derived analysis metadata
  - failure / rejection reason
  - validation / prototype / reference の scope badge

cmp-mp の `SimulationPage` から引くべき構成原則は次の通りである。

- run launch は独立 page の左 rail に固定する
- simulation 固有の追加ブロックは shared config section の後ろに置く
- 実行中は progress / convergence を main 側の先頭に置く
- 完了後は preview より evidence を優先し、最初の視線で主要 observable に到達できるようにする
- running telemetry は research artifact ではなく execution telemetry として扱い、`study` / `evidence bundle` の判断資産と混同しない

`Single Job` の execution telemetry の正本は次とする。

- `GET /api/v1/runs/{run_id}/progress` で heartbeat と solver-specific telemetry を取得する
- queued / running 中は main canvas の先頭に progress surface を置く
- progress surface は wall-clock heartbeat、solver 内 physical time、saved sample count、solver-specific mini metrics を同時に見せる
- terminal 後の physics / validation の正本は従来どおり diagnostics / artifact surface で読む

Higgs デモの既定体験はこの tab から始めるが、
validated baseline との境界は常に表示する。

### 3.4 Compare Jobs

`Compare Jobs` は、複数 run の比較を
**研究判断 artifact**
として固定する作業面である。

ここでは frontend が ad hoc に run を寄せ集めるのではなく、
backend が管理する `job group` を前提にする。  
`job group` は
physics hypothesis 比較と numerical validation 比較の両方を扱う。

必要機能:

- base config を起点に variant 群を作る
- variant ごとに label を付ける
- `comparison_kind` を明示できる
- baseline run を明示できる
- child run 群の進捗をまとめて管理する
- 同一 observable の overlay 表示
- small multiples
- 差分表示
- 正規化比較
- FFT 比較
- convergence / error comparison
- accepted / rejected と failure note を比較面に持ち込める

page composition は `cmp-mp` の `ComparisonPage` を参照し、
次の順序を正本とする。

- 左 rail 先頭で variant list / active variant / baseline 指定を扱う
- 左 rail 下段で active variant の shared parameter form を編集する
- main 冒頭で `job group` summary table を常時見せる
- その下に progress / child-run state / selected axis control を置く
- さらにその下に overlay、difference、small multiples、FFT、convergence / error を積む

つまり `Compare Jobs` は
「プロットだけの compare 面」ではなく、
**どの variant 群をどういう比較意図で束ねたか**
を first view で読める page にする。

初期に想定する比較テンプレート:

- `bond_s` vs `bond_d`
- `hfb` vs `second_born` vs `second_born_reference`
- drive amplitude の離散比較
- seed pairing の離散比較
- `dt` coarse vs fine
- adaptive tolerance loose vs tight
- memory window 比較

将来 `p-wave` が backend へ追加されたら、この tab の比較テンプレートに組み込む。

### 3.5 Parameter Sweep

`Parameter Sweep` は、一つの scalar parameter を連続的に変化させた run 群を扱う作業面である。

初版は **1D sweep のみ** を扱う。  
ただし sweep は physics parameter に限定せず、
`dt`、adaptive tolerance、memory window などの
numerical parameter も first-class に扱う。

初期仕様:

- backend 管理の `sweep` resource を使う
- base config + parameter path + value list から child run を生成する
- `parameter_kind` を `physics` / `numerical` / `analysis` から区別できる
- `parameter x time` ヒートマップを表示する
- `parameter x frequency` ヒートマップを表示する
- numerical sweep では convergence row / error surface を primary にできる
- パラメーターごとの代表時系列 / 代表スペクトルへ drill down できる
- `fixed_axes` を持ち、何を固定した sweep かを明示できる

page composition は
`cmp-mp` の `ParameterDependencyPage` と `ErosionSweepPage` /
`ParamTimeSweepContent` を参照し、
次を正本とする。

- 左 rail の先頭に sweep 軸定義ブロックを置く
- 時間範囲や fixed axes は sweep 軸定義の直後に置く
- その後ろに shared fixed-parameter section を並べる
- main 冒頭で sweep point 数、warning、cost 感を summary する
- progress は heatmap / curve と同じ面で継続表示する
- 結果は primary sweep figure を最初に置き、その後に drilldown や cross-section を置く

TDKB v1 は 1D sweep のみだが、
内部構成は将来の `parameter x time` / `parameter x frequency`
heatmap をそのまま受け入れられるようにする。  
すなわち、
page 内 submode は許容するが、
それは sweep family の派生表示を分けるために使い、
top-level surface の境界を曖昧にするためには使わない。

初版では time-axis の整合を保つため、
time / frequency heatmap 対応 sweep は fixed-grid のみを対象とする。  
一方で numerical sweep 自体は first-class に保持し、
時間軸が揃わない場合でも convergence row や error surface として保存する。

### 3.6 Decision Notes And Evidence Bundles

研究 workbench は、
成功 run だけを並べる画面ではなく、
何を観察し、何を棄却し、何を次に試すか
を残す面でもある。

方針:

- run / group / sweep / analysis の任意の artifact に `decision note` を付けられる
- `decision note` は `observation` / `failure` / `decision` / `todo` を最小単位とする
- negative / rejected run は削除せず、failure note と `failure_tags` 付きで保持する
- `evidence bundle` は figure / table / claim candidate を支える run / analysis / validation scope を束ねる
- `evidence bundle` を作っても、その claim が自動的に validated になるわけではない
- v1 では solo researcher 向けの軽量運用に留め、共同編集ノートや reviewer workflow は持たない

### 3.7 Derived Analysis

simulation 後の事後解析は、
frontend の一時的な計算ではなく、
backend が生成して保存する `derived analysis artifact` として扱う。

初期対応対象:

- FFT
- windowed FFT に向けた窓指定 metadata
- peak 抽出
- peak frequency / intensity の summary
- k-path occupied spectrum
- minimal tr-ARPES intensity

将来的な候補:

- envelope
- damping fit
- mode tracking
- selected observable 間の cross-analysis
- correlated k-space / tr-ARPES extension

`derived analysis artifact` は可視化用の再利用資産であると同時に、
`evidence bundle` の入力として扱う。

### 3.8 Preset 導線

preset は単なる default config 集ではなく、
研究作業の入口として扱う。

少なくとも次のカテゴリを持つ。

- demo preset
- baseline preset
- 単一 run 観察 preset
- 比較テンプレート preset
- sweep テンプレート preset

初期候補:

- Higgs demo
- current validation scope に整合する baseline preset 群
- `bond_s` vs `bond_d`
- `hfb` vs `second_born_reference`

Higgs demo は既定入口として残すが、
validated baseline preset と混同しない。

### 3.9 Visual Direction

視覚方針は次の通りに固定する。

- shell:
  `cmp-mp` のような top navigation + persistent left rail を基準にし、
  その上で study / validation framing を TDKB 向けに追加する
- page layout:
  light theme の研究 UI を基調にし、
  fixed sidebar と広い plot canvas の対比を崩さない
- plot language:
  `cmp-mp` の light scientific page と
  Grafana ライクな scientific panel の中間を基準にする
- tone:
  業務監視画面ではなく研究 workbench
- density:
  情報密度は高くてよいが、プロット面積を削らない
- controls:
  collapsible section、sticky action bar、warning / progress banner を標準部品として扱う
- reuse:
  simulation と compare では shared form section を再利用し、
  sweep ではその前に axis-definition block を追加する

つまり、
**cmp-mp ライクな page grammar** と
**scientific plotting を前面に出す可視化面**
を組み合わせる。

---

## 4. Data And System Model

この workbench では、次の概念を共通語彙として固定する。

### 4.1 `study`

研究問い、baseline、対象 observable、評価方針を束ねる
最上位の research campaign artifact。

役割:

- どの問いに対して run / compare / sweep / analysis を行っているかを固定する
- baseline preset と target observable を明示する
- acceptance check と scope note を研究文脈として残す
- solo researcher の作業単位を durable に保存する

最低限必要な情報:

- `study_id`
- `title`
- `question`
- `baseline_preset_id`
- `target_observables`
- `primary_surfaces`
- `acceptance_checks`
- `status`
- `notes_on_scope`
- `created_at` / `updated_at`

### 4.2 `run`

最小の simulation artifact。

役割:

- 一つの config に対する solver 実行結果
- observables / diagnostics / Green 関数 / derived analysis の起点
- baseline / candidate / control / numerical check のどれとして読むかを固定する

最低限の拡張 metadata:

- `study_id`
- `run_role` (`baseline` / `candidate` / `control` / `numerical_check`)
- `validation_status` (`unchecked` / `screening` / `accepted` / `rejected`)
- `failure_tags`
- `group_id`
- `sweep_id`
- `variant_label`
- `preset_id`
- `tags`
- `config_hash`
- `code_version`
- `storage_uri`

負結果・失敗 run は削除対象ではなく、
`validation_status=rejected` と `failure_tags` 付きで保持する。

### 4.3 `job group`

離散比較のための artifact 集約単位。

役割:

- base config と variant 群を束ねる
- child run 群の進捗をまとめる
- compare tab の primary resource になる
- physics hypothesis 比較と numerical validation 比較を同じ抽象で扱う

最低限必要な情報:

- `group_id`
- `study_id`
- `name`
- `comparison_kind` (`physics_hypothesis` / `numerical_validation` / `regression`)
- `baseline_run_id`
- `base_config`
- `variants`
- `child_run_ids`
- `state`
- `created_at` / `updated_at`

### 4.4 `sweep`

1D parameter scan の artifact 集約単位。

役割:

- scalar parameter path と sampling を保存する
- child run 群と parameter value の対応を保持する
- heatmap と sweep summary の primary resource になる
- physics sweep と numerical sweep を同じ抽象で扱う

最低限必要な情報:

- `sweep_id`
- `study_id`
- `name`
- `parameter_kind` (`physics` / `numerical` / `analysis`)
- `parameter_path`
- `parameter_label`
- `values`
- `baseline_value`
- `fixed_axes`
- `child_run_ids`
- `state`

### 4.5 `decision note`

観察、失敗理由、棄却判断、次アクションを短文で残す軽量 artifact。

役割:

- run / group / sweep / analysis に対する判断を保存する
- negative result を捨てずに保持する
- solo researcher の trial-and-error を後日再読可能にする

最低限必要な情報:

- `note_id`
- `study_id`
- `source_kind`
- `source_id`
- `note_kind` (`observation` / `failure` / `decision` / `todo`)
- `body`
- `tags`
- `created_at`

### 4.6 `derived analysis artifact`

simulation 後に生成される保存可能な解析結果。

役割:

- FFT や peak extraction を再利用可能にする
- compare / sweep に同じ解析結果を使い回す
- frontend の重い再計算を避ける
- `evidence bundle` の入力面になる

最低限必要な情報:

- `analysis_id`
- `study_id`
- `source_kind` (`run` / `job_group` / `sweep`)
- `source_id`
- `analysis_type`
- `analysis_version`
- `cache_key`
- `parameters`
- `status`
- `input_surface_ids`
- `result_metadata`
- `data_refs`
- `supports_bundle_ids`

### 4.7 `evidence bundle`

figure / table / claim candidate を支える run / analysis / validation scope を束ねる artifact。

役割:

- どの artifact がどの主張候補を支えるかを固定する
- source run / analysis / validation scope を後から辿れるようにする
- 再現レシピをまとめ、論文化前の証跡整理を行う

最低限必要な情報:

- `bundle_id`
- `study_id`
- `title`
- `claim_candidate`
- `artifact_refs`
- `analysis_refs`
- `validation_scope`
- `reproduction_recipe`
- `status` (`draft` / `ready` / `superseded`)
- `created_at` / `updated_at`

### 4.8 `preset`

既定設定と研究意図を結びつける artifact。

役割:

- 単なる default 値ではなく、意図のある入口を提供する
- demo preset と baseline preset を明示的に分ける
- どの tab / demo / comparison / study に向く preset かを明示する

最低限必要な情報:

- `preset_id`
- `name`
- `category`
- `default_config`
- `intended_tab`
- `notes_on_scope`

### 4.9 `data surface`

frontend が扱う可視化対象の抽象。

可視化対象を `density`, `pairing_d`, `FFT` などの名前だけでなく、
「どの軸に沿ったデータか」で表す。

最低限必要な情報:

- `surface_id`
- `label`
- `axes`
- `units`
- `provenance`
- `validation_scope`

`data surface` を導入する理由は、
将来の

- 時間軸
- 周波数軸
- probe-delay 軸
- parameter 軸
- site 軸
- bond 軸
- nambu 軸
- error / benchmark 軸
- k-point 軸

を同じ UI 語彙で扱えるようにするためである。

### 4.10 `experiment registry`

`run` / `study` / `job group` / `sweep` / `decision note` / `derived analysis artifact` / `evidence bundle`
を ad hoc な JSON 参照でつなぐのではなく、
**実験メタデータ専用の registry DB** を導入する。

役割:

- study / run / group / sweep / analysis / note / bundle のメタデータ索引
- parent-child 関係と lineage の一貫管理
- tag, preset, parameter path, solver mode, `validation_status`, `failure_tags` による検索
- state 集計と再起動後の状態復元
- 再現に必要な config hash / code version / schema version の保持

最低限必要な情報:

- artifact id (`study_id`, `run_id`, `group_id`, `sweep_id`, `note_id`, `analysis_id`, `bundle_id`)
- artifact kind
- state
- config JSON と `config_hash`
- `preset_id`, `variant_label`, `tags`
- `parameter_path`, `parameter_value`
- `run_role`, `validation_status`, `failure_tags`
- `parent_artifact_id` / `source_id`
- `code_version`, `schema_version`
- `storage_uri`
- `created_at` / `updated_at`

方針:

- DB は metadata / relation / query 専用とし、巨大配列は入れない
- observables / Green 関数 / FFT payload は従来どおり file artifact に保存する
- rejected run や failure note も registry 上の first-class artifact として残す
- 初期導入は SQLite を正本とし、multi-user / remote worker / 高並列が必要になった段階で PostgreSQL へ昇格可能な schema にする

v1 では `hypothesis` を standalone artifact にせず、
`study.question` と `job group.comparison_kind=physics_hypothesis`
で表現する。

### 4.11 `k-space / tr-ARPES surface`

`k` 空間 / `tr-ARPES` は、solver core の別系統ではなく、
既存 real-space / Green-function artifact から再構成する data surface である。

役割:

- run 由来の Green function を momentum-resolved surface に変換する
- occupied spectrum と tr-ARPES intensity を分けて保存する
- probe delay, probe width, broadening を metadata として保持する
- `second_born_reference` を correlated source として同一 contract に載せる

最低限必要な情報:

- `surface_id`
- `source_run_id`
- `analysis_type`
- `k_path` / `k_grid`
- `energy_grid`
- `probe_delay`
- `probe_width`
- `broadening`
- `observable_scope` (`occupied_spectrum` / `tr_arpes_intensity`)
- `result_metadata`
- `data_refs`

---

## 5. Frontend / Backend Responsibility Split

### 5.1 Frontend の責務

frontend は workbench の interaction layer と view composition を担う。

主責務:

- `study` コンテキストの提示
- tabs / workspace shell
- config editing
- artifact selection
- compare / sweep interaction
- plot rendering
- decision note の記録
- evidence bundle の組み立て
- validation scope messaging
- derived analysis の起動と表示

frontend は solver 内部状態を直接知るのではなく、
backend が返す typed artifact と data surface に依存する。

### 5.2 Backend の責務

backend は計算実行だけでなく、
研究 artifact の orchestration と persistence を担う。

主責務:

- `study` の作成 / 保存 / 取得
- run 作成 / 保存 / 取得
- job group の作成 / 実行 / 取得
- sweep の作成 / 実行 / 取得
- decision note の保存 / 再取得
- derived analysis の生成 / 保存 / 再取得
- evidence bundle の生成 / 保存 / 再取得
- preset の提供
- typed API と metadata の整備

### 5.3 ジョブ実行原則

数値計算は CPU bound であり、HTTP request 処理から分離する。

原則:

- API は artifact を登録する
- job runner は別プロセスで実行する
- `queued/running/succeeded/succeeded_with_warnings/failed/cancelled` を全 artifact で一貫させる
- compare / sweep でも child run と親 artifact の両方に状態を持つ

### 5.4 現行の基準 API 契約

現行の typed contract の基本方針は維持する。

- OpenAPI を正とする
- frontend 型は OpenAPI に追従する
- frontend は solver 内部表現ではなく API 返却形式に依存する
- 可視化は backend が整形した data payload を読む

現行 observable payload の最小単位は次を基準にする。

```json
{
  "name": "pairing_d",
  "time": [0.0, 0.1, 0.2],
  "series": [
    {
      "label": "real",
      "values": [0.0, 0.02, 0.03]
    },
    {
      "label": "imag",
      "values": [0.0, 0.0, -0.01]
    }
  ],
  "units": null,
  "metadata": {
    "solver": "tdhfb"
  }
}
```

複素量は初期段階では `real/imag` 分解を許し、
将来的に amplitude / phase / spectrum surface へ拡張する。

### 5.5 現在の artifact API と残作業

現行 `/runs` 系 API に加え、次は backend 実装済みである。

- `studies`
- `job-groups`
- `sweeps`
- `decision-notes`
- `derived-analyses`
- `evidence-bundles`
- enriched `presets`
- run context metadata

実装済み backend artifact の運用詳細は `docs/backend-artifact-lifecycle.md` を参照する。

現時点の残作業は主に frontend 側にある。

- `k` 空間 / `tr-ARPES` の derived analysis surface と result payload の追加
- `study` / tab / run / group / sweep / bundle を横断する URL deep link
- 一覧 / filter / re-read を含む artifact 導線の整理

API 方針:

- `study` を research campaign の primary resource とする
- run / group / sweep / analysis / note / bundle は `study` に従属する artifact として扱う
- compare / sweep の primary resource を明示する
- numerical validation compare / sweep を physics compare / sweep と同列に artifact 化する
- data と metadata を分けて取得できるようにする
- 重い解析結果は再利用可能な artifact として返す
- k-space / tr-ARPES derived analysis は solver core ではなく derived analysis artifact として扱う
- `representation=k_space` native solver path は別能力として扱い、derived analysis と混同しない
- `evidence bundle` は validation scope を明示するが、claim を自動的に validated とみなさない

### 5.6 Storage 方針

artifact persistence は次の原則に従う。

- run は最小実行単位
- job group / sweep は run 群への参照を持つ
- derived analysis は source artifact に紐づく独立 artifact として保存する
- 実験メタデータ、artifact 関係、状態遷移は `experiment registry` DB に保存する
- observables / Green 関数 / 熱枝 / mixed 枝 / FFT payload などの大型配列は file artifact に保存する
- DB row は `storage_uri` と hash を持ち、blob 本体は持たない
- rejected run と failure note は削除せず保存する
- frontend は DB で索引された保存済み artifact を読む

これにより、

- 比較の再利用
- sweep の再描画
- 解析結果の再取得
- 後日の再現

を可能にする。

補足:

- `config.json`, `summary.json`, `diagnostics.json` は export / cache / debug 用の sidecar として残してよい
- ただし一覧取得、tag 検索、group / sweep 集約、analysis lineage は directory scan ではなく DB query を正本にする

### 5.7 Physics Messaging と Research Judgment の境界

UI / API / docs は、physics messaging の境界を共有する。

最低限守ること:

- `second_born` は prototype
- `second_born_reference` は equal-time GKBA contour-dressed scope における reference path
- full contour second Born は future target
- `k` 空間 / `tr-ARPES` は run 由来の derived analysis surface であり、`representation=k_space` native solver path と同一視しない
- `validation_status=accepted/rejected` は study 局所の研究判断であり、backend solver validation の `validated / partially validated / prototype only / not validated` を置き換えない
- `evidence bundle` は証跡整理 artifact であり、validated label を自動付与しない
- demo preset と baseline preset を混同しない

この境界は、表示ラベル、preset、compare view、analysis summary のすべてで維持する。

---

## 6. Development And Validation Workflow

### 6.1 開発順序の原則

最初に固定すべきものは solver detail ではなく、次である。

- research artifact schema (`study` / `decision note` / `evidence bundle`)
- parameter schema
- artifact state model
- experiment registry schema
- API response format
- storage format

この順序により、
frontend と backend を並行開発できる。

### 6.2 実験管理 DB の導入時期

導入時期は **P1 完了直後、P2 着手前** を正本とする。

判断理由:

- P1 の単一 run workbench までは現行 `FileRunStorage` でも成立する
- ただし P2 の `job group` は parent-child 関係、集約 state、variant metadata を要求するため、directory scan ベースではすぐ破綻する
- P3 の `sweep` は `parameter_path` / `parameter_value` 索引が必須であり、P2 後に DB を入れると migration cost が増える
- P4 の derived analysis 再利用は lineage と cache key を durable に持つ必要がある

したがって、
**DB は compare / sweep / analysis の前提基盤であり、後付け機能ではない。**

導入順序:

1. `RunRepository` 相当の抽象を切り出し、filesystem 実装と DB-backed metadata 実装を分離する
2. run 作成時に DB へ metadata を書き、配列 payload は従来どおり file artifact へ保存する
3. 既存 `backend/data/runs/*` を DB へ backfill する indexer を用意する
4. `/runs` 一覧・検索・filter を DB query に切り替える
5. その後で `job group` / `sweep` / `derived analysis` を実装する

昇格条件:

- SQLite のままで十分なのは、単一ユーザー、単一ホスト、ローカル worker が前提の間
- PostgreSQL へ上げるのは、複数 worker、再起動後の queue 回復、共有環境、または artifact 数が directory scan / SQLite 運用を超えてきた段階

### 6.3 frontend / backend の並行開発

- frontend は typed mock / stable API contract で先行開発できるようにする
- backend は CLI / process runner / API の順で固める
- API 連携は mock から実 artifact へ差し替える

### 6.4 テスト方針

backend の physics validation 判定は [validation-spec.md](./validation-spec.md) を正本とする。  
この文書では、研究アプリの開発動線を守る test を次のように位置づける。

- backend workflow test
  - study / run / group / sweep / decision-note / evidence-bundle lifecycle
  - artifact retrieval と lineage
  - rejected run の保持と検索
  - cancel / error propagation
- frontend rendering test
  - study context rendering
  - config editing
  - tab navigation
  - plot surface rendering
  - decision note / evidence bundle 導線
  - validation scope messaging
- end-to-end test
  - baseline preset / demo preset 選択
  - parameter input
  - artifact launch
  - completion wait
  - result / derived analysis / evidence bundle display

DB 導入後は、これに加えて次を backend workflow test に含める。

- run metadata backfill
- study / note / bundle metadata backfill
- tag / preset / parameter path による filter
- `validation_status` / `failure_tags` による filter
- group / sweep の親子関係整合
- evidence bundle provenance の整合
- API 再起動後の state 再構成

### 6.5 現行運用の維持

現行の開発 / 起動 / check 方針は維持する。

- Docker Compose で backend + frontend build を起動可能
- frontend は Vite HMR でローカル開発可能
- backend test, frontend test, frontend build を継続運用する

---

## 7. Extensibility

### 7.1 将来の物理拡張

この workbench は将来的に次を受け入れる前提で設計する。

- k 空間表現
- 実空間分布
- 不純物効果
- 新 pairing channel
- electron-phonon サブプロジェクト

### 7.2 UI で先に固定すべき抽象

将来拡張に備えて、UI は次を固定する。

- observable 名だけで画面設計を閉じない
- 軸情報を持つ `data surface` を primary にする
- compare / sweep / single job が同じ surface registry を参照する
- pairing channel は registry 拡張可能にする

### 7.3 p-wave の扱い

ユーザー体験上は、将来的に
`s-wave`, `d-wave`, `p-wave`
を並べて比較したい。

ただし現時点の backend schema では `p-wave` は未実装である。  
したがって初期段階では

- docs では future extension として明記する
- UI 実装時は disabled / future option として扱う

を原則とする。

### 7.4 k 空間 / 実空間 / 不純物

`k` 空間 derived analysis は P6 で扱い、`representation=k_space` native solver path は backend capability として段階導入し、不純物効果の本実装は後続フェーズとする。  
ただし frontend は最初から

- 軸 selector
- surface descriptor
- compare / sweep plotting primitive

を一般化しておくことで、
「時間波形 UI を後から壊して作り直す」事態を避ける。

---

## 8. Roadmap

### P0: Foundation

目的:

- workbench 全体方針を docs で固定する
- docs 間の役割衝突を解消する
- 次フェーズの正本を一本化する

成果物:

- `docs/research-workbench-plan.md`
- 参照更新
- legacy 高水準 plan の統合と削除

### P1: Single Job Workbench

目的:

- 単一 run の観察を workbench 水準へ引き上げる

成果物:

- top-level navigation shell
- single-job surface
- preset 導線
- baseline / failure / validation context panel
- derived analysis 起動導線
- Higgs demo first preset

受け入れ条件:

- 単一 run に対して時系列、diagnostics、FFT が一画面で確認できる
- validation scope badge を常時表示できる
- baseline と current run の関係が可視である
- failure / rejection reason を表示できる

### P1.5: Experiment Registry Foundation

目的:

- compare / sweep / analysis に先立ち、実験メタデータ管理を durable にする

成果物:

- SQLite ベースの `experiment registry`
- `study` / run / note / bundle metadata schema と relation schema
- filesystem artifact と DB metadata を束ねる repository 層
- 既存 run directory を再索引する backfill / migration utility

受け入れ条件:

- 既存 run を DB に取り込み、一意な artifact metadata として検索できる
- `/runs` 一覧が directory scan ではなく DB query を正本にする
- `study`, `decision note`, `evidence bundle` を registry に格納できる
- `study_id`, `run_role`, `validation_status`, `failure_tags`, `group_id`, `sweep_id`, `preset_id`, `tags`, `config_hash` を run metadata に保持できる
- compare / sweep 実装の前提となる parent-child relation を表現できる

### P2: Compare Jobs

目的:

- 比較を run 単位から group 単位へ昇格させる

成果物:

- `job group` API / 型 / storage
- compare tab
- overlay / difference / FFT compare
- physics hypothesis / numerical validation compare template

受け入れ条件:

- backend では base config から variant 群を作成できる
- backend では `comparison_kind=physics_hypothesis|numerical_validation` を保持できる
- backend では複数 run の比較を一つの artifact として再利用できる
- frontend compare tab から artifact の launch / fetch / re-read ができる
- accepted / rejected と failure reason を比較 artifact 上で再読できる

### P3: Parameter Sweep

目的:

- 1D parameter dependence を定常作業として扱えるようにする

成果物:

- `sweep` API / 型 / storage
- sweep tab
- `parameter x time` / `parameter x frequency` heatmap
- numerical sweep 用 convergence row / error surface

受け入れ条件:

- backend では scalar parameter の 1D sweep を起動できる
- backend では `dt` や tolerance sweep を `parameter_kind=numerical` で保存できる
- frontend sweep tab から heatmap / representative run drill-down ができる
- numerical sweep を physics sweep と同じ抽象で frontend から再取得できる

### P4: Advanced Analysis And Evidence

目的:

- simulation 後の解析を保存資産として扱えるようにする

成果物:

- `derived analysis artifact`
- `evidence bundle`
- FFT, peak extraction, metadata 保存
- compare / sweep からの再利用

受け入れ条件:

- backend では同じ run に対する解析を再計算せず再取得できる
- backend では compare / sweep で共通解析結果を使い回せる
- backend では evidence bundle から source run / analysis / validation scope を一意に辿れる
- frontend から analysis result / bundle resolved provenance を実用的に読める

### P5: Future Physics Surfaces

目的:

- k 空間、実空間、不純物、追加 pairing を受け入れる

成果物:

- axis-aware surface registry の拡張
- future physics surface 用 panel
- compare / sweep の多軸化方針

受け入れ条件:

- 新しい軸を追加しても single / compare / sweep の UI ルールが壊れない

### P6: k-Space / tr-ARPES Derived Analysis

目的:

- 既存 real-space / Green-function run artifact から momentum-resolved feature を再構成する
- `tr-ARPES` を measurement-like derived analysis として扱い、solver core と切り分ける
- P7 の correlated native extension が入ったときに `second_born_reference` を同一 analysis contract へ接続できるよう、先に derived analysis 側の contract と threshold を固める

成果物:

- `k_spectral_preview` / `tr_arpes_preview` derived analysis artifact
- `k-path` 解析 panel
- probe delay / broadening / occupied spectrum の metadata
- `job_group/k_spectral_compare`
- `sweep/tr_arpes_heatmap`

M0-M3:

- `M0`: theory / validation / workbench spec closure
- `M1`: mean-field k-space spectrum
- `M2`: correlated extension
- `M3`: workbench surface integration

受け入れ条件:

- `k` 空間と `tr-ARPES` が run 由来の derived analysis artifact として保存・再取得できる
- `A(k, \omega, t)` と occupied spectrum の関係が docs / code / diagnostics で一貫する
- `tr-ARPES` は matrix element を持たない最小測定モデルとして定義される
- `second_born_reference` correlated source 拡張に備えて、analysis contract / threshold / metadata が先に固定される
- `Single Job` / `Compare Jobs` / `Parameter Sweep` に k-space surface を載せる前提が固まる

P6 の境界:

- P6 は derived analysis surface と result payload の完成を扱う
- native `representation=k_space` solver path の correlated 拡張は扱わない
- `second_born_reference` source 対応は P7 相当の backend capability / validation expansion に属する
- derived analysis と native representation を同一の roadmap item にまとめない

### P7: k-Space Native Solver Representation

目的:

- periodic square lattice の solver backend に `representation=real_space|k_space` を導入する
- 既存 observables / diagnostics / Green-function contract を保ったまま basis mode を切り替えられるようにする
- `noninteracting`、`tdhfb`、`kbe_hfb(self_energy=hfb)` で parity row を閉じる
- 後続の correlated native extension として `second_born_reference(representation=k_space)` を受け入れ可能な validation 枠組みを用意する

現時点の到達点:

- backend は `representation=k_space` を periodic square lattice に対して実装済み
- `noninteracting`、`tdhfb`、`kbe_hfb(self_energy=hfb)` の parity regression を backend に追加済み
- `second_born` / `second_born_reference` は未対応

次フェーズの前提:

- まず `tdhfb` / `kbe_hfb(self_energy=hfb)` の larger-system / longer-time row を整備する
- 次に P6 側の k-space / tr-ARPES threshold と benchmark row を固める
- その後に `second_born_reference(representation=k_space)` の公開境界と acceptance gate を定義する
- correlated native extension の initial target は `partially validated` であり、いきなり `validated` を目標にしない

受け入れ条件:

- basis mode を変えても既存 run artifact contract が変わらない
- `noninteracting` parity は existing validation row と同等の保証を持つ
- `tdhfb` / `kbe_hfb(self_energy=hfb)` parity は larger-system / longer-time row まで拡張される
- `second_born_reference(representation=k_space)` の公開境界が periodic scope / artifact contract / derived-analysis source reuse / reduced-Nambu equal-time GKBA scope の4点で固定される
- `second_born_reference(representation=k_space)` の initial acceptance は `partially validated` を目標とし、independent benchmark または longer-time / larger-system row 拡充後に `validated` を再判定する
- frontend / preset / docs messaging で derived analysis と native representation の境界が維持される

### 8.1 物理フェーズとの対応

physics phase とアプリ実装の対応は次のように読む。

- Phase A-B:
  単一 run の作成、状態遷移、baseline 可視化、非相互作用 benchmark の確認
- Phase C-D:
  paired solver と KBE + HFB の可視化、diagnostics、Green 関数 inspector、仮説比較と numerical check の足場
- Phase E:
  prototype / reference path の切り分け、thermal / mixed / adaptive artifact の表示、backend artifact 化された compare / sweep / analysis / evidence bundle の frontend 接続
- Phase F:
  existing real-space / Green-function artifact を source にした k-space / tr-ARPES derived analysis、mean-field から correlated extension までの段階化

---

## 9. Design Guardrails

- frontend を「backend の薄いビュー」にしない
- ただし physics validation を frontend の見た目で上書きしない
- `study` は collaboration suite ではなく、solo researcher の研究文脈を固定する最小 artifact とする
- compare と sweep は frontend の一時 state ではなく backend artifact として扱う
- derived analysis は disposable な表示ではなく保存資産にする
- `evidence bundle` は証跡整理であって、自動 validation ではない
- rejected run と failure note を捨てない
- default demo は Higgs mode を意識するが、validation scope を超える physics claim はしない
- demo preset と baseline preset を混同しない
- 今ある observable 列挙に UI 設計を閉じ込めない

---

## 10. 現時点の結論

このプロジェクトの次フェーズで作るべきものは、単なる frontend refresh ではない。

作るべきなのは、

> 非平衡超伝導ダイナミクスの simulation、比較、解析、再現を一体化した研究 workbench

である。

そのために、

- `study` を中心にした研究文脈の固定
- top-level navigation で distinct surface を持つ workbench
- backend 管理の `job group` / `sweep`
- 失敗理由と判断を残す `decision note`
- metadata を司る `experiment registry`
- backend 保存の `derived analysis artifact`
- claim candidate を束ねる `evidence bundle`
- Higgs demo を基準にした preset 設計
- demo preset と baseline preset の分離
- 将来の k 空間 / tr-ARPES / 実空間 / 不純物 / 新 pairing channel を見据えた `data surface` 抽象

を、本書の正本として採用する。

2026-03-20 時点では、backend の artifact foundation は `job group` / `sweep` / `derived analysis artifact` / `evidence bundle` まで実装済みであり、加えて periodic scope の `representation=k_space` backend path が `noninteracting` / `tdhfb` / `kbe_hfb(self_energy=hfb)` に入っている。次の主課題は P6 frontend surface と、P7 の correlated extension / validation 拡張である。
