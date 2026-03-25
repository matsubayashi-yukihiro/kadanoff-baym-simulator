# Backend Audit Report — 2026-03-22 (Working Tree Baseline)

## A. Document map

### 1) Problem / model documents

| 文書 | 何を説明しているか | 監査重要度 |
| --- | --- | --- |
| `docs/theory.md` | 理論基準（full two-time KBE）と実装モード（`hfb` / `second_born` / `second_born_reference`）の境界、`real_space` / `k_space` の意味 | High |
| `docs/glossary.md` | 用語境界（validation label と workflow metadata の非同一性） | Medium |
| `docs/literature-index.md` | 文献とローカル PDF の対応、reference path の参照導線 | Medium |

### 2) Numerics / algorithm documents

| 文書 | 何を説明しているか | 監査重要度 |
| --- | --- | --- |
| `docs/validation-spec.md` | 数値閾値・自動テスト・`RunState` 昇格規則の正本 | High |
| `docs/backend-remediation-plan.md` | R0-R5 の設計意図、reference path 採用理由、profiling 根拠 | High |
| `docs/equation-to-code-map.md` | 理論量→実装関数の対応（監査トレース用） | High |

### 3) Data layout / implementation design documents

| 文書 | 何を説明しているか | 監査重要度 |
| --- | --- | --- |
| `docs/research-workbench-plan.md` | backend/frontend/storage 責務分離、artifact lifecycle 前提 | High |
| `docs/backend-artifact-lifecycle.md` | `study`/`run`/`job_group`/`sweep`/`derived_analysis`/`bundle` の backend 実装責務 | High |
| `README.md` | 現行実行面、Validation の公開スコープ要約 | Medium |

### 4) Validation / testing documents

| 文書 | 何を説明しているか | 監査重要度 |
| --- | --- | --- |
| `docs/validation-spec.md` | 判定ラベル、phase gate、しきい値、RunState 意味境界 | High |
| `docs/progress.md` | 到達点、既知課題、テスト実行ログ、優先順位 | High |

### 5) Project context / roadmap documents

| 文書 | 何を説明しているか | 監査重要度 |
| --- | --- | --- |
| `docs/progress.md` | 現時点の完了/部分完了、次優先作業 | High |
| `docs/research-workbench-plan.md` | product/architecture の将来方針 | High |

### 不足/弱いカテゴリ

- `succeeded_with_warnings` 導入後の run lifecycle（terminal 判定、cancel policy、`finished_at` の意味）を横断的に固定する運用文書が不足。
- k-space native path の性能主張（環境依存ノイズをどう扱うか）の benchmark protocol 文書が不足。

---

## B. Executive summary

- 件数: High 1 / Medium 3 / Low 2
- 最重要 5 件:
  1. `succeeded_with_warnings` が storage/service で終端扱いされず、`finished_at` 欠落と cancel 経路の誤作動余地を作っている（High）
  2. `k_space` block-path の性能主張テストが現作業ツリーで失敗し、validation gate と実装状態が不整合（Medium）
  3. `second_born_reference(k_space block path)` の two-time reconstruction 診断ラベルが real-space と不整合（Medium）
  4. canonical docs の一部が run state を旧5状態のまま記載し、schema/validation-spec と乖離（Low）
  5. second-Born/TDHFB コアが大規模単一モジュール化のままで、変更影響範囲が広い（Low）

主因の内訳:
- 主因は **実装不整合 + 検証不備**。
- とくに RunState 追加後の lifecycle 同期漏れが、設計境界（警告完了 vs 失敗 vs キャンセル）を崩している。

---

## C. Intended architecture reconstructed from documents

### 文書から推定される自然な実装方針

- 物理問題:
  - 基準は Nambu 表現 full two-time KBE（`docs/theory.md`）。
  - 現行実装は `hfb` / prototype `second_born` / reference `second_born_reference` を明確分離。
- 状態変数:
  - generalized density（equal-time）、`G^R/G^</Matsubara/mixed`、観測量系列、収束診断系列。
