# BanShield

A desktop app for tracking account bans, appeals, and supporting evidence with timestamped logs, screenshots, AI comparison notes, and edit history. Built with Python and PySide6.

## Start here for players

BanShield helps you assemble a consistent record; you do not need to calculate hashes, organize every evidence file by hand, or write an analysis prompt. Start with a local log and add evidence as it becomes available. AI analysis, HAR captures, and public datasets are optional. You can use the basic app without an API key.

### First time setup

1. Download the program source from the project repository and extract it into a folder you control. Keep the `app` folder, launchers, `requirements.txt` and `policies` together. Use a local writable folder, not the inside of a ZIP file. Avoid a shared or publicly synced folder for private records.
2. Install Python. In the extracted folder, open a terminal and run `python -m pip install -r requirements.txt`. Wait for installation to finish. Use the same Python installation for installing dependencies and starting BanShield.
3. Run `python app/audit_log.py`. The included Windows launcher has a fixed Python path; if double-clicking it fails, use this terminal command to see the actual error. You do not need administrator privileges to use the app in a writable folder.
4. Choose **New audit log** and name it for the account or case. Confirm that name in the dropdown before adding evidence. Each account has separate saved records.
5. Do the short saving check below once. After that, use the normal evidence routine. Keep a private backup after important additions.

### Five minute check that saving works

Use a separate log named **Setup check** so test submissions do not affect your real account statistics.

1. Create an entry with a recognizable title and attach a harmless test image. Save it, close BanShield, then reopen it. The entry and image should still appear in Setup check.
2. Choose **Edit entry**, change its notes, and save. **View edit history** should show the earlier and later values and a change timestamp.
3. Check that the image shows SHA-256, pHash and dHash values. An image with no EXIF should say that its creation timestamp is unavailable; that is expected, not a failure.
4. Click **Process existing attachments**. Complete images should be skipped. The submission count should stay the same. A missing or changed-file warning needs investigation; do not dismiss it as a successful verification.
5. Create a second test log, switch back, and confirm the first entry is still present. Choose your real account log before continuing.
6. Use **Export backup** and open the ZIP without modifying it. It should contain `data/audit-log.sqlite3`, `audit-log.json`, and your copied image under `data/attachments/`. Keep the ZIP private. A stronger restore check is to extract it into a separate throwaway copy of the program, not over your live evidence folder.

If any check fails, stop relying on that feature until the problem is resolved. Tests performed during development are not a guarantee that a different computer, dependency set, or API account is configured correctly.

### Your normal evidence routine

1. Select the correct account log and choose **New entry**. Write what happened in **Factual description**. Put explanations or suspicions in **Notes and explanation**. Use **Estimated** or **Unknown** when you cannot establish the event time.
2. Attach the original screenshot once. BanShield copies it, computes fingerprints and inspects metadata automatically. Keep the source original too. Use **Process existing attachments** for older images rather than reattaching them and inflating submission counts.
3. For support email, use your mail client's original `.eml` download and **Attach raw email / SMTP headers**. For a portal glitch, follow **HAR / API capture guide**, reproduce the issue while Network capture is running, then attach the saved HAR or JSON response. You do not need either format for every entry.
4. Add corrections using **Edit entry** or a dated addendum. Compare email timing only against an explicitly chosen reference event. Short turnaround is a timing observation, not proof of automation or no human review.
5. Save a private backup after important work. The app saves entries when you press Save; an unfinished edit dialog is not autosaved. Closing the app does not delete saved records.

### What BanShield handles and what you review

| BanShield handles | You still review |
| --- | --- |
| Local record storage, screenshot copies and saved edit history | Correct account, factual accuracy, event time and time zone |
| Image fingerprints, metadata flags and similarity clusters | Whether images actually show the same event or meaning; flags can miss identifiers |
| HAR/email parsing and preservation of original bytes | Whether the capture is relevant, complete, authorized and free of secrets before sharing |
| Cached local OCR and text evidence manifests | OCR mistakes, missing evidence, private text and historical policy applicability |
| Structured output validation, rubric scoring and report hashes | Whether the reasoning and opposing arguments are supported; legal questions need qualified review |

