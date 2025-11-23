## Context
此設計文檔闡述DRoASMS Discord機器人系統中各治理面板的基於身分組權限擴充方案的技術架構。目前系統包含5個主要治理面板：常任理事會、國務院（4個部門）、國土安全部、最高議會、最高人民議會。現有的權限控制主要基於特定用戶ID或有限的角色檢查，需要擴充為更靈活和可維護的身分組權限系統。

此變更是跨系統的架構變更，涉及多個服務模塊、新的權限檢查模式、數據庫模型更新以及重要的安全考量，因此需要詳細的技術設計規劃。

## Goals / Non-Goals
- **Goals**:
  - 實現統一的基於Discord身分組的權限檢查機制
  - 確保跨面板權限管理的一致性和可維護性
  - 保持向下相容，不影響現有權限結構
  - 提供細粒度的操作級別權限控制
  - 確保權限系統的安全性和防護機制

- **Non-Goals**:
  - 不重新設計整個認證系統
  - 不修改現有的數據庫表結構（僅添加新字段）
  - 不改變現有的業務邏輯，只擴充權限檢查
  - 不引入新的外部依賴

## Decisions

### Decision: 統一權限檢查服務架構
**What**: 創建一個統一的權限檢查服務 `PermissionService`，提供標準化的權限檢查API。

**Why**:
- 避免在每個服務中重複實作權限檢查邏輯
- 確保權限檢查的一致性
- 便於未來權限系統的維護和擴充
- 提供統一的權限檢查日誌和審計

**Implementation**:
```python
class PermissionService:
    async def check_council_permission(self, guild_id: int, user_roles: Sequence[int]) -> bool
    async def check_department_permission(self, guild_id: int, department: str, user_roles: Sequence[int]) -> bool
    async def check_homeland_security_permission(self, guild_id: int, user_roles: Sequence[int]) -> bool
    async def check_supreme_assembly_permission(self, guild_id: int, user_roles: Sequence[int]) -> bool
    async def check_peoples_assembly_permission(self, guild_id: int, user_roles: Sequence[int]) -> bool
```

### Decision: 配置驅動的權限模型
**What**: 使用數據庫配置來管理身分組權限映射，而不是硬編碼在服務中。

**Why**:
- 提供靈活的權限配置能力
- 支援動態權限更新而無需重啟服務
- 便於權限審計和管理
- 支援多環境配置

**Implementation**: 在現有的配置表中添加權限相關字段：
- CouncilConfig: 添加 `council_role_ids` 數組字段
- StateCouncilConfig: 添加各部門的 `department_role_ids` 字段
- 新增其他面板的權限配置表

### Decision: 權限繼承和層級模型
**What**: 實現權限繼承機制，高級權限自動包含低級權限。

**Why**:
- 避免重複配置權限
- 提供直觀的權限層級結構
- 減少配置錯誤的可能性
- 支援複雜的權限場景

**Implementation**:
- 國務院領袖權限包含所有部門權限
- 議會主席權限包含一般議員權限
- 支援自定義權限層級繼承

### Decision: 漸進式遷移策略
**What**: 採用漸進式遷移，先實作新的權限系統，再逐步替換舊的權限檢查。

**Why**:
- 降低遷移風險
- 確保系統穩定性
- 便於測試和驗證
- 支援回滾機制

**Implementation**:
1. 添加新的權限檢查邏輯，與現有邏輯並行
2. 使用特徵開關控制新舊權限系統
3. 逐步替換各面板的權限檢查
4. 最終移除舊的權限檢查邏輯

## Risks / Trade-offs

### Risk: 權限配置錯誤導致安全漏洞
**Mitigation**:
- 實作權限配置驗證機制
- 提供權限配置測試工具
- 實作權限變更審計日誌
- 提供權限配置回滾功能

### Risk: 性能影響
**Mitigation**:
- 實作權限檢查結果快取
- 使用批量權限檢查
- 優化數據庫查詢
- 監控權限檢查性能

### Trade-off: 複雜性 vs 靈活性
**Decision**: 選擇適度的複雜性以提供足夠的靈活性，同時保持系統的可維護性。

### Risk: 向下相容性問題
**Mitigation**:
- 保持現有API的兼容性
- 提供遷移指南和工具
- 實作充分的測試覆蓋
- 分階段部署和驗證

## Migration Plan

### Phase 1: 基礎架構 (1-2 weeks)
1. 創建 `PermissionService` 基礎架構
2. 更新數據庫模型，添加權限配置字段
3. 實作基礎的權限檢查方法
4. 創建權限配置管理API

### Phase 2: 國務院面板遷移 (1 week)
1. 實作國務院部門權限檢查
2. 更新 StateCouncilService 權限邏輯
3. 測試部門級別權限控制
4. 部署和驗證

### Phase 3: 其他面板遷移 (2 weeks)
1. 常任理事會面板權限遷移
2. 國土安全部面板權限遷移
3. 最高議會面板權限遷移
4. 最高人民議會面板權限遷移

### Phase 4: 清理和優化 (1 week)
1. 移除舊的權限檢查邏輯
2. 性能優化和快取實作
3. 文檔更新和測試完善
4. 監控和日誌完善

### Rollback Plan
- 保留舊的權限檢查邏輯直到完全驗證
- 提供配置選項快速切換到舊系統
- 實作數據庫遷移回滾腳本
- 準備緊急修復程序

## Open Questions

1. **權限快取策略**: 如何在權限變更時有效地失效快取？
2. **批量權限檢查**: 是否需要實作批量權限檢查以提升性能？
3. **權限審計**: 需要什麼級別的權限操作審計？
4. **跨服務權限同步**: 如何確保多個服務實例間的權限配置一致性？
5. **權限測試**: 如何自動化測試複雜的權限場景？
