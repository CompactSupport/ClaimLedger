# ClaimLedger verification report

Backend: `local`; documents: 1; claims: 4

| Claim | Verdict |
|---|---|
| Project Aurora evaluated 120 samples in March 2026. | **supported** |
| The study used synthetic samples. | **insufficient** |
| The research was conducted in London. | **insufficient** |
| The research team published its results on April 2, 2026. | **supported** |

## c1: Project Aurora evaluated 120 samples in March 2026.

**Verdict:** `supported`

**Reason:** Literal substring match only.

- **aurora.md, page 1, extracted-text chars [51, 102)**: `Project Aurora evaluated 120 samples in March 2026.`

## c2: The study used synthetic samples.

**Verdict:** `insufficient`

**Reason:** No exact textual match. Local mode cannot evaluate paraphrases or negation.

No validated source quote.


## c3: The research was conducted in London.

**Verdict:** `insufficient`

**Reason:** No exact textual match. Local mode cannot evaluate paraphrases or negation.

No validated source quote.


## c4: The research team published its results on April 2, 2026.

**Verdict:** `supported`

**Reason:** Literal substring match only.

- **aurora.md, page 1, extracted-text chars [277, 334)**: `The research team published its results on April 2, 2026.`

---

**Important:** Exact citation spans are mechanically checked against extracted source text. A validated quote does not guarantee that the semantic verdict is correct.