### Optional AI analysis without rebuilding the evidence yourself

1. Prepare the manual policy file once using `policies/roblox_tos_and_policies.template.txt`. Save your completed copy as `policies/roblox_tos_and_policies.txt`. Include all five official texts and their sources/dates. The folder README explains the format. Policies are not downloaded automatically.
2. Open **Text evidence analysis** and choose **Build / update manifest**. BanShield extracts and caches OCR locally and assembles the timeline, email clocks and HTTP summaries. You do not need to upload the same screenshots to an AI for every analysis.
3. Review the policy and manifest tabs. Fix transcription problems or remove private text from the manifest. The manifest editor changes this analysis input, not your original evidence. HAR response bodies are opt-in; leave them unchecked unless necessary and reviewed.
4. To use the API, choose **OpenAI** or **Google / Gemini**. Set `OPENAI_API_KEY` for OpenAI, or `GEMINI_API_KEY` (alternatively `GOOGLE_API_KEY`) for Gemini in the process environment before launching. Enter a JSON Schema-capable model ID available to that provider account. Never put the key in the README, code, evidence text, screenshots or GitHub. API charges and access are separate from BanShield.
5. Check the review confirmation and submit only when ready. Without API access, **Save reviewed bundle** still prepares the text documents for private review. No API request is made just by opening the app or building the manifest.
6. After success, inspect the findings and counter-arguments. Invalid, refused or incomplete responses are rejected rather than treated as completed reports. Scores are rubric priorities, not chances of winning a dispute. Reports and the frozen inputs save in the selected log's `data/analysis/` folder.

### Keep private evidence private

- **Your working folder is private evidence.** BanShield has no built-in password protection or encryption. Use a protected computer account, lock your screen, restrict shared-folder access, and use encrypted storage/backups where appropriate. Anyone able to read the folder can read its records.
- **HAR and email files need special care.** They may contain login cookies, bearer tokens, addresses, IPs, private messages and attachments. Do not post them on GitHub or paste them into chat to troubleshoot. If a live credential is exposed, use the affected service's session/sign-out or credential-revocation controls; deleting the public file alone does not revoke it.
- **Private backup is different from public export.** Export backup includes private originals. Public export omits them by default and strips metadata from deliberately selected derivative images. It does not automatically blur visible names, account handles, faces, emails or QR codes. Redact copies, review the JSON/timestamps and images, and keep originals private.
- **Check what you share.** Private backups can contain complete account records. Review the actual files before sharing them; a redacted screenshot does not make its original or backup private by itself.
- **Share a purpose-specific copy.** For an attorney or other authorized reviewer, use a private transfer method and agree which originals are needed. For a public dataset, use Public export, inspect every included file, and deliberately upload only that reviewed derivative. BanShield does not publish files to GitHub for you.

### Back up the whole workspace when it matters

**Export backup** covers the selected log's evidence database, image/email/HAR originals and private JSON. It does not include every account, the log library, local OCR cache, policy files or the full saved analysis/report folders. For a complete recovery copy, close BanShield and copy the entire program folder—including `log-library.sqlite3`, `data`, `account-logs` and `policies`—to a separate private backup location. Keep more than one dated copy and do not overwrite the only working copy during a restore test.

### Check a saved report's hash

A successful analysis saves `audit_report.json`, the exact policy text, frozen input manifest, and `report_integrity.json`. The main evidence manifest records the same report hash and provenance. To check a report manually, open PowerShell in that run's folder and run:

```powershell
(Get-FileHash -LiteralPath '.\audit_report.json' -Algorithm SHA256).Hash
(Get-Content -LiteralPath '.\report_integrity.json' -Raw | ConvertFrom-Json).report_sha256
```

