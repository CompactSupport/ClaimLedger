# Model-visible evaluation view

This directory is the only input an evaluator may read.
Do not open the repository, the audit mapping, the review queue, or the AI annotation files.
inputs.jsonl has one JSON object per line: evaluation_id, claim, passage_id, and passage.
prompt.txt is the instruction.
Copy this directory somewhere outside the repository before handing it to an agent.
This view is an internal export. It is not an independent external test set.
No score file belongs here.
