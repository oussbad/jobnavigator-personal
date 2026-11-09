# Application Autopilot

Open http://127.0.0.1:5173/autopilot after starting the personal runtime.
This is a separate browser worker; it does not require the Chrome autofill extension.

The discovery task searches/scores every six hours. The application worker checks
its queue every ten minutes, and can be run immediately from its dashboard.
It collects new/saved, scored roles in Germany, Ireland or Sweden with a direct
employer link and a score of at least 70. A score is a recommendation, not proof
of sponsorship, eligibility or an active employer opening. Review the employer URL
before giving standing permission. No lower-quality matches are added just to reach ten.

## Permission once, then routine execution

The worker starts with no approved destinations. A job-specific button explicitly
authorizes sharing the CV, contact details and truthful answers, filling the form
and submitting that named application. Alternatively, enter an exact employer name
and its official application-path prefix under Standing employer permissions to
authorize future matching roles at that named destination. A shared ATS hostname
alone is not enough: include the employer-specific path.

After authorization the worker fills ordinary fields from the confirmed Persona,
uploads only the configured original CV PDF, advances supported forms, submits,
and checks the receipt. It does not create qualifications or choose a salary that
is not established in the profile. Pause stops further actions; removing standing
permissions revokes unsent grants derived from those permissions.

The application limit is **10 submission attempts per rolling six hours**. Uncertain
attempts consume the limit too. A durable marker is written BEFORE the submit click;
a crash or missing receipt does not cause a second click. Only a recognized success
heading/status produces Submitted and an Application record. Screenshots and browser
sessions stay under ignored `.personal/autopilot/`.

## Where it needs attention

Missing factual answers, passwords/account setup, verification codes, CAPTCHA,
sensitive disclosures and required agreements stop the worker. Resolve these in the
separate application browser, add confirmed facts to Persona if appropriate, and use
Resume. If a submit click already happened, the item is Unconfirmed and cannot be
retried automatically. Check the employer receipt yourself.

The first implementation supports ordinary HTML inputs/selects, factual checkboxes,
CV file inputs and simple multi-step forms. Cross-origin uploads, new application
paths, custom widgets, embedded forms, email applications and unusual ATS flows can
need manual handling or a future adapter. It is **not verified as universally
unattended across employer sites**. There is no CAPTCHA solver or password generator.

## Validation

- Local browser tests cover form filling, actual multipart PDF upload, one submit,
  receipt verification, agreement handoff, uncertainty, scoped permissions, revocation,
  duplicate URLs and the rolling submission budget.
- A separate smoke test used the real configured Codex planner with a dummy candidate
  and dummy PDF against a local form. It filled, uploaded, submitted exactly once and
  recognized the receipt without scripted planner decisions.
- No live employer application was sent as part of implementation or testing.

The worker is host-native and single-owner. Its browser session is separate from
your normal Chrome profile. Mutating dashboard requests require an explicit-action
header; the worker UI cannot be framed by an outside origin. The local app remains
loopback-only. Do not expose this keyless personal deployment to the public internet.