The values should match ignoring letter case. You can similarly check the policy file against `policy_sha256` and `input_evidence_manifest.json` against `input_manifest_sha256`. Compare the frozen input file, not the post-analysis main manifest. A mismatch means the bytes differ: keep both copies, record what happened, and investigate rather than simply replacing the expected hash. Matching hashes do not certify generation time or authorship; the local clock and hash record are not independently trusted.

### If something does not work

| Symptom | What to do |
| --- | --- |
| Launcher does nothing or closes immediately | Open a terminal in the program folder and run `python app/audit_log.py`; copy the error text after removing personal paths or secrets. The launcher looks for `pythonw` or `pyw` on your PATH. |
| Missing Python module | Run `python -m pip install -r requirements.txt` with the same Python used to launch. `python -m pip check` checks installed dependency compatibility; it is not a full app test. |
| Old entries seem missing | Check the account dropdown and the program folder you launched. Two extracted copies have separate data folders. Do not create replacement evidence or overwrite a database until checking your backups. |
| Changes are not visible | Save the edit, close any older app instance, then reopen the updated copy. Check **View edit history**. |
| Hash mismatch, missing file or processing failure | Preserve the folder and backup. Compare source originals; do not edit the database or modify evidence to make the warning disappear. |
| Metadata, email time or response body says unavailable | The source may not contain it. Keep it unknown; a screenshot, raw JSON or sanitized HAR cannot reconstruct missing transport details. |
| Manual policy rejected | Use the exact `.txt` filename, all five section IDs, official HTTPS URLs, valid collection dates, and filled Content sections. Reload after editing. Never fill missing official clauses with AI-generated text. |
| OCR unavailable | Verify dependencies, try a readable supported image, and inspect the error. Keep unavailable text labeled; review OCR against the original before relying on it. |
| API error, refusal or incomplete response | Check the model ID, API credentials, credits/access and error message. No automatic retry is made. A repeat submission can incur another charge. Never post your API key or private bundle with an error report. |

After updating BanShield, make a private backup, install the updated requirements, and rerun the short saving check in Setup check. Keep the advanced format and evidence notes below for reference; they are not all required for everyday use.

## Features

- **Separate account logs** — create named audit logs, switch between them, and return to older records.
- **Timestamped entries** — record event times separately from when entries were saved, and mark times as reported, estimated, or unknown.
- **Screenshot evidence** — attach images, keep local copies, preview them, and record SHA-256 hashes.
- **Notes and explanations** — keep factual observations separate from interpretation and follow-up.
- **API cross-checks** — generate read-only Gemini or ChatGPT/OpenAI findings from a reviewed evidence bundle. Manual AI-note entry and Grok are not supported.
- **Edit history** — edit saved entries and review timestamped before-and-after values, including screenshot additions and removals. Removed screenshot copies are retained.
- **Addenda** — append dated corrections or additional context.
- **Search and sorting** — search records and display events newest or oldest first.
- **Local persistence and backups** — save records to SQLite and export individual logs as ZIP backups.

## Getting started

The current desktop version is configured for Windows. It has been tested with Python 3.14 and PySide6 6.11.2.

Install Python and the application dependency:

```powershell
python -m pip install -r requirements.txt
```

From the folder containing the source, start the app:

```powershell
python app/audit_log.py
```

Double-click **Setup BanShield.bat** once to install dependencies, then **Open BanShield.bat** to launch. The launcher discovers `pythonw` or `pyw` on Windows instead of requiring a fixed installation path.

## Using BanShield

1. Open the app and select an audit log in the **Account / Audit Log** dropdown. Existing records appear in **Original audit log**.
2. Choose **New audit log** to create a separate log for another account. Use **Rename** to change its name.
3. Choose **New entry**, enter a title and factual description, set the event timestamp, and optionally add notes and screenshots.
4. For optional AI cross-checks, open **API cross-checks · Gemini / ChatGPT**, configure the selected provider, and run a reviewed analysis. There are no manual AI-note fields. Existing manual notes are retained as read-only legacy reference.
5. Save the entry. Use **Edit entry** for later changes and **View edit history** to inspect previous values. Use **Add correction or note** for an addendum.
6. Choose **Export backup** to save the currently selected log. Export other logs separately.

