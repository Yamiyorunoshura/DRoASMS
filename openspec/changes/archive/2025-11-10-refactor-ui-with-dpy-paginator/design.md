# Design: dpy-paginator 整合設計

## Context
目前的 DRoASMS 專案使用 discord.py 2.4.0+，包含複雜的治理系統。理事會面板和最高人民會議面板需要顯示提案清單，目前使用手動限制每頁 10 筆記錄的方式。這種實作導致程式碼重複，且缺乏流暢的分頁體驗。

## Goals / Non-Goals
- **Goals**:
  - 簡化分頁實作邏輯
  - 提供統一的分頁使用者體驗
  - 減少程式碼重複
  - 保持現有功能完整性
- **Non-Goals**:
  - 不改變現有的業務邏輯
  - 不影響即時更新功能
  - 不修改權限控制機制

## Decisions
- **Decision**: 選擇 dpy-paginator 作為分頁解決方案
  - **Rationale**:
    - 專為 discord.py 設計，相容性好
    - 支援按鈕和下拉選單兩種分頁方式
    - 無外部依賴，輕量級
    - 活躍維護，文件完整
- **Alternatives considered**:
  - **自建分頁元件**: 開發成本高，需要處理更多邊界情況
  - **discord.ext.pages**: Pycord 專用，與本專案的 discord.py 不相容
  - **維持現狀**: 程式碼重複，維護困難

## Architecture
1. **共用分頁元件** (`src/bot/ui/paginator.py`)
   - 封裝 dpy-paginator 的使用
   - 提供一致的頁面格式和樣式
   - 支援即時更新機制

2. **整合策略**
   - 保持現有的 View 類別結構
   - 將手動分頁邏輯替換為 dpy-paginator
   - 維持事件訂閱和即時更新功能

3. **頁面內容**
   - 提案清單轉換為 dpy-paginator 頁面格式
   - 保持現有的嵌入訊息格式和資訊
   - 支援動態頁數更新

## Migration Plan
1. **Phase 1**: 新增 dpy-paginator 依賴和共用元件
2. **Phase 2**: 重構理事會面板分頁功能
3. **Phase 3**: 重構最高人民會議面板分頁功能
4. **Phase 4**: 測試和驗證所有功能
5. **Phase 5**: 清理舊的分頁程式碼

## Implementation Details
- **Page Format**: 每頁顯示 10 筆記錄（保持現有設定）
- **Navigation**: 提供上一頁/下一頁按鈕和頁數下拉選單
- **Real-time Updates**: 保持現有的即時更新機制
- **Error Handling**: 優雅處理分頁錯誤和網路問題

## Risks / Trade-offs
- **Dependency Risk**: 新增外部依賴，但 dpy-paginator 是輕量級且穩定的庫
- **Learning Curve**: 團隊需要熟悉 dpy-paginator 的 API
- **Compatibility**: 需要確保與現有 discord.py 版本相容
- **Mitigation**: 充分測試，保持向後相容

## Open Questions
- 是否需要在所有分頁場景中使用統一的頁面大小？
- 如何最佳化大型提案清單的載入效能？
- 是否需要新增分頁狀態的使用者偏好設定？
