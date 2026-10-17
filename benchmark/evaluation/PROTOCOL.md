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

Evaluation IDs are drawn from a separate stream, seed `20261019`. The private map from evaluation ID to canonical ID is `benchmark/evaluation/audit/id_mapping.json`. Model outputs can be joined back only with that file.

An agent must not be pointed at the repository. Copy the isolated directory outside the checkout:

```bash
python scripts/export_label_blind_evaluation.py --agent-dir C:\path\outside\claimledger-eval
```

The command refuses a destination inside this repository. The copy contains `inputs.jsonl`, `prompt.txt`, `README.md`, and `BOUNDARY.txt`.

Prompt version: `claimledger.inference_prompt.v1`. No evaluator is configured. Paid inference is off, and no blinded run has been scored.

## Human calibration

`benchmark/evaluation/human_review/` is a 30-case packet for two independent reviewers. It hides author labels and AI notes. The packet includes the pre-review flags, then enough extra rows to reach 10 supported, 10 contradicted, and 10 insufficient cases. Reviewer A and reviewer B get separate empty sheets. The adjudication log is header-only. Nothing in this packet sets `human_reviewed` or releases gold.

The packet's private map is `benchmark/evaluation/audit/calibration_mapping.json`, seed `20261018`.

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

Claims that share a document still share the same passage, so they can be grouped. A reader who also has the repository can hash that passage and recover the author label. Withholding the repository is part of the control. Do not report a score from this export as external-test accuracy.
