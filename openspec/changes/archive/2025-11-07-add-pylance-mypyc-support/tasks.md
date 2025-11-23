## 1. 配置 Pylance/Pyright
- [x] 1.1 創建 `pyrightconfig.json` 配置檔案，與 mypy 設定保持一致
- [x] 1.2 配置 Pylance 的型別檢查規則，確保與 mypy strict mode 一致
- [x] 1.3 驗證 Pylance 配置正確性

## 2. 引入 Mypyc 支援
- [x] 2.1 在 `pyproject.toml` 的 `[dependency-groups.dev]` 中新增 `mypyc>=1.11.0`
- [x] 2.2 在 `pyproject.toml` 中新增 `[tool.mypyc]` 配置區塊
- [x] 2.3 配置 mypyc 的編譯選項（如需要）

## 3. 修復編譯錯誤
- [x] 3.1 檢查 `src/infra/retry.py:31` 的 `type: ignore[misc]` 註解
- [x] 3.2 移除未使用的 type ignore 註解或修正型別問題
- [x] 3.3 執行 `mypy src/` 驗證所有錯誤已修復

## 4. 驗證與測試
- [x] 4.1 執行 `mypy src/` 確認無編譯錯誤
- [x] 4.2 驗證 Pylance 在 VS Code 中正常工作
- [x] 4.3 驗證 mypyc 配置正確（如需要可執行編譯測試）
- [x] 4.4 更新相關文檔（如需要）
