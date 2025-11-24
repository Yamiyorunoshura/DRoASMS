## MODIFIED Requirements
### Requirement: 型別檢查無錯誤
專案必須（MUST）通過 mypy strict mode 檢查，無任何編譯錯誤。

#### Scenario: Mypy 檢查通過
- **WHEN** 執行 `mypy src/` 指令
- **THEN** 必須無任何型別錯誤或警告
- **AND** 所有 `type: ignore` 註解必須有效且必要（不得有未使用的 `type: ignore` 註解）
- **AND** 所有變數賦值必須符合其類型註解，不得有類型不匹配錯誤

### Requirement: Pre-commit 自動檢查
專案必須（MUST）使用 pre-commit hooks 確保提交前程式碼品質。

#### Scenario: 提交前自動執行檢查
- **WHEN** 開發者執行 `git commit` 或在 CI 環境中執行 `pre-commit run --all-files`
- **THEN** pre-commit hooks 必須自動執行 black、ruff、mypy 檢查
- **AND** 檢查失敗時必須（MUST）阻止提交或 CI 流程
- **AND** Git 環境必須正確配置以支援 pre-commit hooks 執行
- **AND** 在 CI 環境中，如果沒有 git 倉庫，必須適當處理（跳過檢查或正確初始化 git 環境）

## ADDED Requirements
### Requirement: CI 測試配置正確性
CI 管道必須（MUST）正確配置所有測試套件，確保測試可以正確執行。

#### Scenario: Contract Tests 正確執行
- **WHEN** CI 管道執行 Contract Tests
- **THEN** 所有必需的 schema 文件必須可以被找到（路徑解析正確）
- **AND** Contract Tests 必須能夠載入並驗證所有 schema 文件

#### Scenario: Council Tests 正確執行
- **WHEN** CI 管道執行 Council Tests
- **THEN** 必須使用正確的測試目錄路徑（`tests/integration/council/` 或相關單元測試）
- **AND** 測試必須能夠被發現並執行

#### Scenario: Database Function Tests 正確執行
- **WHEN** CI 管道執行 Database Function Tests
- **THEN** 必須使用 `pg_prove` 工具執行 SQL 測試文件（而非 `pytest`）
- **AND** CI 環境必須安裝 `pg_prove` 和 `pgtap` 工具
- **AND** 測試必須能夠連接到資料庫並執行 SQL 測試

#### Scenario: Integration Tests 正確執行
- **WHEN** CI 管道執行 Integration Tests
- **THEN** Docker-in-Docker 配置必須正確，測試容器可以連接到 Docker 服務
- **AND** Docker 網絡配置必須正確，避免連接錯誤
