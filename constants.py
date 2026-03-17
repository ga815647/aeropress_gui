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
EY_MIN = 15.0  # 上調以排除大豆量極淺萃組合（brew_capacity 修正後的附帶效應）

EY_PREFER = {
    "very_light": 17.5,
    "light": 19.0,  # Hoffman 校正：提升至 medium_light 基準，短浸泡低 EY 組合獲有效懲罰
    "medium_light": 19.0,
    "medium": 19.0,
    "moderately_dark": 20.0,
    "dark": 20.0,
    "very_dark": 20.5,
}

# EY 感知修正指數（待實測校正，保守估算）
EY_PS_EXP = 0.7   # PS 對 EY 最敏感（大分子萃出慢）；Hoffman 校正：強化短浸泡欠萃懲罰
EY_CGA_EXP = 0.2  # CGA 對 EY 中等敏感
EY_AC_EXP = 0.1   # AC 對 EY 最不敏感（小分子早期萃出）

ARRHENIUS_COEFF = 0.05
CONC_GRADIENT_COEFF = 0.5
# §16 再評估後：貼近實務，漏水量由低估修正（0.30→0.38、η 1→1.2、上限 12%→18%）
PRE_SEAL_DRIP_RATE_REF = 0.38
PRE_SEAL_DRIP_DIAL_EXP = 1.2
PRE_SEAL_DRIP_MAX_RATIO = 0.18
DOSE_DRIP_REF = 18.0  # 豆量阻力修正基準值（g）；dose=18g 時修正係數為 1.0
                       # 指數 0.3 為保守估算，待實測「不同豆量 × 固定刻度」漏水量後校正
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
BODY_BITTER_PENALTY_WEIGHT = 0.18  # v5.10: 強化醇苦比懲罰（Body 跟不上苦味）
MEL_BITTER_COEFF = {
    "very_light": 0.0,
    "light": 0.0,
    "medium_light": 0.0,
    "medium": 0.1,  # 微調：medium 錨定在 #55 City，其焦苦係數應從 0.0 微調至 0.1，以反映 City Roast 的輕微苦味起始
    "moderately_dark": 0.5,
    "dark": 0.5,
    "very_dark": 0.5,
}

KH_PERCEPT_DECAY = 150
ASYM_BITTER_MULT = 1.8  # v5.10: 加強苦味超標懲罰
ASYM_SWEET_MULT = 1.5

# v5.11: RO/實測口感矯正（高溫苦突出、低溫酸無香、水質權重）
IDEAL_BITTER_REDUCTION = 0.95  # 理想苦味下修 5%，縮小模型與實感落差
LOW_GH_THRESHOLD = 20  # ppm；低於此視為軟水（如 RO），苦味感知加權
SOFT_WATER_BITTER_SLOPE = 2.0  # 軟水時苦味超標之額外懲罰斜率
AC_WITHOUT_SWEET_SLOPE = 3.0   # 酸高甜低（低溫酸無香）懲罰斜率

# v5.10: 下修以對應實測「過於濃烈」，偏日常適飲
TDS_PREFER = {
    "very_light": 1.27,
    "light": 1.27,
    "medium_light": 1.22,
    "medium": 1.17,
    "moderately_dark": 1.12,
    "dark": 1.10,
    "very_dark": 1.07,
}
TDS_GAUSS_SIGMA_LOW = 0.15
TDS_GAUSS_SIGMA_HIGH = 0.20  # v5.10: 收緊過濃懲罰

K_PS = 0.005
PS_TIME_MAX = 0.20
K_CGA_TIME = 0.015
CGA_TIME_MAX = 0.50
K_AC_DECAY = 0.0035

CGA_ASTRINGENCY_THRESHOLD = 1.25
CGA_ASTRINGENCY_SLOPE = 2.0  # Hoffman 校正 v2：96°C+135s 仍受 CGA 懲罰，降至 2.0；HARSHNESS_SLOPE 維持 4.0 作保護
HARSHNESS_SLOPE = 4.0

SW_AROMA_SLOPE = 0.015   # Hoffman 校正：降低高溫懲罰斜率（99°C 僅 3% 損失）
SW_AROMA_THRESH = 97.0   # Hoffman 校正：96–97°C 完全無懲罰（light 搜尋範圍 93–99°C）
SW_AROMA_CAP = 0.25      # Hoffman 校正：收緊極端高溫上限
ASHY_SLOPE = 3.0

MG_PPM_REF = 20.0
CA_PPM_REF = 30.0
MG_FRAC_AC_SW_MULT = 0.16
MG_FRAC_PS_CGA_MULT = 0.08
DIAL_STEP = 0.1
STEEP_STEP = 15

# 各焙度研磨粗細偏好（Hoffman 450–600µm EK43 → ZP6 等效 dial ≈ 4.3 為錨點）
# 懲罰公式：score × (1 - W + W × exp(-0.5 × ((dial - prefer)/sigma)²))
DIAL_PREFER_WEIGHT = 0.06  # 最大 6% 懲罰（軟約束）
DIAL_PREFER_SIGMA = 1.0    # ±1.0 dial 以內 < 2.5% 懲罰

