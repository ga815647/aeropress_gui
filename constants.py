BREWER_PRESETS = {
    "standard": {
        "name": "AeroPress 標準版",
        "water_ml": 200,
        "dose_min": 7.0,
        "dose_max": 21.0,
        "fixed_press_sec": 30,
        "area_cm2": 43.0,   # 內徑 ~74mm → π×37²≈43 cm²
    },
    "xl": {
        "name": "AeroPress XL",
        "water_ml": 400,
        "dose_min": 15.0,
        "dose_max": 36.0,
        "fixed_press_sec": 40,
        "area_cm2": 63.6,   # 內徑 ~90mm → π×45²≈63.6 cm²
    },
}

# 達西定律截面積修正基準（standard 機型）
# XL 截面積較大 → 同等研磨/豆量下流量正比於截面積
DRIP_AREA_REF_CM2 = 43.0

DOSE_STEP = 0.5
POUR_RATE = 12
SEAL_DELAY_DEFAULT = 5.0
SWIRL_TIME_SEC = 5
SWIRL_WAIT_BASE = 30
SWIRL_WAIT_SLOPE = 10
SWIRL_WAIT_MIN = 10
SWIRL_WAIT_MAX = 45
SWIRL_CONVECTION_BASE = 1.0
SWIRL_WAIT_EXT_MULT = 0.3
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
BREWER_INSULATION_COEFF = 0.5
COOL_RATE = 0.0008
K_BASE = 0.025
K_MIN = 0.006
K_MAX = 0.060
DIAL_BASE = 4.5
EY_ABSOLUTE_MAX = 28.0
EY_MIN = 15.0  # 上調以排除大豆量極淺萃組合（brew_capacity 修正後的附帶效應）

EY_PREFER = {
    "very_light": 17.5,
    "light": 21.0,  # 修正：XL 淺焙實際萃取範圍 20~22%；EY_PREFER=19 過低導致 EY 懲罰強迫選 120s 短浸泡，壓制 PS/SW 發展
    "medium_light": 19.0,
    "medium": 19.0,
    "moderately_dark": 20.0,
    "dark": 20.0,
    "very_dark": 20.5,
}

# EY 感知修正指數（待實測校正，保守估算）
EY_PS_EXP = 0.65  # [已棄用] PS 改用 EY_DEV_GATE sigmoid 門控；保留供向後相容
EY_CGA_EXP = 0.55 # CGA 對 EY 敏感（大分子結合型，需充分萃取才大量釋出）
EY_AC_EXP = 0.05  # AC 對 EY 最不敏感（小分子最早萃出，EY 依賴極低）
EY_MEL_EXP = 0.15 # MEL 隨萃取輕度增加（梅納反應產物）
EY_CA_EXP = 0.05  # CA 對 EY 極輕度敏感

# 發展型化合物（SW + PS）sigmoid 門控
# 糖類/香氣/多醣需足夠萃取才能充分釋放；取代 PS 的冪律 EY_PS_EXP
# gate(ey) = floor + (1 - floor) * sigmoid(k * (ey - ey_prefer * center_frac))
# 設計：Hoffman(EY=21) → gate≈1.0；Championship(EY=15.6) → gate≈0.95；Under(EY=9.5) → gate≈0.58
EY_DEV_GATE_CENTER_FRAC = 0.62  # gate=0.5 對應 EY_PREFER 的 62%（light: 13.0%）
EY_DEV_GATE_FLOOR = 0.55        # 即使極低 EY 仍保留 55% 基底
EY_DEV_GATE_K = 0.80            # 門控陡峭度（每 %EY）

# EY Gaussian 懲罰（分焙度，上下不對稱）
# sigma_lo：低於 EY_PREFER 一側（欠萃）；sigma_hi：高於 EY_PREFER 一側（過萃）
EY_SIGMA_LO = {
    "very_light":      1.5,
    "light":           1.5,
    "medium_light":    2.0,
    "medium":          2.0,
    "moderately_dark": 2.5,
    "dark":            2.5,
    "very_dark":       3.0,
}
EY_SIGMA_HI = {
    "very_light":      1.5,
    "light":           1.5,
    "medium_light":    2.0,
    "medium":          2.0,
    "moderately_dark": 2.5,
    "dark":            2.5,
    "very_dark":       3.0,
}
EY_GAUSS_WEIGHT = 0.06  # EY 是過程變數非杯中物品質指標，保留最小防欠萃底線即可