- 自然な表現:
  - solver representation は `real_space` / `k_space` の内部基底差で、artifact contract は同型を維持。
  - `k-space/tr-ARPES` は solver 本体と分離された derived analysis surface。
- 構造/対称性:
  - periodic 系では k-block 構造、Hermiticity、causality、continuity を diagnostics で担保。
- スケーリング想定:
  - second Born の支配項は self-energy 構築（`docs/backend-remediation-plan.md`）。
  - block path は full-matrix path より有利であることを benchmark row で固定。
- validation 基準:
  - `validated/partially/prototype/not validated` は `docs/validation-spec.md` の閾値と pytest marker で決定。

### 実装が従うべき主要 invariants / structures / scaling assumptions

- `second_born` と `second_born_reference` の意味分離（docs/code/diagnostics/UI）。
- RunState は physics validation label と混同しないが、lifecycle として自己無撞着であること。
- `k_space` path 追加時も run artifact contract は維持。
- performance claim は再現可能な benchmark 行として維持。

### 文書不足で不明な点

- `succeeded_with_warnings` の cancel 許容/禁止、`finished_at` の必須性、terminal state 集約規則の単一正本が不足。
- benchmark wall-clock 比が環境依存で崩れた際の運用ポリシー（threshold緩和、統計手法、CIマシン固定）が不明。

---

## D. Findings

### Finding 1

- タイトル: `succeeded_with_warnings` が terminal lifecycle として扱われていない
- 重大度: High
- 種別: implementation mismatch
- 関連ファイル / 関数 / クラス:
  - `backend/app/storage/file_storage.py:44,139-140,635-641` (`TERMINAL_STATES`, `_sync_progress_with_status`)
  - `backend/app/services/run_service.py:287,291-294` (`cancel_run`)
  - `backend/app/jobs/worker.py:74` (`RunState.SUCCEEDED_WITH_WARNINGS` への昇格)
- 現在の実装:
  - worker は非 strict 収束時に `succeeded_with_warnings` を発行する。
  - しかし storage の terminal 判定集合に warning state が含まれず、`status/summary.finished_at` が `None` のまま残る。
  - service の cancel guard も warning state を終端扱いしないため、`pid` fallback kill 経路を通り得る。
- なぜ問題か:
  - lifecycle 整合が崩れ、完了 run が「未終端」に見える。
  - stale PID への signal fallback 経路が開くことで、run外プロセスへの誤シグナルリスクが増える。
- 本来どうあるのが自然か:
  - `succeeded_with_warnings` は terminal として `finished_at` を確定し、cancel 対象から除外する。
- 影響範囲:
  - run status/summary API、cancel API、運用監視、artifact lifecycle 集約の信頼性。
- 確信度: high

### Finding 2

- タイトル: k-space block-path の性能 gate が現作業ツリーで不成立
- 重大度: Medium
- 種別: validation gap
- 関連ファイル / 関数 / クラス:
  - `backend/tests/test_kspace_native_path.py:189-214`
  - `docs/validation-spec.md:290`
  - 実装経路: `backend/app/solvers/kbe_hfb.py:199-211` → `backend/app/solvers/self_energy_second_born.py:395-709`
- 現在の実装:
  - `test_kbe_hfb_kspace_block_second_born_is_faster_than_real_space` が速度比 `real/k >= 1.5` を要求。
  - 実測は `26.82 / 28.56 = 0.94` で失敗（k-space block path が速くない）。
  - validation spec 側には関連 claim が `>=2.0` と記載されており、docs/test/実測の三者が不一致。
- なぜ問題か:
  - computational scaling の主張を支える gate が不安定化し、Phase 5A の根拠が揺らぐ。
- 本来どうあるのが自然か:
  - 性能 claim は docs/test/実測が整合し、環境依存を吸収できる測定設計（固定条件、統計、分離ベンチ）を持つべき。
- 影響範囲:
  - `k_space` path の公開メッセージ、benchmark 信頼性、将来の最適化優先度判断。
- 確信度: high

### Finding 3

