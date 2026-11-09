# Setup report — JobNavigator personal deployment

Reviewed upstream: `623822529389d6919d86be07271e0ea94e20b514` (6 November 2026).
Prepared 9 November 2026. Upstream authorship and license are retained.

## Decision

JobNavigator is the best foundation of the four inspected tools for an existing Codex CLI
workflow. It has a tracker, saved answers, ATS-specific autofill and a separated CLI runner.
It is a dashboard and autofill assistant, not an unattended application-submission bot.

| Alternative | Relevant code finding | Decision |
|---|---|---|
| ApplyPilot `4a8d521` | Applies through Claude Code; dry runs return `RESULT:APPLIED`, which the worker counts as applied. | Do not adopt as-is. |
| AIHawk `1488dcd` | Current model client uses OrcaRouter; submission verification distinguishes uncertain outcomes. | Additional provider integration required for the existing subscriptions. |
| JobSpy `68b88d6` | Structured job discovery, including DE/IE/SE; no application submission. | Useful discovery library, already available in JobNavigator. |
| JobNavigator `6238225` | Codex CLI runner plus non-submitting browser autofill. | Selected. |

## Changes

- Host-native start/stop/status commands using an isolated PostgreSQL cluster; no Docker socket mount.
- Dashboard, API, database and CLI runner listen on loopback only.
- Scheduler and telemetry disabled at startup; no Gmail or LinkedIn account integration enabled.
- Local generated dashboard/database credentials stored under an ignored private directory.
- Opt-in owner-only use of existing host Codex configuration, retaining policy rules and read-only execution.
- Historical tracker preview/import with conservative confirmation detection and repeat-import protection.
- Private data remains local and is excluded from the published source.

## Limits

An Oracle or other enterprise Codex entitlement is not proven portable by the presence of a CLI.
This change preserves existing configuration only when explicitly enabled. No credentials are copied
and no paid API fallback is added. Enterprise authorization and a real provider request remain separate checks.
No claim of Gemini Pro API access is made. CV import/scoring can transmit its content to the selected
model provider, so that should be configured deliberately before using those features.

Application history is imported locally. Pending items remain in a local manifest; they are not
silently promoted to submitted applications. An import does not send applications or fetch employers.
The Chrome extension still requires loading/configuration and review of actual field values.
EU sponsorship must be verified from employer evidence; the H-1B feature concerns the US.

## Validation

- Python 3.13 environment: pinned requirements installed; `pip check` reports no broken requirements.
- Tracker normalization: 2 tests passed; preview found 48 confirmed records and preserved 10 others locally.
- Codex provider regressions: 12 tests passed, including managed-config isolation and API-key non-forwarding.
- Runner authentication/isolation contract suite: 11 tests passed.
- Final combined backend runtime/runner/seeding suite: 72 tests passed; tracker unit tests: 2 passed.
- Frontend: production build passed; 32 test files / 408 tests passed. Upstream large-bundle warning remains.
- Frontend lockfile generated; npm 11 used to avoid an npm 10 peer-resolution crash.
- Local API, authenticated history endpoint, CLI runner and dashboard proxy returned HTTP 200.
- Imported 48 historical applications; repeating the import added zero records.
- Stop/start smoke test passed and preserved the history; the unmodified demonstration CV was removed.
- Host Codex connection test returned `{"connection":"ok"}` using public placeholder text only.
- After authorized persistent setup and restart, the authenticated JobNavigator HTTP runner returned
  `{"runner":"ok"}`; historical application count remained 48.

The running local instance has scheduling and telemetry disabled. The owner explicitly authorized ongoing local reuse of the host Codex login and configuration.
That choice is stored only in the ignored local settings file. No credentials were copied or published. A real CV/Persona must be
configured locally before scoring or autofill; no demonstration qualifications are left selected.
No applications, emails or CV uploads are sent during setup.

## Local candidate configuration

The real base CV, Persona, confirmed reusable answers and original-design PDF are now
configured locally. Twelve focused keyword searches cover four engineering role groups
in Germany, Ireland and Sweden, with a six-hour interval and Codex fit scoring.
Unrelated seed searches/employers are paused. Candidate preferences, factual constraints
and sponsorship uncertainty are included in the scoring instructions. These instructions
are model guidance, not a guarantee that every listing meets all requirements.

The personal runtime supports an explicit local `scheduler_enabled` switch. Four runtime
and tracker tests passed, including scheduling defaults and preservation of private
runner authentication when the dashboard is keyless. No candidate profile or documents
are committed. Browser autofill extension installation remains separate, and there is
no automatic application submission or blanket consent acceptance.

The first real search found seven new listings and exposed an upstream model-default bug:
an empty CLI model incorrectly fell back to a Claude API model. The resolver now leaves
subscription CLI defaults empty while preserving explicit model choices. The new model
regressions plus existing provider tests passed (26 tests); no provider credentials are
committed. The scheduled discovery/scoring loop is enabled locally at a 360-minute interval.

End-to-end verification: the configured real CV was scored against one discovered listing;
a 40/100 score was stored successfully. This validates the model-resolution fix without
claiming the listing is a suitable match. Seven new listings were initially discovered.
Only the 12 targeted searches are active; the uninstalled extension sources remain paused.
The 48 historical applications are unchanged.