ARRHENIUS_COEFF = 0.05
# 低溫萃取補正：輸入溫度（temp_initial）低於 K_LOW_TEMP_FLOOR 時啟動飽和補正
# optimizer 最低搜尋溫度：medium roast 88°C / light roast 93°C → 均高於 87°C 閾值，完全不受影響
# April 85°C / Championship 80°C 才會觸發補正
K_LOW_TEMP_FLOOR = 87.0   # °C，基於 temp_initial（注水溫度），非 t_avg
K_LOW_TEMP_BOOST = 3.0    # 最大補正量（total = 1 + BOOST = 最高 4×）
K_LOW_TEMP_DECAY = 2.0    # 飽和衰減參數（°C）；deficit / DECAY 作為指數輸入
CONC_GRADIENT_COEFF = 0.5
# §16 再評估後：貼近實務，漏水量由低估修正（0.30→0.38、η 1→1.2、上限 12%→18%）
PRE_SEAL_DRIP_RATE_REF = 0.38
PRE_SEAL_DRIP_DIAL_EXP = 1.2
PRE_SEAL_DRIP_MAX_RATIO = 0.18
DOSE_DRIP_REF = 18.0  # 豆量阻力修正基準值（g）；dose=18g 時修正係數為 1.0
                       # 指數 0.3 為保守估算，待實測「不同豆量 × 固定刻度」漏水量後校正
PARTIAL_SEAL_FLOW_FACTOR = 0.35  # 半密封（活塞插入 ~1cm）的相對流量係數；待實測後校正
PRE_SEAL_CONTACT_FRACTION = 0.20
PRE_SEAL_PERCOLATION_EFFICIENCY = 0.03
PRE_SEAL_AC_MULT = 1.35
PRE_SEAL_SW_MULT = 0.92
PRE_SEAL_PS_MULT = 0.72
PRE_SEAL_CA_MULT = 0.78
PRE_SEAL_CGA_MULT = 0.88
PRE_SEAL_MEL_MULT = 0.60

# 化合物感知 sigma（log-ratio 空間，非對稱）
# 黃金交叉：actual_perceived = ideal 時 compound_reward = 1.0；偏離按 sigma 衰減
# sigma_lo：低於理想（加分化合物不足 / 苦味化合物不足均寬鬆）
# sigma_hi：高於理想（苦味超標嚴懲、甜感/醇厚超標寬鬆）
COMPOUND_SIGMA_LO = {
    "AC": 0.30,   # 酸不足中等容忍
    "SW": 0.15,   # 甜不足嚴懲（口感核心）
    "PS": 0.15,   # 醇厚不足嚴懲（body 核心）
    "CA": 0.80,   # 苦不足完全寬鬆
    "CGA": 0.80,  # CGA 不足完全寬鬆
    "MEL": 0.80,  # MEL 不足完全寬鬆
}
COMPOUND_SIGMA_HI = {
    "AC": 0.35,   # 酸超標中等容忍（淺焙特性）
    "SW": 0.60,   # 甜超標非常寬鬆
    "PS": 0.60,   # 醇厚超標非常寬鬆
    "CA": 0.25,   # 苦超標懲罰
    "CGA": 0.18,  # CGA 超標強懲罰（澀感）
    "MEL": 0.25,  # MEL 超標懲罰（焦苦）
}

# 輸出顯示用（terminal.py / export.py / webapp.py 使用，不進評分公式）
MEL_BITTER_COEFF = {
    "very_light": 0.0,
    "light": 0.0,
    "medium_light": 0.0,
    "medium": 0.1,
    "moderately_dark": 0.5,
    "dark": 0.5,
    "very_dark": 0.5,
}

