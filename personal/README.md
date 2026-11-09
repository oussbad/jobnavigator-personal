# Personal JobNavigator setup

This checkout adds a host-native macOS setup to [JobNavigator](https://github.com/vesaias/JobNavigator).
Start here; the upstream README describes the Docker deployment instead.

## Start

Prerequisites: Python 3.13, Node.js with npm, PostgreSQL 17 command-line tools and Codex CLI.
On a Mac with Homebrew, missing prerequisites can be installed from their official packages.
Load nvm first if that is how Node was installed.

```sh
bash personal/install.sh
python3.13 personal/manage.py start
```

Open http://127.0.0.1:5173. The dashboard key is in `.personal/settings.json`.
Keep that file local. The app does not start scraping, email monitoring or sending applications.
The API and CLI runner bind to loopback; the database is a separate cluster on port 55432.

```sh
python3.13 personal/manage.py status
python3.13 personal/manage.py stop
```

Stop preserves the database. Startup is idempotent and refuses occupied ports rather than
stopping unrelated processes. There is no system-wide launch agent or automatic login item.

## Existing applications

Preview an existing tracker, then import confirmed historical applications into the local database:

```sh
.venv313/bin/python personal/tracker.py /absolute/path/to/application_tracker.json
.venv313/bin/python personal/tracker.py /absolute/path/to/application_tracker.json --apply
```

The import is idempotent. Other records remain in `.personal/tracker-import.json` for follow-up;
they are not counted as submissions. It makes no employer-page requests and sends no applications.
This imports history, not blanket permission for future applications. The source tracker is never changed.

## Codex access

The importer selects Codex CLI with an empty model override, preserving the CLI's default model.
A normal personal Codex login uses the upstream isolated configuration behavior.

For an enterprise-managed **host-native** Codex connection, and only if the organization permits
this personal use, opt into preserving its existing configuration and policy rules:

```sh
JN_CODEX_USE_USER_CONFIG=1 python3.13 personal/manage.py start
```

If the services are already running, stop them first. This switch affects the runner started
by that command; it never edits global Codex configuration or copies an auth file. It retains
read-only execution, an empty temporary workspace, disabled web search and ephemeral sessions.
An inherited `CODEX_HOME` is honored in this mode. The local-only setting
`codex_use_user_config: true` in `.personal/settings.json` persists the choice between restarts. Member accounts cannot use the owner's host config.
An enterprise connection that depends on additional environment credentials may need an approved
adapter; those secrets are deliberately not forwarded by this change. Authentication and actual
model access must be verified separately. No real LLM request is part of installation.

A Gemini Pro subscription does not configure a Gemini API key. This setup does not extract Google
credentials or promise that the upstream Antigravity runner is covered by that subscription.

## First-use checklist

1. Import the historical tracker before researching new roles.
2. Keep the original CV PDF outside the repository. Disable generated rewrites until reviewed.
3. Fill Persona with confirmed answers; leave unknown answers unresolved.
4. Add relevant employer career pages and English-language searches in Germany, Ireland and Sweden.
5. Check employer evidence for sponsorship or relocation; the upstream US H-1B dataset is not proof of European sponsorship.
6. Use the extension on click after checking its permissions. It fills forms; it does not submit them.
7. Record submissions only after a success page or verified sent email.

No CV, profile, tracker, home address, credentials or mailbox data belongs in Git. `.personal/`,
virtual environments, environment files and personal document formats are ignored.
See [SETUP_REPORT.md](SETUP_REPORT.md) for the code review and validation status.
