# User flows

## Desktop administration

### Sign in and inspect runtime health

1. Open the desktop app through `admin/src/main.js`.
2. Authenticate in `LoginPanel`.
3. Enter `MainLayout` and open the runtime dashboard.
4. Inspect service state, queues, warnings, and recent operational information.

Required states: authentication check, submitting, invalid credentials/request error, dashboard loading/refresh, partial data, empty state, and permission restriction.

### Configure and run listener or clone tasks

1. Open listener tasks or clone tasks.
2. Add/edit a task using the existing dialog components.
3. Select existing accounts, bots, channels, and templates through shared selectors.
4. Start, pause, resume, stop, or catch up as supported.
5. Inspect logs and recover from errors.

Required states: list loading/empty/error, field validation, saving, action-in-progress, success, failure with recovery, disabled action, permission restriction, and destructive confirmation.

### Manage operational assets

1. Open accounts, bots, channels, support bots, templates, or settings.
2. Search/filter and inspect current status.
3. Add/edit/test/enable/disable/delete as supported.
4. Confirm the refreshed result and readable backend errors.

Required states: loading, empty, search with no results, saving/testing, success/error, disabled, permission restriction, and destructive confirmation.

## Mobile administration

### Handle frequent operational actions

1. Authenticate through `admin-mobile/src/App.vue`.
2. Use bottom navigation from `MobileLayout.vue` to open Home, Listeners, Clones, Channels, or More.
3. Search items, inspect cards, and run common actions.
4. Use bottom drawers for editing, account login, details, and logs.
5. Refresh and confirm the result without losing necessary context.

Required states: login loading/error, page loading/refresh, empty/no-results, drawer saving, success/error, disabled, permission restriction, and destructive confirmation.

## Responsive verification

- Test desktop admin at 1440px, 768px, and 375px even though a separate mobile app exists; it must not become unusable at narrower widths.
- Test mobile admin at 375px and 768px, including bottom navigation, long labels, drawers, keyboard/form behavior, and safe-area/fixed-element overlap.
- Test the same business action on desktop and mobile when both surfaces expose it, ensuring terminology and feedback remain consistent.

## TODO

- TODO: Confirm the single most important end-to-end flow for each surface.
- TODO: Confirm recovery expectations for disconnected Telegram accounts, invalid sessions, failed distribution, and partial batch success.
- TODO: Decide whether desktop and mobile should preserve cross-device filter/task context.
