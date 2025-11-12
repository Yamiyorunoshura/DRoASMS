# 開發者 Onboarding 摘要

1. 依 README 的「安裝步驟」使用 `uv sync` 建置隔離環境並設定 `.env`。
2. 執行 `make unified-migrate-dry-run`／`make unified-migrate`，確認所有編譯設定已整合到 `[tool.unified-compiler]`。
3. 使用 `make unified-compile` 產出 `.so`，並透過 `make unified-compile-test` 驗證兼容性/性能測試。
4. 若需要檢查輸出狀態或 `compile_report.json`，可執行 `make unified-status`；必要時用 `make unified-refresh-baseline` 更新性能基線。
5. 參考 `docs/unified-compiler-guide.md` 了解監控參數與 legacy 腳本位置，其他領域（資料庫、bot 啟動、事件池等）則沿用 README 現有章節。
