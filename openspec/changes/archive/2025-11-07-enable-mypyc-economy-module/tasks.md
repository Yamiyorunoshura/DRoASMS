## 1. 準備工作
- [x] 1.1 檢查經濟模塊的型別註解完整性
- [x] 1.2 確認所有經濟模塊文件符合 mypy strict mode
- [x] 1.3 識別可能不兼容 mypyc 的程式碼模式（如動態屬性、反射等）

## 2. 配置 mypyc 編譯
- [x] 2.1 更新 `pyproject.toml` 中的 `[tool.mypyc]` 配置，指定經濟模塊的編譯目標
- [x] 2.2 配置編譯選項（opt_level、debug_level 等）
- [x] 2.3 設定排除規則（如需要排除某些文件或模塊）

## 3. 嘗試編譯並修復錯誤
- [x] 3.1 對經濟模塊執行 mypyc 編譯測試
- [x] 3.2 記錄所有編譯錯誤和警告（見 PR 註解／變更說明）
- [x] 3.3 修復型別相關錯誤（無需修改）
- [x] 3.4 修復 mypyc 不支援的 Python 特性（為例外類別加上 `@mypyc_attr(native_class=False)`）
 - [x] 3.5 處理動態屬性或反射相關問題（如需要）
       - 掃描 `src/bot/services/*` 未發現 `__getattr__`/`__setattr__`/`__getattribute__` 或危險反射用法；
         僅 `state_council_service.py` 有 `getattr`（不在本次 mypyc 目標範圍內）。
 - [x] 3.6 驗證修復後的代碼仍通過所有測試
       - 本機：`PYTHONPATH=build/mypyc_out:. uv run pytest tests/economy -q`（資料庫未啟動時會略過）
       - 容器：`make test-economy`（使用 docker compose 啟動 postgres 與測試容器）→ 10 passed

## 4. 整合到構建流程
- [x] 4.1 創建構建腳本或更新 Makefile，支援 mypyc 編譯
- [x] 4.2 配置編譯輸出目錄和模塊結構
- [x] 4.3 確保編譯後的模塊可以正確導入和使用（新增 `mypyc-economy-check`）
 - [x] 4.4 更新 Dockerfile（如需要）以支援編譯流程
       - `docker/Dockerfile`：建置階段加入 `uv sync --group dev && uv run python scripts/mypyc_economy_setup.py ...`；
         並設定 `ENV PYTHONPATH=/app/build/mypyc_out:/app`
       - `docker/test.Dockerfile`：同上，且安裝 `build-essential` 以支援 mypyc 編譯

## 5. 測試與驗證
 - [x] 5.1 執行所有經濟模塊相關的單元測試
 - [x] 5.2 執行所有經濟模塊相關的整合測試
 - [x] 5.3 驗證編譯後的模塊功能與原始代碼一致
       - 以容器環境執行 `make test-economy`，10 項測試皆通過（含 DB 操作路徑）
 - [x] 5.4 進行性能基準測試，比較編譯前後的性能差異
       - 新增 `scripts/bench_economy.py` 與 `make bench-economy`；
         本機樣本（1k transfer/200k loops）顯示 mypyc 於驗證熱路徑有可見改善
 - [x] 5.5 驗證型別檢查仍通過（mypy src/）
       - 移除 `src/infra/retry.py:31` 不必要的 `# type: ignore`，`make type-check` 全綠

## 6. 文檔與規範更新
- [x] 6.1 更新 development-tooling spec，記錄 mypyc 編譯要求
- [x] 6.2 更新 README 或開發文檔，說明編譯流程
- [x] 6.3 記錄已知限制和注意事項
