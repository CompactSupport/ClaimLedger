# Model-visible evaluation view

This directory is the only input an evaluator may read.
Do not open the repository, the audit mapping, the review queue, or the AI annotation files.
inputs.jsonl has one JSON object per line: evaluation_id, claim, passage_id, and passage.
prompt.txt is the instruction.
Copying this directory outside the repository only copies these files.
That copy is not an operating-system sandbox.
The audit mapping committed in the repository is publicly readable.
This view is an internal export. It is not an independent external test set.
No score file belongs here.