## Where records are saved

BanShield stores data in the main folder beside the launchers (outside `app/`):

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


## Photo fingerprints

New screenshot attachments receive SHA-256, pHash, and dHash fingerprints. SHA-256 compares exact file bytes. The 64-bit perceptual hashes help compare visual similarity and can match different files; they do not replace SHA-256 or establish authenticity, capture time, ownership, or admissibility.

BanShield uses ImageHash pHash with hash size 8 and high-frequency factor 4, and horizontal dHash with hash size 8. It reads the first frame, applies EXIF orientation to the in-memory image, and converts it to RGB. Original file bytes remain unchanged. The algorithm settings, package versions, and computation timestamp are saved with each attachment and included in database and JSON backups. Computation time is separate from the event and attachment timestamps. Older attachments are labeled when these fingerprints were not recorded. Similarity clustering uses both hashes with the documented Hamming-distance threshold; it does not establish identical meaning or shared origin.

## Metadata inspection and public datasets

New attachments are inspected for embedded creation clocks and metadata field names. Recognized sensitive fields such as GPS, camera/device details, artist/owner, comments, and XMP are flagged on the timeline. These flags are heuristic; absence of a flag is not a privacy guarantee. Unrecognized or nested metadata may exist in originals. The app retains original bytes privately.

The displayed image creation timestamp is recorded separately from the entry's event timestamp. An embedded timestamp is unverified, may be edited, and may lack a time zone; BanShield preserves that uncertainty rather than assuming UTC. Source filesystem creation and modification times are recorded separately where available and can reflect a copy or download. Older attachments are not automatically inspected retroactively.

Use **Public export** for a reviewable public derivative, not **Export backup**. The public dataset defaults to generic event IDs, event times, certainty, and attachment counts. It omits account names, free text, AI notes, original filenames and hashes, private metadata, edit history, and original screenshots. Review identifying event times in the JSON preview before saving.

Optional images must be redacted and reviewed before selection. BanShield applies EXIF orientation and re-encodes a new RGB pixel buffer as PNG without original EXIF, XMP, text chunks, ICC profiles, or source filenames. Original files remain unchanged. Visible names, emails, faces, QR codes, account handles and other identifiers in the pixels are **not automatically redacted**. Selected derivatives receive new SHA-256 hashes. The review confirmation is required; the app saves a ZIP locally and never publishes it to GitHub.


## Visual clusters and CSV statistics

The timeline compares current attachments whenever records are loaded. Public export adds `submissions.csv`, `summary.csv`, and `summary.json` alongside the reviewed dataset. Each current attachment counts as one submission; retired screenshots are excluded. CSV rows include `cluster_id`, cluster size, hash availability, distances to a representative, and the size of the identical perceptual-hash group. Private hash values and source identifiers are omitted from public rows.

Matching requires **both** 64-bit pHash and dHash Hamming distances to be at most **6**, using identical recorded hash-method settings. Groups are connected components: A can match B and B can match C even if A does not directly match C. A representative distance can therefore exceed 6. This is a similarity heuristic, not proof of shared origin. Hashes that are missing or lack a recorded method remain unassigned and are counted separately.

The summary includes total entries, total submissions, hashable and unclustered submissions, unique visual clusters, and exact file-byte duplicate counts. **Exact pattern match rate** is `(hashable submissions − distinct identical pHash/dHash pairs within each hash method) / hashable submissions`. It measures duplicate submissions beyond the first, not all members of repeated groups. No valid hashes produces a null/N/A rate. Identical perceptual hashes do not guarantee identical images; byte equality is tracked separately using SHA-256.

Cluster IDs are clean dataset-local labels such as `cluster-0001`, deterministic for the same membership. Adding or removing images can renumber them. Statistics apply to the selected log. Default exports refer to its private original attachments; optional reviewed public images are separate derivatives and do not silently replace the population being counted. Editing the JSON preview can change the exported statistics, so review them consistently.


