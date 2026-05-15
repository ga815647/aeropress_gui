import constants
from models.compounds import predict_compounds
from models.ey_model import calc_ey, calc_fines_ratio
from models.scoring import flavor_score
from models.tds_model import calc_drip_volume, calc_retention, calc_swirl_wait


def test_calc_fines_ratio_clamps() -> None:
    assert calc_fines_ratio(3.5) > calc_fines_ratio(6.5)
    assert 0.05 <= calc_fines_ratio(9.0) <= 0.35
    assert 0.05 <= calc_fines_ratio(0.0) <= 0.35


def test_retention_and_swirl_wait_boundaries() -> None:
    assert calc_retention("very_light", 3.5) >= 1.60
    assert calc_retention("very_dark", 6.5) <= 2.80
    assert calc_swirl_wait("standard") == constants.BREWER_PRESETS["standard"]["swirl_wait_sec"]
    assert calc_swirl_wait("xl") == constants.BREWER_PRESETS["xl"]["swirl_wait_sec"]


def test_calc_ey_monotonic_and_bounded() -> None:
    low = calc_ey("medium", 90, 5.5, 90, 22, 400, 50)
    high = calc_ey("medium", 94, 4.5, 150, 22, 400, 50)
    assert high > low
    assert high <= constants.EY_ABSOLUTE_MAX


def test_calc_drip_volume_scales_with_time_and_dial_darcy() -> None:
    short = calc_drip_volume(400, 5.5, 20)
    long = calc_drip_volume(400, 5.5, 40)
    fine = calc_drip_volume(400, 4.0, 30)
    coarse = calc_drip_volume(400, 6.0, 30)
    assert long > short
    assert coarse > fine


def test_seal_delay_pushes_compounds_toward_acidity() -> None:
    fast_profile = predict_compounds("medium", 88, 4.5, 120, 19, water_gh=50, water_mg_frac=0.4, seal_delay=0)
    slow_profile = predict_compounds("medium", 88, 4.5, 120, 19, water_gh=50, water_mg_frac=0.4, seal_delay=20)
    assert (slow_profile["AC"] / slow_profile["SW"]) > (fast_profile["AC"] / fast_profile["SW"])


def test_flavor_score_penalties_do_not_crash_and_reward_better_balance() -> None:
    # Hoffman recipe → balanced label is the bullseye; an overshot CGA / under SW
    # version must score lower on the same label.
    clean = predict_compounds("medium_light", 98, 4.3, 120, 21, water_gh=50, water_mg_frac=0.4)
    harsh = dict(clean)
    harsh["CGA"] *= 2.0
    harsh["MEL"] *= 1.5
    harsh["SW"] *= 0.6
    clean_score = flavor_score(
        clean, 1.27, "medium_light", "balanced",
        water_kh=30, t_slurry=96, temp_initial=98,
        ey=21.0, steep_sec=120, dial=4.3,
    )
    harsh_score = flavor_score(
        harsh, 1.27, "medium_light", "balanced",
        water_kh=30, t_slurry=96, temp_initial=98,
        ey=21.0, steep_sec=120, dial=4.3,
    )
    assert clean_score > harsh_score
    assert harsh_score >= 0


def test_label_islands_are_independent() -> None:
    # Channel A discovery: editing one label's IDEAL must not move other labels' scores.
    # Smoke test: April recipe scores higher on acid-forward than balanced.
    april_cpd = predict_compounds("medium_light", 85, 5.0, 90, 15, water_gh=50, water_mg_frac=0.4,
                                  partial_seal_sec=25.0, partial_seal_water_ml=50.0)
    april_tds = 1.17
    on_acid = flavor_score(april_cpd, april_tds, "medium_light", "acid-forward",
                           water_kh=30, t_slurry=81, temp_initial=85,
                           ey=15.0, steep_sec=90, dial=5.0)
    on_balanced = flavor_score(april_cpd, april_tds, "medium_light", "balanced",
                               water_kh=30, t_slurry=81, temp_initial=85,
                               ey=15.0, steep_sec=90, dial=5.0)
    assert on_acid > on_balanced
