# Backend Audit Prompt

## Purpose

このプロンプトは、研究用バックエンド実装に対して、定期的な設計監査・実装監査を実施するためのものである。  
目的は、局所的なバグや style の問題ではなく、**理論・数値計算・データ表現・検証方針の観点から見た構造的欠陥**を早期に発見することにある。

想定する欠陥には、例えば以下が含まれるが、これらに限定しない。

- 方程式に対して不自然な基底・表現の採用
- 対称性や疎構造の未利用
- 不必要な dense 化
- 計算量・メモリ量の不適切なスケーリング
- 数値安定性や保存則を壊しやすい実装
- 将来的な GPU 化・大規模化・高精度化を阻害する設計
- 文書化された数理モデルと実装の乖離
- テストや validation 方針と実装の不整合

---

## Instructions to the reviewer

このリポジトリに対して、**read-only のバックエンド監査**を実施してください。  
コードの編集、リファクタリング、テスト追加、issue 作成はまだ行わないでください。  
まずはリポジトリ内の関連文書を探索・整理し、その後コードベース全体を横断して監査してください。

---

## Step 1. Discover relevant documents

最初に、リポジトリ内の文書を**ファイル名に依存せず**探索してください。  
ファイル名や配置場所を決め打ちしてはいけません。

探索対象の例:
- README
- docs, notes, memo, design, spec, architecture, theory, numerics, validation, test, roadmap などを含む文書
- Markdown, text, notebook, comment-rich source file など
- 実装方針や理論背景が書かれていそうな文書全般

見つけた文書を、内容ベースで次のカテゴリに整理してください。

1. **Problem / model documents**
   - 何を解くか
   - どんな物理・数理モデルか
   - どの近似を採用しているか

2. **Numerics / algorithm documents**
   - 離散化
   - 時間発展
   - 線形代数
   - solver 方針
   - 計算量や性能に関する記述

3. **Data layout / implementation design documents**
   - 状態変数の持ち方
   - API / module 分割
   - データ構造
   - 基底選択
   - メモリ配置

4. **Validation / testing documents**
   - テスト方針
   - 比較対象
   - 保存則
   - 極限チェック
   - 検証仕様

5. **Project context / roadmap documents**
   - 将来拡張
   - 制約
   - 既知課題
   - 優先順位

各カテゴリについて、
- 該当文書
- その文書が何を説明しているか
- 監査に使う価値が高いかどうか
を簡潔にまとめてください。

文書が不足している場合は、それ自体を重要な監査結果として扱ってください。

---

## Step 2. Reconstruct the intended architecture from documents

探索した文書をもとに、このバックエンドが本来どう設計されるべきかを再構成してください。  
ここでは、まだコードの良し悪しを断定せず、まず「文書から読める自然な設計」を整理してください。

少なくとも以下を整理してください。

1. このバックエンドが解くべき物理・数理問題は何か
2. 主要な状態変数と自由度は何か
3. 自然な表現は何か
   - 実空間 / k空間
   - 軌道基底
   - Nambu基底
   - 時間表現
   - 周波数表現
   など
4. 利用可能な対称性・保存則・構造は何か
5. 想定される計算量・メモリ量の支配項は何か
6. validation で守るべき基準は何か

重要:
- 文書に書かれていないことを勝手に補わない
- ただし、文書から強く示唆される自然な設計は明示してよい
- 不明点は不明と書く

---

## Step 3. Audit the implementation

次の観点で、コードベースを横断的に監査してください。

### 1. Model ↔ implementation consistency
- 文書化された数理モデルと実装が整合しているか
- 近似のレベルが場所ごとに食い違っていないか
- 初期状態・時間発展・観測量計算で理論仮定がずれていないか

### 2. Representation and data layout
- 状態変数の持ち方が自然か
- 不必要に自由度を直積化・巨大化していないか
- dense / sparse / block / diagonal の選択が妥当か
- 基底やデータ構造の選択が方程式の自然な形と噛み合っているか

### 3. Structural and symmetry exploitation
- 並進対称性
- エルミート性
- 粒子・正孔対称性
- スピン・軌道・サブラティスのブロック構造
- 畳み込み構造
- 再利用可能な kernel / operator / transform

これらが実装で適切に活用されているかを確認してください。

### 4. Computational scaling
- 計算量の支配項は何か
- メモリ量の支配項は何か
- 不必要に O(N^2), O(N^3), O(N^4) へ悪化していないか
- 各ステップで再計算不要なものを再構築していないか
- 将来的な GPU 化や高解像度化の障害になっていないか

### 5. Numerical integrity
- 保存則の確認がしやすい実装か
- 数値安定性を損なうデータフローになっていないか
- 正規化、境界条件、時間積分、初期条件に不自然さがないか
- 観測量計算が本体実装と整合しているか

### 6. Validation and testability
- validation 方針に対して実装側の責務が明確か
- テストしやすい分解になっているか
- 逆に、データ構造や API のせいで検証が難しくなっていないか

### 7. Extensibility
- 将来の近似拡張、自由度追加、GPU 化、並列化に耐える設計か
- 一見抽象化されていても、実際には特定ケースに強く固定されていないか
- 実験コードが中核 API に混入していないか

---

## Anti-bias rules

最近見つかった不具合や議論中の論点は、監査の参考例ではあるが、**監査の主仮説にしてはいけない**。  
特定の論点に過剰に寄らず、文書とコードの全体像から問題を抽出すること。

次を守ってください。

- 既知の事故に似た問題だけを優先しない
- 逆に、既知の事故と無関係でも重大なら強く指摘する
- 推測だけで断定しない
- ただし、構造的に疑いが強い場合は明確に「疑わしい」と書く
- style / formatting / lint の指摘は不要
- 重要なのは **研究コードとしての構造欠陥** の発見である

---

## Output format

監査結果は必ず以下の形式でまとめてください。

### A. Document map
- 発見した主要文書
- 各文書のカテゴリ
- 監査における重要度
- 不足している文書カテゴリ

### B. Executive summary
- 重大度 High / Medium / Low の件数
- 最重要の問題 3～5 件
- 「設計欠陥」「実装不整合」「検証不備」のどれが主因かを要約

### C. Intended architecture reconstructed from documents
- 文書から推定される自然な実装方針
- 実装が従うべき主要 invariants / structures / scaling assumptions
- 文書不足のため不明な点

### D. Findings
各 finding ごとに以下を記載
- タイトル
- 重大度
- 種別
  - design flaw
  - implementation mismatch
  - numerical risk
  - validation gap
  - extensibility risk
  - documentation gap
- 関連ファイル / 関数 / クラス
- 現在の実装が何をしているか
- なぜ問題か
- 本来どうあるのが自然か
- 影響範囲
- 確信度（high / medium / low）

### E. Priority ranking
以下を分けて提示
1. まず人間が確認すべき上位 5 件
2. 修正効果が大きい上位 5 件
3. 変更時の破壊リスクが高い上位 5 件

### F. Validation implications
- 各 finding が validation にどう影響するか
- 現行テストで見逃されうる理由
- 追加で確認すべき観測量・保存則・極限・比較対象

### G. Evidence
- 根拠となるコード断片
- 呼び出し経路
- 依存関係
- 可能なら簡単な scaling estimate

---

## Final objective

最終的にほしいのは、  
**「このバックエンドが今後の研究基盤としてどこで破綻しうるか」**  
が、文書とコードの対応関係つきで分かる監査レポートである。