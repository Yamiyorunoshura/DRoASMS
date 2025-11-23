# Change: 使用 dpy-paginator 重構嵌入訊息 UI

## Why
目前的理事會面板和最高人民會議面板使用手動實作的分頁邏輯，限制每頁顯示 10 筆記錄。這種實作方式導致程式碼重複、維護困難，且使用者體驗不一致。引入 dpy-paginator 庫可以簡化分頁實作、提供統一的使用者介面，並改善程式碼的可維護性。

## What Changes
- 引入 dpy-paginator 庫作為分頁解決方案
- 重構理事會面板的提案清單分頁功能
- 重構最高人民會議面板的表決提案清單分頁功能
- 建立共用的分頁元件，減少程式碼重複
- 保持現有的功能完整性，包括即時更新和事件處理
- 改善使用者體驗，提供按鈕導航和下拉選單跳轉功能

## Impact
- **Affected specs**: council-panel, supreme-assembly-panel, ui-components (新增)
- **Affected code**:
  - src/bot/commands/council.py (CouncilPanelView class)
  - src/bot/commands/supreme_assembly.py (SupremeAssemblyPanelView class)
  - 可能需要新增 src/bot/ui/paginator.py 共用元件
- **Dependencies**: 新增 dpy-paginator 庫依賴
- **User experience**: 更流暢的分頁導航，保持現有功能不變
