# Backend Artifact Lifecycle

この文書は、research artifact 系 backend の現行運用を整理する補助文書である。  
product / architecture の正本は [research-workbench-plan.md](./research-workbench-plan.md)、physics の正本は [theory.md](./theory.md)、validation label の正本は [validation-spec.md](./validation-spec.md) を参照する。

ここで扱うのは 2026-03-25 時点の backend / frontend 接続事実であり、新しい product decision を追加するものではない。

---

## 1. Purpose And Boundaries

- 目的は、`study` / run metadata / `job group` / `sweep` / `derived analysis artifact` / `evidence bundle` の backend lifecycle を、実装者向けに短く整理することである。
- 正本の役割分担は崩さない。
  - physics の意味と solver scope は `docs/theory.md`
  - validation label の意味は `docs/validation-spec.md`
  - workbench 全体の product / architecture は `docs/research-workbench-plan.md`
  - 進捗と優先順位は `docs/progress.md`
- この文書は backend の責務、主要 API surface、保存 / 再取得の流れ、frontend 未接続部分に絞る。

---

## 2. Artifact Map

### `study`

- 目的:
  - 単発 run ではなく、どの問いに対して compare / sweep / analysis を行っているかを固定する。
- backend での現在の責務:
  - title, question, target observables, acceptance checks, status を durable metadata として保持する。
  - run / group / sweep / analysis / bundle の study 整合の基準になる。
- 主要 API surface:
  - `POST /api/v1/studies`
  - `GET /api/v1/studies`
  - `GET /api/v1/studies/{study_id}`
- frontend 未接続部分:
  - URL deep link と tab / run / group / sweep との連携は未完。

### run metadata

- 目的:
  - solver run 自体は file artifact として維持しつつ、研究文脈を registry 側で索引できるようにする。
- backend での現在の責務:
  - `study_id`, `run_role`, `validation_status`, `failure_tags`, `group_id`, `sweep_id`, `variant_label`, `preset_id`, `tags`, `config_hash`, `storage_uri` を保持する。
  - `/runs` 一覧の正本を directory scan ではなく DB query にする。
- 主要 API surface:
  - `GET /api/v1/runs`
  - `GET /api/v1/runs/{run_id}`
  - `PATCH /api/v1/runs/{run_id}/metadata`
- frontend 未接続部分:
  - `study` や compare / sweep 導線と結びついた URL state は未実装。

### `job group`

- 目的:
  - 複数 run の比較を一つの parent artifact として保持する。
- backend での現在の責務:
  - variant 群、baseline、`comparison_kind`、child run relation、親 artifact の状態集約を保持する。
  - launch 時に base config から child run を生成し、各 child run に `group_id` と `variant_label` を同期する。
- 主要 API surface:
  - `POST /api/v1/job-groups`
  - `POST /api/v1/job-groups/launch`
  - `GET /api/v1/job-groups`
  - `GET /api/v1/job-groups/{group_id}`
- frontend 未接続部分:
  - study / bundle を横断する deep link や filter 導線は未完。

### `sweep`

- 目的:
  - scalar parameter の 1D sweep を parent artifact として保持する。
- backend での現在の責務:
  - `parameter_path`, `parameter_kind`, candidate values, child run relation, 親 artifact の状態集約を保持する。
  - launch 時に base config から child run を生成し、各 child run に `sweep_id` と必要な metadata を同期する。
- 主要 API surface:
  - `POST /api/v1/sweeps`
  - `POST /api/v1/sweeps/launch`
  - `GET /api/v1/sweeps`
  - `GET /api/v1/sweeps/{sweep_id}`
- frontend 未接続部分:
  - study / bundle を横断する deep link や filter 導線は未完。

### `derived analysis artifact`

- 目的:
  - FFT などの解析結果を disposable preview ではなく再利用可能な保存資産として扱う。
- backend での現在の責務:
  - source artifact と analysis type、parameters、cache key、result metadata、payload data ref、bundle support link を保持する。
  - `run/fft_preview`, `job_group/fft_compare`, `sweep/fft_heatmap` を backend 生成できる。
  - `run/k_spectral_preview`, `run/tr_arpes_preview`, `job_group/k_spectral_compare`, `sweep/tr_arpes_heatmap` を backend 生成できる。
- 主要 API surface:
  - `POST /api/v1/derived-analyses`
  - `POST /api/v1/derived-analyses/launch`
  - `GET /api/v1/derived-analyses`
  - `GET /api/v1/derived-analyses/{analysis_id}`
  - `GET /api/v1/derived-analyses/{analysis_id}/result`
- frontend 未接続部分:
  - result surface は `Single Job` / `Compare Jobs` / `Parameter Sweep` に接続済みだが、bundle provenance と一覧 filter 導線は薄い。

### `evidence bundle`

- 目的:
  - figure / table / claim candidate を支える run / analysis / validation scope を束ねる。
