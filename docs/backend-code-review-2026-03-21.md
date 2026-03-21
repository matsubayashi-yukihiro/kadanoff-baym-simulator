# Backend Code Review (Solver-Centric) — 2026-03-21

## 1. Review Scope & Method

- 対象: `backend/app/solvers` を主対象に、`backend/tests` の対応テストを照合。
- 影響範囲確認: `backend/app/jobs/worker.py`, `backend/app/services/run_service.py`, `backend/app/schemas/simulation.py` を追加確認。
- 除外: frontend 実装、storage 詳細実装、E2E。
- 正本として参照した文書:
  - `docs/theory.md`
  - `docs/validation-spec.md`
  - `docs/progress.md`
- 方法:
  - 静的読解（実装とテストの突合）
  - pytest 実行（本ファイル末尾 Evidence 参照）

## 2. Findings (Severity Order)

### Critical

- 該当なし。

### High

- `second_born` / `second_born_reference` の fixed-point 非収束が run state に反映されず、ジョブが `succeeded` になる可能性
  - 該当箇所:
    - `backend/app/solvers/self_energy_second_born.py:97-258,262-313`
    - `backend/app/solvers/self_energy_second_born_prototype.py:95-297,303-320`
    - `backend/app/jobs/worker.py:41-71`
  - 事実:
    - solver 側は `second_born_converged` を diagnostics に保持するが、非収束でも例外は投げない実装。
    - worker 側は例外がなければ `RunState.SUCCEEDED` を設定する。
  - 推測:
    - 収束失敗 run が API/UI 上で「成功」と見える運用上の誤認リスクがある。
  - 再現/確認手順:
    1. `kbe.self_energy=second_born_reference` で `max_fixed_point_iterations` を低く、`mixing` を不利に設定。
    2. 結果の `diagnostics.second_born_converged` と run status を比較。
  - 影響:
    - 研究ワークフローで successful run と validated claim の境界が曖昧化する。
  - 推奨修正:
    - 運用ポリシーを明文化し、少なくとも次のいずれかを導入:
      - `second_born_converged=False` を `RunState.FAILED` または `warning` 状態に昇格。
      - `RunState.SUCCEEDED_WITH_WARNINGS` 相当の状態を追加し UI/API で明示。

### Medium

- fixed-point 許容判定が公称 tolerance の 5 倍まで緩和される
  - 該当箇所:
    - `backend/app/solvers/self_energy_second_born.py:254-255`
    - `backend/app/solvers/self_energy_second_born_prototype.py:282-283`
    - （同様の緩和判定が thermal/mixed branch 側にも存在）
  - 事実:
    - `last_residual <= 5.0 * tolerance` なら `converged_step=True` と判定される。
  - 推測:
    - 数値実務上の安定化策としては合理的だが、診断上の「converged」の意味が直感より広い。
  - 再現/確認手順:
    1. tolerance 近傍で residual history を観察。
    2. `converged=True` だが residual が tolerance 超過のケースを確認。
  - 影響:
    - 収束解釈の誤読により benchmark 比較や threshold 設計を誤る可能性。
  - 推奨修正:
    - diagnostics に `convergence_criterion`（`strict` / `relaxed_5x`）を明示追加。

- `self_energy_second_born` 本体に対する unit 粒度テストが薄く、回帰検知が benchmark/invariant 偏重
  - 該当箇所:
    - `backend/tests/test_self_energy_second_born.py:1-40`
    - 対象実装規模: `backend/app/solvers/self_energy_second_born.py` (919 lines)
  - 事実:
    - unit marker の当該ファイルは `_build_local_second_born_self_energy` 単体テスト 1 件。
    - 主要ロジック（GKBA 行再構成、mixed/thermal coupling、equation residual）は主に invariant/benchmark で間接検証。
  - 推測:
    - 局所変更時に、どの構成要素が壊れたかを unit レベルで即座に特定しづらい。
  - 再現/確認手順:
    1. `pytest backend/tests/test_self_energy_second_born.py`（1件のみ）
    2. 失敗時の局所化可能性を他 suite と比較。
  - 影響:
    - 開発速度低下、デバッグコスト増、将来の refactor 抵抗。
  - 推奨修正:
    - 低コストで次を unit 化: `_build_gkba_row_data`, `_damping_collision`, thermal/mixed branch の最小 shape/対称性検査。

