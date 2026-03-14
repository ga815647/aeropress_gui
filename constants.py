BREWER_PRESETS = {
    "standard": {
        "name": "AeroPress 標準版",
        "water_ml": 200,
        "dose_min": 9.0,
        "dose_max": 18.0,
    },
    "xl": {
        "name": "AeroPress XL",
        "water_ml": 400,
        "dose_min": 18.0,
        "dose_max": 30.0,
    },
}

DOSE_STEP = 0.5
POUR_RATE = 12
SEAL_DELAY_DEFAULT = 5.0
SWIRL_TIME_SEC = 5
SWIRL_WAIT_BASE = 30
SWIRL_WAIT_SLOPE = 10
SWIRL_WAIT_MIN = 10
SWIRL_WAIT_MAX = 45
SWIRL_CONVECTION_BASE = 1.0
SWIRL_DOSE_REF = 18.0

PRESS_TIME_MIN_FLOOR = 15
PRESS_TIME_MIN = 30
PRESS_TIME_MAX = 90
PRESS_TIME_PER_G = 2
DARCY_PRESS_EXP = 0.6
BED_COMPACTION_COEFF = 0.15
SWIRL_RESET_FRACTION = 0.35

RETENTION_BASE = {
    "very_light": 1.95,
    "light": 2.05,
    "medium_light": 2.15,
    "medium": 2.25,
    "moderately_dark": 2.35,
    "dark": 2.45,
    "very_dark": 2.55,
}
RETENTION_DIAL_SLOPE = {
    "very_light": 0.10,
    "light": 0.10,
    "medium_light": 0.10,
    "medium": 0.10,
    "moderately_dark": 0.09,
    "dark": 0.08,
    "very_dark": 0.07,
}

K_CA = 0.030
FINES_RATIO_BASE = 0.15
FINES_RATIO_DIAL_SLOPE = 0.04
K_FINES_MULT = 10.0
K_BOULDERS_MULT = 0.55

COFFEE_SPECIFIC_HEAT_RATIO = 0.33
BREWER_TEMP_DROP = 2.5

T_ENV = 25.0
COOL_RATE = 0.0008
K_BASE = 0.025
K_MIN = 0.006
K_MAX = 0.060
DIAL_BASE = 4.5
EY_ABSOLUTE_MAX = 28.0
EY_MIN = 14.0

ARRHENIUS_COEFF = 0.05
CONC_GRADIENT_COEFF = 0.5
PRE_SEAL_DRIP_RATE_REF = 0.30
PRE_SEAL_DRIP_DIAL_EXP = 1.0
PRE_SEAL_DRIP_MAX_RATIO = 0.12
PRE_SEAL_CONTACT_FRACTION = 0.20
PRE_SEAL_PERCOLATION_EFFICIENCY = 0.03
PRE_SEAL_AC_MULT = 1.35
PRE_SEAL_SW_MULT = 0.92
PRE_SEAL_PS_MULT = 0.72
PRE_SEAL_CA_MULT = 0.78
PRE_SEAL_CGA_MULT = 0.88
PRE_SEAL_MEL_MULT = 0.60

CONC_HUBER_DELTA = 0.5
BALANCE_PENALTY_WEIGHT = 0.15
BODY_BITTER_PENALTY_WEIGHT = 0.12
MEL_BITTER_COEFF = {
    "very_light": 0.0,
    "light": 0.0,
    "medium_light": 0.0,
    "medium": 0.0,
    "moderately_dark": 0.5,
    "dark": 0.5,
    "very_dark": 0.5,
}

KH_PERCEPT_DECAY = 150
ASYM_BITTER_MULT = 1.5
ASYM_SWEET_MULT = 1.5

TDS_PREFER = {
    "very_light": 1.35,
    "light": 1.35,
    "medium_light": 1.30,
    "medium": 1.25,
    "moderately_dark": 1.20,
    "dark": 1.18,
    "very_dark": 1.15,
}
TDS_GAUSS_SIGMA_LOW = 0.15
TDS_GAUSS_SIGMA_HIGH = 0.25