- backend での現在の責務:
  - artifact refs と analysis refs の study 整合を検証する。
  - `status=draft|ready|superseded` を保持する。
  - derived analysis 側 `supports_bundle_ids` を create / patch で差分同期する。
  - resolved provenance を通じて source artifact / analysis を再読できるようにする。
- 主要 API surface:
  - `POST /api/v1/evidence-bundles`
  - `GET /api/v1/evidence-bundles`
  - `GET /api/v1/evidence-bundles/{bundle_id}`
  - `PATCH /api/v1/evidence-bundles/{bundle_id}`
  - `GET /api/v1/evidence-bundles/{bundle_id}/resolved`
- frontend 未接続部分:
  - 一覧 / deep link / study context をまたぐ導線はまだ薄い。

---

## 3. Current Backend Lifecycle

### `job group` / `sweep`

1. frontend または API client が base config と variant / parameter 定義を送る。
2. backend は parent artifact を registry に作り、child run を生成する。
3. child run の `group_id` / `sweep_id` / `variant_label` を run metadata として同期する。
4. child run state を集約して parent artifact の state を更新する。
5. parent artifact は compare / sweep 系の `derived analysis artifact` の source になれる。

### `derived analysis artifact`

1. client は metadata-only create ではなく、通常は `POST /derived-analyses/launch` を使う。
2. backend は source artifact と analysis type、parameters を検証し、cache key を評価する。
3. cache hit なら既存 analysis を返し、cache miss なら payload を生成する。
4. payload 本体は file artifact として保存し、registry には result metadata と `data_refs` を残す。
5. `GET /derived-analyses/{analysis_id}/result` で payload を再取得する。
6. analysis は `evidence bundle` から参照されると `supports_bundle_ids` を逆同期される。

現時点の analysis type:

- `source_kind=run`, `analysis_type=fft_preview`
- `source_kind=run`, `analysis_type=k_spectral_preview`
- `source_kind=run`, `analysis_type=tr_arpes_preview`
- `source_kind=job_group`, `analysis_type=fft_compare`
- `source_kind=job_group`, `analysis_type=k_spectral_compare`
- `source_kind=sweep`, `analysis_type=fft_heatmap`
- `source_kind=sweep`, `analysis_type=tr_arpes_heatmap`

### `evidence bundle`

1. client が bundle metadata、artifact refs、analysis refs、validation scope を送る。
2. backend は参照先の存在と `study_id` 整合を検証する。
3. bundle を registry に保存し、参照された analysis 側へ `supports_bundle_ids` を逆同期する。
4. patch 時は旧 refs と新 refs の差分を見て、analysis support link を追加 / 削除する。
5. `GET /evidence-bundles/{bundle_id}/resolved` で source artifact / analysis provenance を展開する。

### persistence / restart

- metadata, relation, state aggregation は SQLite-backed な `experiment registry` を正本にする。
- observables, Green 関数, derived-analysis payload などの大きいデータは file artifact に保存する。
- run 実行中の execution telemetry は run artifact 配下の `progress.json` に保存し、`GET /runs/{run_id}/progress` で再取得する。
- bundle status migration と、analysis payload / bundle resolved provenance の restart persistence は workflow regression 済みである。

---

## 4. API Surface Summary

現在の backend artifact 系 surface を実装者向けにまとめると次の通りである。

- `studies`
  - create / list / get
- `runs`
  - create / list / get / progress / cancel / metadata patch / log / observables / contour slices
- `job-groups`
  - create / launch / list / get
- `sweeps`
  - create / launch / list / get
- `decision-notes`
  - create / list / get
- `derived-analyses`
  - create / launch / list / get / result
- `evidence-bundles`
  - create / list / get / patch / resolved

list query の現状:

- `evidence-bundles` は `study_id` と `status` で絞り込める。
- run 一覧は research metadata を含む。
- group / sweep / analysis の richer filter surface は将来拡張の余地がある。

---

## 5. Validation / Research Metadata Boundary

- `validated` / `partially validated` / `prototype only` / `not validated` は solver validation の語彙であり、正本は `docs/validation-spec.md` である。
- `study`, `run_role`, `validation_status`, `comparison_kind`, `parameter_kind`, `evidence bundle` は research workflow metadata であり、solver validation label の代用品ではない。
- `validation_status=accepted/rejected` は study 局所の研究判断であって、backend solver validation の保証範囲を上書きしない。
- `evidence bundle` は証跡整理 artifact であり、その存在だけで claim が validated になるわけではない。

---

## 6. Known Gaps For Frontend Integration

- `Single Job` の running telemetry は `progress.json` / progress API を正本とし、`run.log` は terminal 後の詳細出力面として維持する。
- `study` / tab / run / group / sweep / bundle を横断する URL deep link は未実装である。
- bundle 一覧、resolved provenance、analysis result の使い勝手は frontend 導線次第でまだ改善余地がある。
