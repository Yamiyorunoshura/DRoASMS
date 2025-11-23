# Change: Fix CI/CD Failures

## Why
CI/CD 管道目前有 6 個失敗的檢查：
1. **Type Check (mypy)** - 發現 2 個類型錯誤
2. **Pre-commit Check** - Git 環境問題（CI 環境中沒有 git 倉庫）
3. **Contract Tests** - 2 個測試失敗，找不到 schema 文件
4. **Council Tests** - 測試目錄不存在（`tests/council/`），CI 配置錯誤
5. **Database Function Tests** - 使用錯誤的工具（pytest 而非 pg_prove）
6. **Integration Tests** - Docker-in-Docker 連接問題

這些錯誤阻止了代碼合併，需要修復以確保代碼質量標準和測試完整性。

## What Changes
- 修復 `src/infra/retry.py:31` 中未使用的 `type: ignore` 註釋
- 修復 `src/bot/commands/supreme_assembly.py:715` 中的類型不匹配問題
- 修復 Contract Tests 中的 schema 文件路徑問題
- 修復 Council Tests 的 CI 配置（使用正確的測試目錄）
- 修復 Database Function Tests 的 CI 配置（使用 pg_prove 而非 pytest）
- 修復 Integration Tests 的 Docker-in-Docker 配置
- 修復 Pre-commit Check 的 Git 環境配置

## Impact
- **Affected specs**: `development-tooling` (代碼質量要求), `test-infrastructure` (測試基礎設施)
- **Affected code**:
  - `src/infra/retry.py`
  - `src/bot/commands/supreme_assembly.py`
  - `.github/workflows/ci.yml` (CI 配置)
  - `tests/contracts/_utils.py` (schema 路徑解析)
