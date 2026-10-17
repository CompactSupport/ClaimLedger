# Known local-baseline failures

These two smoke rows are expected misses. The source says the study did not use synthetic samples and that two reviewers checked each sample. The local verifier only detects an exact substring, so it abstains.

| Claim | Expected | Local actual |
| --- | --- | --- |
| The study used synthetic samples. | contradicted | insufficient |
| Three independent reviewers checked each sample. | contradicted | insufficient |

An OpenAI run might label them differently. This repository does not record a paid run of that backend, so no semantic score is published for it.
