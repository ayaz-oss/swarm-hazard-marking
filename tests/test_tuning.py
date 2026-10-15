import pandas as pd

from swarmhazard.tuning import select_best


def test_highest_median_delivered_wins_and_ties_go_to_fewer_losses():
    df = pd.DataFrame({
        "controller": ["C2"] * 6 + ["C0"] * 2,
        "p_repel_weight": [1.0, 1.0, 2.0, 2.0, 4.0, 4.0, 9.0, 9.0],
        "delivered":      [40,  42,  45,  45,  45,  45,  99,  99],
        "robots_lost":    [1,   1,   3,   3,   1,   2,   0,   0],
    })
    assert select_best(df, ["repel_weight"], "C2") == {"repel_weight": 4.0}