TEMP_BOILING_POINT = 100.0
SCORCH_PARAMS = {
    "very_light": (100, 0.00, 0.00),
    "light": (100, 0.00, 0.00),
    "medium_light": (97, 0.05, 0.00),
    "medium": (92, 0.08, 0.00),
    "moderately_dark": (88, 0.15, 0.10),
    "dark": (88, 0.20, 0.15),
    "very_dark": (85, 0.25, 0.20),
}

CHANNELING_PRESS_THRESHOLD = 60
CHANNELING_EY_SLOPE = 0.005
CHANNELING_CGA_MULT = 2.5
CHANNELING_BYPASS_MAX = 0.15
CHANNELING_COLLAPSE_RATIO = 0.20
PRESS_EQUIV_FRACTION = 0.15

# 下壓滲流化合物選擇性（壓力驅動水流穿透粉層，不同於靜態浸泡）
# 物理依據：壓力流維持濃度梯度（新鮮溶劑接觸）→ 難萃化合物（CGA/MEL）額外釋放；
#           香氣揮發物（SW）在機械擾動+熱氣中部分散失
# press_frac = min(press_sec / PRESS_PERC_REF_SEC, 2.0)
PRESS_PERC_CGA_DIFF = 0.05   # CGA：壓力流釋放細胞壁結合型 CGA，+5% / 30s 基準
PRESS_PERC_MEL_DIFF = 0.03   # MEL：大分子聚合物需壓力輔助溶出，+3% / 30s
PRESS_PERC_CA_DIFF  = 0.02   # CA ：碳水化合物輕微受惠，+2% / 30s
PRESS_PERC_SW_LOSS  = 0.03   # SW ：揮發性香氣在下壓時逸散，-3% / 30s
PRESS_PERC_REF_SEC  = 30.0   # 基準下壓時間（Hoffman 標準版 30s；XL ~47s）

# Roast: SCA/SCAA official classification + Agtron (ground) range.
# Reference: SCA roast color standards. Keys = SCA level names.
ROAST_TABLE = {
    "very_light": {
        "name": "極淺焙",
        "sca_level": "Light/Cinnamon",
        "agtron_min": 85,
        "agtron_max": 95,
        "base_temp": 97,
        "base_ey": 17.0,
        "dial_prefer": 4.2,  # 豆質最硬，細研磨穿透細胞壁
        "note": "SCA: Light/Cinnamon (Agtron #85-95)。淺肉桂色，表面皺褶多、體積小。豆質極硬。100°C 封頂動能破壁。",
    },
    "light": {
        "name": "淺焙",
        "sca_level": "Medium",
        "agtron_min": 75,
        "agtron_max": 75,
        "base_temp": 96,
        "base_ey": 17.0,
        "dial_prefer": 4.3,  # Hoffman 錨點：450–600µm EK43 ≈ ZP6 dial 4.3
        "note": "SCA: Medium (Agtron #75)。栗子色，表面乾燥無油。一爆剛結束。維持高溫動能以推動甜感發展。",
    },
    "medium_light": {
        "name": "中淺焙",
        "sca_level": "High",
        "agtron_min": 65,
        "agtron_max": 65,
        "base_temp": 95,
        "base_ey": 19.0,
        "dial_prefer": 4.5,  # 溶出性提升，稍粗
        "note": "SCA: High (Agtron #65)。褐棕色。一爆完全結束，皺褶撐開。台灣精品市場最大公約數，酸甜平衡基準。",
    },
    "medium": {
        "name": "中焙",
        "sca_level": "City",
        "agtron_min": 55,
        "agtron_max": 55,
        "base_temp": 91,
        "base_ey": 19.0,
        "dial_prefer": 4.7,  # City 焙溶出最佳，可稍粗
        "note": "SCA: City (Agtron #55)。巧克力色。酸質退場、堅果轉強。若遇標示模糊豆，往下靠攏選此項最穩妥。",
    },
    "moderately_dark": {
        "name": "中深焙",
        "sca_level": "Full City",
        "agtron_min": 45,
        "agtron_max": 45,
        "base_temp": 86,
        "base_ey": 21.0,
        "dial_prefer": 4.5,  # 回細，低溫 + 過萃保護
        "note": "SCA: Full City (Agtron #45)。暗棕色帶油光。剛過二爆。系統啟動最大幅度急煞，嚴防焦苦物質瞬間爆發。",
    },
    "dark": {
        "name": "深焙",
        "sca_level": "French",
        "agtron_min": 35,
        "agtron_max": 35,
        "base_temp": 82,
        "base_ey": 21.0,
        "dial_prefer": 4.3,  # 細研磨補償低溫萃取動能不足
        "note": "SCA: French (Agtron #35)。表面佈滿油脂。結構極疏鬆。接近萃取底線，平滑降溫以保留糖蜜與 Body。",
    },
    "very_dark": {
        "name": "極深焙",
        "sca_level": "Italian",
        "agtron_min": 25,
        "agtron_max": 25,
        "base_temp": 80,
        "base_ey": 21.5,
        "dial_prefer": 4.1,  # 最細補償，防空洞口感
        "note": "SCA: Italian (Agtron #25)。極亮黏膩感。觸及 80°C 物理地板。守住最低熱能以溶出基本醇厚度，防止焦炭化。",
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
