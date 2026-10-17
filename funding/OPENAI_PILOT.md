# OpenAI evaluation pilot

This pilot has not been run. No API key is stored here, and no dollar amount has been spent.

## Proposed boundary

- Dataset: the candidate JSONL shards only, after a person approves the run.
- Calls: at most one local-sized request per candidate row. The current set has 108 rows, so the cap is 108 requests.
- Backend flag: `--allow-paid` must be present. The default command does not call the API.
- Storage: `store=false`, as the verifier already requests.
- Budget: the operator must write a numeric currency cap in the approval before any call. No cap has been approved.
- Output: token counts from the API response may be recorded. This file does not invent those counts.

Do not start the pilot from CI.
