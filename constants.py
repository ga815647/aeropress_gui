BREWER_PRESETS = {
    "standard": {
        "name": "AeroPress 標準版",
        "water_ml": 200,
        "dose_min": 7.0,
        "dose_max": 21.0,
        "fixed_press_sec": 30,
        "swirl_wait_sec": 30,  # 旋轉後靜置等沉粉（容器固定，不依 dial）
        "area_cm2": 43.0,   # 內徑 ~74mm → π×37²≈43 cm²
    },
    "xl": {
        "name": "AeroPress XL",
        "water_ml": 400,
        "dose_min": 15.0,
        "dose_max": 36.0,
        "fixed_press_sec": 40,
        "swirl_wait_sec": 40,  # XL 深床（22g/400ml）沉降較慢，比 standard 多 10s
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
    "light": 21.0,  # Nordic 真淺焙：硬豆需充分萃取（21%）才能展開香氣
    "medium_light": 21.0,  # Hoffman 錨點搬遷：原 light=21.0 對應 El Tambo (Agtron 65) 中淺焙，實際 20-22%
    "medium": 19.0,
    "moderately_dark": 20.0,
    "dark": 20.0,
    "very_dark": 20.5,
}

# EY 感知修正指數（待實測校正，保守估算）
EY_PS_EXP = 0.65  # [已棄用] PS 改用 EY_DEV_GATE sigmoid 門控；保留供向後相容
EY_CGA_EXP = 0.55 # CGA 對 EY 敏感（大分子結合型，需充分萃取才大量釋出）
EY_AC_EXP = 0.05  # AC 對 EY 最不敏感（小分子最早萃出，EY 依賴極低）
EY_MEL_EXP = 0.40 # MEL 隨萃取增加（大分子聚合物需充分萃取）
EY_CA_EXP = 0.05  # CA 對 EY 極輕度敏感

# 發展型化合物（SW + PS）sigmoid 門控
# 糖類/香氣/多醣需足夠萃取才能充分釋放；取代 PS 的冪律 EY_PS_EXP
# gate(ey) = floor + (1 - floor) * sigmoid(k * (ey - ey_prefer * center_frac))
# [已移除] DEV_GATE：SW/PS 不再用 EY 門控
# SW/PS 的萃取發展完全通過時間/溫度/研磨敏感度表達（K_SW, K_PS, 溫度係數）
# 理由：EY 和 SW/PS 都是 temp/time/grind 的輸出，用 EY gate SW/PS 是因果倒置

# EY Gaussian 懲罰（分焙度，上下不對稱）
# sigma_lo：低於 EY_PREFER 一側（欠萃）；sigma_hi：高於 EY_PREFER 一側（過萃）
EY_SIGMA_LO = {
    "very_light":      1.5,
    "light":           1.5,
    "medium_light":    1.5,  # Hoffman 錨點搬遷：原 light=1.5
    "medium":          2.0,
    "moderately_dark": 2.5,
    "dark":            2.5,
    "very_dark":       3.0,
}
EY_SIGMA_HI = {
    "very_light":      1.5,
    "light":           1.5,
    "medium_light":    1.5,  # Hoffman 錨點搬遷：原 light=1.5
    "medium":          2.0,
    "moderately_dark": 2.5,
    "dark":            2.5,
    "very_dark":       3.0,
}
EY_GAUSS_WEIGHT = 0.0   # EY 是物理過程變數，不進口感評分；化合物模型已通過 DEV_GATE + 冪律間接反映

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
    "CGA": 0.18,  # CGA 超標懲罰（澀感）
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

KH_PERCEPT_DECAY = 150          # [舊公式用] 保留供參考；新公式用 KH_FLOOR + KH_PERCEPT_DECAY_SMOOTH
KH_FLOOR = 0.65                 # KH 酸質壓制漸近底線（kh→∞ 時 AC 感知最低保留 65%）
KH_PERCEPT_DECAY_SMOOTH = 42.0  # 平滑 KH 衰減常數；對齊 kh=30 → kh_factor≈0.82
IDEAL_BITTER_REDUCTION = 0.95   # 理想苦味下修 5%，縮小模型與實感落差
LOW_GH_THRESHOLD = 20           # ppm；低於此視為軟水（如 RO）
SOFT_WATER_BITTER_AMP = 0.25    # 軟水苦味感知放大係數：GH→0 時苦味感知 +25%（preprocessing）
GH_SOFT_SIGMOID_K = 0.3         # 軟水 sigmoid 平滑過渡斜率

# 全面上調 TDS 偏好值，鼓勵更濃郁、有層次的萃取（Aeropress 哲學）
TDS_PREFER = {
    "very_light": 1.28,
    "light": 1.30,           # Nordic 真淺焙：高 TDS 才壓得住酸刺、撐得起香氣
    "medium_light": 1.27,    # Hoffman 錨點搬遷：原 light=1.27（El Tambo 實測 1.23）
    "medium": 1.20,
    "moderately_dark": 1.15,
    "dark": 1.12,
    "very_dark": 1.09,
}
TDS_GAUSS_SIGMA_LOW = 0.15   # 低 TDS 側 sigma（Super-Gaussian）：April 1.17% 不嚴懲
TDS_GAUSS_SIGMA_HIGH = 0.65  # 高 TDS 側 sigma 適度放寬（0.50→0.65），解除 dose 鎖定但防極端
TDS_SIGMA_BLEND_K = 5.0      # TDS sigma 平滑混合斜率
TDS_SUPER_GAUSS_EXP = 4      # 超高斯（平頂 → dose 多元性需靠寬 sigma）

# 甜感（SW）時間函數參數：從浸泡開始即隨時間增加，使用飽和曲線
K_SW = 0.014  # 速率提高（0.010→0.014），讓 90-120s 接近平台、60s 明顯落後
SW_TIME_FLOOR = 0.30  # t=0 時 SW 基底（從 0.50 收緊到 0.30，讓 60s 欠萃明顯低於 120s 完整發展）
SW_DIAL_COEFF = 0.10  # SW 研磨敏感度：對數線性，每 dial 單位 10%（細研磨接觸面積大，香氣揮發物萃取多）

# 醇厚度（PS）時間函數參數：降低啟動閾值，提高萃取速率
K_PS = 0.012  # 速率提高（0.008→0.012），配合 floor 降低後仍保 100-120s 飽和度
PS_TIME_FLOOR = 0.30  # t=0 時 PS 基底（從 0.50 收緊到 0.30，配合 SW 加強短浸泡欠發展懲罰）

# CGA 時間函數參數
K_CGA_TIME = 0.015
CGA_TIME_MAX = 0.50
CGA_TIME_ONSET = 150  # CGA 時間累積起始點（秒）；softplus 平滑過渡

# MEL 時間函數參數（大分子聚合物需時間溶出，比 CGA 慢）
K_MEL_TIME = 0.008      # 溶解速率
MEL_TIME_MAX = 0.35     # 最大時間增益
MEL_TIME_ONSET = 80     # 起始時間（秒）；softplus 平滑過渡

# 酸質（AC）衰減參數：調整開始衰減時間
K_AC_DECAY = 0.004  # 酸質衰減速率常數（稍微降低）
AC_DECAY_START = 150  # 酸質開始衰減的時間點（從 140 測試值進一步推到 150，確保長浸泡不失酸）
AC_HIGH_TEMP_THRESH = 95.0  # 揮發性有機酸高溫降解閾值（°C）；softplus 平滑過渡
AC_HIGH_TEMP_DECAY = 0.020  # 高溫降解斜率（每 softplus 單位損失 2%）

# 研磨粗細對 AC 衰減 / CGA 累積動力學的耦合（Fuller & Rao 2017 Sci. Reports + coffeeadastra）
# 粗磨內部擴散慢 → 起始延後 + 速率降低；細磨表面積大 → 起始提前 + 速率加快
# 同時作用：(a) 速率乘以 grind_kinetics；(b) 起始時間除以 grind_kinetics
# >1 for fine（dial < DIAL_BASE）, <1 for coarse（dial > DIAL_BASE）
GRIND_KINETICS_COEFF = 0.40

# Grind-dependent EY 欠萃懲罰（Phase 5 lite）
# 細磨（dial < DIAL_BASE）目標 Hoffman 風格，EY 不足要扣分；
# 粗磨（dial > DIAL_BASE）刻意低 EY 是 April/Hedrick 風格，EY 不足不扣分。
# 公式：factor = exp(-EY_DEMAND_WEIGHT × sigmoid(GRIND_EY_DEMAND_K × (DIAL_BASE - dial)) × ey_z²)
# 其中 ey_z = max(0, (EY_PREFER - EY) / EY_SIGMA_LO[roast])（單側、softplus 平滑）
GRIND_EY_DEMAND_K = 10.0      # sigmoid 銳度（dial 4.5 為中心；±0.1 dial 差距即足以區分）
EY_DEMAND_WEIGHT = 0.30       # 最大懲罰強度（細磨 + EY 差 1 個 sigma → ~25% 扣分）

# TDS-EY mismatch 懲罰（Phase 5 lite+）：「低 TDS + 高 EY」=「under-concentrated 過萃」象限
# 兩條件同時觸發才扣分（自我 gating）：dose 過瘦 → 必須過萃補 TDS → 酸感集中、澀鹹、無香
# softplus(k=10) 確保負側 arg ≈ 0，正常配方不誤殺
TDS_EY_MISMATCH_WEIGHT = 3.0  # 兩個 deficit/surplus 各為 1 單位時扣分強度
TDS_EY_MISMATCH_K = 20.0      # softplus 銳度（高 k 讓「達標」殘留近 0，避免 Hoffman 誤扣）

CGA_ASTRINGENCY_THRESHOLD = 1.15  # diagnose_anchor.py 顯示用，不進評分公式；Phase 3 調整：IDEAL_CGA 從 0.05→0.057，比值分母增大，對應閾值從 1.25→1.15

SW_AROMA_SLOPE = 0.015      # [舊公式用] 保留供參考
SW_AROMA_THRESH = 97.0      # Sigmoid 中心溫度（低於此≈無損失，高於此平滑飽和）
SW_AROMA_CAP = 0.25         # 最大香氣損失比例
SW_AROMA_SIGMOID_K = 3.0    # SW 香氣損失 sigmoid 斜率（每°C）

SCORCH_SOFTPLUS_K = 0.5     # 焦苦放大 softplus 平滑度（越小越平滑）

MG_PPM_REF = 20.0
CA_PPM_REF = 30.0
MG_FRAC_AC_SW_MULT = 0.16
MG_FRAC_PS_CGA_MULT = 0.08
DIAL_STEP = 0.1
STEEP_STEP = 30

# 各焙度研磨粗細偏好（Hoffman 450–600µm EK43 → ZP6 等效 dial ≈ 4.3 為錨點）
# 懲罰公式：score × (1 - W + W × exp(-0.5 × ((dial - prefer)/sigma)²))
DIAL_PREFER_WEIGHT = 0.15  # 最大 15% 懲罰（Phase 3 提升鑑別度）
DIAL_PREFER_SIGMA = 0.6    # ±0.6 dial 懲罰區間（Phase 3 收緊）

# Top N 多樣化門檻（#2 起每名強制與已選方案在三軸至少一軸差異 ≥ 閾值）
TOP_DIVERSITY_DIAL_MIN = 1.0   # dial 至少差 1 格（粗磨/細磨明確區分）
TOP_DIVERSITY_STEEP_MIN = 60   # steep 至少差 60s（2 個 STEEP_STEP）
TOP_DIVERSITY_DOSE_MIN = 2.0   # dose 至少差 2g（劑量改變要明顯）

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
        "dose_per_100ml": (5.0, 7.0),  # 預設豆量範圍 g/100ml（XL: 20-28g, std: 10-14g）
        "note": "SCA: Light/Cinnamon (Agtron #85-95)。淺肉桂色，表面皺褶多、體積小。豆質極硬。100°C 封頂動能破壁。",
    },
    "light": {
        "name": "淺焙",
        "sca_level": "Light",
        "agtron_min": 75,
        "agtron_max": 85,
        "base_temp": 99,
        "base_ey": 17.0,
        "dial_prefer": 4.0,  # Nordic 硬豆需更細研磨穿透密實細胞壁
        "dose_per_100ml": (5.5, 7.5),  # 推高豆量補低 TDS，避免酸刺澀無香的欠濃陷阱
        "note": "SCA: Light (Agtron #75-85)。Nordic 風格淺焙，豆質硬密。需 99°C 沸點水＋細研磨＋足夠豆量推完整萃取，否則低濃高萃象限（酸刺/澀/無香）。",
    },
    "medium_light": {
        "name": "中淺焙",
        "sca_level": "Medium-Light",
        "agtron_min": 65,
        "agtron_max": 75,
        "base_temp": 96,
        "base_ey": 17.0,
        "dial_prefer": 4.3,  # Hoffman 錨點搬遷：450–600µm EK43 ≈ ZP6 dial 4.3
        "dose_per_100ml": (5.0, 7.0),  # Hoffman 11g/200ml=5.5；Championship 17g/200ml=8.5 用 fixed_dose
        "note": "SCA: Medium-Light (Agtron #65-75)。Hoffmann/Square Mile filter roast 標竿，El Tambo 等中淺焙水洗豆。栗子色，一爆剛結束。台灣精品市場最大公約數。",
    },
    "medium": {
        "name": "中焙",
        "sca_level": "City",
        "agtron_min": 55,
        "agtron_max": 55,
        "base_temp": 91,
        "base_ey": 19.0,
        "dial_prefer": 4.7,  # City 焙溶出最佳，可稍粗
        "dose_per_100ml": (4.5, 6.0),  # 溶出佳，豆量需求降
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
        "dose_per_100ml": (4.0, 5.5),  # 深焙溶出快，省豆
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
        "dose_per_100ml": (3.5, 5.0),  # 結構疏鬆易萃，少量即足
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
        "dose_per_100ml": (3.5, 5.0),  # 極易萃，最省豆
        "note": "SCA: Italian (Agtron #25)。極亮黏膩感。觸及 80°C 物理地板。守住最低熱能以溶出基本醇厚度，防止焦炭化。",
    },
}

