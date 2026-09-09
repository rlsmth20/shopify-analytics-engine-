# Design A frontend release

Applies the approved A direction across the workspace and public shared UI: light navigation, teal actions, locally hosted Inter, compact headers, account disclosure, and responsive forms. The action queue defaults to comparison with expandable recommendations. Lead-time settings group suppliers, categories, SKU exceptions and defaults while retaining edits across sections; mobile SKU rows are labeled records and Save stays in document flow. Import explanations and setup guidance use expandable details.

Validation before release: 236 frontend tests, TypeScript and production build passed. All 45 routes were inspected at desktop (1440px) and mobile (390px) widths with no page-level horizontal overflow. Overview, actions and billing were also checked at 768px and 360px after final layout adjustments. Browser checks covered navigation focus and Escape dismissal, account disclosure, action expansion and public mobile navigation.

Populated settings and connection states used browser-local synthetic responses. A SKU edit survived section switching and produced a SKU-only save request and confirmation in the simulated session. These checks do not establish live backend persistence. Backend code and API contracts are unchanged.

The original A/B/C draft artifacts remain local for comparison. Shared visual tokens are in `frontend/app/design-a.css`; workspace navigation layout is in `frontend/components/app-shell.module.css`.
