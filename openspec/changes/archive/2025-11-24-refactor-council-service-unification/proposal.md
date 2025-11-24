# Change: Unify Council Service Implementation with Result Pattern

## Why

目前存在兩個 council service 實作：傳統異常處理的`CouncilService`和新的`CouncilServiceResult`。根據 project.md 中的 Result<T,E>遷移策略，需要統一為 Result 模式以提供類型安全的錯誤處理，同時保持向後相容性。

## What Changes

- **BREAKING**: 將`CouncilService`內部實作替換為基於`CouncilServiceResult`的 Result 模式
- 更新所有使用`CouncilService`的程式碼以處理新的 Result 返回類型
- 保持`CouncilService`的公共 API 相容性，使用異常包裝 Result 返回值
- 更新相關測試案例以覆蓋 Result 模式行為
- 添加遷移警告和棄用通知

## Impact

- Affected specs: council-governance, council-panel, error-handling
- Affected code:
  - `src/bot/services/council_service.py` (主要重構)
  - `src/bot/commands/council.py` (呼叫端更新)
  - `src/infra/di/bootstrap.py` (DI 容器更新)
  - 所有測試檔案使用 council service 的測試
- Migration strategy: 漸進式遷移，保持向後相容性