KH_PERCEPT_DECAY = 150
IDEAL_BITTER_REDUCTION = 0.95  # 理想苦味下修 5%，縮小模型與實感落差
LOW_GH_THRESHOLD = 20          # ppm；低於此視為軟水（如 RO）
SOFT_WATER_BITTER_AMP = 0.25   # 軟水苦味感知放大係數：GH→0 時苦味感知 +25%（preprocessing）

# 全面上調 TDS 偏好值，鼓勵更濃郁、有層次的萃取（Aeropress 哲學）
TDS_PREFER = {
    "very_light": 1.28,
    "light": 1.27,
    "medium_light": 1.25,
    "medium": 1.20,
    "moderately_dark": 1.15,
    "dark": 1.12,
    "very_dark": 1.09,
}
TDS_GAUSS_SIGMA_LOW = 0.10   # 太淡懲罰收緊：偏低 TDS 對口感強度影響更直接
TDS_GAUSS_SIGMA_HIGH = 0.20  # 高 TDS 保持較寬：Championship 1.56% 屬合法高濃縮風格

# 甜感（SW）時間函數參數：從浸泡開始即隨時間增加，使用飽和曲線
K_SW = 0.003  # 從 0.004 降至 0.003（更慢增長，鼓勵長時間浸泡）
SW_TIME_MAX = 0.28  # 從 0.25 升至 0.28（更高上限，讓長時間浸泡更有優勢）

# 醇厚度（PS）時間函數參數：降低啟動閾值，提高萃取速率
K_PS = 0.005  # 從 0.006 降至 0.005（更慢增長，鼓勵長時間浸泡）
PS_TIME_MAX = 0.38  # 從 0.35 升至 0.38（更高上限，強化 Aeropress 醇厚度優勢）

# CGA 時間函數參數
K_CGA_TIME = 0.015
CGA_TIME_MAX = 0.50
CGA_TIME_ONSET = 150  # CGA 時間累積起始點（秒）；softplus 平滑過渡

# 酸質（AC）衰減參數：調整開始衰減時間
K_AC_DECAY = 0.004  # 酸質衰減速率常數（稍微降低）
AC_DECAY_START = 150  # 酸質開始衰減的時間點（從 140 測試值進一步推到 150，確保長浸泡不失酸）
AC_HIGH_TEMP_THRESH = 95.0  # 揮發性有機酸高溫降解閾值（°C）；softplus 平滑過渡
AC_HIGH_TEMP_DECAY = 0.020  # 高溫降解斜率（每 softplus 單位損失 2%）

CGA_ASTRINGENCY_THRESHOLD = 1.25  # diagnose_anchor.py 顯示用，不進評分公式

SW_AROMA_SLOPE = 0.015   # Hoffman 校正：降低高溫懲罰斜率（99°C 僅 3% 損失）
SW_AROMA_THRESH = 97.0   # Hoffman 校正：96–97°C 完全無懲罰（light 搜尋範圍 93–99°C）
SW_AROMA_CAP = 0.25      # Hoffman 校正：收緊極端高溫上限

