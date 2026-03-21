# Backend Code Review (Complementary) — 2026-03-21

## 1. レビュースコープと方法

- 本文書は `docs/backend-code-review-2026-03-21.md`（Codex による solver 中心レビュー）の補完である。
- Codex レビューが確認した所見のうち重要なものは本文書でも確認し、評価を共有する。
- 本文書独自の観点として、エラーハンドリングパターンの非対称性、silent fallback のリスク、
  ドキュメント/アノテーション欠如に重点を置く。
- 対象:
  - `backend/app/solvers/kbe_hfb.py`
  - `backend/app/solvers/self_energy_second_born.py`
  - `backend/app/solvers/self_energy_second_born_prototype.py`
  - `backend/app/solvers/noninteracting.py`
  - `backend/app/solvers/registry.py`
  - `backend/app/jobs/worker.py`
  - `backend/app/schemas/simulation.py`
- 参照文書: `docs/theory.md`, `docs/validation-spec.md`, `docs/progress.md`
- 方法: 静的読解（実装とテストの突合）、テスト結果は `docs/progress.md` 検証ログから引用

---

## 2. 所見（Severity 順）

### High（Codex 確認）

- **`second_born_converged=False` の run が `RunState.SUCCEEDED` になる**
  - Codex レビュー §2 High と同一所見。本レビューでも確認。
  - `backend/app/solvers/self_energy_second_born.py:97-258,262-313`
  - `backend/app/solvers/self_energy_second_born_prototype.py:95-297,303-320`
  - `backend/app/jobs/worker.py:41-71`
  - solver は `second_born_converged` を diagnostics に格納するが例外を投げない。
    worker は例外なし完了を `RunState.SUCCEEDED` とする。
  - 非収束 run が API / UI で「成功」と見える運用リスク。
  - 推奨対応: Codex 提案と同一。`second_born_converged=False` の run lifecycle ポリシーを
    `docs/validation-spec.md` に明文化し、FAILED 昇格または SUCCEEDED_WITH_WARNINGS 導入を検討。

---

### Medium（新規指摘）

#### M-1: `kbe_hfb.py` の `assert` 文がエラー通知として不適切

- 該当箇所:
  - `backend/app/solvers/kbe_hfb.py:91` — `assert green_function_reference is not None`
  - `backend/app/solvers/kbe_hfb.py:166` — `assert hfb_green_functions is not None`
- 事実:
  - `AssertionError` は `worker.py:27-72` の `except Exception` に捕捉されるため、
    現状では run が FAILED になり結果は外に漏れない。
  - ただし Python を `-O`（optimize）フラグで実行すると `assert` が無効化され、
    None が後続処理に渡って予期しない NumPy エラーや誤計算が生じる可能性がある。
  - `AssertionError` は「開発時の不変条件チェック」の意味論であり、
    「実行時の想定外状態の明示的通知」には不適切。
- 推奨修正:
  ```python
  if green_function_reference is None:
      raise ValueError("green_function_reference is None: second_born_reference path requires a valid reference")
  ```

#### M-2: `self_energy_second_born*.py` の silent fallback パターン

- 該当箇所:
  - `backend/app/solvers/self_energy_second_born.py:61-82` — `sample_count <= 1 or onsite_strength <= 1e-12` で HFB limit に無通知退行
  - `backend/app/solvers/self_energy_second_born.py:362-380` — 同様
  - `backend/app/solvers/self_energy_second_born_prototype.py:56-72` — 同様
  - `backend/app/solvers/self_energy_second_born_prototype.py:108-121` — fixed-point iteration を無通知スキップ
  - `backend/app/solvers/self_energy_second_born_prototype.py:357-373` — 非 second-born mode を無通知スルー
- 事実:
  - デgenerate条件（U≈0, 単一サイト等）では計算をスキップして HFB / factorized 近似を返す。
  - diagnostics への記録は実装されているが、呼び出し元への例外・警告・ログは出ない。
  - `kbe_hfb.py` の orchestration 層も fallback 発生の有無を能動的に検出しない。
- 影響:
  - デバッグ時に「second Born が走っていたつもりが HFB 結果だった」という誤認が生じうる。
  - 特に interacting run で `onsite_strength` が計算誤差で閾値を下回った場合に発現しやすい。