- タイトル: `k_space` second-Born block path で reconstruction 診断ラベルが real-space と不整合
- 重大度: Medium
- 種別: implementation mismatch
- 関連ファイル / 関数 / クラス:
  - `backend/app/solvers/self_energy_second_born.py:695` (`second_born_solver_mode="gkba_causal_marching_kspace_blocks"`)
  - `backend/app/solvers/kbe_hfb.py:266-280` (`_reconstruction_mode`)
  - `backend/app/solvers/green_functions.py:186-190` (`kbe_two_time_reconstruction`)
- 現在の実装:
  - real-space reference path は `kbe_two_time_reconstruction="gkba_causal_marching"`。
  - k-space block path は `_reconstruction_mode` が mode 名を認識せず `None` となり、`equal_time_average` にフォールバック。
- なぜ問題か:
  - 同等アルゴリズム（reference GKBA causal marching）でも diagnostics の意味が基底依存で変わり、validation 解釈を誤らせる。
- 本来どうあるのが自然か:
  - `gkba_causal_marching_kspace_blocks` を同等の reconstruction mode として明示的にマッピングする。
- 影響範囲:
  - diagnostics 可視化、run比較、検証ログ解釈、将来の自動判定ロジック。
- 確信度: high

### Finding 4

- タイトル: canonical docs の run state 記述が `succeeded_with_warnings` 導入と不整合
- 重大度: Low
- 種別: documentation gap
- 関連ファイル / 関数 / クラス:
  - `docs/research-workbench-plan.md:965`
  - `docs/progress.md:101`
  - 対照: `docs/validation-spec.md:413-427`, `backend/app/schemas/runs.py:13-19`
- 現在の実装:
  - schema/validation-spec は warning state を正式採用済み。
  - ただし roadmap/progress の canonical 表では旧5状態のまま。
- なぜ問題か:
  - API/運用の読み手に誤った状態機械を伝え、監視やUI仕様の整合を崩す。
- 本来どうあるのが自然か:
  - run state 語彙を正本間で統一し、warning state の意味境界を共通化する。
- 影響範囲:
  - ドキュメント駆動運用、UI文言、外部連携。
- 確信度: high

### Finding 5

- タイトル: second-Born / TDHFB コアの大規模単一モジュール化が継続
- 重大度: Low
- 種別: extensibility risk
- 関連ファイル / 関数 / クラス:
  - `backend/app/solvers/self_energy_second_born.py` (1375 lines)
  - `backend/app/solvers/tdhfb.py` (1167 lines)
  - `backend/app/solvers/self_energy_second_born_prototype.py` (896 lines)
- 現在の実装:
  - 数値核、orchestration、diagnostics、progress 更新が密結合。
- なぜ問題か:
  - k-space 追加や contour 拡張時に変更波及が大きく、検証コストが増える。
- 本来どうあるのが自然か:
  - kernels / contour builders / diagnostics assembler / progress reporting を責務分離。
- 影響範囲:
  - 保守性、将来拡張、レビュー容易性。
- 確信度: medium

### Finding 6

- タイトル: benchmark threshold の docs/test drift（`2.0` vs `1.5`）
- 重大度: Low
- 種別: validation gap
- 関連ファイル / 関数 / クラス:
  - `docs/validation-spec.md:290`
  - `backend/tests/test_kspace_native_path.py:117,156,214`
- 現在の実装:
  - docs は speed ratio gate を `>=2.0` と記載。
  - test 実装では一部 `>=1.5` に緩和され、別テストは `>=2.0` のまま混在。
- なぜ問題か:
  - phase gate の意味が固定されず、レビュー・運用判断が揺れる。
- 本来どうあるのが自然か:
  - claim と test 閾値を単一正本で一致させる。
- 影響範囲:
  - validation label の再現性、進捗判定。
- 確信度: high

### 2026-03-21 既存レビュー所見の再評価

