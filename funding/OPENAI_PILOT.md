# OpenAI evaluation pilot

This pilot has not been run. No API key is stored here, and no dollar amount has been spent.

## Caps that are not a spending ceiling

The current candidate set has 108 rows, 36 documents, and 5 shards. A cap of 108 logical cases does not guarantee a dollar ceiling: retries, longer prompts, and price changes can spend more. The planner therefore uses a conservative allowance of 4,000 input tokens and 800 output tokens for every allowed HTTP attempt.

- Logical case cap: 108.
- Retry policy: configurable, default 2 retries, so at most 3 HTTP attempts per case.
- HTTP attempt cap at that default: 324.
- Proposed preflight budget: 25 USD. This number is a planning cap, not an approved spend and not a measurement.
- Prices must be supplied by the operator for the preflight. This repository does not assume a current provider price.
- Before any future call, set a separate budget on the provider account. The local estimate cannot enforce that account limit.

## Confirmation

`claimledger.paid_pilot.execute_pilot` refuses to run without explicit confirmation. Even with confirmation, this revision raises an error and does not contact the API. Results are intended to be appended as JSONL so a later approved runner can resume completed case IDs.

Do not start the pilot from CI.
