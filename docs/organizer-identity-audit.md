# Organizer identity audit

Run `python scripts/audit_organizer_identity.py <canonical-events.json> --output <audit.json>` to produce a read-only organizer identity audit.

The audit never treats a display-name match as identity proof. Unicode/whitespace normalization only creates a comparison bucket. A candidate is `merged` only when every member has the same explicit strong identity key (VRChat group ID or explicit profile-specific HTTPS organizer URL), `distinct` when strong evidence conflicts, and `ambiguous` when strong evidence is missing. Output is sorted so decisions do not depend on input order.

This stage creates no public organizer URL and does not use classifier priors as identity authority. Public navigation can consume only reviewed stable candidates in a later change.

An event `official_url` is not identity evidence: unrelated organizers may publish on the same platform. Bare website origins, credential-bearing URLs, and malformed profile URLs are excluded. This read-only audit does not authorize public organizer merging.
