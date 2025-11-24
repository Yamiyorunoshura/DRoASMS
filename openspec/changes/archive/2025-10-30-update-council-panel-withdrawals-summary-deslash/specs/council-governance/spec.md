## ADDED Requirements
### Requirement: Slash Commands 去重（面板優先）
系統必須（MUST）避免提供與「理事會面板」重複之斜線指令；當某功能已可自面板操作時，不得（MUST NOT）再提供對等的斜線指令。允許的治理相關斜線指令限：`/council panel` 與設定類（例如 `/council config_role`）。

#### Scenario: 僅保留面板與設定指令
- **WHEN** 查閱可用的 `/council` 指令
- **THEN** 僅看見 `/council panel` 與設定相關指令，且無撤案/建案/匯出等重複指令

## REMOVED Requirements
### Requirement: Admin Exports via Slash Commands
**Reason**: 匯出功能已由理事會面板完整提供，保留斜線指令將造成操作冗餘與體驗分裂。
**Migration**: 管理者請改由 `/council panel` 進入面板，於面板中選擇期間與格式（JSON/CSV）後下載。
