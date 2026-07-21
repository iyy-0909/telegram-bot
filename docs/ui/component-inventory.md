# Component inventory

## Desktop admin (`admin/src/`)

### Shell and feedback

- `layouts/MainLayout.vue`: desktop shell and navigation.
- `components/LoginPanel.vue`: authentication entry.
- `components/RuntimeDashboard.vue`, `StatusCards.vue`, `StatusTag.vue`: runtime/status presentation.
- `components/ErrorText.vue`, `CopyText.vue`, `JsonPreview.vue`: shared feedback and data utilities.

### Shared selectors and editors

- `AccountSelect.vue`, `BotSelect.vue`, `ChannelSelect.vue`
- `ReplaceRulesEditor.vue`, `TemplateRulePanel.vue`, `SendSettingsPanel.vue`

### Operational tables/dialogs

- Accounts: `AccountTable.vue`, `AccountDialog.vue`, `AccountLoginDialog.vue`
- Bots: `BotTable.vue`, `BotDialog.vue`, `BotBindingTable.vue`, `BotBindingDialog.vue`
- Tasks: `ListenerTaskTable.vue`, `ListenerTaskDialog.vue`, `CloneTaskTable.vue`, `CloneTaskDialog.vue`
- Templates: `ContentTemplateTable.vue`, `ContentTemplateDialog.vue`
- Channels/support/tools: `MyChannelTable.vue`, `SupportPanel.vue`, `BulkReplacePanel.vue`, `RuleTable.vue`, `RuleDialog.vue`, `UserGuide.vue`

## Mobile admin (`admin-mobile/src/`)

- `components/MobileLayout.vue`: top bar, content shell, refresh action, and bottom navigation.
- `components/StatusPill.vue`: compact status treatment.
- `components/EmptyState.vue`: empty-result feedback.
- Additional task cards, list pages, forms, log/detail drawers, and More-page concepts are currently composed from `admin-mobile/src/App.vue`; inspect that file before adding equivalents.

## Reuse rules

- Reuse Element Plus components and the shared selectors/status/error/copy utilities first.
- Extend existing table/dialog/card/drawer patterns when behavior is compatible.
- Do not create parallel desktop/mobile terminology or status mappings for the same business concept.
- Keep desktop density and mobile touch ergonomics deliberately different while preserving business meaning.
- Follow the canonical component requirements already documented in `docs/frontend-ui-skill.md`.

## TODO

- TODO: Inventory all mobile components after any deliberate extraction from the large `admin-mobile/src/App.vue`.
- TODO: Document public props/events and ownership for canonical shared components.
- TODO: Identify which patterns can safely share tokens or logic between the two separate frontends.
