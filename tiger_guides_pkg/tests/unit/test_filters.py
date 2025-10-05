import pandas as pd

from tiger_guides.filters.ranking import apply_filters


def test_apply_filters_basic():
    data = pd.DataFrame({
        "Gene": ["A", "A", "B"],
        "Sequence": ["AAA", "AAT", "GGG"],
        "Score": [0.9, 0.85, 0.95],
        "MM0": [3, 4, 2],
        "MM1": [0, 0, 0],
        "MM2": [0, 0, 0],
    })
    config = {
        "filtering": {
            "min_guide_score": 0.8,
            "mm1_threshold": 0,
            "mm2_threshold": 0,
            "adaptive_mm0": True,
            "mm0_tolerance": 1,
        },
        "top_n_guides": 1,
    }

    ranked, stats = apply_filters(data, config)
    assert len(ranked) == 2
    assert stats["final"] == 2
