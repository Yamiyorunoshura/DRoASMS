## Context

當轉帳在事件池模式下異步完成時，需要在轉帳成功時向轉帳人發送 ephemeral notification。由於轉帳可能異步完成，原始的 `discord.Interaction` 物件可能已不可用，需要找到替代方式發送通知。

## Goals / Non-Goals

### Goals
- 在轉帳成功時向轉帳人發送 ephemeral notification
- 支援同步模式和事件池模式
- 通知失敗不影響轉帳流程

### Non-Goals
- 不需要修改資料庫 schema（優先使用現有機制）
- 不需要實現複雜的 token 管理系統

## Decisions

### Decision: 使用 Interaction Token 發送 Followup
在轉帳請求時保存 interaction token，並在 `TelemetryListener` 收到 `transaction_success` 事件時使用 Discord HTTP API 發送 followup。

**Rationale**:
- Discord interaction token 有效期為 15 分鐘，通常足夠覆蓋轉帳完成時間
- 不需要修改資料庫 schema，可在 metadata 中儲存 token
- 使用標準 Discord API，符合現有架構

**Alternatives considered**:
1. **使用 DM 通知轉帳人**：不符合需求（用戶要求 server notification）
2. **修改資料庫 schema 儲存 token**：過度設計，token 有時效性且不需要持久化
3. **使用 webhook**：需要額外設定，複雜度較高

### Decision: Token 儲存在 Transfer Metadata
將 interaction token 儲存在轉帳的 metadata 中，透過現有的 `metadata` JSONB 欄位傳遞。

**Rationale**:
- 現有架構已支援 metadata
- 不需要修改資料庫 schema
- Token 有時效性，不需要長期儲存

**Implementation**:
- 在 `transfer.py` 中，當進入 event pool 模式時，將 `interaction.token` 加入 metadata
- 在 `TelemetryListener` 中，從 metadata 讀取 token 並發送 followup

### Decision: 使用 Discord HTTP API 發送 Followup
在 `TelemetryListener` 中使用 Discord HTTP API（透過 `discord.Client.http`）發送 followup，而非嘗試重新建立 interaction 物件。

**Rationale**:
- Interaction 物件無法輕易重建
- HTTP API 直接且可控
- 符合 Discord 官方建議的做法

**Implementation**:
```python
# 在 TelemetryListener 中
token = metadata.get("interaction_token")
if token and self._discord_client:
    # Discord interaction followup 需要 application_id 和 token
    # application_id 可從 client 取得
    application_id = self._discord_client.application_id
    if application_id:
        await self._discord_client.http.followup.send(
            application_id=application_id,
            token=token,
            content=success_message,
            flags=64  # EPHEMERAL flag
        )
```

## Risks / Trade-offs

### Risk: Token 過期
**Mitigation**:
- Token 有效期 15 分鐘，通常足夠
- 若 token 過期，靜默失敗並記錄日誌（不影響轉帳流程）

### Risk: 無法取得 Guild ID
**Mitigation**:
- 從事件 payload 中取得 `guild_id`
- 若無法取得，則無法發送 followup，靜默失敗

### Trade-off: 同步模式 vs 事件池模式
- 同步模式：interaction 仍可用，可直接使用 `interaction.followup.send()`
- 事件池模式：需要透過 HTTP API 發送 followup
- 兩種模式都需要處理，但實作方式略有不同

## Migration Plan

1. 無需遷移：此為新增功能，不影響現有行為
2. 向後相容：同步模式下的現有行為保持不變

## Open Questions

- [ ] 是否需要處理 interaction application ID？（通常從 bot client 取得）
- [ ] 是否需要額外的錯誤處理機制？