MG_PPM_REF = 20.0
CA_PPM_REF = 30.0
MG_FRAC_AC_SW_MULT = 0.16
MG_FRAC_PS_CGA_MULT = 0.08
DIAL_STEP = 0.1
STEEP_STEP = 30

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
    # 極淺焙：大幅提高醇厚度和甜感，降低酸質（Aeropress 哲學）
    ("very_light", "low"): {"AC": 0.20, "SW": 0.36, "PS": 0.24, "CA": 0.09, "CGA": 0.07, "MEL": 0.04},
    ("very_light", "mid"): {"AC": 0.18, "SW": 0.38, "PS": 0.26, "CA": 0.08, "CGA": 0.06, "MEL": 0.04},
    ("very_light", "high"): {"AC": 0.15, "SW": 0.40, "PS": 0.28, "CA": 0.07, "CGA": 0.06, "MEL": 0.04},
    # 淺焙：對齊化合物模型實際預測值（PS~0.355, SW~0.381 for Hoffman anchor）
    # 原 PS=0.27 遠低於模型預測，造成濃度懲罰系統性壓制長浸泡配方
    ("light", "low"): {"AC": 0.13, "SW": 0.37, "PS": 0.33, "CA": 0.08, "CGA": 0.06, "MEL": 0.03},
    ("light", "mid"): {"AC": 0.12, "SW": 0.38, "PS": 0.35, "CA": 0.07, "CGA": 0.05, "MEL": 0.03},
    ("light", "high"): {"AC": 0.10, "SW": 0.39, "PS": 0.38, "CA": 0.06, "CGA": 0.04, "MEL": 0.03},
    ("medium_light", "low"): {"AC": 0.15, "SW": 0.37, "PS": 0.24, "CA": 0.13, "CGA": 0.07, "MEL": 0.04},
    ("medium_light", "mid"): {"AC": 0.13, "SW": 0.39, "PS": 0.26, "CA": 0.12, "CGA": 0.06, "MEL": 0.04},
    ("medium_light", "high"): {"AC": 0.11, "SW": 0.41, "PS": 0.27, "CA": 0.11, "CGA": 0.06, "MEL": 0.04},
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

# 萃取模型用的豆子原始化合物基準（與 IDEAL_FLAVOR 評分目標獨立）
COMPOUND_BASE = {
    "very_light":      {"AC": 0.18, "SW": 0.38, "PS": 0.26, "CA": 0.08, "CGA": 0.06, "MEL": 0.04},
    "light":           {"AC": 0.14, "SW": 0.42, "PS": 0.27, "CA": 0.08, "CGA": 0.05, "MEL": 0.04},
    "medium_light":    {"AC": 0.13, "SW": 0.39, "PS": 0.26, "CA": 0.12, "CGA": 0.06, "MEL": 0.04},
    "medium":          {"AC": 0.10, "SW": 0.40, "PS": 0.24, "CA": 0.13, "CGA": 0.07, "MEL": 0.06},
    "moderately_dark": {"AC": 0.07, "SW": 0.34, "PS": 0.23, "CA": 0.12, "CGA": 0.07, "MEL": 0.17},
    "dark":            {"AC": 0.05, "SW": 0.30, "PS": 0.23, "CA": 0.11, "CGA": 0.05, "MEL": 0.26},
    "very_dark":       {"AC": 0.04, "SW": 0.28, "PS": 0.23, "CA": 0.11, "CGA": 0.05, "MEL": 0.29},
}


KEYS = ["AC", "SW", "PS", "CA", "CGA", "MEL"]
WEIGHTS = {"AC": 1.0, "SW": 1.8, "PS": 2.0, "CA": 1.3, "CGA": 1.3, "MEL": 1.3}
TDS_W3_LOW = 0.70   # 太淡扣分（floor=0.30）：低 TDS 顯著影響口感強度感知
TDS_W3_HIGH = 0.15  # 高 TDS 輕度懲罰（floor=0.85）：過萃靠 CGA 澀感扣分，不靠 TDS
CONC_SENSITIVITY_FLOOR = 0.02
TDS_BROWN_WATER_FLOOR = 0.80

# 風味偏好篩選：門檻 = ideal_abs[key] × 乘數
# 各維度乘數設計依據：
#   AC  ×1.05 → 酸感需稍高於理想，才能和一般配方有效區隔
#   SW  ×1.00 → 甜感達到理想即入選（已是優化目標，不需抬高門檻）
#   PS  ×1.00 → 香氣達到理想即入選（同上）
#   苦味 ×1.10 → Bitter 合計需明確超標，才算「偏苦」配方
FLAVOR_PREF_MULTIPLIER: dict[str, float] = {
    "acidic":   1.05,
    "sweet":    1.00,
    "aromatic": 1.00,
    "bitter":   1.10,
}

# "bitter" 同時比較 CA + CGA + MEL 的合計；其餘單一 key
FLAVOR_PREF_KEYS: dict[str, list[str]] = {
    "acidic":   ["AC"],
    "sweet":    ["SW"],
    "aromatic": ["PS"],
    "bitter":   ["CA", "CGA", "MEL"],
}
