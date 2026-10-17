# Benchmark summary

There is no gold benchmark result. The 60-row candidate fixture is fictional and `synthetic_author_labeled`. A local exact-match run on 2026-10-17 scored 22 of 60 rows, with pooled macro-F1 0.2315. That figure is an engineering smoke result. See [benchmark/BENCHMARK_CARD.md](../benchmark/BENCHMARK_CARD.md).

The only measured evaluation is the smoke fixture described in [benchmark/README.md](../benchmark/README.md). On that fixture the local baseline matches 4 of 6 labels. The test suite expects macro-F1 0.5 under the rule in `claimledger.metrics`. Citation validity on the quotes that run emits is part of the same command. Retrieval recall is null.

An abstain baseline is reported beside it. No second semantic model has been scored.
