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

## Verified-profile registry and freshness check

The advisory profile data above is unchanged. Separately, [`verified.toml`](../src/tracemantle/profiles/verified.toml) records what a human last checked for each agent:

| Field | Content |
|---|---|
| `version` | Exact runtime version string or documentation revision that was checked |
| `checked` | The commit, tag or URL inspected |
| `verified_on` | Date of the inspection, as a TOML date |
| `docs_url` | Published documentation page, used only for the Last-Modified check |
| `confirmed`, `contradicted` | Compatibility rule IDs the inspection confirmed or contradicted |

The shipped entries carry over the `historical-v1` provenance: an unversioned documentation page recorded on 2026-04-20, no pinned runtime build and no rule confirmed or contradicted. They are stale on purpose until someone re-verifies them.

`tracemantle SKILL.md --check-profile-freshness` prints a warning on stderr for each profile that:

- was verified more than `--profile-max-age-days N` days ago (default 90), or
- has a `docs_url` whose HTTP `Last-Modified` header is later than `verified_on`.

The check sends one HTTP HEAD request per profile, so it needs network access and is never run unless the flag is given. It does not download or parse pages and does not contact an agent. An unreachable page or a response with no `Last-Modified` header is reported as unchecked instead of being counted as fresh. `--target-agent` limits the check to one profile, and `--profile-registry PATH` reads another registry file, for example a team copy that is newer than the installed package. Warnings never change the report on stdout or the exit code.

Limits: `Last-Modified` is a hint. Several vendor documentation hosts omit it, and dynamically rendered pages report the time of the request, which always looks newer. A quiet result means the registry entry is recent; it does not mean an agent runtime behaves as the profile says.

### Updating an entry

No parser or rule code changes are needed.

1. Open the agent's `docs_url` and note the documentation revision, or install the agent and record its exact version string.
2. For each compatibility rule that names the agent (`compat.*` in the [generated reference](generated-reference.md)), check the documented or observed behavior. Add the rule ID to `confirmed` or `contradicted`. Leave out rules you did not check.
3. Set `version`, `checked` (the commit, tag or URL you inspected) and `verified_on` (today's date) in the agent's table.
4. Run `tracemantle skills/tracemantle/SKILL.md --check-profile-freshness --target-agent AGENT` and confirm the age warning is gone.
5. A contradicted rule is a finding, not a registry edit: open an issue or change the advisory profile in a separate, reviewed commit with the source and runtime evidence required above.
