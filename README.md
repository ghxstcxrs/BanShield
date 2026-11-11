# BanShield

A desktop app for tracking account bans, appeals, and supporting evidence with timestamped logs, screenshots, AI comparison notes, and edit history. Built with Python and PySide6.

## Features

- **Separate account logs** — create named audit logs, switch between them, and return to older records.
- **Timestamped entries** — record event times separately from when entries were saved, and mark times as reported, estimated, or unknown.
- **Screenshot evidence** — attach images, keep local copies, preview them, and record SHA-256 hashes.
- **Notes and explanations** — keep factual observations separate from interpretation and follow-up.
- **AI comparison notes** — manually add Gemini, ChatGPT, and Grok notes in compact, color-coded cards.
- **Edit history** — edit saved entries and review timestamped before-and-after values, including screenshot additions and removals. Removed screenshot copies are retained.
- **Addenda** — append dated corrections or additional context.
- **Search and sorting** — search records and display events newest or oldest first.
- **Local persistence and backups** — save records to SQLite and export individual logs as ZIP backups.

## Getting started

The current desktop version is configured for Windows. It has been tested with Python 3.14 and PySide6 6.11.2.

Install Python and the application dependency:

```powershell
python -m pip install PySide6
```

From the folder containing the source, start the app:

```powershell
python audit_log.py
```

The included **Open BanShield.bat** launcher currently uses `C:\Python314\pythonw.exe`. If your Python installation is elsewhere, use the command above or update the launcher's Python path.

## Using BanShield

1. Open the app and select an audit log in the **Account / Audit Log** dropdown. Existing records appear in **Original audit log**.
2. Choose **New audit log** to create a separate log for another account. Use **Rename** to change its name.
3. Choose **New entry**, enter a title and factual description, set the event timestamp, and optionally add notes and screenshots.
4. Add any AI comparison notes under the labeled Gemini, ChatGPT, and Grok fields. These are manual notes; BanShield does not contact those services or generate responses.
5. Save the entry. Use **Edit entry** for later changes and **View edit history** to inspect previous values. Use **Add correction or note** for an addendum.
6. Choose **Export backup** to save the currently selected log. Export other logs separately.

## Where records are saved

BanShield stores data beside `audit_log.py`:

```text
log-library.sqlite3             Log names and last selected log
data/                          Original audit log
  audit-log.sqlite3            Entries, notes, addenda, and edit history
  attachments/                 Copied screenshots, including retired copies
account-logs/
  <log-id>/data/                Separate database and attachments for each new log
```

Saved entries remain after closing the app. The app folder must be writable. Screenshot copies are stored alongside the databases rather than inside them.

## Backups and restoration

**Export backup** creates a ZIP containing the selected log's SQLite database, a readable JSON export, and its screenshot copies, including those retained for edit history. It does not back up all account logs at once or include the log library.

To restore an individual ZIP backup:

1. Close BanShield.
2. Make a safety copy of the target log's existing `data` folder.
3. Extract the backup's `data` folder into the target log's directory: the app directory for the original log, or `account-logs/<log-id>/` for a named log. Replace the entire target `data` folder with the restored folder so old SQLite journal files are not mixed with the restored database.
4. Reopen BanShield and select that log.

For a complete backup of every account and its names, close the app and copy `log-library.sqlite3`, `data/`, and `account-logs/` together.

**More > Import browser app backup** accepts JSON backups from the earlier browser version. It imports into the current log and skips existing entry IDs. This is separate from restoring desktop ZIP backups.

## Privacy and record limitations

Records and screenshots can contain sensitive account information. Keep personal databases, attachments, and backup exports out of a public repository. The included `.gitignore` excludes the app's local storage and common backup filenames; review files before publishing.

The desktop app stores records locally and has no built-in cloud sync, account authentication, or encryption. It relies on the computer clock. Its edit history is maintained by the app and can be altered outside it; it is not an immutable or independently verified audit trail. Screenshot hashes help compare file contents but do not establish authenticity or when an event occurred. BanShield does not guarantee legal admissibility or an appeal outcome.
