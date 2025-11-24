# state-council-panel – Department → User Transfer

## ADDED Requirements
### Requirement: Department To User Transfer From Panel
面板必須（MUST）提供「部門 → 使用者」轉帳功能。授權對象為：具有來源部門權限之人員或國務院領袖；受款人可為任意使用者（包含執行者本人）。

#### Scenario: 部門領導轉帳給一般使用者成功
- GIVEN 使用者擁有「來源部門」權限
- WHEN 在該部門頁點擊「轉帳給使用者」，選擇受款人並填寫金額與理由（>0）
- THEN 系統完成轉帳，來源為該部門政府帳戶、目標為受款人個人帳戶，並於面板回覆成功訊息

#### Scenario: 國務院領袖跨部門撥款成功
- GIVEN 使用者為國務院領袖
- WHEN 在面板（總覽或任一部門頁）發起「部門 → 使用者」轉帳
- THEN 系統允許選擇任一部門作為來源並完成轉帳

#### Scenario: 無權限被拒
- GIVEN 使用者不具來源部門權限且非國務院領袖
- WHEN 嘗試送出轉帳
- THEN 系統拒絕並提示無權限

#### Scenario: 可轉帳至本人
- GIVEN 授權使用者
- WHEN 將受款人指定為自身
- THEN 不因 initiator==target 檢核被擋（來源為部門帳戶，目標為個人帳戶）
