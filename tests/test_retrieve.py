from evidenceforge.models import EvidenceUnit
from evidenceforge.retrieve import retrieve, tokenize


def _unit(unit_id: str, text: str) -> EvidenceUnit:
    return EvidenceUnit(unit_id, "notes.md", "a" * 64, 1, 0, len(text), text)


def test_top_k_recalls_rare_token_among_distractors():
    units = [
        _unit(f"d{i:02d}", f"The study sample note {i} remains archived.")
        for i in range(12)
    ]
    units.append(_unit("needle", "The study sample zephyrlattice remained intact."))
    found = retrieve("Did zephyrlattice remain intact?", units, top_k=3)
    assert len(found) <= 3
    assert found[0].id == "needle"


def test_exact_substring_is_not_crowded_out_of_top_k():
    units = [_unit(f"s{i:02d}", "zephyr") for i in range(8)]
    needle = "zephyr quota is 17 wafers " + " ".join(f"filler{i}" for i in range(400))
    units.append(_unit("long", needle))
    found = retrieve("zephyr quota is 17 wafers", units, top_k=1)
    assert [unit.id for unit in found] == ["long"]


def test_paraphrase_without_shared_tokens_is_missed():
    units = [_unit("u", "The company increased sales by 100 percent.")]
    assert retrieve("revenue doubled", units, top_k=5) == []


def test_cjk_and_kana_are_retrievable():
    units = [
        _unit("zh", "研究結果：成功率為百分之八十。"),
        _unit("ja", "昨日の天気は晴れでした。"),
        _unit("ko", "실험은 성공했습니다."),
        _unit("other", "The weather was unrelated."),
    ]
    assert retrieve("成功率為百分之八十", units, top_k=1)[0].id == "zh"
    assert retrieve("天気は晴れ", units, top_k=1)[0].id == "ja"
    assert retrieve("실험은 성공", units, top_k=1)[0].id == "ko"
    assert tokenize("天気") == ["天", "気"]


def test_ranking_tie_breaks_by_unit_id():
    units = [_unit("b", "zephyr quota"), _unit("a", "zephyr quota")]
    assert [unit.id for unit in retrieve("zephyr quota", units, top_k=2)] == ["a", "b"]


def test_top_k_limits_the_list():
    units = [_unit(f"u{i:02d}", f"zephyr note {i}") for i in range(6)]
    assert len(retrieve("zephyr", units, top_k=2)) == 2
