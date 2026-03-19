# CLAUDE.md

Claude Code でこのリポジトリを触るときは、最初にプロジェクト直下の `AGENTS.md` を読むこと。  
プロジェクト固有ルールの正本は `AGENTS.md` で、このファイルは Claude Code 向けの入口と補足だけを置く。

## Start Here

- まず `AGENTS.md` を読む。
- 次に、今回触る領域に応じて `docs/theory.md`、`docs/validation-spec.md`、`docs/research-workbench-plan.md`、`docs/progress.md` を読む。
- docs と code の意味づけがずれていたら、片方だけ直さず整合を取る。

## Claude Code Notes

- 大きい作業ではサブエージェントで調査・独立実装・検証を並列化してよいが、同じファイル群の同時編集は避け、最終統合と検証責任はメインエージェントが持つ。
- `second_born` は heuristic prototype、`second_born_reference` は equal-time GKBA contour-dressed scope の reference path であり、混同しない。
- `validated` / `partially validated` / `prototype only` のラベルは `docs/validation-spec.md` に従う。
- backend schema / API contract を変えたら `cd frontend && npm run generate:api` を実行し、generated client を同期する。
- solver の出力や diagnostics の意味を変えたら、tests と docs を同じ変更で揃える。
- マイルストーン状態や検証ログが変わったら `docs/progress.md` を更新する。
