# 轉帳功能擴充 - 支援法務部

## ADDED Requirements

### Requirement: 法務部轉帳支援
系統SHALL支援法務部作為轉帳的目標和發起者，並正確處理政府部門間的資金轉移。

#### Scenario: 用戶向法務部轉帳
- **Given:** 用戶執行 `/transfer` 指令
- **And:** 目標為法務部領導人身份組
- **When:** 指令執行時
- **Then:** 系統SHALL識別為向法務部政府帳戶轉帳
- **And:** 轉帳SHALL記錄為政府部門間交易
- **And:** 法務部帳戶餘額SHALL正確更新

#### Scenario: 法務部領導人發起轉帳
- **Given:** 用戶擁有法務部領導人身份組
- **And:** 用戶執行 `/transfer` 指令
- **When:** 從法務部帳戶轉出資金時
- **Then:** 系統SHALL驗證法務部帳戶餘額
- **And:** 轉帳SHALL遵循現有的政府帳戶轉帳規則
- **And:** 操作SHALL記錄到審計日誌

### Requirement: 政府帳戶豁免
系統SHALL為法務部政府帳戶提供與其他政府部門相同的轉帳豁免權限。

#### Scenario: 法務部帳戶進行轉帳
- **Given:** 轉帳涉及法務部政府帳戶
- **When:** 系統檢查轉帳限制時
- **Then:** 法務部帳戶SHALL享有與其他政府部門相同的豁免權
- **And:** SHALL不受每日轉帳次數限制
- **And:** SHALL不受最低餘額限制
- **And:** 但仍需記錄交易明細

## MODIFIED Requirements

### Requirement: 身份組映射更新
系統SHALL更新現有的身份組映射邏輯，以正確識別法務部領導人身份組並映射到相應的法務部政府帳戶。

#### Scenario: 系統映射身份組到部門
- **Given:** `transfer` 指令接收到身份組目標
- **When:** 系統解析目標身份組時
- **Then:** SHALL正確識別法務部領導人身份組
- **And:** SHALL映射到正確的法務部政府帳戶ID
- **And:** SHALL使用正確的部門名稱進行記錄

### Requirement: 幫助文本更新
系統SHALL更新轉帳指令的幫助文本，包含法務部在支援的政府部門列表中。

#### Scenario: 用戶查看轉帳指令幫助
- **Given:** 用戶執行 `/transfer help`
- **When:** 系統顯示支援的目標類型時
- **Then:** SHALL包含法務部在支援的政府部門列表中
- **And:** SHALL提供法務部轉帳的使用示例

### Requirement: 錯誤訊息更新
系統SHALL更新轉帳相關的錯誤訊息，確保法務部被正確列在支援的部門列表中。

#### Scenario: 轉帳到無效目標
- **Given:** 用戶嘗試轉帳到無效身份組
- **When:** 系統返回錯誤時
- **Then:** 錯誤訊息SHALL列出所有支援的部門，包含法務部
- **And:** SHALL提供正確的身份組名稱格式

## 技術實現要點

### 1. 修改文件
- `/src/bot/commands/transfer.py` - 更新身份組映射邏輯
- `/src/bot/services/transfer_service.py` - 添加法務部支援
- `/src/config/departments.json` - 確認法務部配置

### 2. 資料流程
```
用戶輸入 /transfer -> 身份組檢查 -> 法務部識別 -> 政府帳戶映射 -> 執行轉帳
```

## 跨能力依賴
- 依賴 `justice_department_panel` 能力提供 UI 界面
- 與 `adjust_economics` 能力共享身份組配置
- 依賴核心經濟系統的基礎功能