- 推奨修正:
  - fallback 発生時に `logging.warning` を出す（例外にする必要はない）。
  - diagnostics に `applied_fallback: str | None`（`"hfb_limit_u_zero"` 等）を追加。

#### M-3: 全 solver モジュールで module docstring / function docstring が皆無

- 該当箇所（例）:
  - `backend/app/solvers/kbe_hfb.py:57` — `def solve(...)` — docstring なし
  - `backend/app/solvers/kbe_hfb.py:356` — `def _analyze_trajectory(...)` — docstring なし
  - `backend/app/solvers/noninteracting.py:73` — `def solve(...)` — docstring なし
  - `backend/app/solvers/self_energy_second_born.py:45` — `def apply_reference_second_born_corrections(...)` — docstring なし
  - `backend/app/solvers/self_energy_second_born.py:317` — `def build_reference_green_functions(...)` — docstring なし
  - `backend/app/jobs/worker.py:16` — `def execute_run(...)` — docstring なし
  - `backend/app/solvers/registry.py:18` — `def run_simulation(...)` — docstring なし
  - 計 20+ 関数に docstring が存在しない
- 事実:
  - 型アノテーションは充実している（95%+ coverage）。
  - コードの「何をするか」は型から推測できるが、「なぜそうするか」「どの物理量に対応するか」は読み取れない。
  - 特に `apply_reference_second_born_corrections` や `build_matsubara_branch_reference` のように
    physics 上の役割が関数名から直接読み取れないものは注釈が必要。
- 影響:
  - 新規コントリビューターや長期間後の自己参照でのオンボーディングコストが高い。
  - `docs/theory.md` との対応関係が暗黙知として蓄積される。
- 推奨対応:
  - 最優先は公開 API に相当する関数: `solve()`, `run_simulation()`, `execute_run()`,
    `apply_reference_second_born_corrections()`, `build_reference_green_functions()`,
    `build_matsubara_branch_reference()`, `build_mixed_branch_reference()` に
    1〜3 行の docstring（物理的役割と主要引数の意味）を追加する。

---

### Medium（Codex 確認）

- **fixed-point 許容判定が公称 tolerance の 5 倍まで緩和される**
  - Codex レビュー §2 Medium と同一所見。本レビューでも確認。
  - `backend/app/solvers/self_energy_second_born.py:254-255`
  - `backend/app/solvers/self_energy_second_born_prototype.py:282-283`
  - `last_residual <= 5.0 * tolerance` なら `converged_step=True`。
  - diagnostics で `converged=True` かつ residual が tolerance を超過するケースが生じうる。
  - → `docs/validation-spec.md` の 注記 に明記することで対処（本文書末尾 Next Actions 参照）。

---

### Low（Codex 確認）

- **巨大モジュール**
  - `self_energy_second_born.py` 919 行、`self_energy_second_born_prototype.py` 779 行、`kbe_hfb.py` 599 行
  - Codex レビュー §2 Low と同一評価。数値カーネル / contour branch / diagnostics assembler への分割が将来課題。

---

### Low（新規指摘）

#### L-1: validation status がコード構造上に存在しない

- 事実:
  - `simulation.py:277-280` に `PresetValidationStatus` enum（`validated` / `partial` / `prototype`）が定義され、
    `PresetEntry.validation_status` として preset に付与されている。
  - しかし solver モジュール自体（`kbe_hfb.py`, `self_energy_second_born.py` 等）には
    validation status を示す定数・デコレータ・モジュール変数が存在しない。
  - `REFERENCE_IMPLEMENTATION_KIND = "gkba_local_nambu_reference"`（`self_energy_second_born.py:34`）や
    `PROTOTYPE_IMPLEMENTATION_KIND = "heuristic_prototype"`（`prototype.py:34`）は implementation kind であり、
    validation status ではない。
- 影響:
  - validation status は `docs/validation-spec.md` にのみ存在し、
    コードを読んで確認することができない（docs ドリフトへの抵抗力が低い）。
- 推奨対応:
  - `MODULE_VALIDATION_STATUS = "prototype_only"` または `"partially_validated"` の定数を
    各 solver モジュールの先頭に置き、`docs/validation-spec.md` との対応を明示する。
  - これにより grep で validation status を探索でき、docs ドリフトを early に検出できる。

---

## 3. 物理レビュー