TDS_ANCHORS = {"low": 1.00, "mid": 1.20, "high": 1.40}
IDEAL_FLAVOR = {
    # 極淺焙：大幅提高醇厚度和甜感，降低酸質（Aeropress 哲學）
    ("very_light", "low"): {"AC": 0.20, "SW": 0.36, "PS": 0.24, "CA": 0.09, "CGA": 0.07, "MEL": 0.04},
    ("very_light", "mid"): {"AC": 0.18, "SW": 0.38, "PS": 0.26, "CA": 0.08, "CGA": 0.06, "MEL": 0.04},
    ("very_light", "high"): {"AC": 0.15, "SW": 0.40, "PS": 0.28, "CA": 0.07, "CGA": 0.06, "MEL": 0.04},
    # 淺焙（Nordic, Agtron 75-85）：暫用 very_light 同款 profile（豆質接近，差別在發展度）
    # 待真淺焙實測食譜後重校
    ("light", "low"): {"AC": 0.20, "SW": 0.36, "PS": 0.24, "CA": 0.09, "CGA": 0.07, "MEL": 0.04},
    ("light", "mid"): {"AC": 0.18, "SW": 0.38, "PS": 0.26, "CA": 0.08, "CGA": 0.06, "MEL": 0.04},
    ("light", "high"): {"AC": 0.15, "SW": 0.40, "PS": 0.28, "CA": 0.07, "CGA": 0.06, "MEL": 0.04},
    # 中淺焙（Hoffman 錨點搬遷自原 light）：CGA=0.057 對齊 El Tambo 模型實測 CGA_frac≈0.064
    ("medium_light", "low"): {"AC": 0.193, "SW": 0.35, "PS": 0.25, "CA": 0.10, "CGA": 0.057, "MEL": 0.05},
    ("medium_light", "mid"): {"AC": 0.153, "SW": 0.36, "PS": 0.29, "CA": 0.09, "CGA": 0.057, "MEL": 0.05},
    ("medium_light", "high"): {"AC": 0.123, "SW": 0.37, "PS": 0.29, "CA": 0.11, "CGA": 0.057, "MEL": 0.05},
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
    "light":           {"AC": 0.16, "SW": 0.40, "PS": 0.26, "CA": 0.07, "CGA": 0.05, "MEL": 0.04},   # Nordic 真淺焙暫定
    "medium_light":    {"AC": 0.14, "SW": 0.42, "PS": 0.27, "CA": 0.08, "CGA": 0.05, "MEL": 0.04},   # Hoffman 錨點搬遷自原 light（El Tambo Agtron 65-75）
    "medium":          {"AC": 0.10, "SW": 0.40, "PS": 0.24, "CA": 0.13, "CGA": 0.07, "MEL": 0.06},
    "moderately_dark": {"AC": 0.07, "SW": 0.34, "PS": 0.23, "CA": 0.12, "CGA": 0.07, "MEL": 0.17},
    "dark":            {"AC": 0.05, "SW": 0.30, "PS": 0.23, "CA": 0.11, "CGA": 0.05, "MEL": 0.26},
    "very_dark":       {"AC": 0.04, "SW": 0.28, "PS": 0.23, "CA": 0.11, "CGA": 0.05, "MEL": 0.29},
}