## Process existing attachments

Click **Process existing attachments** below the account selector to fill in missing pHash, dHash, method details, computation timestamps, and metadata inspection for current attachments in the selected log. The app verifies each saved copy against its recorded SHA-256 before processing it. Missing files, changed bytes, and incompatible existing fingerprints are reported and left unchanged. Already complete attachments are skipped. Repeating the operation does not create duplicate submissions.

Original bytes, entry timestamps, screenshot IDs, and submission counts remain unchanged. For old copies, original source filesystem creation times cannot be recovered; metadata inspection explicitly records that limitation. Embedded image creation clocks are extracted when available. Processing outcomes and timestamps are retained in a private database audit table and JSON backups; public exports omit that audit table. Cancel stops between attachments and keeps completed work. Retired attachments are excluded from this action.

## HAR and raw API response evidence

Use **HAR / API capture guide** near the top of the app for capture instructions. Start your browser's Network capture before reproducing the problem, then export a HAR with response content when supported. Attach the file to an existing event using **Attach HAR / JSON response**. You can also attach a saved JSON API response body. BanShield does not automate browser capture or contact the portal.

The private viewer lists requests, HTTP status codes, client request start times, response headers including server `Date` when present, durations, and response bodies. Base64 bodies are decoded for text viewing; original file bytes remain intact. Missing bodies remain marked unavailable; status 0 is not treated as HTTP success. Raw JSON alone cannot establish transport status or server time, so those fields remain unknown. Imported capture times and SHA-256 hashes are recorded separately. Server and client clocks are unverified and do not replace manually recorded event times.

Captures can include session credentials, cookies, private URLs, and account information. They stay in the selected log's `data/network/` folder and are included in **private backups only**. Public exports omit capture files and parsed content. Network evidence does not count as a visual submission or participate in image clustering. Captures are limited to 100 MB and 50,000 requests; the text viewer previews up to 1,000,000 characters per request. Originals and full parsed content remain in private storage.


## Original emails and SMTP headers

Use **Attach raw email / SMTP headers** on an entry. Prefer the mail client's Download original / Save as `.eml` option to a screenshot. Import the original file unchanged, or paste complete SMTP headers as an explicitly labeled user-supplied derivative. Email bodies and attachments are never executed or rendered as HTML.

The private viewer retains Date headers, all Received hops in file order, DKIM-Signature presence, and reported Authentication-Results. Parseable clocks with known offsets are normalized to UTC; missing zones and malformed timestamps remain unknown. BanShield does not verify DKIM, trust Authentication-Results automatically, or establish a trusted Received boundary. A signature's presence is not authentication. Date is an origination clock, not definitive transport time (RFC 5322); DKIM semantics are defined by RFC 6376.

Select an email timestamp and a separate logged event as the reference to calculate a signed elapsed interval in seconds. Negative intervals are flagged. Under-three-hour intervals are descriptive of the selected clocks only, not proof of automation or absence of human review. Save a comparison as an addendum to retain its selected sources, event ID, capture ID, timestamps and uncertainty. No “instant automation” verdict is generated.

Email originals and pasted headers are SHA-256 hashed, stored in the selected log's private network-evidence folder, included in private backups, and excluded from public dataset exports. They may contain private addresses, IPs, bodies and attachments. The size limit is 100 MB.

## Text-only evidence analysis backend

Open **Text evidence analysis** near the top of BanShield. **Build / update manifest** runs local RapidOCR on current screenshot copies and caches machine-extracted text by SHA-256. OCR errors or missing files are explicitly marked. It also gathers timeline records, selected factual/user notes, addenda, email Date/Received clocks, DKIM verification limitations, and HAR status/timing summaries. Prior AI notes are excluded. Credential-bearing HAR headers and URLs are omitted; raw response bodies are opt-in because they may contain secrets. Machine OCR is not a verified transcription.

