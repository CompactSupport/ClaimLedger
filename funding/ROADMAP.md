# Roadmap

## Done in 0.2.0

Provenance checks, offline smoke metrics, local and OpenAI verifiers, and the public-release hygiene in the changelog.

## Next, in order

1. Collect at least 100 original or permissively licensed examples, labeled by a person before they are treated as gold. Include supported, contradicted, insufficient, numeric, negation, missing-citation, and conflicting-document cases.
2. Add one more offline baseline only if it is deterministic and tested. Do not add a paid baseline without approval.
3. Add another model provider behind `ClaimVerifier` without making it the default.

## Later

Numeric and date checks that abstain when the unit is ambiguous, optional cost logging from user-supplied rates, and a thin local UI. No hosted dashboard is planned for this stage.