KEYS = ["AC", "SW", "PS", "CA", "CGA", "MEL"]
WEIGHTS = {"AC": 1.0, "SW": 1.8, "PS": 2.0, "CA": 1.3, "CGA": 1.3, "MEL": 1.3}
SIGMA_BLEND_K = 8.0            # 化合物不對稱 sigma sigmoid 混合斜率
EY_BLEND_K = 8.0               # EY 不對稱 sigma sigmoid 混合斜率

# TDS 底線 sigmoid（取代 min(tds/floor, 1)²）
TDS_FLOOR_MID = 0.50           # Sigmoid 中心：TDS=0.50 → factor=0.5
TDS_FLOOR_K = 8.0              # Sigmoid 斜率

# Ideal 內插 Gaussian basis 寬度
IDEAL_INTERP_SIGMA = 0.15      # TDS 錨點間 Gaussian 基函數寬度

# 化合物比值獎勵（純淨酸質 + 甜感主導 + 醇厚乾淨度）
AC_CGA_RATIO_IDEAL = 2.0       # AC/CGA 理想比值（高 = 純淨酸質）
SW_BITTER_RATIO_IDEAL = 3.0    # SW/(MEL+CGA) 理想比值（高 = 甜感主導）
PS_CA_RATIO_IDEAL = 2.0        # PS/CA 理想比值（高 = 乾淨醇厚無苦）
RATIO_SIGMOID_K = 1.0          # 比值評分 sigmoid 斜率
RATIO_WEIGHT = 0.15            # 比值獎勵權重（最多降 15% compound_loss）
RATIO_W_AC_CGA = 1.0           # AC/CGA 比值權重
RATIO_W_SW_BITTER = 1.0        # SW/(MEL+CGA) 比值權重
RATIO_W_PS_CA = 0.6            # PS/CA 比值權重（醇厚乾淨度，Phase 2）

# Phase 2: 苦澀化合物超標加速懲罰（壞處邊際遞增）
# 物理意義：CGA/MEL 超標代表過萃澀感/焦苦，偏離越多懲罰越大
# excess = sigmoid(K × log_dev)；accel = softplus(r_sq − threshold)
# 完全平滑：sigmoid 方向門控，softplus 強度閾值，無 if/else
ACCEL_ONSET_K = 3.0            # sigmoid 斜率（判斷超標方向；log_dev > 0 = 超標）
PENALTY_ACCEL_THRESHOLD = 2.5  # r_sq 啟動閾值（≈ 1.58σ 後加速；保護正常配方）
PENALTY_ACCEL_K = 1.0          # softplus 平滑斜率
ACCEL_W_PER_COMPOUND = {       # 各化合物超標加速懲罰權重（0 = 不啟動）
    "AC": 0.0, "SW": 0.0, "PS": 0.0,
    "CA": 0.0, "CGA": 0.20, "MEL": 0.15,
}