- Codex レビュー §3 と同評価。
- `second_born` / `second_born_reference` のコード上の分離は明確（`kbe_hfb.py:165-211`）。
- `validation-spec.md` の claim 境界（prototype only / reference path 分離）とは整合している。
- source-free continuity diagnostics は HFB mode 限定で有効化されており、未検証領域の過剰主張を抑制。
- 追加観点: silent fallback（M-2）が physics 上の近似境界を不透明にする可能性を補足。
  `U ≈ 0` 近傍での `onsite_strength` 閾値判定は物理的に妥当だが、fallback が発生したことを
  diagnostics に明示しないと、どの run で second Born 自己エネルギーが実際に計算されたかが
  事後追跡しにくい。

---

## 4. アルゴリズムレビュー

- Codex レビュー §4 に同意。
- 追加観点（silent fallback の数値的含意）:
  - `onsite_strength <= 1e-12` 閾値は single precision での相対誤差 (~10^-7) に対して
    相当に厳しい閾値であり、double precision 通常計算では偽陽性はほぼない。
  - ただし、periodic k-space path での BdG Hamiltonian 構築で
    Nambu space の off-diagonal block に小さな数値誤差が混入した場合、
    意図せず閾値付近の `onsite_strength` を生成する可能性は排除できない。
  - 影響は小さいと推定されるが、fallback 発生の logging があれば実際の発生頻度を
    観測データとして確認できる。

---

## 5. ソフトウェアエンジニアリングレビュー

- 良い点:
  - 型アノテーションが全体に充実しており、型レベルでの仕様が明確（Codex 評価と同じ）。
  - worker / solver / repository の責務は明確に分離されている。
  - schema バリデーション層（`simulation.py:229-253`）が不正設定の入口を塞いでいる。
  - pytest marker 体系（`physics_unit` / `physics_invariant` / `physics_benchmark` / `workflow`）が
    整備されており、テストの意図が構造化されている。
- 改善余地:
  - エラーハンドリングの非対称性:
    - `worker.py`: 包括的な例外補足 + tracebacks ログ
    - `kbe_hfb.py`: `assert` 文（`-O` フラグで無効化リスク）
    - `self_energy_second_born*.py`: silent fallback（ログなし）
    - `noninteracting.py`: エラーハンドリングほぼゼロ（NumPy エラーが worker で捕捉される想定）
  - コード上に validation status アノテーションがない（L-1）。
  - モジュール / 関数 docstring の欠如により、コードと docs の双方向参照が断絶している（M-3）。

---

## 6. Evidence

テスト実行は `docs/progress.md` 2026-03-21 検証ログより:

```
uv run python -m pytest backend/tests  → 109 件すべて成功（41 分 04 秒）
```

本レビューの所見は静的読解によるものであり、テスト通過と矛盾しない
（指摘はいずれも動作中断を起こすバグではなく、運用上のリスクと保守性の課題）。

---

## 7. 残存リスクと次アクション

Codex レビュー §7 の 4 件に加えて、本レビューが追加する項目:

| # | 作業 | 優先度 | 対象ファイル |
|---|---|---|---|
| 1 | (Codex) `second_born_converged=False` の RunState 昇格ルール定義 | 最優先 | `worker.py`, `validation-spec.md` |
| 2 | (Codex) diagnostics に `convergence_criterion`（`strict`/`relaxed_5x`）を追加 | 高 | `self_energy_second_born*.py`, `validation-spec.md` |
| 3 | (Codex) `self_energy_second_born` の unit テストを 3-5 ケース追加 | 中 | `test_self_energy_second_born.py` |
| 4 | (Codex) solver 巨大モジュールの分割方針を `backend-remediation-plan.md` に追記 | 低 | `backend-remediation-plan.md` |
| 5 | (新規) `kbe_hfb.py:91,166` の `assert` を明示的例外に置換 | 中 | `kbe_hfb.py` |
| 6 | (新規) silent fallback 発生時の `logging.warning` と `applied_fallback` diagnostics 追加 | 中 | `self_energy_second_born*.py` |
| 7 | (新規) 公開 API 関数群への最小 docstring 追加（物理的役割 + 引数） | 中 | 全 solver モジュール |
| 8 | (新規) 各 solver モジュール先頭に `MODULE_VALIDATION_STATUS` 定数を追加 | 低 | `kbe_hfb.py`, `self_energy_second_born*.py`, `noninteracting.py`, `tdhfb.py` |
