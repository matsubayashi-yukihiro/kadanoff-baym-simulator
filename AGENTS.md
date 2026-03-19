# AGENTS.md

## Purpose

このリポジトリは、非平衡超伝導ダイナミクスの simulation / compare / analysis / reproduce を支える research workbench である。  
作業では、physics claim の境界、validation の意味、frontend/backend/storage の責務分離を崩さないことを優先する。

## Canonical Documents

判断に迷ったら、まず次を読むこと。

1. `docs/theory.md`
   物理仕様の正本。
2. `docs/validation-spec.md`
   backend solver validation の正本。`validated` / `partially validated` / `prototype only` / `not validated` の意味はここに従う。
3. `docs/research-workbench-plan.md`
   product / architecture / workflow model の正本。`study`, `Compare Jobs`, `Parameter Sweep`, `evidence bundle` などの語彙はここに従う。
4. `docs/progress.md`
   現在到達点、次優先作業、検証ログの正本。
5. `docs/backend-remediation-plan.md`
   KBE remediation の設計・段階・参考文献束の正本。
6. `docs/literature-index.md`
   PDF ファイル名と文献タイトルの対応表。
7. `README.md`
   ローカル開発手順と基本コマンド。

文書間で齟齬がある場合は、上の番号順を優先し、必要なら code / docs / diagnostics をまとめて整合させること。

## Current Baseline

`docs/progress.md` の 2026-03-18 時点の要約に従う。特に重要なのは次の点。

- 到達点は `Phase E` 完了、backend remediation `R0-R5` 完了。
- `noninteracting` は現行 reference problem の範囲で `validated`。
- `tdhfb` / `kbe_hfb` は `partially validated`。
- `kbe.self_energy=second_born_reference` は equal-time GKBA contour-dressed scope の範囲で `validated`。
- legacy `kbe.self_energy=second_born` は heuristic `prototype only`。文献準拠 full second Born として扱わない。
- frontend の workbench shell は着手済みだが、`Compare Jobs` / `Parameter Sweep` は backend の上位 resource 未整備のため placeholder が残る。

## Working Rules

- solver の physics、validation label、UI messaging を触る前に、関連する正本 docs を読む。
- `validated` と `prototype only` の境界を曖昧にしない。
- `second_born` と `second_born_reference` を docs、code、UI、diagnostics のすべてで明確に分離する。
- 研究 workflow metadata と physics validation label を混同しない。`study` や `validation_status` は `validated` の代用品ではない。
- 既存 run API は単一 artifact 取得面として維持する。新機能は可能な限り追加的に拡張する。
- backend schema / API contract を変えたら、`frontend/src/api/generated.ts` を手で直さず `cd frontend && npm run generate:api` で再生成する。
- solver の意味や出力を変えたら、docs、diagnostics、tests を同じ変更で揃える。
- milestone の状態、検証ログ、次優先作業が変わったら `docs/progress.md` を更新する。
- 実装しただけの項目は「完了」にしない。テスト / build / 動作確認の証跡があるときだけ進捗を上げる。

## Sub-Agent Use

コードベースが大きいため、必要に応じてサブエージェントを使って並列化してよい。

- 読み取り調査、独立した実装、テスト / 検証の並列化に使う。
- 直近の判断が必要なクリティカルパスはメインエージェントが進める。
- 同じファイル群を複数サブエージェントに同時に触らせない。
- 重複調査を避け、担当範囲を明確に分ける。
- 最終的な統合、差分確認、検証責任はメインエージェントが持つ。

## Repository Map

- `backend/app/solvers/`: 数値計算の中核、self-energy、KBE / TDHFB orchestration
- `backend/app/api/`, `backend/app/schemas/`, `backend/app/storage/`, `backend/app/jobs/`: API、schema、保存、run lifecycle
- `backend/tests/`: pytest suite。marker は `physics_unit`, `physics_invariant`, `physics_benchmark`, `workflow`
- `frontend/src/components/`: workbench UI
- `frontend/src/api/`: API client と generated types
- `frontend/src/lib/`: config / workbench / spectrum utilities
- `docs/`: 正本文書群

## Common Commands

Backend 起動:

```bash
uv run python main.py
```

Backend test:

```bash
uv run python -m pytest backend/tests
uv run python -m pytest backend/tests -m physics_unit
uv run python -m pytest backend/tests -m physics_invariant
uv run python -m pytest backend/tests -m physics_benchmark
uv run python -m pytest backend/tests -m workflow
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm test
npm run build
```

OpenAPI 型再生成:

```bash
cd frontend
npm run generate:api
```

## Practical Defaults

- 小さい変更でも、影響した層の最小テストは回す。
- schema 変更時は backend test だけで終わらせず frontend 型再生成まで行う。
- 生成物更新がある場合は、その生成コマンドも検証ログや作業メモに残す。
- frontend の見た目変更より、validation scope の表示整合と run artifact の意味整合を優先する。
