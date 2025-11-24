## ADDED Requirements

### Requirement: Transfer Success Notification to Initiator
系統必須（MUST）在轉帳成功時，除了 DM 通知收款人外，也向轉帳人（發起人）發送 ephemeral notification，告知轉帳已成功執行。

#### Scenario: 同步模式轉帳成功通知
- **WHEN** 轉帳在同步模式下成功執行
- **THEN** 轉帳人在執行 `/transfer` 指令時收到 ephemeral 回應，顯示轉帳成功訊息
- **AND** 收款人收到 DM 通知

#### Scenario: 事件池模式轉帳成功通知
- **WHEN** 轉帳在事件池模式下異步完成
- **THEN** 系統向轉帳人發送 ephemeral followup notification，顯示轉帳成功訊息
- **AND** 收款人收到 DM 通知

#### Scenario: 通知內容包含轉帳詳情
- **WHEN** 轉帳成功執行
- **THEN** 轉帳人收到的 ephemeral notification 包含以下資訊：
  - 轉帳金額
  - 收款人資訊（mention 或顯示名稱）
  - 轉帳後的餘額
  - 備註（如有）

#### Scenario: 通知失敗不影響轉帳流程
- **WHEN** 轉帳成功但發送 ephemeral notification 失敗（例如 interaction token 過期、guild 不存在等）
- **THEN** 轉帳交易仍視為成功完成
- **AND** 系統記錄通知失敗事件，但不中斷後續流程
