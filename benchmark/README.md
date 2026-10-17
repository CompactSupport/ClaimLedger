# Evaluation fixtures

`examples/eval.jsonl` is a **smoke fixture**, not a gold benchmark.

| Field | Measured value |
| --- | --- |
| Rows | 6 |
| Label origin | `synthetic_author_labeled` |
| Human-verified gold | No |
| Model-generated labels | No |
| Supported / contradicted / insufficient rows | 3 / 2 / 1 |

The local baseline currently matches 4 of the 6 labels. Both misses are the contradicted rows, which it labels `insufficient`. See [known_failures.md](known_failures.md).

## Command

```bash
python -m claimledger evaluate --dataset examples/eval.jsonl --out output/eval.json
```

The JSON includes macro-F1, per-class precision and recall, abstention rate, citation validity, latency, and token use for the selected backend. It also scores an abstain baseline that always returns `insufficient` and does not read a model. Retrieval recall is `null` because these rows do not name a relevant evidence unit.

## Metric rule

Macro-F1 is the unweighted mean of the three class F1 scores. A class with gold rows but no predictions has recall 0, precision `null`, and F1 0, and it stays in the average. The checked-in test expects macro-F1 **0.5** and abstention **0.5** for the local backend on this fixture. That is a regression check, not a claim about research quality.

Candidate rows live in [candidates/README.md](candidates/README.md). They are fictional and author-labeled. They are not gold.

## Not in this release

A gold set of at least 100 original or permissively licensed examples, with human review before any model-written label is treated as gold, is still future work. Do not fill it with unlabeled synthetic text and call the result gold.
