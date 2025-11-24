## MODIFIED Requirements
### Requirement: Mention Council Role in /transfer
系統必須（MUST）允許一般成員在 `/transfer` 以「常任理事會」綁定之身分組作為受款人，並將其映射至該 guild 的理事會帳戶 ID 後執行轉帳。系統必須（MUST）同時支援以「國務院領袖」綁定之身分組作為受款人，並將其映射至該 guild 的國務院主帳戶 ID 後執行轉帳。系統必須（MUST）同時支援以「部門領導人」綁定之身分組作為受款人，並將其映射至對應的部門政府帳戶 ID 後執行轉帳。系統必須（MUST）在同步模式和事件池模式下都正確支援上述所有身分組轉帳功能。

#### Scenario: 轉入理事會帳戶成功
- WHEN 成員在已設定理事會的 guild 中執行 `/transfer`，target 提及為已綁定的理事會身分組
- AND amount 為正整數
- THEN 系統將目標映射為「理事會帳戶」並成功完成轉帳

#### Scenario: 轉入國務院主帳戶成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的國務院領袖身分組
- AND amount 為正整數
- THEN 系統將目標映射為「國務院主帳戶」並成功完成轉帳

#### Scenario: 轉入部門政府帳戶成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的部門領導人身分組
- AND amount 為正整數
- THEN 系統將目標映射為對應的「部門政府帳戶」並成功完成轉帳

#### Scenario: 未設定治理被拒
- WHEN guild 尚未完成理事會或國務院綁定
- AND target 提及為理事會身分組或國務院領袖身分組
- THEN 系統拒絕並提示應先執行 `/council config_role` 或 `/state_council config_leader`

#### Scenario: 提及非綁定身分組被拒
- WHEN target 為任意身分組但非已綁定的理事會、國務院領袖或部門領導人身分組
- THEN 系統拒絕請求並提示「僅支援提及常任理事會、國務院領袖或已綁定之部門領導人身分組，或直接指定個別成員」

#### Scenario: 事件池模式下理事會身分組轉帳成功
- WHEN 成員在已設定理事會的 guild 中執行 `/transfer`，target 提及為已綁定的理事會身分組
- AND 系統啟用事件池模式（`TRANSFER_EVENT_POOL_ENABLED=true`）
- AND amount 為正整數
- THEN 轉帳請求被記錄到 `economy.pending_transfers` 表
- AND 系統將目標映射為「理事會帳戶」並在檢查通過後自動執行轉帳

#### Scenario: 事件池模式下國務院領袖身分組轉帳成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的國務院領袖身分組
- AND 系統啟用事件池模式（`TRANSFER_EVENT_POOL_ENABLED=true`）
- AND amount 為正整數
- THEN 轉帳請求被記錄到 `economy.pending_transfers` 表
- AND 系統將目標映射為「國務院主帳戶」並在檢查通過後自動執行轉帳

#### Scenario: 事件池模式下部門領導人身分組轉帳成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的部門領導人身分組
- AND 系統啟用事件池模式（`TRANSFER_EVENT_POOL_ENABLED=true`）
- AND amount 為正整數
- THEN 轉帳請求被記錄到 `economy.pending_transfers` 表
- AND 系統將目標映射為對應的「部門政府帳戶」並在檢查通過後自動執行轉帳
