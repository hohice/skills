# OKF Note-Taking Templates

These templates are also available as files in `assets/`.

## Concept template

See `assets/concept-template.md`.

Key frontmatter fields:

- `type` (required): e.g. `Note`, `Topic`, `Reference`, `Formula`, `Attested Computation`.
- `title`: human-readable display name.
- `description`: one-sentence summary.
- `resource`: optional canonical URI for the underlying asset.
- `tags`: YAML list of short strings.
- `status`: `draft` | `stable` | `deprecated`.
- `generated`: `{ by: <actor>, at: <ISO-8601-UTC> }`.
- `verified`: list of verification events.
- `stale_after`: absolute expiration instant.
- `sources`: provenance with credibility signals.
- `assets`: extension field for attached media paths.

## Actor convention

- Agent/tool: `<producer>/<version>`, e.g. `kimi-code-cli`.
- Human: `human:<id>`, e.g. `human:alice`.
- Process: `process:<id>`, e.g. `process:nightly-check`.

Use `human:` for hand-authored or human-reviewed content.

## Index template

See `assets/index-template.md`.

## Log template

See `assets/log-template.md`.

Date headings must be `YYYY-MM-DD`, newest first.
