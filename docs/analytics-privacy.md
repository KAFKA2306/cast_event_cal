# Analytics privacy contract

Browser analytics is opt-in. The default `unknown` state and an explicit `denied` state do not load the third-party analytics script or send analytics events. A stored `granted` choice is local to the browser and is the only state that permits analytics initialization.

Global Privacy Control or Do Not Track overrides a stored grant and fails closed without showing another tracking prompt. Events that happen before consent are not replayed after consent is granted. Analytics refusal does not gate calendar browsing, search, official links, or ICS access.

GA4 automatic page views, Google signals, and ad-personalization signals are disabled; ads data redaction is enabled. Missing or invalid analytics configuration is a normal no-analytics state.

The fixed Node fixture `tests/browser_analytics_privacy.cjs` enforces the negative network boundary for unknown, denied, GPC, and DNT states and verifies explicit-grant behavior in CI.
