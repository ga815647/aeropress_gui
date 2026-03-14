import constants
from models.compounds import predict_compounds
from models.ey_model import calc_ey, calc_fines_ratio
from models.scoring import build_ideal_abs, flavor_score
from models.tds_model import calc_drip_volume, calc_press_time, calc_retention, calc_swirl_wait


def test_calc_fines_ratio_clamps() -> None:
    assert calc_fines_ratio(3.5) > calc_fines_ratio(6.5)
    assert 0.05 <= calc_fines_ratio(9.0) <= 0.35
    assert 0.05 <= calc_fines_ratio(0.0) <= 0.35


def test_retention_and_swirl_wait_boundaries() -> None:
    assert calc_retention("very_light", 3.5) >= 1.60
    assert calc_retention("very_dark", 6.5) <= 2.80
    assert calc_swirl_wait(3.5) == 40
    assert calc_swirl_wait(6.5) == 10


def test_calc_press_time_increases_for_finer_and_larger_dose() -> None:
    coarse = calc_press_time(18, 6.5, 120)
    fine = calc_press_time(18, 3.5, 120)
    assert fine > coarse
    assert calc_press_time(30, 4.5, 120) > calc_press_time(18, 4.5, 120)


def test_calc_ey_monotonic_and_bounded() -> None:
    low = calc_ey("medium", 90, 5.5, 90, 22, 400, 50, 30)
    high = calc_ey("medium", 94, 4.5, 150, 22, 400, 50, 30)
    assert high > low
    assert high <= constants.EY_ABSOLUTE_MAX


def test_calc_drip_volume_scales_with_time_and_dial_darcy() -> None:
    short = calc_drip_volume(400, 5.5, 20)
    long = calc_drip_volume(400, 5.5, 40)
    fine = calc_drip_volume(400, 4.0, 30)
    coarse = calc_drip_volume(400, 6.0, 30)
    assert long > short
    assert coarse > fine  # Darcy: coarser grind → lower resistance → more drip


def test_seal_delay_pushes_compounds_toward_acidity() -> None:
    fast_profile = predict_compounds("medium", 88, 4.5, 120, 19, 30, 0.4, seal_delay=0)
    slow_profile = predict_compounds("medium", 88, 4.5, 120, 19, 30, 0.4, seal_delay=20)
    assert (slow_profile["AC"] / slow_profile["SW"]) > (fast_profile["AC"] / fast_profile["SW"])


def test_flavor_score_penalties_do_not_crash_and_reward_better_balance() -> None:
    ideal = build_ideal_abs("medium", 1.25)
    balanced = predict_compounds("medium", 88, 4.5, 120, 19, 30, 0.4)
    harsh = dict(balanced)
    harsh["AC"] *= 1.6
    harsh["CGA"] *= 2.0
    balanced_score = flavor_score(
        balanced, ideal, 1.25, "medium", water_kh=30, t_slurry=88, temp_initial=92
    )
    harsh_score = flavor_score(
        harsh, ideal, 1.25, "medium", water_kh=30, t_slurry=95, temp_initial=100
    )
    assert balanced_score > harsh_score
    assert harsh_score >= 0
