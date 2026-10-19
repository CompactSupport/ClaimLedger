# Held-out v0.5

This is a fresh fictional set. It is not part of `benchmark/candidates/`, and it is not a released gold benchmark.

`catalog.json` freezes the documents, claims, and dataset-author reference labels. Those author labels are not human review. `human/adjudication_sheet.csv` is frozen blank. `model_view/` contains the claim and passage only.

No evaluation model has been given these files. `freeze.json` records `model_contact_count` 0. Contact stays closed until a person completes the adjudication sheet and a separate model-release record allows the first run.

`entailment_audit.json` is a deterministic check, not a model score. A quote can be present while entailment stays `unresolved`. Presence is not entailment.

Regenerate or check the derived files with:

```bash
python scripts/check_heldout_v05.py --check
```
