# Design tokens

## Current confirmed implementation

Both frontends use Element Plus and its default stylesheet. Project-level styling exists in:

- Desktop: `admin/src/style.css` plus scoped styles in Vue components such as `admin/src/layouts/MainLayout.vue`.
- Mobile: `admin-mobile/src/style.css` plus scoped component styles.
- Icons: `@element-plus/icons-vue`.

The current desktop layout uses an example application background of `#f3f4f6` and Element Plus semantic colors/components. These existing values describe implementation, not an approved brand specification.

## Required token policy

- Prefer Element Plus CSS variables, component props, and existing shared CSS over arbitrary one-off values.
- Preserve consistent primary, success, warning, danger, info, and disabled semantics.
- Pair status color with readable text/iconography.
- Keep focus indicators visible and maintain readable contrast.
- Use consistent spacing, radii, typography, and touch-target sizes across desktop and mobile.
- Treat the mappings in `docs/frontend-ui-skill.md` as current project conventions until explicitly revised.

## TODO

- TODO: Confirm brand colors and whether Element Plus defaults should be themed.
- TODO: Define typography family, scale, weights, and Chinese fallback.
- TODO: Define spacing, radii, shadows, breakpoints, table density, and layer/z-index scales.
- TODO: Document shared desktop/mobile semantic tokens and deliberate surface-specific differences.
- TODO: Convert approved values into shared CSS custom properties or Element Plus theme overrides.
