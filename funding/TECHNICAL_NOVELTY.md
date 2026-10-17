# Technical novelty

The distinctive piece that exists today is deterministic provenance: a verdict that cites a source must point at a SHA-256, a page number, and a character span that reproduces the quote exactly. A matching span is not treated as proof that a model's semantic label is correct.

## Implemented

- Exact quote validation and fail-closed behavior when the quote or the provider response is unusable.
- A local substring baseline and one optional OpenAI structured-output backend.

## Not implemented

- Multi-model adjudication.
- A provider other than local and OpenAI.
- A gold benchmark large enough to support a research claim about accuracy.

Those three items are the planned differentiation. They are not current capabilities.