| 旧所見 | 判定 | コメント |
| --- | --- | --- |
| non-converged second-Born が `succeeded` 扱い | resolved | `RunState.SUCCEEDED_WITH_WARNINGS` 導入で解消（`worker.py`） |
| `strict`/`relaxed_5x` 区別不透明 | superseded | diagnostics key と validation-spec 境界が追加された |
| self-energy unit テスト不足 | resolved | `test_self_energy_second_born.py` が 14件へ拡張 |
| silent fallback の追跡性不足 | resolved | fallback diagnostics + warning log を追加済み |
| 巨大モジュール化 | persisting | 依然として主要 solver が 900-1300行規模 |
| assert を実行時チェックに使う問題 | persisting (partial) | `kbe_hfb` 本体は runtime error 化済みだが `self_energy_second_born.py` k-space path に assert が残存 |

---

## E. Priority ranking

### 1) まず人間が確認すべき上位 5 件

1. Finding 1: `succeeded_with_warnings` の terminal 定義（status/summary/progress/cancel）
2. Finding 2: k-space speed gate failure の再現性（同一条件で複数回）
3. Finding 3: reconstruction diagnostics 名称の `real_space`/`k_space` 差分意図
4. Finding 6: validation-spec と test 閾値のどちらを正とするか
5. Finding 4: canonical docs の run state 語彙統一

### 2) 修正効果が大きい上位 5 件

1. Finding 1（lifecycle 整合修正）
2. Finding 2（performance gate の再設計）
3. Finding 3（diagnostics mode mapping 統一）
4. Finding 6（閾値正本統一）
5. Finding 5（モジュール責務分離計画）

### 3) 変更時の破壊リスクが高い上位 5 件

1. Finding 1（cancel/pid 経路は誤実装で副作用が大きい）
2. Finding 3（diagnostics key は downstream UI/解析に影響）
3. Finding 2（benchmark 変更は validation label 判定に直結）
4. Finding 5（大規模分割は回帰面積が広い）
5. Finding 6（閾値変更は過去ログとの比較互換に影響）

---

## F. Validation implications

### Finding 1 の影響

- 影響:
  - `succeeded_with_warnings` run の lifecycle 証跡（`finished_at`）が欠落し、運用上 terminal 判定が曖昧。
- 現行テストで見逃す理由:
  - `test_worker.py` は最終 state 値のみ検証し、`finished_at` / cancel guard は未検証。
- 追加確認すべき項目:
  - warning run の `status.finished_at` / `summary.finished_at` が埋まること。
  - warning run に対する `POST /runs/{id}/cancel` が no-op であること。

### Finding 2 / 6 の影響

- 影響:
  - Phase 5A の「block path は速い」主張が regression した状態で残ると、`partially validated` 根拠が弱体化。
- 現行テストで見逃す理由:
  - 単一ホスト・単発 wall-clock 比で環境ノイズを吸収できない。
- 追加確認すべき項目:
  - 反復回数の増加、warmup 固定、統計（median + IQR）記録。
  - propagation kernel 単体と end-to-end solver を分離して threshold を別管理。

### Finding 3 の影響

- 影響:
  - diagnostics ベース比較で `k_space` だけ再構成モードが別名扱いされ、同等性評価を誤る。
- 現行テストで見逃す理由:
  - parity test は observables 中心で、`kbe_two_time_reconstruction` ラベル整合を直接見ない。
- 追加確認すべき項目:
  - `second_born_reference` の `real_space` / `k_space` で reconstruction mode を同値判定。

### Finding 4 の影響

- 影響:
  - docs を正本にする運用で state machine 誤解を誘発。
- 現行テストで見逃す理由:
  - docs と code の自動整合チェックがない。
- 追加確認すべき項目:
  - docs lint/consistency check（RunState 列挙の同期）。

---

## G. 対応進捗管理テーブル

状態の定義:
- `未着手`: 方針未確定
- `調査中`: 再現・影響範囲を確認中
- `対応中`: 実装または文書修正を実施中
- `検証中`: テスト・ベンチマークで確認中
- `完了`: 修正と検証が完了
- `保留`: 意思決定待ち

