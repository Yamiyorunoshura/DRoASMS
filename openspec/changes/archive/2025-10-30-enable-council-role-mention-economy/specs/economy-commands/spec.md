# economy-commands — Change Delta (enable-council-role-mention-economy)

## ADDED Requirements

### Requirement: Mention Council Role in /adjust
系統必須（MUST）允許管理者在 `/adjust` 以「常任理事會」綁定之身分組作為目標，並將其映射至該 guild 的理事會帳戶 ID（由程式以 deterministic 方式生成）。

#### Scenario: 以理事會身分組加值成功
- WHEN 管理者在已設定理事會的 guild 中執行 `/adjust`，target 提及為已綁定的理事會身分組
- AND amount 為正整數，reason 填寫
- THEN 系統將目標映射為「理事會帳戶」並成功完成加值

#### Scenario: 以理事會身分組扣點成功
- WHEN 管理者在已設定理事會的 guild 中執行 `/adjust`，target 提及為已綁定的理事會身分組
- AND amount 為負整數，reason 填寫
- THEN 系統將目標映射為「理事會帳戶」並成功完成扣點，且不得使餘額為負

#### Scenario: 未設定治理被拒
- WHEN guild 尚未完成理事會綁定
- THEN 系統拒絕並提示應先執行 `/council config_role`

#### Scenario: 提及非綁定身分組被拒
- WHEN target 為任意身分組但非理事會綁定者
- THEN 系統拒絕請求並提示「僅支援提及已綁定的常任理事會身分組」

### Requirement: Mention Council Role in /transfer
系統必須（MUST）允許一般成員在 `/transfer` 以「常任理事會」綁定之身分組作為受款人，並將其映射至該 guild 的理事會帳戶 ID 後執行轉帳。

#### Scenario: 轉入理事會帳戶成功
- WHEN 成員在已設定理事會的 guild 中執行 `/transfer`，target 提及為已綁定的理事會身分組
- AND amount 為正整數
- THEN 系統將目標映射為「理事會帳戶」並成功完成轉帳

#### Scenario: 未設定治理被拒
- WHEN guild 尚未完成理事會綁定
- THEN 系統拒絕並提示應先執行 `/council config_role`

#### Scenario: 提及非綁定身分組被拒
- WHEN target 為任意身分組但非理事會綁定者
- THEN 系統拒絕請求並提示「僅支援提及已綁定的常任理事會身分組」
