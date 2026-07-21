# Product overview

## Confirmed product scope

`telegram-bot` is a Telegram collection, cloning, and distribution operations system. Repository guidance states that Telethon user accounts listen to and collect source-channel content, while the official Telegram Bot API distributes content to target channels. The repository also contains support-bot management functionality.

## Confirmed users

- Operations staff using the desktop administration console.
- Operations staff handling frequent or urgent actions from the mobile administration console.
- No public customer-facing Web frontend is confirmed in this repository.

## Frontend stack and entry points

### Desktop admin

- Root: `admin/`
- Application entry: `admin/src/main.js`
- Page orchestration: `admin/src/App.vue`
- Main shell/navigation: `admin/src/layouts/MainLayout.vue`
- Shared components: `admin/src/components/`
- API modules: `admin/src/api/`
- Global styles: `admin/src/style.css`
- Stack: Vue 3 + Vite 5 + Element Plus + Axios

### Mobile admin

- Root: `admin-mobile/`
- Application entry: `admin-mobile/src/main.js`
- Page orchestration: `admin-mobile/src/App.vue`
- Mobile shell/navigation: `admin-mobile/src/components/MobileLayout.vue`
- Shared components: `admin-mobile/src/components/`
- API modules: `admin-mobile/src/api/`
- Global styles: `admin-mobile/src/style.css`
- Stack: Vue 3 + Vite 5 + Element Plus + Axios
- Development server: `npm run dev` from `admin-mobile/`, configured for port 5174.

Both frontends build with `npm run build` from their respective directories.

## Confirmed administration areas

- Desktop: runtime dashboard, listener tasks, clone tasks, send settings, content templates, Telegram accounts, bots, support bots, channels, bulk replacement, and user guidance.
- Mobile: operational dashboard, listeners, clones, channels, bots/support bots, templates, accounts, settings, logs, and common task controls.

## Existing project-specific UI guidance

`docs/frontend-ui-skill.md` contains established Element Plus, table, form, status, error, and component conventions. Continue following compatible rules there alongside `docs/ui/`.

## TODO

- TODO: Confirm the primary desktop and mobile personas and their top three tasks.
- TODO: Confirm which capabilities must remain desktop-only.
- TODO: Add approved reference screenshots under `docs/ui/reference-screens/`.
- TODO: Document supported browsers and accessibility target.
