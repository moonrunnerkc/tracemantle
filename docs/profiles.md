# Standard conformance and compatibility profiles

The standard field set is `name`, `description`, `license`, `metadata`, `compatibility`, and experimental `allowed-tools`. TraceMantle validates compatibility as a 1–500 character string and metadata as a string-to-string mapping. Vendor extension fields and ecosystem metadata are classified separately; quality scoring and reserved-name advice are advisory.

Reference: [Agent Skills specification](https://agentskills.io/specification), inspected 2026-09-12. The pinned [skills-ref source](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref) is version 0.1.0 at commit `69ef37e9424c0a7ea9dd2293b559e43ec8176379`. Its Apache-2.0 license, source bytes and SHA-256 provenance are retained in `tests/fixtures/upstream/skills-ref-69ef37e/`. It has a CLI (`skills-ref validate`) and checks directory-name matching.

Executed shared cases and intentional divergences are recorded in [conformance.json](verification/conformance.json). TraceMantle's portable naming profile remains ASCII lowercase letters/digits/hyphens, with no automatic normalization. The reference normalizes NFKC and accepts Unicode alphanumeric names. TraceMantle enforces string metadata values and nonempty compatibility, which this reference revision does not fully enforce. These divergences are explicit, not claims that the reference validates those cases identically.

Compatibility profile `historical-v1` retains the prior advisory field matrix and provenance date 2026-04-20. Its runtime applicability is **unverified**: the historical claims do not identify tested VS Code, Cursor, Codex or Claude runtime versions. A freshness date is not runtime evidence. In particular, dirname enforcement follows the standard; claims about a specific loader silently rejecting it are not established by the static analyzer. Cursor block-scalar behavior remains historical advice, with strict promotion only when the caller explicitly selects that policy.

Authoritative vendor documentation for future profile updates:

| Profile | Source | Revision evidence | Runtime applicability |
|---|---|---|---|
| Claude | https://code.claude.com/docs/en/skills | Historical source reference, no pinned runtime build | Unverified |
| VS Code | https://code.visualstudio.com/docs/copilot/customization/agent-skills | Historical source reference, no pinned runtime build | Unverified |
| Codex | https://developers.openai.com/codex/skills | Historical source reference, no pinned runtime build | Unverified |
| Cursor | https://cursor.com/docs/context/skills | Historical source reference, no pinned runtime build | Unverified |

New vendor assertions require source/revision and runtime evidence in the profile registry before changing a claim. Neither selecting an agent prompt variant nor importing an agent label proves execution by that vendor runtime.
