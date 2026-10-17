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

Copying an adjudicated label into `review_queue.csv` requires an approval record whose decision is `approved_for_queue_import`, with an approver, a timestamp, and an approval id. The validation command does not write that queue. An approved plan alone does not release a gold benchmark.

## Controlled semantic pilot

`claimledger.semantic_pilot` prepares one evaluation record per invocation, in a directory outside the repository, with credential environment variables removed. That is not an operating-system sandbox. The harness checks the model JSON, the evaluation id, and whether a quote is an exact substring of the passage it wrote. Scoring requires a declared subset and rejects duplicate, missing, and unknown ids. Predictions stay separate from human-reviewed labels.

Codex runs only after authentication and subscription billing have both been verified. API-key billing is not a fallback. Real Codex execution is disabled in this revision. Tests use a mock runner only.

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