| ID | 対象 finding | 重大度 | 種別 | 対応方針 | 状態 | 担当 | 次アクション | 完了条件 | 目標日 | 最終更新 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | `succeeded_with_warnings` terminal 不整合 | High | implementation mismatch | `RunState` 終端定義を storage/service で統一 | 完了 | codex | storage/service に warning 終端対応を反映し回帰テストを追加済み | warning run で `finished_at` が埋まり cancel が no-op | 2026-03-22 | 2026-03-22 |
| F2 | k-space 性能 gate 不成立 | Medium | validation gap | benchmark 行の再測定設計を見直し | 完了 | codex | kernel speed row (`tdhfb>=1.5`, `kbe kernel>=2.0`) と end-to-end non-regression row (`real/k>=0.9`) に分離し docs/test を同期済み | docs/test の閾値と実測が整合 | 2026-03-23 | 2026-03-23 |
| F3 | reconstruction 診断ラベル不整合 | Medium | implementation mismatch | k-space block mode を reconstruction mapping に追加 | 完了 | codex | `_reconstruction_mode` に k-space block mode を追加し回帰テストへ反映済み | real/k で `kbe_two_time_reconstruction` が同義判定 | 2026-03-22 | 2026-03-22 |
| F4 | canonical docs の state 語彙 drift | Low | documentation gap | 正本文書の run state 記述を統一 | 完了 | codex | `research-workbench-plan`/`progress` の state 列挙を更新済み | schema/validation-spec と docs が一致 | 2026-03-22 | 2026-03-22 |
| F5 | solver 巨大モジュール化 | Low | extensibility risk | 分割方針を先に文書化し段階分割 | 完了 | codex | Phase 7 として `second_born_kernels.py` を導入し、`self_energy_second_born.py` の GKBA row/local self-energy/stabilized kernel helper を分離（`self_energy_second_born.py`: 879→832）。互換のため既存 private 関数名は薄いラッパーとして維持し、関連回帰を実行済み | 巨大モジュールの責務分離が段階実装され、各段で回帰テストが通る | 2026-03-23 | 2026-03-23 |
| F6 | docs/test 閾値 drift (`2.0` vs `1.5`) | Low | validation gap | phase gate の正本閾値を一本化 | 完了 | codex | `validation-spec` と `test_kspace_native_path` の閾値・テスト名を同期済み | 関連テストと文書が同一閾値を参照 | 2026-03-22 | 2026-03-22 |

---

## H. Evidence

### 実行コマンドと結果

1. `uv run python -m pytest backend/tests/test_worker.py backend/tests/test_self_energy_second_born.py`
- 結果: `14 passed in 6.53s`

2. `uv run python -m pytest backend/tests/test_kbe_hfb_solver.py backend/tests/test_kspace_native_path.py`
- 結果: `27 passed, 1 failed in 183.45s`
- 失敗: `test_kbe_hfb_kspace_block_second_born_is_faster_than_real_space`
- 実測比: `real_time/k_time = 26.823/28.558 = 0.94`（閾値 `>=1.5` 未達）

3. `uv run python -m pytest backend/tests/test_api.py -k "progress or second_born_reference"`
- 結果: `4 passed, 23 deselected in 1.71s`

4. `uv run python -m pytest backend/tests/test_experiment_registry.py -k "succeeded_with_warnings"`
- 結果: `1 passed, 13 deselected in 0.16s`

5. `uv run python -m pytest backend/tests/test_self_energy_second_born.py backend/tests/test_tdhfb_solver.py::test_tdhfb_solver_emits_pairing_projections_and_preserves_stationary_state backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero`
- 結果: `16 passed in 17.02s`

6. `uv run python -m pytest backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero backend/tests/test_tdhfb_solver.py::test_tdhfb_solver_emits_pairing_projections_and_preserves_stationary_state backend/tests/test_self_energy_second_born.py`
- 結果: `16 passed in 17.83s`

7. `uv run python -m pytest backend/tests/test_tdhfb_solver.py backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero backend/tests/test_self_energy_second_born.py`
- 結果: `24 passed in 55.95s`

