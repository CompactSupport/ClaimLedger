# Semantic relevance and entailment checklist

An exact, unique quote proves only that the span exists in the extracted document. It does not prove that the span entails the claim, or that a supported or contradicted label is correct.

Use this list before setting `human_reviewed` to true. Do not set that flag automatically.

1. The quote is about the same proposition as the claim: the same number, date, unit, negation, or comparison. A true sentence about a different fact is not evidence for this row.
2. The quote is an exact unique substring of the source document. Record the character span. If the quote occurs twice, choose a longer unique passage or leave the row unreviewed.
3. For `supported`, the quote has to establish the whole claim. A shared word is not enough.
4. For `contradicted`, the quote has to establish that the claim is false. Citing a nearby true sentence that does not address the claim is not a contradiction.
5. For `insufficient`, explain the gap. Absence of a measurement is not automatically a contradiction of a specific value.
6. Check units (`kWh` versus `MWh`), dates, and negation words such as "not" and "excluded".
7. Leave `reviewed_label` blank until a person decides. Do not copy `expected`.
8. Do not treat the reviewer name as proof that the reviewer was independent of the author.
9. A comparison or an arithmetic claim needs every number the inference uses. Those numbers appearing in the document does not mean the compared or summed sentence is itself written there.
10. A repeating schedule and a count "per hour" can disagree at the endpoints of the operating window.
11. A funding statement that something is covered is not automatically a statement that the cost can be charged or reimbursed.
12. Do not infer the label from a case id. In this candidate set, `-1`, `-2`, and `-3` currently encode `supported`, `contradicted`, and `insufficient`.
