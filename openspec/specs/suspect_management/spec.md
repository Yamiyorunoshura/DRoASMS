# suspect_management Specification

## Purpose
提供完整的嫌犯管理功能，包括嫌犯資料管理、起訴控制、釋放控制和歷史追蹤，確保司法流程的完整性和正確性。

## Requirements

### Requirement: 嫌犯資料管理
系統SHALL提供完整的嫌犯資料管理功能，包括自動創建嫌犯記錄和狀態追蹤。

#### Scenario: 創建嫌犯記錄
- **Given:** 國土安全部執行逮捕操作
- **When:** 逮捕成功時
- **Then:** 系統SHALL自動在 `governance.suspects` 表格創建記錄
- **And:** 記錄SHALL包含：公會ID、成員ID、逮捕人ID、逮捕時間
- **And:** 初始狀態SHALL設為 "detained"

#### Scenario: 查詢嫌犯的當前狀態
- **Given:** 有成員曾被逮捕
- **When:** 系統查詢該成員狀態時
- **Then:** SHALL返回最新的嫌犯記錄
- **And:** 狀態SHALL為以下之一："detained"、"charged"、"released"
- **And:** SHALL包含狀態變更的時間和操作人

### Requirement: 起訴管理
系統SHALL支援法務部對嫌犯執行起訴和撤銷起訴操作，並正確管理起訴狀態。

#### Scenario: 法務部起訴嫌犯
- **Given:** 嫌犯當前狀態為 "detained"
- **And:** 操作者為法務部領導人
- **When:** 執行起訴操作並提供原因
- **Then:** 系統SHALL更新嫌犯狀態為 "charged"
- **And:** SHALL記錄起訴人ID、起訴時間、起訴原因
- **And:** SHALL更新記錄的時間戳

#### Scenario: 法務部撤銷起訴
- **Given:** 嫌犯當前狀態為 "charged"
- **And:** 操作者為法務部領導人
- **When:** 執行撤銷起訴操作
- **Then:** 系統SHALL更新嫌犯狀態為 "detained"
- **And:** SHALL保留起訴歷史但標記為已撤銷
- **And:** SHALL記錄撤銷操作的時間和操作人

#### Scenario: 檢查成員是否被起訴
- **Given:** 需要檢查特定成員
- **When:** 系統查詢該成員狀態時
- **Then:** 如果最新記錄狀態為 "charged"，SHALL返回 true
- **And:** 對於所有其他狀態，SHALL返回 false
- **And:** 對於沒有記錄的成員，SHALL返回 false

### Requirement: 釋放控制
系統SHALL實施起訴阻擋釋放機制，確保已起訴的嫌犯不能被釋放。

#### Scenario: 國土安全部嘗試釋放已起訴嫌犯
- **Given:** 嫌犯狀態為 "charged"
- **And:** 國土安全部執行釋放操作
- **When:** 系統檢查釋放條件時
- **Then:** SHALL拒絕釋放操作
- **And:** SHALL返回錯誤訊息："該嫌犯已被起訴，無法釋放"
- **And:** SHALL保持嫌犯狀態不變

#### Scenario: 釋放未被起訴的嫌犯
- **Given:** 嫌犯狀態為 "detained"
- **And:** 未被起訴
- **When:** 國土安全部執行釋放操作時
- **Then:** SHALL允許釋放
- **And:** SHALL更新狀態為 "released"
- **And:** SHALL記錄釋放人和釋放時間

### Requirement: 嫌犯查詢
系統SHALL提供完整的嫌犯查詢功能，支援列表查詢和狀態篩選。

#### Scenario: 法務部查詢所有嫌犯
- **Given:** 法務部領導人請求嫌犯列表
- **When:** 系統查詢資料庫時
- **Then:** SHALL返回所有未被釋放的嫌犯
- **And:** SHALL按逮捕時間倒序排列
- **And:** SHALL支援分頁查詢（每頁10條）

#### Scenario: 按狀態篩選嫌犯
- **Given:** 用戶指定篩選條件
- **When:** 查詢特定狀態的嫌犯時
- **Then:** SHALL返回符合狀態的所有記錄
- **And:** SHALL支援的篩選條件："detained"、"charged"、"released"
- **And:** SHALL保持相同的排序和分頁規則

### Requirement: 歷史追蹤
系統SHALL提供完整的司法歷史追蹤功能，記錄成員的所有逮捕和狀態變更歷史。

#### Scenario: 查詢成員的完整司法歷史
- **Given:** 特定成員曾被多次逮捕
- **When:** 查詢該成員的所有記錄時
- **Then:** SHALL返回所有相關記錄（包含已釋放的）
- **And:** SHALL按時間倒序排列
- **And:** SHALL包含完整的狀態變更歷史

### Requirement: 逮捕流程整合
系統SHALL將現有的逮捕流程與嫌犯管理系統整合，確保資料一致性。

#### Scenario: 國土安全部執行逮捕
- **Given:** 國土安全部執行逮捕指令
- **When:** 逮捕操作成功時
- **Then:** SHALL同時創建或更新嫌犯記錄
- **And:** SHALL確保資料一致性
- **And:** SHALL避免重複創建記錄

### Requirement: 釋放流程修改
系統SHALL修改現有的釋放流程，加入起訴狀態檢查機制。

#### Scenario: 修改現有的釋放邏輯
- **Given:** 國土安全部執行釋放操作
- **When:** 系統處理釋放請求時
- **Then:** SHALL先檢查起訴狀態
- **And:** SHALL只有未被起訴的嫌犯才能被釋放
- **And:** SHALL更新現有的釋放服務方法

### Requirement: 資料完整性要求 - 唯一性約束
每個成員在同一公會中只能有一個進行中的嫌犯記錄（非 released 狀態）。

#### Scenario: 防止重複的進行中記錄
- **Given:** 成員已有一個進行中的嫌犯記錄
- **When:** 嘗試創建新的進行中記錄時
- **Then:** 系統SHALL拒絕創建
- **And:** SHALL返回錯誤訊息

### Requirement: 資料完整性要求 - 外鍵完整性
所有 ID 欄位（guild_id, member_id, arrested_by 等）SHALL參照有效的 Discord 實體。

#### Scenario: 驗證外鍵有效性
- **Given:** 系統創建或更新嫌犯記錄
- **When:** 系統驗證 ID 欄位時
- **Then:** SHALL確保所有 ID 都對應有效的 Discord 實體
- **And:** SHALL拒絕無效 ID 的操作

### Requirement: 資料完整性要求 - 狀態一致性
狀態轉換SHALL遵循：detained -> charged -> detained（撤銷）-> released。

#### Scenario: 狀態轉換驗證
- **Given:** 當前嫌犯狀態
- **When:** 嘗試狀態轉換時
- **Then:** 系統SHALL驗證轉換的合法性
- **And:** SHALL拒絕無效的狀態轉換

### Requirement: 查詢性能要求
嫌犯列表查詢SHALL在 100ms 內完成，狀態檢查查詢SHALL在 50ms 內完成。

#### Scenario: 性能基準測試
- **Given:** 大量嫌犯記錄
- **When:** 執行查詢操作時
- **Then:** 系統SHALL在指定的時間限制內返回結果
- **And:** SHALL保持響應時間穩定性

### Requirement: 並發處理要求
系統SHALL支援多個法務部人員同時操作，並避免並發更新衝突。

#### Scenario: 並發操作測試
- **Given:** 多個法務部人員同時操作嫌犯記錄
- **When:** 系統處理並發請求時
- **Then:** SHALL使用適當的鎖定機制避免衝突
- **And:** SHALL確保資料一致性