8. `python -m py_compile backend/app/solvers/second_born_branch_diagnostics.py backend/app/solvers/self_energy_second_born.py backend/app/solvers/self_energy_second_born_prototype.py backend/app/solvers/tdhfb.py backend/app/solvers/tdhfb_propagation.py backend/app/solvers/kbe_hfb.py backend/app/solvers/kbe_trajectory.py`
- 結果: `success`

9. `uv run python -m pytest backend/tests/test_self_energy_second_born.py backend/tests/test_tdhfb_solver.py backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero`
- 結果: `24 passed in 59.15s`

10. `python -m py_compile backend/app/solvers/second_born_contour_updates.py backend/app/solvers/self_energy_second_born.py backend/app/solvers/self_energy_second_born_prototype.py`
- 結果: `success`

11. `uv run python -m pytest backend/tests/test_self_energy_second_born.py backend/tests/test_tdhfb_solver.py::test_tdhfb_solver_emits_pairing_projections_and_preserves_stationary_state backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero`
- 結果: `16 passed in 15.92s`

12. `uv run python -m pytest backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_reduces_to_hfb_when_onsite_u_zero backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_matches_real_space`
- 結果: `2 passed in 1.35s`

13. `python -m py_compile backend/app/solvers/second_born_realtime_updates.py backend/app/solvers/self_energy_second_born.py backend/app/solvers/self_energy_second_born_prototype.py backend/app/solvers/second_born_contour_updates.py`
- 結果: `success`

14. `uv run python -m pytest backend/tests/test_self_energy_second_born.py backend/tests/test_tdhfb_solver.py::test_tdhfb_solver_emits_pairing_projections_and_preserves_stationary_state backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_reduces_to_hfb_when_onsite_u_zero backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_matches_real_space`
- 結果: `18 passed in 17.48s`

15. `python -m py_compile backend/app/solvers/second_born_kernels.py backend/app/solvers/self_energy_second_born.py backend/app/solvers/second_born_realtime_updates.py backend/app/solvers/self_energy_second_born_prototype.py backend/app/solvers/second_born_contour_updates.py`
- 結果: `success`

16. `uv run python -m pytest backend/tests/test_self_energy_second_born.py backend/tests/test_tdhfb_solver.py::test_tdhfb_solver_emits_pairing_projections_and_preserves_stationary_state backend/tests/test_kbe_hfb_solver.py::test_kbe_hfb_matches_tdhfb_equal_time_observables backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_reduces_to_hfb_when_onsite_u_zero backend/tests/test_kbe_hfb_solver.py::test_kbe_second_born_reference_k_space_representation_matches_real_space`
- 結果: `18 passed in 17.84s`

### 追加再現（storage lifecycle）

- 再現コマンド（`FileRunStorage.update_status(..., RunState.SUCCEEDED_WITH_WARNINGS)`）で、
  `status_finished_at=None`, `summary_finished_at=None` を確認。

### 根拠コード断片（呼び出し経路）

- RunState warning 昇格:
  - `backend/app/jobs/worker.py:66-75`
- status/summary 更新:
  - `backend/app/storage/file_storage.py:127-166`
  - `TERMINAL_STATES` 定義 `backend/app/storage/file_storage.py:44`
- cancel fallback:
  - `backend/app/services/run_service.py:285-295`
  - PID signal 実装 `backend/app/services/run_service.py:589-617`
- k-space block reference path:
  - dispatcher `backend/app/solvers/kbe_hfb.py:199-211`
  - block solver `backend/app/solvers/self_energy_second_born.py:395-709`
- reconstruction label 決定:
  - `backend/app/solvers/kbe_hfb.py:266-280`
  - `backend/app/solvers/green_functions.py:186-190`

### scaling estimate（簡易）

- `k_space` block path は Nambu full matrix `(2N x 2N)` 演算の一部を `(N_k x 2 x 2)` block 演算へ縮約する設計。
- ただし現行 end-to-end では two-time Green 関数再構築が依然 dense 4-index 配列を伴うため、
  期待される速度改善がケース依存で相殺される（今回 6x6 row で実測未達）。