K_PS = 0.005
PS_TIME_MAX = 0.20
K_CGA_TIME = 0.015
CGA_TIME_MAX = 0.50
K_AC_DECAY = 0.0035

CGA_ASTRINGENCY_THRESHOLD = 1.25
CGA_ASTRINGENCY_SLOPE = 4.0
HARSHNESS_SLOPE = 4.0

SW_AROMA_SLOPE = 0.02
SW_AROMA_THRESH = 95.0
SW_AROMA_CAP = 0.30
ASHY_SLOPE = 3.0

MG_FRAC_AC_SW_MULT = 0.16
MG_FRAC_PS_CGA_MULT = 0.08
DIAL_STEP = 0.1
STEEP_STEP = 15

TEMP_BOILING_POINT = 100.0
SCORCH_PARAMS = {
    "very_light": (100, 0.00, 0.00),
    "light": (100, 0.00, 0.00),
    "medium_light": (97, 0.05, 0.00),
    "medium": (95, 0.08, 0.00),
    "moderately_dark": (91, 0.15, 0.10),
    "dark": (88, 0.20, 0.15),
    "very_dark": (85, 0.25, 0.20),
}

CHANNELING_PRESS_THRESHOLD = 60
CHANNELING_EY_SLOPE = 0.005
CHANNELING_CGA_MULT = 2.5
CHANNELING_BYPASS_MAX = 0.15
CHANNELING_COLLAPSE_RATIO = 0.20
PRESS_EQUIV_FRACTION = 0.15

# Roast: SCA/SCAA official classification + Agtron (ground) range.
# Reference: SCA roast color standards. Keys = SCA level names.
ROAST_TABLE = {
    "very_light": {
        "name": "Very Light (Agtron 85–95)",
        "sca_level": "Very Light",
        "agtron_min": 85,
        "agtron_max": 95,
        "base_temp": 100,
        "base_ey": 17.0,
    },
    "light": {
        "name": "Light (Agtron 75–80)",
        "sca_level": "Light",
        "agtron_min": 75,
        "agtron_max": 80,
        "base_temp": 99,
        "base_ey": 17.0,
    },
    "medium_light": {
        "name": "Medium Light (Agtron 60–70)",
        "sca_level": "Medium Light",
        "agtron_min": 60,
        "agtron_max": 70,
        "base_temp": 95,
        "base_ey": 19.0,
    },
    "medium": {
        "name": "Medium (Agtron 50–55)",
        "sca_level": "Medium",
        "agtron_min": 50,
        "agtron_max": 55,
        "base_temp": 92,
        "base_ey": 19.0,
    },
    "moderately_dark": {
        "name": "Moderately Dark (Agtron 40–45)",
        "sca_level": "Moderately Dark",
        "agtron_min": 40,
        "agtron_max": 45,
        "base_temp": 88,
        "base_ey": 21.0,
    },
    "dark": {
        "name": "Dark (Agtron 30–35)",
        "sca_level": "Dark",
        "agtron_min": 30,
        "agtron_max": 35,
        "base_temp": 85,
        "base_ey": 21.0,
    },
    "very_dark": {
        "name": "Very Dark (Agtron 20–25)",
        "sca_level": "Very Dark",
        "agtron_min": 20,
        "agtron_max": 25,
        "base_temp": 82,
        "base_ey": 21.5,
    },
}

