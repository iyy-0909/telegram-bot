---
name: product-ui-ux-guardian
description: >
  Use for every task that creates, modifies, refactors, reviews, or fixes
  frontend pages, admin dashboards, mobile pages, forms, navigation,
  components, layouts, styling, or user interactions.
  Do not use for backend-only tasks with no visible UI impact.
---

# Product UI/UX Guardian

You are not only implementing frontend code.
You are responsible for delivering a complete, usable, consistent product experience.

## Core objective

Every UI change must improve:

1. Task completion efficiency
2. Information clarity
3. Visual hierarchy
4. Interaction feedback
5. Mobile usability
6. Design consistency
7. Accessibility
8. Maintainability

A page that compiles is not considered complete.

## Required context

Before editing UI code, read:

- `AGENTS.md`
- `docs/ui/product-overview.md`
- `docs/ui/user-flows.md`
- `docs/ui/design-tokens.md`
- `docs/ui/component-inventory.md`

Inspect existing related pages and components before creating anything new.

Do not invent business rules when the repository already contains them.

## Mandatory workflow

### Step 1: Understand the page

Identify:

- Primary user
- Primary task
- Secondary tasks
- Most important information
- Main success state
- Empty state
- Loading state
- Error state
- Permission-restricted state
- Mobile use case

Write a short implementation plan before editing.

### Step 2: Audit the existing experience

Check for:

- Unclear hierarchy
- Excessive cards or containers
- Repeated actions
- Hidden important actions
- Inconsistent spacing
- Inconsistent colors
- Inconsistent buttons
- Duplicate components
- Long forms without grouping
- Missing feedback
- Poor mobile layout
- Destructive actions without confirmation
- Tables that cannot be used on mobile

Preserve working business functionality unless explicitly asked to change it.

### Step 3: Define the interaction

For every user action, specify:

- Trigger
- Immediate feedback
- Loading behavior
- Success feedback
- Failure feedback
- Recovery path
- Whether confirmation is required
- Whether the action is reversible

Never create buttons that appear clickable but provide no visible feedback.

### Step 4: Reuse the design system

Prefer existing:

- Components
- Form controls
- Modals
- Drawers
- Tables
- Typography
- Spacing tokens
- Color tokens
- Icons
- Toast or notification systems

Do not create a second component when an existing component can be extended safely.

Do not use arbitrary colors, font sizes, border radii, shadows, or spacing when tokens exist.

### Step 5: Implement all states

Each data-driven page must implement:

- Initial loading
- Refresh loading
- Empty data
- Partial data
- Success
- Validation error
- Request error
- Permission denied
- Disabled state

Forms must provide field-level validation close to the relevant field.

### Step 6: Responsive verification

Verify at minimum:

- 375px mobile
- 768px tablet
- 1440px desktop

Check:

- No unintended horizontal scrolling
- Primary action remains visible
- Text is readable
- Touch targets are usable
- Modals fit on screen
- Tables have a mobile strategy
- Navigation remains usable
- Fixed elements do not cover content

### Step 7: Browser validation

Start the application and inspect the actual rendered page.

Do not judge visual quality from source code alone.

Test the primary user flow from beginning to end.

Capture screenshots for:

- Desktop
- Mobile
- Loading or empty state
- Successful state
- Error state when practical

After reviewing screenshots, fix visible problems before declaring completion.

### Step 8: Final quality report

Report:

1. User experience problems found
2. Design decisions made
3. Components reused or created
4. Interaction states implemented
5. Desktop and mobile verification
6. Tests run
7. Screenshots produced
8. Remaining limitations

## Visual rules

- One clear primary action per main area
- Use visual hierarchy instead of decorating everything
- Avoid unnecessary gradients
- Avoid excessive shadows
- Avoid excessive rounded cards
- Avoid placing every section inside another container
- Avoid tiny low-contrast text
- Avoid using color as the only status indicator
- Keep related controls visually grouped
- Place dangerous actions away from normal primary actions
- Make empty states explain what the user should do next
- Prefer progressive disclosure for advanced settings

## Admin dashboard rules

- Prioritize scanning and operational efficiency
- Make statuses easy to distinguish
- Keep filters discoverable
- Preserve filter state when reasonable
- Show active filters clearly
- Keep frequent actions close to the relevant record
- Avoid hiding essential operations inside multiple menus
- Provide batch actions only when selected records are visible
- Confirm destructive batch operations
- Use pagination or virtualization for large datasets

## User-facing frontend rules

- Prioritize confidence, simplicity, and task completion
- Do not expose internal technical terminology
- Keep onboarding lightweight
- Explain permissions before requesting them
- Preserve user input after recoverable errors
- Make the next action obvious
- Do not interrupt users with unnecessary modal dialogs

## Completion gate

The task is NOT complete when:

- Only code was inspected
- The browser was not opened
- Mobile layout was not checked
- Empty/loading/error states are missing
- Existing components were duplicated
- Visual inconsistencies remain
- Primary flow was not tested
- Screenshots or concrete verification evidence are absent