The evidence bundle contains text only: `evidence_manifest.json` and `roblox_tos_and_policies.txt`. No screenshot bytes, original email files, or raw HAR files are submitted. OCR, notes and response bodies can still expose personal information: review both documents and redact the manifest before sending (edit the manual policy file if needed, then reload). Saved bundles and model outputs are private, not public dataset exports.

Policy text must now be collected manually. BanShield never downloads policies. Open the official links in `policies/roblox_tos_and_policies.template.txt`, copy the full text into its five sections, record the actual retrieval dates and known effective dates, then save a UTF-8 plain text copy as **`policies/roblox_tos_and_policies.txt`**. Each section requires `Source:`, `Retrieved: YYYY-MM-DD`, `Effective: YYYY-MM-DD` (or `unknown`), and `Content:` followed by the policy text. All five IDs — `[terms]`, `[standards]`, `[appeals]`, `[moderation]`, `[support]` — are required exactly once.

The analysis dialog reads that exact file when opened. **Open policy folder** shows its location; **Reload policy file** reads changes; **Import manual policy** validates and copies an externally prepared `.txt` file into the folder. The policy tab is read-only; edit the local file and reload. Missing files, invalid dates, non-official source URL domains, duplicate/missing sections, and unfilled templates block analysis. Format checks do not authenticate the text or ensure its completeness. A policy changed on disk must be reloaded and reviewed before API submission. PDF, raw HTML and DOCX are not accepted; extract/copy their text into the template manually. Current policies may differ from those applicable at an event's date or in a user's jurisdiction.

Install dependencies from `requirements.txt`. Set `OPENAI_API_KEY` in the process environment before launching (do not put it in source, a public repository, or the evidence bundle). Enter a Structured Outputs-capable model ID available to your API account; optionally set `BANSHIELD_OPENAI_MODEL`. The app does not embed a default model or API key. API access and billing are separate from this application.

After reviewing both documents, explicitly authorize submission and click **Send reviewed text for structured analysis**. A single Responses API request carries both documents as text and uses `text.format` JSON Schema with `strict: true` and `store: false`. No tools or image inputs are sent. The application does not automatically retry requests or silently truncate large bundles; it rejects input above 600,000 characters, which is not a guarantee that a selected model's context limit will fit. Provider retention policies still apply; `store: false` is not a promise of zero retention.

Results distinguish documented facts, possible policy inconsistencies and insufficient evidence, with evidence and policy references, limitations, questions and missing evidence. Local JSON Schema validation and reference checks reject malformed or unsupported findings. Refusal and incomplete responses are rejected. Schema compliance does not guarantee factual correctness. Timing alone cannot prove automated rejection or no human review; legal breach, authenticity and court admissibility are not established by these findings.

Successful results are saved under the selected log's `data/analysis/<run-id>/` with exact reviewed input texts, their hashes, model/response identifiers, `findings.json` and `review_draft.md`. **Save reviewed bundle** exports a private review folder and schema even without API access. The Markdown is a draft for human or attorney review, not a certified legal report. Analysis cache and report folders should be copied separately if preserving full analysis runs; per-log evidence ZIP backups do not include them.


Official references: https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses and the source URLs inside `roblox_tos_and_policies.txt`.

## Evidence-review scoring rubric

Structured findings now require a rubric band, rationale, verbatim policy excerpt, and verbatim evidence excerpt. Scores are fixed application-assigned values, not model-guessed percentages or calibrated probabilities:

| Band | Fixed score | Review criteria |
| --- | --- | --- |
| Direct contradiction (90–100 band) | 90/100 | An applicable explicit policy commitment conflicts with documented conduct; exceptions and counterevidence must be addressed. |
| Procedural failure (70–89 band) | 70/100 | Evidence supports incompatible directions or an appeal loop; bad faith and automation are not assumed. |
| Discretionary gray area (40–69 band) | 40/100 | Relevant evidence and policy exist, but discretion, applicability or ambiguity requires deeper interpretation. |
| Weak or unsupported (below 40) | 0/100 | Missing or unlinked evidence, missing policy support or unsupported assertions. |

