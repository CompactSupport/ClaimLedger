# Held-out v0.5

This is a fresh fictional set. It is not part of `benchmark/candidates/`, and it is not a released gold benchmark.

`catalog.json` freezes the documents, claims, and dataset-author reference labels. Those author labels are not human review. `human/initial_blank_sheet.csv` is the immutable blank snapshot. `model_view/` contains the claim and passage only.

`research/ledger.json` is the later record for reviewer submissions, human adjudications, approval, and model contact. The check command does not rebuild it from the catalog. It is bound to `freeze.json`'s `freeze_sha256`. The committed ledger has no adjudications and no model contacts.

One author label stays `contradicted` and is marked `author_label_under_review`: Kiln North firing 18 batches in June does not follow from Kiln North firing 18 batches in May. A different month is not a contradiction. The heuristic may flag that period difference. It does not certify the label.

No evaluation model has a recorded contact with these files. `model_contact_count` in the ledger is 0. `gold_benchmark_released` is false. The inference entry refuses a held-out claim unless the ledger contains a complete human adjudication and one approval bound to this freeze hash, and no earlier contact for that hash.

`entailment_audit.json` is a deterministic heuristic, not a model score and not a certification. A quote can be present while entailment stays `unresolved`. An empty quote on an insufficient label matches the format and leaves the semantics unverified. `verdict_confirmed` stays false.

These files are a fixed internal set. They are in the public repository, so they are not a secret external test. No recorded evaluation-model contact is not the same as a guarantee that every possible model has never seen them.

Regenerate or check the derived files with:

```bash
python scripts/check_heldout_v05.py --check
```