TDS_ANCHORS = {"low": 1.00, "mid": 1.20, "high": 1.40}
IDEAL_FLAVOR = {
    ("very_light", "low"): {"AC": 0.28, "SW": 0.30, "PS": 0.18, "CA": 0.12, "CGA": 0.08, "MEL": 0.04},
    ("very_light", "mid"): {"AC": 0.25, "SW": 0.32, "PS": 0.20, "CA": 0.11, "CGA": 0.08, "MEL": 0.04},
    ("very_light", "high"): {"AC": 0.22, "SW": 0.35, "PS": 0.22, "CA": 0.10, "CGA": 0.07, "MEL": 0.04},
    ("light", "low"): {"AC": 0.25, "SW": 0.32, "PS": 0.18, "CA": 0.13, "CGA": 0.08, "MEL": 0.04},
    ("light", "mid"): {"AC": 0.22, "SW": 0.35, "PS": 0.20, "CA": 0.12, "CGA": 0.07, "MEL": 0.04},
    ("light", "high"): {"AC": 0.20, "SW": 0.37, "PS": 0.22, "CA": 0.11, "CGA": 0.06, "MEL": 0.04},
    ("medium_light", "low"): {"AC": 0.18, "SW": 0.35, "PS": 0.20, "CA": 0.14, "CGA": 0.09, "MEL": 0.04},
    ("medium_light", "mid"): {"AC": 0.15, "SW": 0.38, "PS": 0.22, "CA": 0.13, "CGA": 0.08, "MEL": 0.04},
    ("medium_light", "high"): {"AC": 0.13, "SW": 0.40, "PS": 0.23, "CA": 0.12, "CGA": 0.08, "MEL": 0.04},
    ("medium", "low"): {"AC": 0.12, "SW": 0.38, "PS": 0.22, "CA": 0.14, "CGA": 0.08, "MEL": 0.06},
    ("medium", "mid"): {"AC": 0.10, "SW": 0.40, "PS": 0.24, "CA": 0.13, "CGA": 0.07, "MEL": 0.06},
    ("medium", "high"): {"AC": 0.09, "SW": 0.42, "PS": 0.24, "CA": 0.12, "CGA": 0.07, "MEL": 0.06},
    ("moderately_dark", "low"): {"AC": 0.08, "SW": 0.32, "PS": 0.22, "CA": 0.13, "CGA": 0.08, "MEL": 0.17},
    ("moderately_dark", "mid"): {"AC": 0.07, "SW": 0.34, "PS": 0.23, "CA": 0.12, "CGA": 0.07, "MEL": 0.17},
    ("moderately_dark", "high"): {"AC": 0.06, "SW": 0.35, "PS": 0.24, "CA": 0.11, "CGA": 0.07, "MEL": 0.17},
    ("dark", "low"): {"AC": 0.05, "SW": 0.28, "PS": 0.22, "CA": 0.12, "CGA": 0.06, "MEL": 0.27},
    ("dark", "mid"): {"AC": 0.05, "SW": 0.30, "PS": 0.23, "CA": 0.11, "CGA": 0.05, "MEL": 0.26},
    ("dark", "high"): {"AC": 0.04, "SW": 0.30, "PS": 0.24, "CA": 0.10, "CGA": 0.05, "MEL": 0.27},
    ("very_dark", "low"): {"AC": 0.04, "SW": 0.26, "PS": 0.22, "CA": 0.12, "CGA": 0.05, "MEL": 0.30},
    ("very_dark", "mid"): {"AC": 0.04, "SW": 0.28, "PS": 0.23, "CA": 0.11, "CGA": 0.05, "MEL": 0.29},
    ("very_dark", "high"): {"AC": 0.03, "SW": 0.28, "PS": 0.24, "CA": 0.10, "CGA": 0.04, "MEL": 0.30},
}

KEYS = ["AC", "SW", "PS", "CA", "CGA", "MEL"]
WEIGHTS = {"AC": 1.2, "SW": 1.8, "PS": 1.5, "CA": 1.0, "CGA": 1.3, "MEL": 1.0}
TDS_W3_LOW = 0.25
TDS_W3_HIGH = 0.10
CONC_SENSITIVITY_FLOOR = 0.02
TDS_BROWN_WATER_FLOOR = 0.80
