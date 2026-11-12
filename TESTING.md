# BanShield pre-upload verification

Test date: November 12, 2026. Local Windows environment with Python 3.14. All test records, captures and images were synthetic and stored in temporary folders. Real account evidence was not used by the stress tests. No paid/live AI calls were made.

## Results

All 16 existing regression scripts passed after updating two obsolete test fixtures to the current policy format and export contents. An additional pagination check passed. Python compilation also passed for every app module.

Covered: local saving and reopening, account isolation/switching, before/after edits, preserved originals, SHA-256/pHash/dHash, metadata stripping and flags, private HAR/email preservation, public-export exclusions, clustering/CSV statistics, old-attachment processing, cancellation, malformed inputs, OCR caching, manual policy validation, strict Pydantic validation, citation/rubric filtering, report integrity, and mocked OpenAI/Gemini output/error paths.

## Bounded stress workload

| Workload | Observed result |
| --- | --- |
| 300 entries, including long text and Unicode; 60 attached images | Saved and reopened successfully |
| 100 edits of a saved entry | All revisions retained |
| 20 additional account logs | Isolated and persistent |
| SQLite integrity check | Passed |
| ZIP backup and extraction into a separate log | 300 entries and 100 revisions restored |
| Public export | 60 submissions; no image duplication |
| Reprocess complete attachments | Skipped; no duplicate submissions |
| 2,000 synthetic visual hash submissions | Clustered in approximately 0.5 seconds |
| Initial timeline load for the 300-entry log | Approximately 1.3 seconds after pagination improvement |

Measurements describe this machine and test data, not guaranteed performance. Comparisons remain pairwise; very large datasets can still take longer. OCR, large images, long network captures and API latency have separate costs.

## Improvements made during verification

- Convert valid hash strings to integers once for repeated Hamming comparisons.
- Compute cluster representatives once per group rather than for every member.
- Load timeline cards in batches of 50, with a Load next 50 entries button. Search still covers the entire log, and clustering totals still cover every current attachment.
- Verify all entries remain accessible and searches reset the visible page correctly.

## Limits

This is a smoke/regression and bounded stress test, not an independent security audit, penetration test, cross-platform certification or exhaustive load test. UI rendering checks used Qt's offscreen platform. Real API availability, provider billing/quota, network behavior and OS differences require an individual setup check. Full backups and manual review remain necessary. No claim about legal admissibility or evidentiary authenticity follows from these results.
