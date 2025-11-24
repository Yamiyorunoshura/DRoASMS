## ADDED Requirements

### Requirement: 指令處理錯誤管理
指令處理器 SHALL 使用 Result<T,E> 模式進行錯誤處理，替代傳統的異常捕獲機制。

#### Scenario: 命令執行錯誤
- **WHEN** 斜線指令執行過程中發生錯誤時
- **THEN** 指令處理器必須返回 Result.Err 而非拋出異常
- **AND** 錯誤回應必須使用標準化的 Discord 訊息格式
- **AND** 系統必須記錄詳細的錯誤上下文到日誌

#### Scenario: 參數驗證錯誤
- **WHEN** 指令參數驗證失敗時
- **THEN** 必須返回包含具體驗證錯誤的 Result
- **AND** 錯誤訊息必須指出哪些參數無效及原因
- **AND** 必須提供正確的參數使用範例

### Requirement: 服務層錯誤傳播
服務層 SHALL 統一使用 Result 類型進行錯誤傳播，避免異常跨層傳遞。

#### Scenario: 跨服務調用錯誤
- **WHEN** 服務 A 調用服務 B 時發生錯誤
- **THEN** 服務 B 必須返回 Result.Err
- **AND** 服務 A 必須正確處理和轉發錯誤
- **AND** 錯誤上下文必須保留完整的調用鏈資訊

#### Scenario: 資料庫操作錯誤
- **WHEN** 資料庫 gateway 操作失敗時
- **THEN** gateway 方法必須返回 Result.Err
- **AND** 服務層必須使用 Result.map 或 Result.and_then 處理
- **AND** 資料庫錯誤必須包含查詢參數和執行上下文

### Requirement: 事務處理錯誤回滾
事務操作 SHALL 與 Result 機制集成，確保錯誤情況下的正確回滾。

#### Scenario: 事務執行錯誤
- **WHEN** 事務中的任何操作返回 Result.Err 時
- **THEN** 事務管理器必須自動回滾所有更改
- **AND** 必須返回包含回滾狀態的 Result
- **AND** 回滾失敗必須記錄為嚴重錯誤

#### Scenario: 部分成功操作
- **WHEN** 批次操作中部分成功、部分失敗時
- **THEN** 必須返回包含成功和失敗詳細信息的 Result
- **AND** 已成功的操作必須正確提交
- **AND** 失敗操作的錯誤必須詳細記錄
