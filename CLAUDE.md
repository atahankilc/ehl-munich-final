# CLAUDE.md

@AGENTS.md

## Claude-specific notes

- `AGENTS.md` (imported above) is the canonical rule set shared with Codex and other agents — edit rules there, not here, so both stay in sync.
- The project memory is `foundation/` — read `foundation/README.md` for the read/write protocol. Prefer it over personal memory for anything project-related.
- The app's LLM provider is **OpenAI** (D-006) — don't add the Anthropic SDK or Claude model IDs to the app code.
