# 法務部分頁功能規格

## ADDED Requirements

### Requirement: 國務院面板擴展
系統SHALL提供法務部分頁顯示功能，允許法務部領導人通過國務院面板訪問法務部專屬功能。

#### Scenario: 法務部分頁顯示
- **Given:** 用戶擁有法務部領導人身份組
- **When:** 執行 `/state-council` 指令
- **Then:** 面板SHALL顯示包含法務部的分頁選項
- **And:** 法務部分頁SHALL顯示在現有部門之後

### Requirement: 嫌犯列表顯示
系統SHALL在法務部分頁中顯示所有被逮捕且未被釋放的嫌犯列表，並提供詳細的嫌犯資訊。

#### Scenario: 嫌犯列表載入
- **Given:** 用戶在法務部分頁
- **When:** 頁面載入時
- **Then:** SHALL顯示所有被逮捕且未被釋放的嫌犯列表
- **And:** 每個嫌犯SHALL顯示：成員名稱、逮捕時間、逮捕人、當前狀態
- **And:** 列表SHALL支援分頁，每頁10條記錄

### Requirement: 嫌犯詳情檢視
系統SHALL提供嫌犯詳細資訊檢視功能，允許法務部領導人查看特定嫌犯的完整司法資訊。

#### Scenario: 查看嫌犯詳情
- **Given:** 用戶在法務部分頁的嫌犯列表
- **When:** 點擊特定嫌犯的"查看詳情"按鈕
- **Then:** SHALL顯示該嫌犯的完整資訊
- **And:** SHALL包含：逮捕原因、逮捕時間、逮捕人、起訴狀態、起訴時間、起訴人

### Requirement: 起訴功能
系統SHALL允許法務部領導人對被逮捕的嫌犯執行起訴操作，並記錄相關的審計資訊。

#### Scenario: 法務部起訴嫌犯
- **Given:** 用戶是法務部領導人
- **And:** 嫌犯狀態為 "detained"
- **When:** 點擊"起訴"按鈕並輸入起訴原因
- **Then:** 系統SHALL將嫌犯狀態更新為 "charged"
- **And:** SHALL記錄起訴人ID和起訴時間
- **And:** SHALL記錄起訴原因到審計日誌
- **And:** SHALL顯示成功訊息

### Requirement: 撤銷起訴
系統SHALL允許法務部領導人撤銷已執行的起訴操作，並恢復嫌犯狀態。

#### Scenario: 法務部撤銷起訴
- **Given:** 用戶是法務部領導人
- **And:** 嫌犯狀態為 "charged"
- **When:** 點擊"撤銷起訴"按鈕
- **Then:** 系統SHALL將嫌犯狀態更新為 "detained"
- **And:** SHALL清空起訴相關欄位
- **And:** SHALL記錄操作到審計日誌
- **And:** SHALL顯示成功訊息

### Requirement: 權限控制
系統SHALL對法務部功能實施嚴格的權限控制，確保只有授權人員才能訪問和操作。

#### Scenario: 非法務部人員嘗試訪問
- **Given:** 用戶沒有法務部領導人身份組
- **When:** 嘗試訪問法務部分頁功能
- **Then:** 系統SHALL拒絕訪問
- **And:** SHALL顯示錯誤訊息："您沒有權限訪問法務部功能"

#### Scenario: 嘗試起訴已起訴的嫌犯
- **Given:** 嫌犯狀態已為 "charged"
- **When:** 嘗試再次起訴
- **Then:** 系統SHALL拒絕操作
- **And:** SHALL顯示錯誤訊息："該嫌犯已被起訴"

## MODIFIED Requirements

### Requirement: 部門配置更新
系統SHALL在現有的部門配置中包含法務部，並確保法務部有正確的身份組ID映射和政府帳戶配置。

#### Scenario: 系統載入部門配置
- **Given:** 系統啟動時
- **When:** 載入 `departments.json`
- **Then:** SHALL包含法務部配置
- **And:** 法務部SHALL有正確的身份組ID映射
- **And:** 法務部SHALL有政府帳戶配置

## 跨能力依賴
- 依賴 `transfer_economics` 能力實現法務部轉帳功能
- 依賴 `adjust_economics` 能力實現法務部餘額調整
- 依賴 `suspect_management` 能力提供嫌犯資料
