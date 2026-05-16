# git-workflow

Git 版控、分支管理、commit 規範的一站式指引。
執行任何 git 操作前先讀這份規則；如果使用者要求違反規則的操作，主動說明並建議正確做法。

## 用法
`/git-workflow`                    — 顯示規範摘要
`/git-workflow new <type> <name>`  — 建立符合規範的新分支
`/git-workflow commit`             — 引導寫出符合規範的 commit message
`/git-workflow review`             — 提交前完整審查（branch + commit + 資安）

---

## 一、分支命名規則

### 格式
```
<type>/<ticket-or-date>-<kebab-case-description>
```

### type 對照表

| type | 用途 | 範例 |
|------|------|------|
| `feat` | 新功能 | `feat/0515-technical-analyzer` |
| `fix` | 修 bug | `fix/0515-kd-nan-crash` |
| `refactor` | 重構（不改行為）| `refactor/0515-score-engine` |
| `chore` | 維護雜務（依賴、設定）| `chore/0515-update-deps` |
| `docs` | 文件 | `docs/0515-readme-update` |
| `test` | 測試 | `test/0515-technical-analyzer` |
| `hotfix` | 緊急修正（直接從 main 開）| `hotfix/0515-line-token-leak` |

### 分支規則
- **main**：永遠是穩定可執行版本，禁止直接 push，只接受 PR merge
- **develop**：整合分支，所有 feature 都 merge 進這裡再測試
- 功能分支從 `develop` 開，merge 回 `develop`
- `hotfix` 從 `main` 開，同時 merge 回 `main` 和 `develop`
- 分支名稱全小寫、用 `-` 分隔單字，不用底線或空格

---

## 二、Commit Message 規範

### 格式（Conventional Commits）
```
<type>(<scope>): <中文描述>

[body — 可選，說明 why 而非 what]

[footer — 可選，如 Closes #123]
```

### type 對照表

| type | 用途 | 範例 |
|------|------|------|
| `feat` | 新功能 | `feat(analysis): 新增技術面 KD 交叉偵測` |
| `fix` | 修 bug | `fix(collector): 修正 FinMind 日期格式錯誤` |
| `refactor` | 重構 | `refactor(score): 將評分邏輯抽成獨立方法` |
| `chore` | 維護 | `chore(deps): 補上 FinMind 至 requirements.txt` |
| `docs` | 文件 | `docs(readme): 更新執行指令說明` |
| `test` | 測試 | `test(technical): 新增均線突破單元測試` |
| `perf` | 效能 | `perf(db): 為 stock_id 欄位加索引` |
| `ci` | CI/CD | `ci(actions): 排程改為盤後 17:30 觸發` |
| `revert` | 回滾 | `revert: 取消 feat(analysis): xxx` |

### scope 對照（這個專案）

| scope | 對應目錄/模組 |
|-------|------------|
| `analysis` | `analysis/` |
| `collector` | `collectors/` |
| `db` | `database/` |
| `notifier` | `notifiers/` |
| `config` | `config/` |
| `ci` | `.github/` |
| `llm` | `ai_service/` |

### Commit 寫作原則
1. **描述 why，不描述 what** — 程式碼已經說明 what
   - 壞：`fix: 修改 if 條件式`
   - 好：`fix(analysis): KD 值為 NaN 時跳過，避免連線失敗誤判`
2. **一個 commit 一件事** — 不要把功能開發和格式整理混在一起
3. **描述用現在式動詞** — `新增`、`修正`、`移除`，不用過去式
4. **標題不超過 72 字**，超過就移到 body
5. **禁止的 commit message**：`update`、`fix bug`、`WIP`、`temp`、`test123`

---

## 三、合併規則

```
main ←── develop ←── feat/xxx
                 ←── fix/xxx
     ←── hotfix/xxx
```

- Feature → develop：用 **Squash merge**（壓成一個乾淨的 commit）
- develop → main：用 **Merge commit**（保留歷史節點）
- hotfix → main/develop：用 **Merge commit**

### PR 規則
- PR 標題遵循 commit 格式：`feat(analysis): 技術面分析模組`
- PR 必須有描述：做了什麼、為什麼、如何測試
- 合併前確認：`/security-check` 通過

---

## 四、你的任務（依 $ARGUMENTS 執行）

### `new <type> <name>`
1. 確認 type 在允許清單裡
2. 組出完整分支名稱：`<type>/<MMDD>-<name>`
3. 執行：`git checkout develop && git pull && git checkout -b <branch-name>`
4. 告訴使用者分支建好了，可以開始開發

### `commit`
1. 執行 `git status` 和 `git diff --staged` 看目前變更
2. 根據變更內容，建議最適合的 type 和 scope
3. 草擬符合規範的 commit message，說明你為什麼這樣寫
4. 等使用者確認後再執行 `git commit`
5. **禁止加 `--no-verify`**；如果 hook 失敗，診斷並修正

### `review`（提交前完整審查）
1. 執行 `/security-check` 的所有步驟
2. 確認分支名稱符合規範
3. 列出所有 staged commits，確認每一筆符合 commit 規範
4. 確認沒有以下問題：
   - `.env` 被 stage
   - `TODO` / `FIXME` / `print(secret)` 殘留在程式碼
   - `debug = True` 在 production 設定裡
5. 報告：通過或需修正的項目

### `（無參數）`
顯示這份規範的摘要版本，方便快速查閱。
