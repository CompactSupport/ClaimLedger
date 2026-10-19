"""Quote presence and entailment stay separate. No model is called."""

from claimledger.entailment import audit_entailment, label_assessment

PASSAGE = (
    "The quay office counted 40 oil lanterns and 12 electric lanterns on 2 June 2026. "
    "The oil lanterns were tagged for repair. The ledger does not give their purchase price.\n"
)


def test_verbatim_quote_supports_the_claim():
    audit = audit_entailment(
        "The oil lanterns were tagged for repair.",
        "The oil lanterns were tagged for repair.",
        PASSAGE,
    )
    assert audit["quote_present"] is True
    assert audit["entailment"] == "supports"
    assessment = label_assessment(audit, "supported")
    assert assessment["heuristic_suggestion"] == "claim_verbatim_in_quote"
    assert assessment["verdict_confirmed"] is False
    assert assessment["semantics_verified"] is False


def test_a_true_sentence_can_be_present_without_entailing_the_claim():
    audit = audit_entailment(
        "The oil lanterns cost 40 dollars.",
        "The quay office counted 40 oil lanterns and 12 electric lanterns on 2 June 2026.",
        PASSAGE,
    )
    assert audit["quote_present"] is True
    assert audit["entailment"] == "unresolved"
    assert audit["rule"] == "same_number_different_unit"
    assert label_assessment(audit, "supported")["verdict_confirmed"] is False


def test_a_clock_time_does_not_entail_a_dollar_amount():
    passage = "Lock Seven opened at 09:40. The notice says the lock closes at 17:00.\n"
    audit = audit_entailment("The lock fee is 17 dollars.", "The notice says the lock closes at 17:00.", passage)
    assert audit["quote_present"] is True
    assert audit["entailment"] == "unresolved"


def test_a_different_month_is_not_a_contradiction():
    passage = "Kiln North fired 18 batches in May 2026. Kiln South fired 18 batches in June 2026.\n"
    audit = audit_entailment(
        "Kiln North fired 18 batches in June 2026.",
        "Kiln North fired 18 batches in May 2026.",
        passage,
    )
    assert audit["quote_present"] is True
    assert audit["entailment"] == "unresolved"
    assert audit["rule"] == "different_period_not_exclusive"
    assert audit["verdict_confirmed"] is False
    assessment = label_assessment(audit, "contradicted")
    assert assessment["heuristic_suggestion"] == "different_period_not_exclusive"
    assert assessment["verdict_confirmed"] is False


def test_a_different_entity_in_the_same_month_is_not_a_contradiction():
    passage = "Kiln North fired 18 batches in May 2026. Kiln South fired 18 batches in June 2026.\n"
    audit = audit_entailment(
        "Kiln North fired 18 batches in June 2026.",
        "Kiln South fired 18 batches in June 2026.",
        passage,
    )
    assert audit["quote_present"] is True
    assert audit["entailment"] == "unresolved"
    assert audit["rule"] == "presence_is_not_entailment"
    assert audit["verdict_confirmed"] is False


def test_exclusion_refutes_an_inclusion_claim():
    passage = "The sample used only plant dye. No mineral dye was added.\n"
    audit = audit_entailment(
        "The sample included mineral dye.",
        "No mineral dye was added.",
        passage,
    )
    assert audit["quote_present"] is True
    assert audit["entailment"] == "refutes"
    assert audit["rule"] == "exclusion_conflict"
    assert audit["verdict_confirmed"] is False


def test_less_than_uses_the_two_measures():
    passage = "Plot A yielded 6 kilograms. Plot B yielded 9 kilograms.\n"
    audit = audit_entailment(
        "Plot A is less than Plot B.",
        "Plot A yielded 6 kilograms. Plot B yielded 9 kilograms.",
        passage,
    )
    assert audit["entailment"] == "supports"
    assert audit["rule"] == "less_than_measures"


def test_missing_quote_is_not_entailment():
    audit = audit_entailment("The ferry carried 40 passengers.", "", "The log gives no passenger count.\n")
    assert audit["quote_present"] is False
    assert audit["entailment"] == "not_applicable"
    assessment = label_assessment(audit, "insufficient")
    assert assessment["format_ok"] is True
    assert assessment["semantics_verified"] is False
    assert assessment["verdict_confirmed"] is False
    absent = audit_entailment("The ferry carried 40 passengers.", "40 passengers", "The log gives no passenger count.\n")
    assert absent["rule"] == "quote_absent"
    assert label_assessment(absent, "supported")["verdict_confirmed"] is False