### Low

- 可読性/保守性リスク（巨大モジュール化）
  - 該当箇所:
    - `backend/app/solvers/self_energy_second_born.py` (919 lines)
    - `backend/app/solvers/self_energy_second_born_prototype.py` (779 lines)
    - `backend/app/solvers/kbe_hfb.py` (599 lines)
  - 事実:
    - 1 モジュール内に orchestration・数値核・diagnostics・progress 報告が同居。
  - 推測:
    - 仕様追加時の副作用範囲が広く、レビュー難易度が上がる。
  - 再現/確認手順:
    - 単一関数変更で影響 import/責務をトレース。
  - 影響:
    - 保守性低下（ただし現時点で機能不全を示す直接証拠はなし）。
  - 推奨修正:
    - 「数値カーネル」「contour branch」「diagnostics assembler」に段階分割。

## 3. Physics Review

- `second_born` と `second_born_reference` はコード上で明確に分離されている。
  - `backend/app/solvers/kbe_hfb.py:165-211`
  - 診断ラベルも区別（`second_born_reference_implementation` など）。
- `validation-spec` が要求する claim 境界（prototype only と reference path の分離）とは整合。
- source-free continuity diagnostics は HFB mode 限定で有効化されており、未検証領域の過剰主張を抑制。
  - `backend/app/solvers/kbe_hfb.py:374-383`
- 残存リスク:
  - run 成功/失敗と solver 収束診断の意味境界が UI/API 運用で誤読されうる（High findings 参照）。

## 4. Algorithm Review

- 良い点:
  - causal history rule と memory window を明示的に実装し、diagnostics へ履歴を保存。
  - adaptive tolerance と memory-window row の benchmark regression が整備済み。
- 注意点:
  - 収束判定の緩和（`5x tolerance`）は実務上の救済策だが、strict 判定と区別表示が必要。
  - 非収束でも結果を返せる設計のため、下流での扱いを設計的に固定する必要がある。

## 5. Software Engineering Review

- 良い点:
  - schema で `k_space` 制約、`second_born` 非対応境界、equilibrium method 整合を検証しており、防波堤として機能。
    - `backend/app/schemas/simulation.py:229-253`
  - solver registry / worker / repository の責務は分離されている。
- 改善余地:
  - solver モジュールの責務密度が高く、テストの粒度と合わせて将来変更の負債になりうる。
  - run lifecycle で diagnostics ベースの warning 昇格規約が未定義。

## 6. Evidence

### 実行コマンド

```bash
uv run python -m pytest backend/tests/test_kbe_hfb_solver.py
uv run python -m pytest backend/tests/test_self_energy_second_born.py
uv run python -m pytest backend/tests/test_kbe_stationarity.py
uv run python -m pytest backend/tests/test_exact_diagonalization_benchmark.py -k 'second_born or kbe_hfb or tdhfb'
uv run python -m pytest backend/tests -m physics_invariant
```

### 実行結果サマリ

- `test_kbe_hfb_solver.py`: 22 passed
- `test_self_energy_second_born.py`: 1 passed
- `test_kbe_stationarity.py`: 4 passed
- `test_exact_diagonalization_benchmark.py -k 'second_born or kbe_hfb or tdhfb'`: 12 passed, 2 deselected
- `-m physics_invariant`: 40 passed, 86 deselected

### 未実行項目

- `physics_unit` / `physics_benchmark` の全件通しは今回は未実行（solver中心レビューの範囲外）。

## 7. Residual Risks & Next Actions

1. `second_born_converged=False` の run を status へ昇格する運用ルールを定義（最優先）。
2. convergence 診断に `strict` / `relaxed_5x` の判定種別を明示追加。
3. `self_energy_second_born` の unit テストを 3-5 ケース追加して回帰検知を局所化。
4. solver 巨大モジュールの分割方針（責務単位）を `docs/backend-remediation-plan.md` に追記。