The application checks literal excerpts of at least 20 characters against cited evidence and policy sections. A failure downgrades the finding to weak/unsupported. These checks establish textual linkage only: they do not establish that the quote proves the conclusion, that OCR is accurate, that a source is authentic, or that policy exceptions do not apply. Rubric bands and substantive reasoning still require human verification. A rapid email response or a zero-rule notice alone does not prove a policy contradiction, automation, bad faith, or absence of human intervention.

The default findings view and Markdown review report show scores of at least 40. All findings, requested bands, adjusted scores, rationale, and downgrade reasons remain in private findings.json for auditability. The unfiltered model summary is retained in JSON rather than copied into the filtered report. Scores do not represent legal success likelihood, admissibility, or a lawyer's assessment. New analyses use this rubric; previously saved reports are not rewritten.

## Pydantic validation

`analysis_models.py` defines strict Pydantic v2 models for API findings and application-scored findings. The API JSON Schema is generated from those models. Missing fields, extra fields, invalid rubric bands, and wrong types are rejected without coercion. Raw JSON is parsed and validated by Pydantic, followed by the existing JSON Schema and citation checks. A second Pydantic pass verifies the deterministic rubric score and report-inclusion threshold after scoring. Refusals, incomplete responses, and transport failures still use the existing error paths; Pydantic does not guarantee factual accuracy or successful API calls.


## Help Center policies and EU/DSA review

The manual roblox_tos_and_policies.txt baseline now requires Content Moderation on Roblox as [moderation], in addition to [terms], [standards], [appeals] and [support]. Copy the full official pages using the new template. Preserve the unlisted-violation Support Form pathway, ordinary appeal requirements, six-month EU window and certified out-of-court dispute settlement language, together with qualifications. Analysis instructions ask for these clauses explicitly and require evidence of EU applicability before applying EU-specific provisions. Help Center text may be relevant evidence of representations, but whether a provision is legally binding or actionable is not automatically determined by this app. Existing policy files are not silently rewritten or treated as complete.

## Counter Argument and Defense Shield

Each new TOSFinding requires `anticipated_corporate_defense` and `rebuttal`. These fields are required nonempty strings in the generated API schema and strict Pydantic models, shown in findings JSON and the eligible findings in the Markdown review draft. The prompt asks for the strongest plausible opposing interpretation and a record-based response, including exceptions, eligibility, discretion, deadlines and counterevidence. It prohibits invented section numbers, human-review promises, legal rules and conclusions that short turnaround proves automation or deception. Unsupported arguments must state missing information rather than invent a position. Defense language is hypothetical, not a corporate admission; rebuttals are issues for human/attorney review, not settled legal conclusions. Existing saved analyses are preserved; rerun analysis to populate the new required fields. There is no new API submission without explicit review.

## Report hashes and analysis provenance

Successful analyses save `audit_report.json` plus an identical `findings.json` compatibility copy. SHA-256 is computed from the exact saved report bytes. `report_integrity.json` and `evidence_manifest.json` record that hash, the generation/recording timestamps, model and response ID, policy-text SHA-256 and frozen input-manifest SHA-256. `input_evidence_manifest.json` preserves the exact pre-analysis UTF-8 serialization used for its input hash, and the saved policy text preserves its original UTF-8 bytes/newlines. The report does not contain its own hash; post-analysis manifest records avoid circular hashing.

A per-log `analysis_runs` SQLite index retains these records, and later manifest builds include them. The selected log's `data/evidence_manifest.json` is the latest analyzed manifest plus report provenance records, not an automatically updated snapshot of every future edit. Reports are stored under `data/analysis/<run-id>/`. Re-exporting a completed reviewed bundle includes its report hashes and frozen input. Existing reports are not retroactively hashed. Local timestamps and hashes do not independently prove generation time, authorship or tamper resistance if both records and files can be altered. Preserve report bundles and their recorded hashes separately when needed.


## Google Gemini as an alternative provider

