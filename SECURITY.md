# Security and responsible disclosure

Use GitHub private vulnerability reporting after the repository is published. Do not put exploit details in a public issue.

## Trust boundary

EvidenceForge reads documents you supply. Those documents are data, not instructions. The local backend does not send them anywhere. `--backend openai` sends the claim and the retrieved excerpts to OpenAI. Do not use that mode for material you are not allowed to transmit.

A quote whose character span matches the extracted text only proves that the span exists. It does not prove the verdict is semantically correct, and it does not prove the source is true.

## Fail closed

If the OpenAI call times out, cannot connect, is refused, or comes back incomplete, the command exits with an error and does not write a verdict. A model verdict of `supported` or `contradicted` without a verbatim quote is stored as `insufficient`.

## Secrets and inputs

- Put `OPENAI_API_KEY` in an environment variable or a secret manager. The committed `.env.example` is a placeholder, not a credential.
- Do not open a public issue that contains keys, private documents, or model prompts copied from private data.
- `store=false` is set on OpenAI Responses requests. That is a request flag, not a promise about the provider's retention policy. Read the current OpenAI terms before sending sensitive text.
- This MVP is not a multi-tenant upload service. Do not expose it as a public file-upload endpoint without a separate review.
