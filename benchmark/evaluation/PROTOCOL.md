# Label-blind evaluation protocol

Protocol version: `claimledger.evaluation_export.v1`

This export prepares an internal semantic-model view of the 108-row candidate set. It does not replace the canonical files, and it does not create an independent external test set.

## What stays in the canonical set

`benchmark/candidates/` keeps the original case IDs, author labels, empty reviewed labels, source hashes, and AI second-opinion files. The case-id suffix still encodes the author label there. That is intentional. Earlier smoke runs refer to those IDs.

## What a model may see

`benchmark/evaluation/isolated/` is the audited copy of the model view:

- opaque `ev-` evaluation IDs that do not use the `-1`, `-2`, `-3` suffix rule
- one global shuffle of all 108 claims, seed `20261017`, using CPython `random.Random`
- each input contains the claim and the source passage only
- the leading `# Fictional scenario NNN` heading is removed because that number is the document number

Evaluation IDs are drawn from a separate stream, seed `20261019`. The join from evaluation ID to canonical ID is `benchmark/evaluation/audit/id_mapping.json`. That file is committed in this public repository. It is publicly readable. It is not access-controlled, and it is not a private secret. Model-visible inputs omit it; anyone with the repository can still open it.

An agent should not be pointed at the repository. The export command can copy the isolated directory outside the checkout:

```bash
python scripts/export_label_blind_evaluation.py --agent-dir C:\path\outside\claimledger-eval
```

The command refuses a destination inside this repository. The copy contains `inputs.jsonl`, `prompt.txt`, `README.md`, and `BOUNDARY.txt`. The copy is not an operating-system sandbox: it does not hide the repository, drop privileges, or clear credentials. A process that can open other paths can still read the checkout and the audit mapping.

Prompt version: `claimledger.inference_prompt.v1`. No evaluator is configured. Paid inference is off, and no blinded run has been scored.

## Human calibration

`benchmark/evaluation/human_review/` is a 30-case packet for two independent reviewers. It hides author labels and AI notes. The packet includes the pre-review flags, then enough extra rows to reach 10 supported, 10 contradicted, and 10 insufficient cases. Reviewer A and reviewer B get separate empty sheets. The adjudication log is header-only. Nothing in this packet sets `human_reviewed` or releases gold.

The packet's join file is `benchmark/evaluation/audit/calibration_mapping.json`, seed `20261018`. That file is also committed and publicly readable.

Reviewer sheets are validated by `scripts/validate_calibration.py`. The committed sheets are empty, so the agreement report has no pairs and Cohen's kappa is null. A valid pair needs two different human reviewer ids, timezone-aware timestamps, a label from the three classes, and an evidence quote that matches a character span of the packet passage. An AI identity is rejected and is not counted as human review. Disagreements stay unresolved until a person adjudicates them.

An adjudication can be planned for `review_queue.csv` only when both of these are true. Two distinct validated human submissions exist for that case, and the approval record's decision is `approved_for_queue_import`. The approval must name the dataset version and the SHA-256 of the exact adjudication artifact. The import checks canonical id, claim text, document hash, passage hash, reviewer ids, labels, timestamps, and the adjudicated evidence span. A reviewer name does not prove a real-world identity or independence. A syntactically valid approval of a fabricated adjudication is refused. Writing the queue needs a second decision, `approved_queue_write`, bound to the same digest and dataset version. The validation command does not write the queue. Neither decision releases a gold benchmark.

## Controlled semantic pilot

`claimledger.semantic_pilot` prepares one evaluation record per invocation, in a directory outside the repository, with credential environment variables removed. That is not an operating-system sandbox. The harness checks the model JSON, the evaluation id, and whether a quote is an exact substring of the passage it wrote. Scoring requires a declared subset and rejects duplicate, missing, and unknown ids. Predictions stay separate from human-reviewed labels.

`scripts/run_semantic_pilot.py --check` parses its arguments and runs those checks offline with a mock. The command exits nonzero when a check fails. Its passing output is a gate result, not a semantic-model score. A test may also run a subprocess command in the stripped workspace. That command is not model execution and it is not an operating-system sandbox.

Codex, Gemini, or Antigravity starts only after authentication and subscription billing have both been verified, and only for one record outside the repository. API-key billing is not a fallback. A Codex command passes `-s read-only` and does not use the desktop config's default sandbox. `real_model_execution` is true only for that model subprocess. An in-process mock, and any other subprocess, stays false. The mock gate does not make a paid model call. One recorded ChatGPT-subscription run is in `semantic_pilot/codex_subscription_run.json`. It is an internal comparison, not an external test.

## Result classes

| Class | Where it stands |
| --- | --- |
| Synthetic author-label smoke | Local exact-match scores on the canonical queue |
| AI second opinion | `benchmark/candidates/ai_second_opinion/` |
| Human-reviewed development | No decisions recorded |
| Internal label-blinded test | Export exists; no model score |
| Independent external test | Not available |

Regenerate or check the files with:

```bash
python scripts/export_label_blind_evaluation.py --check
```

## Residual leakage

Claims that share a document still share the same passage, so they can be grouped. The audit mapping is in the public repository, so a reader of this checkout can join every evaluation ID back to its author label. Copying the model view elsewhere does not remove that public file. Do not report a score from this export as external-test accuracy.