In **Text evidence analysis**, choose **Google / Gemini** in the Provider dropdown. Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in the environment of the process launching BanShield and enter a model ID your Google API account can access with JSON Schema output support. `GEMINI_API_KEY` takes precedence if both Google key variables are set. You can set `BANSHIELD_GEMINI_MODEL` to prefill the model; OpenAI retains its separate `BANSHIELD_OPENAI_MODEL` setting. No key is written into bundles, report metadata, the database or source code.

For a temporary Windows PowerShell session, the following prompts without displaying your key or putting the literal key in command history. Run it in the program folder, then close the app before clearing the key:

```powershell
$geminiSecret = Read-Host 'Gemini API key' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $geminiSecret).Password
python app/audit_log.py
Remove-Item Env:\GEMINI_API_KEY
Remove-Variable geminiSecret
```

Choose the provider, build/review the same policy and manifest text, and explicitly authorize submission. Changing providers or model IDs clears the confirmation. The app remembers each provider's model field while the window is open. It never switches providers automatically on error, so a failed OpenAI call does not send evidence to Google without your choice and renewed review. Costs, quota, retention and data-use terms depend on the selected provider/account; review them before submitting private evidence.

Gemini requests use its generateContent REST endpoint, a system instruction, text-only content, application/json response MIME type and a generated JSON Schema. Credentials are sent in the x-goog-api-key header, not the URL. Both providers use the same strict Pydantic validation, citation checks, rubric, defense/rebuttal fields, filtering and report-integrity records. Provider, requested model and returned model version when available are saved with results. Blocked, empty, unexpected or incomplete Gemini output is rejected. There are no automatic retries or cross-provider fallback. Live access still depends on model availability, schema support, key and quota.



## Where to find things

```text
Open BanShield.bat     Launch the desktop app
Setup BanShield.bat    Install dependencies for first-time setup or updates
START HERE.txt        Short beginner instructions
README.md             Full guide
requirements.txt      Dependency list
app/                  All Python program modules
policies/             Policy templates, instructions and manually supplied text
data/                 Private original-log evidence and analysis outputs
account-logs/         Private additional account logs
log-library.sqlite3   Private log names and last selected log
```

Keep the launchers and folders together. Use **Open BanShield.bat** for normal startup; you do not need to open the Python files. Saved evidence lives in the main folder, outside `app/`. See the backup instructions before moving the installation to another computer.


## Large timelines and reliability

See TESTING.md for verification scope and limitations. Large timelines render 50 entries initially; use **Load next 50 entries** to see more. Search still checks the whole selected log and cluster statistics still cover all current attachments. Local tests passed on the documented Windows environment; live provider API access and independent security auditing are outside those results.


## API-only cross-checks

The entry form no longer has editable Gemini, ChatGPT or Grok note fields. Cross-checks are generated only by the selected Gemini or OpenAI API through the reviewed analysis workflow; Grok is not supported. In the analysis window, choose Gemini or ChatGPT/OpenAI, configure its environment key and model, build and review the evidence bundle and manual policy baseline, and explicitly authorize sending. The send button is disabled while the selected provider has no configured key. A configured key is not a guarantee of valid credentials, model access, credits or quota.

Eligible findings from successfully saved, indexed reports appear on entries referenced by the finding's evidence IDs. These cards are read-only and show provider, model, generation time and rubric score. The app verifies the saved report against its indexed SHA-256 and validates the scored findings before displaying them. Modified/missing reports, unsupported providers and below-threshold findings are not presented as cross-check cards. Saved findings describe an analysis snapshot and may predate current edits; rerun after changing evidence. Closing the analysis window refreshes the timeline. Detailed findings and full reports remain private.

Previously entered manual notes are preserved behind **View legacy manual notes (not API output)** and in private backups/edit history. Editing an entry does not clear them. They cannot be added or modified from the current form and are excluded from the model evidence manifest. Ordinary factual notes and explanations remain editable. Existing saved API results remain readable without making another API call. ChatGPT/OpenAI API access is separate from a ChatGPT subscription.
