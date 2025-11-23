# Change: 實現 Rust 風格 Result<T,E> 錯誤處理機制

## Why
當前 Discord 機器人系統使用傳統的 Python 異常處理機制，這種方式存在以下問題：異常堆疊追蹤在生產環境中不易管理、錯誤類型缺乏統一的型別安全、以及跨層級錯誤傳遞的複雜性。引入 Rust 風格的 Result<T,E> 類型將提供更明確、類型安全的錯誤處理模式，減少程式碼中的意外崩潰，並提升系統的可維護性和調試能力。

## What Changes
- **新增核心 Result 類型**: 實現泛型 Result<T,E> 類型，支援 Ok(T) 和 Err(E) 兩種變體
- **新增錯誤處理工具函數**: 提供鏈式操作方法如 map、and_then、unwrap_or 等
- **更新所有斜線指令**: 將現有的 try/except 異常處理遷移到 Result 模式
- **新增裝飾器支援**: 為現有函數提供 Result 包裝的裝飾器工具
- **集成日誌系統**: 將 Result 錯誤自動集成到現有的 structlog 系統

## Impact
- **影響的規範**: `economy-commands`, `council-governance`, `state-council-governance`, `command-registry`
- **影響的程式碼**: 所有 `src/bot/commands/` 下的斜線指令檔案、`src/bot/services/` 服務層、以及相關的錯誤處理邏輯
- **重大變更**: 需要更新大量現有錯誤處理程式碼，但提供向後相容的遷移工具
