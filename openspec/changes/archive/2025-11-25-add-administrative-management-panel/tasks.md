# Tasks: 新增行政管理嵌入訊息面板

## 1. UI 元件修改

- [x] 1.1 移除 `StateCouncilPanelView._add_overview_actions` 中的部門選擇下拉選單（`_DeptSelect`）
- [x] 1.2 移除 `StateCouncilPanelView._add_overview_actions` 中的身分組選擇器（`_RolePicker`）
- [x] 1.3 移除 `config_target_department` 狀態變數的相關邏輯
- [x] 1.4 新增「行政管理」按鈕，僅在 `is_leader` 為 True 時顯示

## 2. 行政管理面板實現

- [x] 2.1 創建 `AdministrativeManagementView` 類別，繼承 `discord.ui.View`
- [x] 2.2 實現嵌入訊息建構方法，顯示各部門當前領導人狀態
- [x] 2.3 實現部門選擇下拉選單（所有 5 個部門）
- [x] 2.4 實現領導人身分組選擇下拉選單（`discord.ui.RoleSelect`）
- [x] 2.5 實現設定提交邏輯，呼叫 `service.update_department_config`
- [x] 2.6 實現設定成功後的面板刷新邏輯

## 3. 實時更新功能

- [x] 3.1 為 `AdministrativeManagementView` 訂閱 State Council 事件
- [x] 3.2 實現事件處理器，當收到部門配置變更事件時刷新嵌入訊息
- [x] 3.3 實現 View 超時與取消訂閱的清理邏輯

## 4. 測試

- [x] 4.1 新增行政管理按鈕顯示邏輯的單元測試（僅領袖可見）
- [x] 4.2 新增行政管理面板初始載入的單元測試
- [x] 4.3 新增部門領導設定成功流程的單元測試
- [x] 4.4 新增實時更新功能的單元測試
- [x] 4.5 更新現有測試以適應 UI 元件變更
