# AeroPress 四向量最佳化系統 — 完整白皮書

本文件整合 v5.8s 主體規格、v5.9 封閉前漏水、v5.10/v5.11 口感校正與焙度對照，為單一規格來源。實作時請以 **constants.py** 與現行程式碼為準；焙度代號已採用 SCA 標準（very_light, light, medium_light, medium, moderately_dark, dark, very_dark）。

**快速導讀：** §0–§9 模型規格 | §10 主程式 | §11–§12 輸出與 CLI | §13 檔案結構 | §14–§16 限制與迭代 | 附錄 A 封閉前漏水 | 附錄 B 口感校正 | 附錄 C 焙度對照。

---

## 0. 基礎常數（Constants）

```python
import math

# ── 沖煮設備常數 ──────────────────────────────────────────
# WATER_ML 已從固定常數改為機型依賴（v5.5r：大小愛樂壓快選）
BREWER_PRESETS = {
    'standard': {
        'name':      'AeroPress 標準版',
        'water_ml':  200,
        'dose_min':  9.0,    # 最低豆量（g）→ 粉水比 1:22
        'dose_max':  18.0,   # 最高豆量（g）→ 粉水比 1:11
    },
    'xl': {
        'name':      'AeroPress XL',
        'water_ml':  400,
        'dose_min':  18.0,   # 最低豆量（g）→ 粉水比 1:22
        'dose_max':  30.0,   # 最高豆量（g）→ 粉水比 1:13
    },
}
# 物理設計說明：
# - COOL_RATE 兩機型幾乎相同（理論 r = hA/(mc)：標準版 0.000136，XL 0.000123，比值 1.10×）
#   → 保持單一 COOL_RATE 常數（機身表面積/水量比值等比例放大）
# - BREWER_TEMP_DROP 同理：塑膠質量與水量等比例放大，失溫幅度不變（v3.9 推導）
# - 搜尋空間：標準版 7×31×13×19 = 53,599 組合；XL 7×31×13×25 = 70,525 組合
DOSE_STEP         = 0.5

# ── 注水階段修正（v5.5r 新增）─────────────────────────────────
POUR_RATE         = 12     # 注水流速（ml/s）；Bonavita 鵝頸壺中高速倒水（Hoffman 快倒法）
                            # 搜尋數據：Brewista max=24 g/s、Fellow Stagg max=20 g/s、
                            # Bonavita 中速=10 g/s、慢速手沖=3 g/s
                            # Hoffman AeroPress 法為快速一次注滿（非緩慢繞圈手沖），
                            # Bonavita 中高速 ~12 ml/s 為合理預設
                            # pour_time = water_ml / POUR_RATE
                            # pour_offset = pour_time / 2（線性注水的平均接觸延遲）
                            # Standard 200ml：pour_time=16.7s → offset=8.3s
                            # XL 400ml：pour_time=33.3s → offset=16.7s
                            # 影響量級：XL 60s 浸泡時 EY −3.1%（結構性偏差），120s 時 −1.0%
                            # 此為系統性偏差（永遠高估浸泡時間），且可以秤+計時器實測校正
SWIRL_TIME_SEC    = 5      # v4.8 修正：真實操作時間（約 3 下旋轉，5 秒）
                             # 原始值 10 秒偏長，與 Hoffman 法實際手法不符
                             # 注意：操作時間與動力學等效補償已正式分離（見 SWIRL_CONVECTION_BASE）
# SWIRL_WAIT_SEC 已從固定常數改為動態函數（v4.3，見 §6 calc_swirl_wait）
SWIRL_WAIT_BASE   = 30     # v4.3：動態靜置時間基準（dial=4.5 時 30s，斯托克斯沉降原理）
SWIRL_WAIT_SLOPE  = 10     # v4.3：每格研磨增減 10 秒（細粉等更久、粗粉等更短）
SWIRL_WAIT_MIN    = 10     # v4.3：物理下限（粗粉最快 10s 沉底）
SWIRL_WAIT_MAX    = 45     # v4.3：物理上限（極細粉 45s 足以建立粉床）
                             # calc_swirl_wait(dial) = clamp(30 + (4.5-dial)×10, 10, 45)
                             # dial=3.5→40s；dial=4.5→30s；dial=6.5→10s
SWIRL_CONVECTION_BASE = 1.0   # v4.8 調整：從 0.5 升至 1.0，確保動力學等效補償維持不變
                                # 設計邏輯：SWIRL_TIME_SEC（操作時間）× swirl_mult（對流倍率）= 等效補償時間
                                # dose=18g：5s × (1 + 1.0 × 18/18) = 5 × 2.0 = 10s 等效（與 v4.7 相同）
                                # dose=24g：5s × (1 + 1.0 × 18/24) = 5 × 1.75 = 8.75s 等效
                                # dose=30g：5s × (1 + 1.0 × 18/30) = 5 × 1.60 = 8.0s 等效
                                # v4.7 舊值（BASE=0.5）：dose=18g → 10×1.5=15s；dose=30g → 10×1.3=13s
                                # v4.8 調整後（BASE=1.0）：dose=18g → 5×2.0=10s；dose=30g → 5×1.6=8s
                                # 注意：大豆量的等效補償略微降低（13s→8s），
                                # 物理上合理——5 秒的 Swirl 在高黏滯漿體中效率本就有限
SWIRL_DOSE_REF    = 18.0       # 對流倍率的基準豆量（g）；swirl_mult 在此豆量時為最大值

# ── 壓降時間（動態函數 calc_press_time(dose, dial)，見 §6）──
PRESS_TIME_MIN_FLOOR = 15  # v4.2 新增：物理安全下限（均勻施壓最少需要 15s）
PRESS_TIME_MIN    = 30     # 基準增量起點（18g 基礎壓降時間）
PRESS_TIME_MAX    = 90     # v4.0：從 60 升至 90（達西定律修正後，大豆量極細粉需要容忍空間）
PRESS_TIME_PER_G  = 2
DARCY_PRESS_EXP   = 0.6    # v4.0 新增：達西指數壓降倍率，dial_modifier = exp((4.5-dial)×0.6)
                             # dial=3.5 → 1.82×；dial=4.5 → 1.00×；dial=6.5 → 0.30×
                             # v4.2 Bug Fix：dial_modifier 現在乘以完整時間（含基礎 + 增量）
                             # 而非僅乘增量，18g 極細粉的基礎阻力不再被錯誤歸零
BED_COMPACTION_COEFF = 0.15  # v5.5 新增：粉床時間壓實修正係數
                              # v5.6：compaction_mult 改以 effective_compaction_time 計算
                              #   compaction_mult = 1.0 + (effective_compaction_time / 240) × 0.15
                              # 物理依據：斯托克斯沉降使細粉隨浸泡時間遷移至濾紙面，
                              # 形成緻密阻水層；Swirl 部分重置（見 SWIRL_RESET_FRACTION）
                              # 長浸泡使 Stall 機率上升，連動 apply_channeling 提升 CGA
SWIRL_RESET_FRACTION = 0.35   # v5.6 新增：Swirl 粉床重置比例（理論推導值）
                               # 物理依據：斯托克斯沉降 + 渦流雷諾數分析
                               #   Re ≈ 500（層流邊界）→ 可懸浮粒徑 < 80μm 顆粒
                               #   < 80μm 顆粒佔細粉層約 35%，剩餘 65% 嵌入間隙不被重置
                               # effective_compaction_time = steep_sec × (1 − SWIRL_RESET_FRACTION)
                               #                             + swirl_wait_sec
                               # 範例（dial=4.5，swirl_wait=30s）：
                               #   steep=60s  → eff = 60×0.65+30 = 69s（vs 舊值 60s）
                               #   steep=120s → eff = 120×0.65+30 = 108s（vs 舊值 120s）
                               #   steep=240s → eff = 240×0.65+30 = 186s（vs 舊值 240s）
                               # §14：來源為流體力學理論推導，待實測校正

# ── 動態截留係數（v4.3：烘焙度 × 研磨度二元函數，見 §6）────
RETENTION_BASE = {               # dial=4.5 時各焙度的基準截留值（g 水 / g 豆）
    'very_light': 1.95, 'light': 2.05, 'medium_light': 2.15,
    'medium':     2.25, 'moderately_dark': 2.35, 'dark': 2.45, 'very_dark': 2.55,
}
RETENTION_DIAL_SLOPE = {         # 研磨度修正斜率（每格刻度的截留增量）
    'very_light': 0.10, 'light': 0.10, 'medium_light': 0.10,
    'medium':     0.10, 'moderately_dark': 0.09, 'dark': 0.08, 'very_dark': 0.07,
}
# 深焙豆孔隙率高，研磨斜率略低（結構疏鬆，顆粒不規則性對截留邊際效應較小）
# retention = RETENTION_BASE[roast] + (4.5 - dial) × RETENTION_DIAL_SLOPE[roast]
# 夾緊至 [1.60, 2.80]
# 範例：L+ dial=3.5 → 2.10；M dial=4.5 → 2.30；D dial=6.5 → 2.34

# ── 咖啡因動力學常數（v4.3 新增）────────────────────────────
K_CA = 0.030   # 咖啡因一階萃取速率常數（/秒）
               # ca_extraction = 1 - exp(-K_CA × steep_sec)
               # steep=90s → 93% 飽和；steep=150s → 99%；steep=240s → 99.9%
               # 解耦總 EY 線性綁定，反映咖啡因「快速溶出、提早飽和」的化學本質

# ── EY 雙峰動力學——細粉率（函數化，見 calc_fines_ratio）──
FINES_RATIO_BASE       = 0.15
FINES_RATIO_DIAL_SLOPE = 0.04
# calc_fines_ratio(dial) = 0.15 + (4.5 - dial) × 0.04
# dial=3.5 → 19% | dial=4.5 → 15% | dial=6.5 → 7%（夾緊 5%–35%）

# ── EY 雙峰動力學——速率倍率 ────────────────────────────
K_FINES_MULT      = 10.0
K_BOULDERS_MULT   = 0.55

# ── 熱平衡失溫修正 ────────────────────────────────────────
# SLURRY_TEMP_DROP_PER_G = 0.15  # DEPRECATED（v5.8r：改以比熱混合方程式取代）
                                   # 舊線性公式 t_slurry = temp - dose×0.15 - 2.5 忽略 water_ml，
                                   # 導致 Standard(200ml) 與 XL(400ml) 同一豆量得到相同 t_slurry
                                   # 這在雙機型設計下是結構性錯誤（18g 冷卻 200ml 幅度 > 400ml）
COFFEE_SPECIFIC_HEAT_RATIO = 0.33  # v5.8r 新增：咖啡熟豆比熱 / 水比熱（無量綱）
                                    # 咖啡熟豆 c ≈ 1.4 J/(g·K)，水 c ≈ 4.18 J/(g·K)
                                    # 比值 ≈ 0.33（文獻值 0.30–0.38，取中間偏低）
                                    # 混合溫度：t_mix = (water_ml×T_w + dose×0.33×T_ENV) / (water_ml + dose×0.33)
                                    # t_slurry = t_mix − BREWER_TEMP_DROP
                                    # 驗算（M 92°C）：
                                    #   XL 400ml 22g: t_mix=(400×92+7.26×25)/407.26 = 90.8°C → t_slurry=88.3°C
                                    #   Std 200ml 14g: t_mix=(200×92+4.62×25)/204.62 = 90.5°C → t_slurry=88.0°C
                                    #   XL 400ml 30g: t_mix=(400×92+9.90×25)/409.90 = 90.4°C → t_slurry=87.9°C
                                    # 舊線性：22g→86.2°C（差 2.1°C）；30g→85.0°C（差 2.9°C）
BREWER_TEMP_DROP       = 2.5   # 塑膠機身熱容吸熱固定常數（°C，v3.9 新增）
                                 # 物理依據：ΔT_水 ∝ m_塑膠 / m_水；XL 與標準版的
                                 # 塑膠質量與注水量等比例放大，比值不變，
                                 # 故失溫幅度與機型無關，普適約 2–3°C，取 2.5°C。
# v5.8r：比熱混合方程式（見 COFFEE_SPECIFIC_HEAT_RATIO）
# t_mix = (water_ml × T_w + dose × 0.33 × T_ENV) / (water_ml + dose × 0.33)
# t_slurry = t_mix − BREWER_TEMP_DROP
# 100°C + 30g/XL → t_mix = (400×100 + 9.9×25)/409.9 = 98.2°C → t_slurry = 95.7°C

# ── EY 溫度模型常數 ───────────────────────────────────────
# ⚠️ AGENT 實作指示：T_ENV 與 TDS_BROWN_WATER_FLOOR 為「使用者環境參數」，
# 必須透過 CLI 參數注入，不得硬編碼。實作時須：
# 1. 解析 CLI 參數 --t-env（float，預設 25.0）後以 T_ENV = args.t_env 覆寫此行
# 2. 解析 CLI 參數 --tds-floor（float，預設 0.80）後以 TDS_BROWN_WATER_FLOOR = args.tds_floor 覆寫此行
# 兩者影響所有溫度計算與評分下限，屬首批啟動前必須確認的個人化常數。

T_ENV             = 25.0   # 環境室溫（°C）——由 CLI --t-env 覆寫（預設 25.0）
                            # 影響：①t_slurry（粉末初溫假設 = T_ENV）
                            #       ②牛頓冷卻終態溫度（漸近線 = T_ENV）
                            # 冬天寒流（15°C）vs 夏天冷氣房（25°C）差 10°C
                            # → t_slurry 差 ≈ 0.5°C；長浸泡冷卻速率差異更大
                            # 量測方式：用溫度計量測沖煮當下室溫即可，免費且即時
COOL_RATE         = 0.0008      # v5.3 修正：牛頓冷卻速率常數（/s）
                                 # v5.2 以前的 0.02 意味 120s 後水溫降至 31°C（荒謬）
                                 # 熱力學估算 r = hA/(mc) ≈ 0.00012（理論值）
                                 # 實測合理範圍 0.0005–0.001（取決於活塞密封程度）
                                 # 取 0.0008：對應 120s 降溫 5.9°C（90→84.1°C）
                                 # 修正後 T_eff 從虛幻的 51°C 回升至 87°C（M 焙 120s）
                                 # 長浸泡參數的鑑別力大幅提升，EY 輸出更符合實際沖煮經驗
                                 # 精確值需以 §15 第 2 點的實測方案校正
K_BASE            = 0.025       # v5.5 校準：90°C 基準速率常數
                                 # v5.2 原值 0.010 在舊 COOL_RATE=0.02 下「恰好」能產出合理 EY，
                                 # 但 v5.3 修正 COOL_RATE（→0.0008）+ v5.4 T_avg 修正後，
                                 # EY_max 天花板從虛幻的 ~15% 回升至真實的 ~25%，
                                 # 舊 K_BASE 太慢，M 焙基準配方僅產出 EY=12.5%（不可飲用）。
                                 # 二元搜尋校準：以 M 焙 92°C/dial4.5/120s/22g → EY≈19% 為目標，
                                 # K_BASE ≈ 0.023–0.025。取 0.025 為暫定值，待折射儀實測校正。
K_MIN             = 0.006       # v5.5 校準：速率常數下限夾緊
                                 # v5.2 原值 0.003 在 D 焙低溫場景（T_avg≈76°C）下過度限制，
                                 # 導致深焙 EY 系統性偏低（~13%）。上調至 0.006 緩解下限瓶頸，
                                 # 待 D 焙實測 TDS 後精確校正。
K_MAX             = 0.060
DIAL_BASE         = 4.5
EY_ABSOLUTE_MAX   = 28.0
EY_MIN            = 14.0

# ── 阿瑞尼斯動態速率修正（v5.2 新增）─────────────────────────
ARRHENIUS_COEFF = 0.05  # 溫度每升高 1°C，萃取速率常數增加約 5%
                         # k_base_dynamic = K_BASE × exp((T_avg − 90) × 0.05)
                         # v5.4：以 T_avg（牛頓冷卻定積分時間平均溫度）為輸入，
                         # 修補 v5.2 以 t_slurry（起始最高溫）為輸入的恆溫假設偏差
                         # 物理依據：固液擴散遵循阿瑞尼斯方程式 k ∝ exp(−Ea/RT)

# ── 有限溶劑濃度梯度修正（v5.5 新增）────────────────────────
CONC_GRADIENT_COEFF = 0.5  # 溶質分配係數 K_d（批次平衡方程式）
                            # brew_capacity = WATER_ML / (WATER_ML + dose × K_d)
                            # 18g → 0.978（−0.9%）；24g → 0.971（−1.4%）；30g → 0.964（−1.5%）
                            # 物理依據：有限溶劑中 TDS 上升壓抑濃度梯度驅動力
                            # K_d=0.5 極保守，咖啡可溶物在水中溶解度極高
                            # 18g→30g 差異僅 ~0.6%，在搜尋空間中屬微弱修正

# ── 動態截留係數（v4.3：見 §6 calc_retention）──────────────────
# retention = RETENTION_BASE[roast] + (4.5 - dial) × RETENTION_DIAL_SLOPE[roast]
# 夾緊至 [1.60, 2.80]

# ── 風味評分常數 ──────────────────────────────────────────
CONC_HUBER_DELTA           = 0.5
BALANCE_PENALTY_WEIGHT     = 0.15   # AC/SW 甜酸比（v3.7）
BODY_BITTER_PENALTY_WEIGHT = 0.18   # PS/(CA+CGA+MEL×coeff) 醇苦比（v5.10：0.12→0.18，強化醇苦比懲罰）

MEL_BITTER_COEFF = {               # MEL 進入苦澀分母的焙度依賴係數（v3.9 新增）
    'very_light': 0.0,              # 淺焙 MEL 極少，不計入苦澀
    'light':  0.0,
    'medium_light': 0.0,
    'medium':  0.0,
    'moderately_dark': 0.5,         # 中深焙 MEL 開始顯著貢獻焦苦
    'dark':  0.5,                   # 深焙焦苦（Ashy/Roasty）明顯
    'very_dark': 0.5,               # 極深焙傳承 dark 的焦苦麥分度
}
# 醇苦比分母：CA + CGA + MEL × MEL_BITTER_COEFF[roast_code]
# very_light → medium：分母不含 MEL
# moderately_dark → very_dark：分母加入 MEL × 0.5，抑制深焙高萃取組合的過度獎勵

# ── 感知過濾器常數（v4.1 更新）─────────────────────────────
KH_PERCEPT_DECAY = 150   # v4.1：取代 v4.0 的 KH_ACID_PERCEPT_COEFF=500
                          # kh_penalty = max(0.65, exp(-water_kh / 150))
                          # 指數衰減擬合 Henderson-Hasselbalch 緩衝曲線：
                          #   KH=0 → 1.000；KH=30 → 0.819；KH=80 → 0.588 → 夾緊 0.65

# ── 非對稱 Huber Loss 係數（v4.0 新增）───────────────────
ASYM_BITTER_MULT = 1.8  # v5.10：CA/CGA 過量（actual > ideal）時的懲罰倍率（1.5 →1.8，加強苦味懲罰）
ASYM_SWEET_MULT  = 1.5  # SW 不足（actual < ideal）時的懲罰倍率
# 反映人類感官非對稱性：苦澀過量的破壞力遠大於苦澀不足；甜感不足是缺陷

# ── 全局 TDS 高斯偏好懲罰（v4.1 新增）───────────────────
TDS_PREFER = {            # 各焙度人類偏好的 TDS 峰值（%）——v5.10 下修（偏日常適飲）
    'very_light': 1.27, 'light': 1.27,        # 淺焙：保留酸質突出感
    'medium_light': 1.22, 'medium': 1.17,     # 中淺/中焙：均衡區間
    'moderately_dark': 1.12, 'dark': 1.10,    # 中深/深焙：稍低以抑制焦苦
    'very_dark': 1.07,                        # 極深焙：最低濃度偏好，片少焦苦
}
TDS_GAUSS_SIGMA_LOW  = 0.15  # v4.2：低於目標時（水感），衰減快，嚴格懲罰
TDS_GAUSS_SIGMA_HIGH = 0.20  # v5.10：收緊過濃懲罰（原 0.25 → 0.20），對應實測「過於濃烈」
                              # 感官依據：TDS 偏低（空洞水感）是不可逆缺陷；
                              #           TDS 偏高可加冰/加水補救，容忍度更高
# TDS_PREFER_WEIGHT = 0.10  # DEPRECATED（v5.0 已被 TDS_W3_LOW/HIGH 動態雙權重取代）

# ── 多糖體一階動力學常數（v5.1：修復 PS 線性時間破窗）──────
K_PS        = 0.005   # PS 緩速擴散速率常數（/s）；大分子（MW>10,000 Da）極慢擴散
PS_TIME_MAX = 0.20    # PS 時間項最大貢獻值（240s 時約 0.090，遠低於舊線性 0.24）
# 舊線性公式：PS += max(steep_sec-120, 0) × 0.002（到達 1.0 前無上界）
# 新漸近公式：PS += 0.20 × (1 − exp(−0.005 × extra_time))
# 對比：steep=240s 時，舊公式 +0.24，新公式 +0.090；更保守且物理正確

# ── CGA 一階動力學時間漸近線（v5.3：封堵線性時間破窗）─────────
K_CGA_TIME    = 0.015   # CGA 時間項萃取速率常數（/s）
CGA_TIME_MAX  = 0.50    # CGA 時間項最大乘數貢獻（飽和值）
# 舊線性公式：CGA *= 1 + max(steep-150, 0) × 0.004（600s 時飆至 2.8×，無界！）
# 新漸近公式：CGA *= 1 + 0.50 × (1 − exp(−0.015 × extra))
# 校準：240s 時新值 1.370 vs 舊值 1.360（搜尋空間內完美匹配）
# 長時間收斂至 1.50×（物理飽和），消除外推爆炸風險

# ── AC 相對衰減指數化（v5.3：封堵線性衰減負值 Bug）────────────
K_AC_DECAY    = 0.0035  # AC 時間項指數衰減速率（/s）
# 舊線性公式：AC *= 1 − max(steep-150, 0) × 0.003（steep > 483s 時 AC 變負！）
# 新指數公式：AC *= exp(−0.0035 × extra)（永不為負）
# 校準：240s 時新值 0.730 vs 舊值 0.730（精確匹配）
# 語意不變：長浸泡後其他物質湧出，AC 在六維向量中的相對比重指數下降

# ── CGA 澀感指數懲罰（v5.1：生物閾值連續函數，取代 Huber 不敏感問題）──
CGA_ASTRINGENCY_THRESHOLD = 1.25   # 觸發澀感指數懲罰的 CGA 倍率閾值（相對理想值）
                                     # 低於 1.25× ideal：走正常 ASYM_BITTER Huber Loss
                                     # 超過 1.25× ideal：額外觸發指數衰減懲罰乘數
                                     # 生物依據：CGA 與唾液 PRP（富含脯氨酸蛋白）結合沉澱
                                     # 閾值以下幾乎察覺不到；超過後口腔潤滑瞬間失效
CGA_ASTRINGENCY_SLOPE     = 4.0    # 指數懲罰陡峻係數（越大閾值後曲線越陡）
                                     # excess_ratio = actual/（ideal×1.25）- 1
                                     # penalty = exp(−SLOPE × excess_ratio²)
                                     # excess=0（剛達閾值）→ penalty=1.00（無額外懲罰）
                                     # excess=0.20（超標 20%，即 actual/ideal=1.50）→ 0.852
                                     # 等效 actual/ideal 倍率的感知效果：
                                     #   1.50× → penalty ≈ 0.75（扣 25%）
                                     #   1.75× → penalty ≈ 0.37（扣 63%，等同斬首）
                                     # 函數連續，但閾值後陡峻，無評分斷崖

# ── 酸澀協同劣變懲罰（v5.5 新增）──────────────────────────
HARSHNESS_SLOPE = 4.0   # AC×CGA 交叉乘積指數懲罰斜率（與 CGA_ASTRINGENCY_SLOPE 設計一致）
                         # harshness_product = max(AC/ideal-1, 0) × max(CGA/ideal-1, 0)
                         # penalty = exp(−4.0 × harshness_product)
                         # 單維超標（乘積=0）不觸發；雙維同時超標觸發交叉懲罰
                         # AC=1.3×+CGA=1.3× → product=0.09 → penalty=0.698（−30%）
                         # AC=1.5×+CGA=1.5× → product=0.25 → penalty=0.368（−63%）
                         # 口腔化學依據：高酸+高澀在缺乏甜感包覆時產生「金屬味/胃酸」
                         # 的毀滅性交互作用（Harshness），為乘積性非加法性效應

# ── 高溫揮發芳香逸散（v5.7 新增）──────────────────────────
SW_AROMA_SLOPE   = 0.02  # 每 1°C 超過 95°C，SW 感知衰減 2%
SW_AROMA_THRESH  = 95.0  # 觸發閾值（°C）；v5.8 修正：使用 temp_initial（壺溫），非 t_slurry
SW_AROMA_CAP     = 0.30  # 最大衰減上限 30%（防止極端高溫完全斬首甜感）
                          # 物理依據：揮發性芳香物質（Linalool、Furaneol 等花香/果甜來源）
                          # 在 >95°C 時熱降解速率加快，且高溫蒸氣攜帶更多揮發物逸散
                          # 此效應與 predict_compounds 的 SW 溶出拋物線正交：
                          #   溶出層：高溫多溶出焦糖化產物（質量層）
                          #   逸散層：高溫揮發性香氣損失（感知層，作用於 actual_perceived['SW']）
                          # 適用場景：L+ 以 t_slurry=98°C 沖煮 → SW 感知 × 0.94（−6%）
                          #            L+ 以 t_slurry=100°C 沖煮 → SW 感知 × 0.90（−10%）
                          # §14：SW_AROMA_SLOPE=0.02 及閾值 95°C 為感官化學估算值，非盲測數據

# ── 深焙焦澀協同懲罰（v5.7 新增，第 8 層）────────────────────
ASHY_SLOPE       = 3.0   # MEL×CGA 交叉乘積指數懲罰斜率
                          # 低於酸澀協同（4.0）：焦澀感官閾值約比酸澀高 25%
                          # penalty = exp(−3.0 × mel_excess × cga_excess)
                          # 僅對 moderately_dark/dark/very_dark 焙度啟用（深焙 AC 極低，無法觸發 AC×CGA 層）
                          # MEL=1.3×+CGA=1.3× → product=0.09 → penalty=0.763（−23%）
                          # MEL=1.5×+CGA=1.5× → product=0.25 → penalty=0.472（−53%）
                          # 感官化學依據：類黑素（Melanoidins）與多酚（CGA）競爭唾液
                          # PRP 結合位點，同時過萃時產生「煙灰/燒焦橡膠」的感官崩潰；
                          # 補足酸澀協同對深焙的盲區，完成完整八層評分架構
                          # §14：ASHY_SLOPE=3.0 為感官化學推導值，非盲測數據

# ── 水質鈣鎂比例（v5.1：GH Ca²⁺/Mg²⁺ 離子分軌）───────────────
MG_FRAC_AC_SW_MULT = 0.16  # Mg²⁺ 比例對 AC/SW 的最大正向乘數（mg_frac=1 時 AC/SW ×1.16）
MG_FRAC_PS_CGA_MULT = 0.08 # Ca²⁺ 比例對 PS/CGA 的最大正向乘數（mg_frac=0 時 PS/CGA ×1.08）
# 物理依據：Mg²⁺（帶電半徑小）與極性小分子（有機酸、游離糖）親和力高；
#           Ca²⁺（偏向大分子）傾向萃取多糖體、加速綠原酸溶出
# 設計：乘數範圍 ±8%，不破壞現有評分量級；mg_frac=0.5（預設）時修正為 0，與 v5.0 行為相同
DIAL_STEP         = 0.1
STEEP_STEP        = 15

# ── 溫度物理邊界（v4.4 新增）────────────────────────────────
TEMP_BOILING_POINT = 100   # 標準大氣壓下液態水的物理上限（°C）——由 CLI --altitude 自動計算覆寫
                             # 搜尋迴圈上限：min(base_temp + 3, TEMP_BOILING_POINT)
                             # ⚠️ AGENT 實作指示：解析 CLI --altitude（float，預設 0.0，單位公尺）後自動計算：
                             #   TEMP_BOILING_POINT = 100.0 - altitude / 300.0
                             #   （每升高 300m 沸點降約 1°C，SCA 標準近似）
                             #   花蓮市區（altitude≈10m）：99.97°C，差異可忽略
                             #   合歡山主峰（altitude≈3416m）：88.6°C，影響顯著
                             # ★必實作（但預設值 0m 對平地使用者零影響）

# ── 高溫劣變感知懲罰（Scorching Penalty，v4.5：連續焙度閾值矩陣，取代 v4.4 硬切）──
SCORCH_PARAMS = {
    # (threshold_°C, cga_sensitivity/°C, mel_sensitivity/°C)
    # threshold：超過此溫度才觸發懲罰
    # cga_sensitivity：CGA 感知放大斜率（所有焙度，依據 CGA 高溫水解化學）
    # mel_sensitivity：MEL 感知放大斜率（淺焙 MEL 極少設為 0.0，僅 moderately_dark/dark/very_dark 生效）
    'very_light': (100, 0.00, 0.00),  # 沸點夾緊後永不觸發，關閉
    'light':  (100, 0.00, 0.00),  # 同上，關閉
    'medium_light': ( 97, 0.05, 0.00),  # 接近搜尋上限（98°C）時輕微懲罰
    'medium':  ( 95, 0.08, 0.00),  # 搜尋上限（95°C）即觸發，適度懲罰
    'moderately_dark': ( 91, 0.15, 0.10),  # 搜尋上限（91°C）即觸發，嚴格懲罰 CGA + MEL
    'dark':  ( 88, 0.20, 0.15),  # 搜尋上限（88°C）即觸發，最嚴格
    'very_dark': ( 85, 0.25, 0.20),  # 極深焙：閾值更低，懲罰更嚴層
}
# 物理依據：CGA 高溫水解（→奎尼酸+咖啡酸→乙烯基兒茶酚，尖銳澀感）對所有焙度有效；
# MEL 焦炭調性惡化（Ashy/Scorched）主要在深焙高濃度 MEL 下顯著。
# 連續函數取代 v4.4 的 if MD/D 硬切，消除 M→MD 邊界的評分斷崖。

# ── 通道效應物理懲罰（Channeling Penalty，v4.5 新增）────────
CHANNELING_PRESS_THRESHOLD = 60  # 超過此壓降時間（秒）觸發通道效應懲罰
CHANNELING_EY_SLOPE        = 0.005  # 每超過 1s 降低 0.5% 的巨觀 EY（水流 Bypass）
CHANNELING_CGA_MULT        = 2.5    # 通道效應局部過萃導致 CGA 感知非線性放大倍率
CHANNELING_BYPASS_MAX      = 0.15   # bypass_ratio 上限（最多 15% 的水走旁路）
# 物理依據：極細粉+大豆量高壓場景下，水沿阻力最小路徑繞道（Channeling），
# 導致局部粉層過萃（CGA飆升）同時粉餅死角完全未萃取，整體 EY 下降。
# calc_press_time > 60s 是 Stall 邊界的代理指標。
CHANNELING_COLLAPSE_RATIO  = 0.20   # v5.2 新增：通道貫穿後阻力崩潰的時間折算比
                                      # 超過 60s 的部分，因通道形成物理阻力瓦解，
                                      # 使用者實際操作時間僅剩原本的 20%
                                      # display_press_sec = 60 + (press_sec - 60) × 0.20
                                      # 內部 press_sec 不變（仍為嚴重度代理指標）
                                      # press_sec=70 → display=62s；press_sec=90 → display=66s

# ── 壓降等效時間折算（Press-Phase Equivalent Time，v5.3 重構）─────
PRESS_EQUIV_FRACTION = 0.15   # 壓降效率折算比（相對被動浸泡的萃取效率）
                               # press_equiv = display_press_sec × 0.15（v5.4：基於阻力崩潰後的真實接觸時間）
                               # 物理依據：壓降期間水流穿過粉餅，溫度低、流速非恆定，
                               # 萃取效率遠低於靜態浸泡，估算約 15%
                               # 注入 calc_ey（t_kinetic 延伸）與 predict_compounds（effective_steep）
                               # 動力學方程式自動處理差異萃取：CA 已飽和（+0.6%），PS 未飽和（+4.4%）
```

---

## 1. 先決條件（使用者輸入）

| 輸入項 | 型別 | 建議範圍 | 說明 |
|---|---|---|---|
| `brewer_size` | str | `standard` / `xl` | **愛樂壓機型**（v5.5r 新增）：標準版 200ml / XL 400ml；決定注水量與豆量搜尋範圍 |
| `roast_code` | str | `very_light` / `light` / `medium_light` / `medium` / `moderately_dark` / `dark` / `very_dark` | 烘焙度代號（SCA 7 選 1） |
| `water_gh` | int | 0 – 300（ppm CaCO3） | **用水總硬度**（Ca²⁺ + Mg²⁺）；最佳區間 40–100 ppm。 |
| `water_kh` | int | 0 – 150（ppm CaCO3） | **碳酸鹽硬度（KH）**；中和有機酸，建議 ≤ 50 ppm。 |
| `water_mg_frac` | float | 0.0 – 1.0 | **GH 中鎂離子比例**（v5.1 新增）；Mg²⁺ 萃取 AC/SW，Ca²⁺ 萃取 PS/CGA。預設 0.40（台灣自來水 Ca 偏多）。 |

> **目標 TDS 不由使用者指定**——程式直接搜尋四向量空間，計算每組合的實際 TDS，取最高評分輸出。

---

## 1.1 水質快選預設（Water Presets）

```python
WATER_PRESETS = {
    # --- 💧 基準水與原液 (Baselines & Concentrates) ---
    "ro": {
        "name": "RO 純水（逆滲透）", "gh": 2, "kh": 2, "mg_frac": 0.50,
        "note": "近乎純水。作為所有配方的歸零畫布與稀釋基底。"
    },
    "aquacode_7l": {
        "name": "Aquacode（1包 + 7L RO 水）", "gh": 65, "kh": 5, "mg_frac": 0.73,
        "note": "SCA 賽事標準。極低 KH (無緩衝)，高鎂。風味解析度極高，適合極淺焙競賽豆。"
    },
    "dr_you_jeju_yongamsoo": {
        "name": "Dr.You 濟州熔岩水", "gh": 202, "kh": 178, "mg_frac": 0.18,
        "note": "極硬水，鈣主導。作為厚實度 (Body) 與焙烤香氣的鈣質補充原液。"
    },
    "tamsaa_jeju_water_j_creation": {
        "name": "TAMSAA 濟州探沙水", "gh": 100, "kh": 133, "mg_frac": 0.76,
        "note": "天然純鎂主導。提亮果酸與甜感，作為鎂質補充原液。"
    },
    "volvic_pure": {
        "name": "Volvic 富維克天然礦泉水", "gh": 62, "kh": 58, "mg_frac": 0.40,
        "note": "鈣鎂均衡。免兌水可直接沖煮，偏高的 KH 提供強大避震效果，口感圓潤扎實。"
    },

    # --- 🏆 排列組合最佳勾兌前 3 名 (Top 3 Signature Blends) ---
    "top1_tamsaa_sweetness": {
        "name": "🥇 Top 1：極致甜感果汁配方（1 探沙 + 2 RO）",
        "gh": 35, "kh": 46, "mg_frac": 0.75,
        "note": "【長浸泡首選】中等 KH 作為完美避震器修飾澀感，極高鎂比例抓取果酸。能創造爆發性的果汁甜感。"
    },
    "top2_volvic_balance": {
        "name": "🥈 Top 2：柔和降酸明亮配方（2 富維克 + 1 RO）",
        "gh": 42, "kh": 39, "mg_frac": 0.40,
        "note": "【高階微調】解除 Volvic 原本過高 KH 對酸值的封印。保留扎實的核果骨架，同時讓淺焙的明亮酸值跳出來。"
    },
    "top3_jeju_structure": {
        "name": "🥉 Top 3：濟州均衡骨架配方（1 好麗友 + 2 探沙 + 7 RO）",
        "gh": 42, "kh": 46, "mg_frac": 0.47,
        "note": "【全能通吃】鈣鎂完美平衡。借 Dr.You 撐起立體骨架，探沙補足甜感，適合中淺焙到中焙豆展現複雜層次。"
    }
}

def get_water_preset(preset_key: str) -> dict:
    if preset_key not in WATER_PRESETS:
        raise ValueError(f"未知水質預設 '{preset_key}'。可用：{', '.join(WATER_PRESETS.keys())}")
    return WATER_PRESETS[preset_key]
```

> **Preset key（8 個）：** `ro` `aquacode_7l` `dr_you_jeju_yongamsoo` `tamsaa_jeju_water_j_creation` `volvic_pure` `top1_tamsaa_sweetness` `top2_volvic_balance` `top3_jeju_structure`

---

## 2. 烘焙度設定表（Roast Table）

```python
ROAST_TABLE = {
    'very_light':     {'name': 'Light/Cinnamon (Agtron #85-95)', 'base_temp': 100, 'base_ey': 17.0},
    'light':          {'name': 'Medium (Agtron #75)',           'base_temp': 99,  'base_ey': 17.0},
    'medium_light':   {'name': 'High (Agtron #65)',             'base_temp': 95,  'base_ey': 19.0},
    'medium':         {'name': 'City (Agtron #55)',             'base_temp': 92,  'base_ey': 19.0},
    'moderately_dark':{'name': 'Full City (Agtron #45)',        'base_temp': 88,  'base_ey': 21.0},
    'dark':           {'name': 'French (Agtron #35)',           'base_temp': 85,  'base_ey': 21.0},
    'very_dark':      {'name': 'Italian (Agtron #25)',          'base_temp': 82,  'base_ey': 21.5},  # v5.x 新增
}
```

---

## 3. 四向量搜尋空間

| 向量 | 符號 | 範圍 | 步長 | 說明 |
|---|---|---|---|---|
| 水溫 | `T` | `base_temp ± 3°C`，**上限夾緊至 100°C** | 1°C | v4.4 Bug Fix：L+ base_temp=100 時防止產生 101–103°C 虛構參數 |
| 研磨刻度 | `G` | 3.5 – 6.5 | 0.1 | ZP6 實際可調範圍 |
| 被動浸泡時間 | `S` | 60 – 240 秒 | 15 秒 | Hoffman 基準 120s |
| 豆量 | `D` | **標準版 9–18g / XL 18–30g** | 0.5 g | 第四向量；範圍依機型自動切換 |
| （固定） | — | 旋轉 **5s**（v4.8）+ 靜置 30s | — | 旋轉進入 t_kinetic（見 §5） |
| （動態） | — | 壓降 30–60s | — | `calc_press_time(dose, dial, steep_sec)` |

> **搜尋空間大小：** 標準版 7 × 31 × 13 × 19 = **53,599 組合**；XL 7 × 31 × 13 × 25 = **70,525 組合**

---

## 4. Hoffman 法標準沖煮流程

> **與標準 Hoffman 法的差異：** ①支援 AeroPress 標準版（200ml）與 XL（400ml）；②壓降時間依豆量與研磨度動態調整（30–60 秒）。

### 4.1 核心原則

- 正置（Standard Position）非倒置；插入活塞 1cm 製造真空止滴
- 旋轉（Swirl）在浸泡結束後 10 秒，靜置 30 秒後壓降
- 不潤濕濾紙、不預熱機身
- 輕柔均勻施壓穿過嗤聲壓到底

### 4.2 完整步驟

```
步驟 1  T=0:00             AeroPress 正置，裝濾紙（無需潤濕）、裝研磨粉（豆量 D）
步驟 2  T=0:00             注入 water_ml 熱水（標準版 200ml / XL 400ml），插入活塞 1cm 防滴
步驟 3  T=0:00–S           被動浸泡 steep_sec 秒
步驟 4  T=S                輕柔旋轉 **5 秒**（Swirl，v4.8 定值）——強制對流，邊界層撕裂，萃取突波
步驟 5  T=S+10             靜置 calc_swirl_wait(dial) 秒（v4.3：10–45s，研磨度動態化）
步驟 6  T=S+40             緩慢下壓 calc_press_time(dose, dial) 秒，壓到底穿過嗤聲
步驟 7  T=S+40+press_sec   Contact End
```

### 4.3 接觸時間定義

| 階段 | 時長（秒） | 動力學處理 |
|---|---|---|
| **注水** | **標準版 ~17s / XL ~33s** | **v5.5r：扣除平均接觸延遲 `pour_offset = pour_time/2`（線性注水，第一滴 t=0、最後一滴 t=pour_time）；Standard −8.3s / XL −16.7s** |
| 被動浸泡 | 60–240（可調）| 主要積分時間（已扣除 pour_offset）|
| 旋轉 Swirl | **5（v4.8 修正，SWIRL_TIME_SEC 常數值）**| 等效 10s（dose=18g 時 ×2.0 對流倍率），計入 t_kinetic |
| 靜置 | **10–45（v4.3 動態，依 dial）** | 未計入動力學（斯托克斯沉降，粉床建立）|
| 壓降 | 15–90（動態）| **v5.3：以 `press_equiv = display_press_sec × 0.15` 注入 calc_ey 與 predict_compounds**；Channeling 懲罰獨立作用；**v5.2：輸出顯示 `display_press_sec`** |

### 4.4 研磨度參考

> **系統設計說明：** 底層物理公式（細粉率、截留係數、達西壓降）以 **1Zpresso ZP6 刻度（3.5–6.5）** 為錨點設計。使用其他磨豆機時，請查下表換算 ZP6 等效刻度後輸入 `--dial` 參數。等效刻度為實戰估算值，建議以折射儀量測 EY 後微調校正。

| 磨豆機 | 淺焙原始刻度 | 中焙原始刻度 | **建議 ZP6 等效刻度** |
|---|---|---|---|
| 1Zpresso ZP6 | 3.5–4.5 | 4.5–5.5 | **直接輸入，無需換算** |
| 1Zpresso JX Pro | 3.2.0 | — | ≈ 4.0–4.5 |
| 1Zpresso JX | 42–48 clicks | — | ≈ 3.8–4.5 |
| 1Zpresso K-max | 5–5.5 | — | ≈ 4.0–4.5 |
| Aergrind | 1.3–1.9 | — | ≈ 3.8–4.5 |
| Baratza Encore | 12–14 | — | ≈ 4.5–5.0 |
| Comandante C40 | 11–14 clicks | 14–16 clicks | ≈ 3.8–4.5 / 4.5–5.0 |
| Timemore C2 | 11 clicks | 12–14 clicks | ≈ 4.0–4.5 |
| Timemore C3/C3 Pro | — | 11 clicks | ≈ 4.5 |
| Porlex Mini | 5–7 clicks | — | ≈ 4.0–4.5 |
| Wilfa Aroma | AeroPress 刻度 | — | 直接參考廠商標示 |

> **為何不導入常態化研磨空間（G_norm）：** 不同磨豆機的細粉分佈（fines distribution）在相同「粗細程度」下物理特性不同，線性正規化會引入比現有近似更大的系統誤差；且底層常數（`DARCY_PRESS_EXP`、`FINES_RATIO_DIAL_SLOPE`）具有可與 ZP6 實測數據直接對應的物理語意，重構後將失去可校正性。正確擴展路徑是建立各磨豆機的「ZP6 等效換算表」（即本表），而非重構底層物理引擎。

---

## 5. EY 計算模型（雙峰動力學 + 動態細粉率 + 三重熱力修正 + 阿瑞尼斯動態速率 + 壓降等效注入）

> **v3.9 熱力修正完整架構：**
>
> | 修正項 | 公式 | 修正量（30g 示例） |
> |---|---|---|
> | 粉水熱交換失溫 | $dose \times 0.15$ | −4.5°C |
> | 機身熱容失溫 | $BREWER\_TEMP\_DROP$ | −2.5°C |
> | **合計 T_slurry 修正** | **−7.0°C（30g）** | **−5.2°C（18g）** |
>
> **阿瑞尼斯動態速率（v5.4：改用 T_avg 時間平均溫度）：**
> $$T_{avg} = T_{env} + \frac{T_{slurry} - T_{env}}{r \cdot t} \cdot (1 - e^{-rt})$$
> $$k_{base,dynamic} = K_{BASE} \times e^{(T_{avg} - 90) \times ARRHENIUS\_COEFF}$$
> v5.2 以 T_slurry（最高溫）為輸入，高估 k 達 18–40%。T_avg 為封閉解析解、無循環依賴。
> M焙 120s：T_avg=86.7°C（vs T_slurry=90°C），k 下修 15%；L+ 240s：T_avg=87.8°C（vs 94.5°C），k 下修 29%。
>
> **牛頓冷卻率修正（v5.3）：** `COOL_RATE` 從 0.02 修正為 0.0008（120s 降溫 5.9°C vs 舊值 59°C）
>
> **壓降等效時間注入（v5.3 新增）：**
> $$press\_equiv = press\_sec \times PRESS\_EQUIV\_FRACTION \quad (0.15)$$
> $$t_{kinetic} = steep\_sec + SWIRL\_TIME\_SEC \times swirl\_mult + press\_equiv$$
> 60s 壓降 → +9s 等效被動浸泡；90s Stall → +13.5s。動力學方程式自動處理差異萃取。
>
> **Swirl 強制對流補償（v4.8：操作時間與對流補償正式分離）：**
> $$swirl\_mult = 1.0 + SWIRL\_CONVECTION\_BASE \times \frac{SWIRL\_DOSE\_REF}{dose}$$
> $$t_{kinetic} = steep\_sec + SWIRL\_TIME\_SEC \times swirl\_mult$$
> dose=18g → swirl_mult=2.0，等效補償 5×2.0=**10s**；dose=30g → swirl_mult=1.6，等效 5×1.6=**8s**。
> v4.8 調整：操作時間 5s（真實）× 更高的 BASE（1.0）= 等效補償量維持 v4.7 的 dose=18g 基準值不變。

```python
def calc_fines_ratio(dial):
    """
    動態細粉率（v3.8）：刻度越細，細粉率越高。
    f(dial) = FINES_RATIO_BASE + (DIAL_BASE - dial) × FINES_RATIO_DIAL_SLOPE
    夾緊至 [5%, 35%]。
    """
    ratio = FINES_RATIO_BASE + (DIAL_BASE - dial) * FINES_RATIO_DIAL_SLOPE
    return max(0.05, min(ratio, 0.35))


def _calc_t_eff(temp_slurry, k, r, t):
    """
    萃取速率加權有效溫度（封閉解析解）。
    T_eff = T_env + (T_slurry - T_env) × [k/(r+k)] × [(1 - e^{-(r+k)t}) / (1 - e^{-kt})]

    t = t_kinetic（已含 Swirl 對流補償）。
    T_slurry = 粉水混合漿體真實起始溫度（已扣除粉吸熱與機身熱容）。
    t=0 邊界：洛必達法則下 T_eff → T_slurry。
    """
    kt = k * t
    if kt < 1e-9:
        return temp_slurry
    return T_ENV + (temp_slurry - T_ENV) * (k / (r + k)) * (
        (1 - math.exp(-(r + k) * t)) / (1 - math.exp(-kt))
    )


def calc_ey(roast_code, temp_initial, dial, steep_sec, dose, water_ml=400, water_gh=50, water_kh=30, press_equiv=0, pour_offset=0):
    """
    雙峰動力學 EY 模型（v5.5）。

    water_ml     : 注水量（ml）；標準版 200 / XL 400（v5.5r 新增）
    pour_offset  : 注水階段平均接觸延遲（秒，v5.5r 新增）
                   = (water_ml / POUR_RATE) / 2；從 steep_sec 扣除

    temp_initial : 注水初始溫度（手沖壺水溫，°C）
    steep_sec    : 被動浸泡時間（秒，不含旋轉與壓降）
    dose         : 豆量（g）；用於熱平衡失溫修正與 Swirl 黏滯度修正
    water_gh     : 用水總硬度（ppm CaCO3）；驅動萃取
    water_kh     : 不影響 EY（影響 AC 感知，見 §9）
    press_equiv  : 壓降等效被動浸泡時間（秒，v5.3 新增）
                   = press_sec × PRESS_EQUIV_FRACTION（0.15）
                   注入 t_kinetic 使壓降萃取透過動力學方程式自然分配

    比熱混合溫度（v5.8r：取代線性近似，正確反映 water_ml 影響）：
      t_mix = (water_ml × T_initial + dose × 0.33 × T_ENV) / (water_ml + dose × 0.33)
      T_slurry = t_mix − BREWER_TEMP_DROP
    Swirl 動態對流補償（v4.8：操作時間與補償分離）：
      swirl_mult = 1.0 + SWIRL_CONVECTION_BASE × (SWIRL_DOSE_REF / dose)
      t_kinetic  = steep_sec + SWIRL_TIME_SEC × swirl_mult + press_equiv
    阿瑞尼斯動態速率（v5.4：改用 T_avg 時間平均溫度）：
      T_avg = T_env + (T_s - T_env)/(r×t) × (1 - e^{-r×t})
      k_base_dynamic = K_BASE × exp((T_avg - 90) × ARRHENIUS_COEFF)
      修補 v5.2 以 t_slurry（最高溫）為輸入的恆溫假設（高估 k 達 18–40%）
    牛頓冷卻率修正（v5.3）：COOL_RATE 從 0.02 修正為 0.0008
    """
    cfg = ROAST_TABLE[roast_code]
    r   = COOL_RATE

    # ── 比熱混合溫度（v5.8r：取代線性近似，正確反映 water_ml 影響）──
    # 舊公式：t_slurry = temp - dose×0.15 - 2.5（忽略 water_ml，雙機型結構性錯誤）
    # 新公式：比熱平衡方程式 + 機身熱容
    heat_water  = water_ml * 1.0                            # 水的熱容量（g × 比熱比 1.0）
    heat_coffee = dose * COFFEE_SPECIFIC_HEAT_RATIO         # 咖啡粉等效熱容量
    t_mix = (heat_water * temp_initial + heat_coffee * T_ENV) / (heat_water + heat_coffee)
    t_slurry = t_mix - BREWER_TEMP_DROP

    # ── Swirl 動態對流補償（v4.8：操作時間 5s × 倍率，與 BASE=1.0 配合維持補償量）
    # 豆量越大，漿體越黏，Swirl 的邊界層撕裂效率越低
    swirl_mult = 1.0 + SWIRL_CONVECTION_BASE * (SWIRL_DOSE_REF / dose)
    t_kinetic = max(0, steep_sec - pour_offset) + SWIRL_TIME_SEC * swirl_mult + press_equiv  # v5.5r：扣除注水延遲

    # ── 動態細粉率（v3.8）────────────────────────────────
    f = calc_fines_ratio(dial)

    # ── 阿瑞尼斯動態速率常數（v5.4：以 T_avg 取代 t_slurry）──────
    # v5.2 原始設計以 t_slurry（最高溫度）為輸入，系統性高估平均速率（120s +18%、240s +40%）
    # v5.4：以牛頓冷卻定積分的時間平均溫度取代——封閉解析解、無循環依賴
    # T_avg = T_env + (T_s - T_env)/(r×t) × (1 - e^{-r×t})
    rt = r * t_kinetic
    if rt > 1e-9:
        T_avg = T_ENV + (t_slurry - T_ENV) / rt * (1.0 - math.exp(-rt))
    else:
        T_avg = t_slurry  # t→0 邊界：T_avg → T_slurry
    k_base_dynamic = K_BASE * math.exp((T_avg - 90) * ARRHENIUS_COEFF)

    # ── 速率常數（v5.2：使用溫度敏感的 k_base_dynamic）──────
    k_b = k_base_dynamic * K_BOULDERS_MULT * (1.8 ** ((DIAL_BASE - dial) / 0.5))
    k_b = max(K_MIN, min(k_b, K_MAX))
    k_f = min(k_b * K_FINES_MULT, K_MAX * K_FINES_MULT)

    # ── 各峰的 T_eff（使用 t_kinetic 與 T_slurry）────────────
    t_eff_f = _calc_t_eff(t_slurry, k_f, r, t_kinetic)
    t_eff_b = _calc_t_eff(t_slurry, k_b, r, t_kinetic)

    # ── 各峰的 EY_max（v5.6：自由溶劑修正升級）──────────────
    base_t = cfg['base_temp']
    # brew_capacity：有限溶劑中的平衡 EY 低於理論 EY_max（Infinite Sink Correction）
    # v5.5：brew_capacity = water_ml / (water_ml + dose × K_d)
    # v5.6：以 free_water（扣除截留水後的真正可用溶劑）取代總注水量
    #   free_water = water_ml − dose × calc_retention(roast_code, dial)
    #   brew_capacity = free_water / (free_water + dose × K_d)
    # 物理意義：截留水在粉床內部已飽和，不參與巨觀溶劑池的濃度平衡；
    #           只有 free_water 才是真正驅動擴散的溶劑量
    # 數值影響（K_d=0.5）：
    #   18g L+（ret=2.00）：free=364ml，capacity=0.978→0.979（差異微小）
    #   30g D  （ret=2.50）：free=325ml，capacity=0.964→0.955（差異 −0.9%）
    free_water = water_ml - dose * calc_retention(roast_code, dial)
    free_water = max(free_water, 1.0)   # 防止極端豆量/截留下除以零
    brew_capacity = free_water / (free_water + dose * CONC_GRADIENT_COEFF)
    def _ey_max(t_eff):
        return min((cfg['base_ey'] + 8.0) + (t_eff - base_t) / 5 * 1.5, EY_ABSOLUTE_MAX) * brew_capacity

    # ── 雙峰 EY 合計（使用 t_kinetic 積分）──────────────────
    ey = (f * _ey_max(t_eff_f) * (1 - math.exp(-k_f * t_kinetic)) +
          (1 - f) * _ey_max(t_eff_b) * (1 - math.exp(-k_b * t_kinetic)))

    # ── 水質 GH 修正 ──────────────────────────────────────
    if water_gh < 20:
        ey *= 0.94
    elif water_gh <= 100:
        ey *= 1.0 + (water_gh - 20) / 800
    else:
        ey *= max(0.97, 1.10 - (water_gh - 100) / 1000)

    return round(min(ey, EY_ABSOLUTE_MAX), 3)
```

---

## 6. TDS 計算模型（動態截留係數 + 雙變數壓降時間 + 動態沉降時間）

```python
def calc_retention(roast_code, dial):
    """
    動態截留係數（v4.3：烘焙度 × 研磨度二元函數）。

    v4.2 舊版（僅依賴 dial）：
      Retention = 2.5 - (dial - 3.5) × 0.15  ← 忽略烘焙度差異

    v4.3 新版（烘焙度基準 + 研磨度微調）：
      retention = RETENTION_BASE[roast] + (DIAL_BASE - dial) × RETENTION_DIAL_SLOPE[roast]

    物理依據：深焙豆細胞壁在二爆後大幅膨脹，孔隙率顯著高於淺焙豆。
    相同研磨刻度下，深焙粉（D）截留約 2.4–2.6 g/g，淺焙粉（L+）約 1.8–2.1 g/g。
    忽略此差異會使深焙的實際出液量被高估，導致 TDS 系統性偏高。

    深焙斜率（0.08）< 淺焙斜率（0.10）：深焙豆結構疏鬆，研磨刻度對截留的邊際影響略低。
    夾緊範圍：[1.60, 2.80] g/g。
    """
    base  = RETENTION_BASE[roast_code]
    slope = RETENTION_DIAL_SLOPE[roast_code]
    return round(max(1.60, min(base + (DIAL_BASE - dial) * slope, 2.80)), 2)


def calc_tds(roast_code, dose, ey, dial, water_ml=400):
    """
    計算實際 TDS（%）。截留係數由烘焙度與研磨度共同決定（v4.3）。
    water_ml：注水量（ml），v5.5r 新增——標準版 200 / XL 400。

    v4.7：修正溶液質量守恆（溶質質量 Bug Fix）。
    TDS 的嚴格定義：溶質質量 / 溶液總質量（溶劑 + 溶質）。
    """
    retention          = calc_retention(roast_code, dial)
    extracted_solids_g = dose * (ey / 100)
    water_yield_g      = water_ml - dose * retention
    yield_mass_g       = water_yield_g + extracted_solids_g   # 真實溶液總質量
    if yield_mass_g <= 0:
        return 0.0
    return round((extracted_solids_g / yield_mass_g) * 100, 4)


def calc_swirl_wait(dial):
    """
    動態靜置時間（v4.3 新增：斯托克斯沉降原理）。

    Hoffman 靜置步驟的目的是讓咖啡粉渣自然沉降，在濾紙上方形成天然粉床過濾層，
    防止細粉直接堵塞濾紙孔隙（導致 Stall）。

    根據斯托克斯定律（Stokes' Law），顆粒沉降速度與半徑平方成正比：
      v ∝ r²  →  粗粉（大 r）沉降極快，細粉（小 r）長時間懸浮

    公式：swirl_wait = clamp(SWIRL_WAIT_BASE + (DIAL_BASE - dial) × SWIRL_WAIT_SLOPE, MIN, MAX)
      dial=3.5（極細）→ 30 + 10 = 40s
      dial=4.5（基準）→ 30 + 0  = 30s
      dial=6.5（粗）  → 30 - 20 = 10s

    夾緊範圍：[SWIRL_WAIT_MIN=10, SWIRL_WAIT_MAX=45] 秒。
    """
    raw = SWIRL_WAIT_BASE + (DIAL_BASE - dial) * SWIRL_WAIT_SLOPE
    return int(max(SWIRL_WAIT_MIN, min(raw, SWIRL_WAIT_MAX)))


def calc_press_time(dose, dial, steep_sec=120):
    """
    動態壓降時間（v5.6：Swirl 粉床重置修正）。

    v4.2 新公式（Bug Fix）：
      press_time = dial_modifier × (PRESS_TIME_MIN + (dose - 18) × PRESS_TIME_PER_G)

    v5.5 新增：粉床時間壓實（Bed Compaction）
      compaction_mult = 1.0 + (steep_sec / 240) × BED_COMPACTION_COEFF

    v5.6 修正：Swirl 部分重置粉床（SWIRL_RESET_FRACTION = 0.35，理論推導值）
      真正決定壓降阻力的不是完整浸泡時間，而是「Swirl 重置後的二次沉降時間」：
        effective_compaction_time = steep_sec × (1 − SWIRL_RESET_FRACTION) + swirl_wait_sec
      物理依據：
        Swirl 渦流（Re≈500）可懸浮粒徑 <80μm 顆粒（約佔細粉層 35%），
        剩餘 65% 已嵌入粉層間隙，不被 5s 輕柔旋轉重置。
        Swirl 後粉床重新沉降時間 = calc_swirl_wait(dial)，
        這段時間是最後一批細粉沉積到濾紙面的時間窗口。

    compaction_mult = 1.0 + (effective_compaction_time / 240) × BED_COMPACTION_COEFF
    dial_modifier = exp((DIAL_BASE - dial) × DARCY_PRESS_EXP) × compaction_mult

    範例（dial=4.5，swirl_wait=30s）：
      steep=60s  → eff=69s  → mult=1.043；dial=3.5 → 1.82×1.043=1.898
      steep=120s → eff=108s → mult=1.068；dial=3.5 → 1.82×1.068=1.943
      steep=240s → eff=186s → mult=1.116；dial=3.5 → 1.82×1.116=2.031
    """
    swirl_wait_sec = calc_swirl_wait(dial)
    effective_compaction_time = steep_sec * (1.0 - SWIRL_RESET_FRACTION) + swirl_wait_sec
    compaction_mult = 1.0 + (effective_compaction_time / 240.0) * BED_COMPACTION_COEFF
    dial_modifier = math.exp((DIAL_BASE - dial) * DARCY_PRESS_EXP) * compaction_mult
    base_time     = PRESS_TIME_MIN + (dose - 18) * PRESS_TIME_PER_G
    raw_time      = dial_modifier * base_time
    return int(min(max(raw_time, PRESS_TIME_MIN_FLOOR), PRESS_TIME_MAX))


def apply_channeling(ey, compounds, press_sec):
    """
    通道效應後處理（v4.5 新增）。

    當壓降時間超過 CHANNELING_PRESS_THRESHOLD（60s）時，判定為 Stall / 高壓場景，
    觸發通道效應（Channeling）物理懲罰：

    流體力學依據：
      極細粉（dial≤3.8）+ 大豆量（dose≥26g）的高壓粉餅中，水會尋找阻力最小路徑
      形成通道（Channel），導致：
        ① 通道附近粉層嚴重過萃 → CGA 非線性飆升（尖銳咬喉澀感）
        ② 粉餅死角完全未萃取  → 整體巨觀 EY 下降

    計算：
      bypass_ratio = min((press_sec - 60) × 0.005, CHANNELING_BYPASS_MAX)
      ey_out       = ey × (1 - bypass_ratio)
      CGA_out      = CGA × (1 + bypass_ratio × CHANNELING_CGA_MULT)

    必須在 calc_tds() 調用前套用，確保 EY、TDS、Compounds 三者一致。
    press_sec ≤ 60 時直接回傳原值，無效能損耗。
    """
    if press_sec <= CHANNELING_PRESS_THRESHOLD:
        return ey, compounds

    bypass_ratio = min(
        (press_sec - CHANNELING_PRESS_THRESHOLD) * CHANNELING_EY_SLOPE,
        CHANNELING_BYPASS_MAX
    )
    ey_out = ey * (1.0 - bypass_ratio)

    compounds_out = dict(compounds)
    compounds_out['CGA'] = compounds['CGA'] * (1.0 + bypass_ratio * CHANNELING_CGA_MULT)

    return round(ey_out, 3), compounds_out
```

---

## 7. 風味物質預測模型

### 7.1 六類物質定義

| 代號 | 物質類別 | 感官貢獻 | 萃取特性 |
|---|---|---|---|
| `AC` | 有機酸（檸檬酸、蘋果酸） | 明亮酸質、清爽 | 早期萃取，高溫加速，淺焙含量高；受 KH 中和 |
| `SW` | 游離糖與焦糖化產物 | 甜感、Body 骨架 | 中期萃取，中溫最佳，深焙衰減 |
| `PS` | 多糖體（Polysaccharides） | 醇厚度、滑順感 | 慢速擴散，細研磨＋長時間才釋出 |
| `CA` | 咖啡因 | 苦感輪廓 | 高溫快速萃取，中段趨於飽和 |
| `CGA` | 綠原酸及其內酯 | 後段苦感、澀感 | 高溫長時間萃出，深焙轉化後減少 |
| `MEL` | 類黑素（Melanoidins） | 焦糖深度 / 深焙焦苦 | 深焙大量生成；低濃度提供 Body，高濃度轉為焦苦 |

### 7.2 預測公式

```python
def predict_compounds(roast_code, temp, dial, steep_sec, ey, water_kh=30, water_mg_frac=0.40, press_equiv=0, pour_offset=0):
    """
    回傳各物質「萃取質量強度」（mass，未正規化）。

    【v4.0 架構說明：感知層與質量層分離】
    KH 對 AC 的中和作用（改變感官酸度）不在此函數處理。
    AC 回傳值為真實萃取質量——KH 僅降低 H⁺ 濃度，有機酸鹽仍留在杯中。
    感知修正由 flavor_score() 入口的「感知過濾器」負責，確保底層質量守恆。
    water_kh 參數保留於簽名，供未來擴展（如 CGA 酸鹼解離修正）使用。

    【v5.0 架構澄清：AC 時間衰減項的語意】
    AC 的時間衰減不是「有機酸質量消失」（物質不滅定律不違反）。
    這是六維相對強度向量的比重建模：長時間萃取後 SW/PS/CGA 大量湧出，
    AC 在輪廓向量中的相對比重下降，建模「感知上酸感被其他物質遮蔽」的效果。
    真實物理的絕對酸質量守恆，由 flavor_score 的質量分率正規化（v5.2）保證。

    【v5.3 重構：壓降等效時間注入】
    press_equiv：壓降期間的等效被動浸泡秒數（= press_sec × 0.15）。
    effective_steep = steep_sec + press_equiv。
    所有時間依賴項使用 effective_steep，讓壓降期間的物質演變透過動力學方程式自然分配：
    CA 已近飽和（steep=120s 時 97.3%，+9s equiv → 97.9%，幾乎不變）；
    PS/CGA 仍在曲線早段，獲得有意義的漸近線推進。

    【v5.3 修復：CGA 線性時間破窗 → 指數漸近線】
    舊公式：CGA *= 1 + max(steep-150, 0) × 0.004（600s 時 2.8×，無界）
    新公式：CGA *= 1 + CGA_TIME_MAX × (1 − exp(−K_CGA_TIME × extra))
    240s 時新值 1.370 vs 舊值 1.360（搜尋空間內完美匹配），長時間收斂至 1.50×。

    【v5.3 修復：AC 線性衰減 → 指數衰減（防止負值 Bug）】
    舊公式：AC *= 1 − max(steep-150, 0) × 0.003（steep > 483s 時 AC 變負！）
    新公式：AC *= exp(−K_AC_DECAY × extra)
    240s 時精確匹配舊值 0.730，且永不為負。
    """
    # ── v5.3/v5.5r：壓降等效 + 注水延遲扣除 ────────────────────
    effective_steep = max(0, steep_sec - pour_offset) + press_equiv
    # ── Mg²⁺/Ca²⁺ 分軌修正係數（v5.1）──────────────────────────
    mg_delta      = water_mg_frac - 0.50          # 相對中性基準的偏差（+：Mg 多；-：Ca 多）
    ac_sw_mult    = 1.0 + mg_delta * MG_FRAC_AC_SW_MULT    # mg_frac=0.90 → 1.064
    ps_cga_mult   = 1.0 + (-mg_delta) * MG_FRAC_PS_CGA_MULT  # mg_frac=0.90 → 0.968

    ac_roast = {'very_light':1.0, 'light':0.9, 'medium_light':0.7, 'medium':0.5, 'moderately_dark':0.3, 'dark':0.2, 'very_dark':0.15}
    AC = ac_roast[roast_code]
    AC *= 1 + (temp - 90) * 0.02
    # v5.3：指數衰減取代線性（舊公式 steep > 483s 時 AC 變負；指數永不為負）
    # effective_steep 包含壓降等效時間
    ac_extra = max(effective_steep - 150, 0)
    AC *= math.exp(-K_AC_DECAY * ac_extra)
    AC *= ac_sw_mult   # v5.1：Mg²⁺ 對 AC 的分軌修正
    # ↑ v4.0：移除 AC *= max(0.65, 1.0 - water_kh / 500)
    #   KH 不消滅有機酸質量，感官中和效果移至 flavor_score 感知過濾器

    sw_roast = {'very_light':0.5, 'light':0.7, 'medium_light':0.9, 'medium':1.0, 'moderately_dark':0.8, 'dark':0.5, 'very_dark':0.4}
    SW = sw_roast[roast_code]
    # v4.6：甜感峰值溫度焙度動態化（取代固定 90°C 的化學謬誤）
    optimal_sw_temp = ROAST_TABLE[roast_code]['base_temp'] - 2
    SW *= 1 - abs(temp - optimal_sw_temp) * 0.01
    SW *= 1 + min(effective_steep - 120, 60) * 0.002   # v5.3：使用 effective_steep（含壓降等效）
    SW *= ac_sw_mult   # v5.1：Mg²⁺ 對 SW 的分軌修正

    PS = 0.3
    PS += max(4.5 - dial, 0) * 0.15
    # v5.1：修復 PS 線性時間破窗——改為緩速指數漸近線
    # v5.3：使用 effective_steep（含壓降等效時間）
    if effective_steep > 120:
        extra_time = effective_steep - 120
        PS += PS_TIME_MAX * (1.0 - math.exp(-K_PS * extra_time))
    PS *= {'very_light':0.6, 'light':0.7, 'medium_light':0.8, 'medium':1.0, 'moderately_dark':1.1, 'dark':1.2, 'very_dark':1.25}[roast_code]
    # v4.7：多糖體熱力學驅動係數（吸熱反應，低溫溶解度大幅降低）
    PS *= max(0.0, 1.0 + (temp - 90) * 0.015)
    PS *= ps_cga_mult  # v5.1：Ca²⁺ 對 PS 的分軌修正（高 Ca → PS 略高）
    PS = min(PS, 1.0)

    ca_roast = {'very_light':1.0, 'light':1.0, 'medium_light':0.95, 'medium':0.9, 'moderately_dark':0.85, 'dark':0.8, 'very_dark':0.75}
    # v4.3：CA 解耦總 EY，改為一階動力學漸近線
    # v5.3：使用 effective_steep（含壓降等效；CA 已近飽和，壓降影響可忽略：97.3%→97.9%）
    ca_extraction_ratio = 1.0 - math.exp(-K_CA * effective_steep)
    CA = ca_roast[roast_code] * ca_extraction_ratio

    cga_roast = {'very_light':0.5, 'light':0.6, 'medium_light':0.8, 'medium':1.0, 'moderately_dark':0.7, 'dark':0.4, 'very_dark':0.30}
    CGA = cga_roast[roast_code]
    CGA *= 1 + max(temp - 92, 0) * 0.03
    # v5.3：指數漸近線取代線性（舊公式 600s 時 CGA 飆至 2.8×，無界）
    # effective_steep 包含壓降等效時間
    cga_extra = max(effective_steep - 150, 0)
    CGA *= 1.0 + CGA_TIME_MAX * (1.0 - math.exp(-K_CGA_TIME * cga_extra))
    CGA *= ps_cga_mult  # v5.1：Ca²⁺ 對 CGA 的分軌修正（高 Ca → CGA 略高）

    mel_roast = {'very_light':0.1, 'light':0.2, 'medium_light':0.4, 'medium':0.6, 'moderately_dark':0.9, 'dark':1.0, 'very_dark':1.10}
    MEL = mel_roast[roast_code] * (1 + (temp - 90) * 0.01)

    return {
        'AC':  round(AC,  4), 'SW':  round(SW,  4), 'PS':  round(PS,  4),
        'CA':  round(CA,  4), 'CGA': round(CGA, 4), 'MEL': round(MEL, 4),
    }
```

---

## 8. 理想風味表（Ideal Flavor Target）

```python
TDS_ANCHORS = {'low': 1.00, 'mid': 1.20, 'high': 1.40}

IDEAL_FLAVOR = {
    ('very_light', 'low'):  {'AC':0.28, 'SW':0.30, 'PS':0.18, 'CA':0.12, 'CGA':0.08, 'MEL':0.04},
    ('very_light', 'mid'):  {'AC':0.25, 'SW':0.32, 'PS':0.20, 'CA':0.11, 'CGA':0.08, 'MEL':0.04},
    ('very_light', 'high'): {'AC':0.22, 'SW':0.35, 'PS':0.22, 'CA':0.10, 'CGA':0.07, 'MEL':0.04},

    ('light',  'low'):  {'AC':0.25, 'SW':0.32, 'PS':0.18, 'CA':0.13, 'CGA':0.08, 'MEL':0.04},
    ('light',  'mid'):  {'AC':0.22, 'SW':0.35, 'PS':0.20, 'CA':0.12, 'CGA':0.07, 'MEL':0.04},
    ('light',  'high'): {'AC':0.20, 'SW':0.37, 'PS':0.22, 'CA':0.11, 'CGA':0.06, 'MEL':0.04},

    ('medium_light', 'low'):  {'AC':0.18, 'SW':0.35, 'PS':0.20, 'CA':0.14, 'CGA':0.09, 'MEL':0.04},
    ('medium_light', 'mid'):  {'AC':0.15, 'SW':0.38, 'PS':0.22, 'CA':0.13, 'CGA':0.08, 'MEL':0.04},
    ('medium_light', 'high'): {'AC':0.13, 'SW':0.40, 'PS':0.23, 'CA':0.12, 'CGA':0.08, 'MEL':0.04},

    ('medium',  'low'):  {'AC':0.12, 'SW':0.38, 'PS':0.22, 'CA':0.14, 'CGA':0.08, 'MEL':0.06},
    ('medium',  'mid'):  {'AC':0.10, 'SW':0.40, 'PS':0.24, 'CA':0.13, 'CGA':0.07, 'MEL':0.06},
    ('medium',  'high'): {'AC':0.09, 'SW':0.42, 'PS':0.24, 'CA':0.12, 'CGA':0.07, 'MEL':0.06},

    ('moderately_dark', 'low'):  {'AC':0.08, 'SW':0.32, 'PS':0.22, 'CA':0.13, 'CGA':0.08, 'MEL':0.17},
    ('moderately_dark', 'mid'):  {'AC':0.07, 'SW':0.34, 'PS':0.23, 'CA':0.12, 'CGA':0.07, 'MEL':0.17},
    ('moderately_dark', 'high'): {'AC':0.06, 'SW':0.35, 'PS':0.24, 'CA':0.11, 'CGA':0.07, 'MEL':0.17},

    ('dark',  'low'):  {'AC':0.05, 'SW':0.28, 'PS':0.22, 'CA':0.12, 'CGA':0.06, 'MEL':0.27},
    ('dark',  'mid'):  {'AC':0.05, 'SW':0.30, 'PS':0.23, 'CA':0.11, 'CGA':0.05, 'MEL':0.26},
    ('dark',  'high'): {'AC':0.04, 'SW':0.30, 'PS':0.24, 'CA':0.10, 'CGA':0.05, 'MEL':0.27},

    ('very_dark', 'low'):  {'AC':0.04, 'SW':0.26, 'PS':0.22, 'CA':0.12, 'CGA':0.05, 'MEL':0.30},  # v5.x 新增
    ('very_dark', 'mid'):  {'AC':0.04, 'SW':0.28, 'PS':0.23, 'CA':0.11, 'CGA':0.05, 'MEL':0.29},
    ('very_dark', 'high'): {'AC':0.03, 'SW':0.28, 'PS':0.24, 'CA':0.10, 'CGA':0.04, 'MEL':0.30},
}
```

---

## 9. 風味評分公式（八層評分架構 + 協同懲罰 + 質量分率正規化）

> **八層評分架構（v5.7）：**
>
> | 層 | 機制 | 捕捉目標 | 上限影響 |
> |---|---|---|---|
> | `cosine_sim` | 加權餘弦相似度 | 六維輪廓方向 | 主要項 |
> | `conc_score` | 非對稱 Huber Loss（v4.0）+ **質量分率正規化**（v5.2） | 各物質絕對濃度；v5.2 修正尺度失真 | 主要項 |
> | `b_ac_sw` | AC/SW 比值 Huber Loss | 甜酸感官遮蔽 | 最多 −15% |
> | `b_ps` | PS/(CA+CGA+MEL×coeff) Huber Loss | 醇苦感官遮蔽（v3.9：焙度依賴 MEL） | 最多 −12% |
> | `tds_factor` | **動態非對稱** TDS 高斯懲罰（v5.0） | 全局濃度偏好 | 水感最多 −25%；濃郁最多 −10% |
> | `cga_astringency` | **指數衰減懲罰乘數**（v5.4：TDS_PREFER 錨定） | CGA 澀感生物閾值 | 超過 1.25× anchor 後指數劣化 |
> | `harshness_penalty` | **AC×CGA 交叉乘積**（v5.5） | 酸澀協同劣變（淺/中焙） | AC=1.3×+CGA=1.3× 扣 30% |
> | `ashy_penalty` | **MEL×CGA 交叉乘積**（v5.7，MD/D 限定） | 焦澀協同劣變（深焙） | MEL=1.3×+CGA=1.3× 扣 23% |
>
> **最終評分（v5.7）：**
> $$score = cosine \times conc \times (1{-}W_1{+}W_1 b_1) \times (1{-}W_2{+}W_2 b_2) \times tds \times cga\_ast \times harshness \times ashy \times 100$$

```python
KEYS         = ['AC', 'SW', 'PS', 'CA', 'CGA', 'MEL']
WEIGHTS      = {'AC':1.2, 'SW':1.8, 'PS':1.5, 'CA':1.0, 'CGA':1.3, 'MEL':1.0}

_TDS_ANCHOR_LIST = [1.00, 1.20, 1.40]
_WEIGHT_TOTAL    = sum(WEIGHTS.values())   # = 7.8
_CONC_FLOOR      = 1e-8
_W1              = BALANCE_PENALTY_WEIGHT       # = 0.15
_W2              = BODY_BITTER_PENALTY_WEIGHT   # = 0.12
# _W3 已升級為動態雙權重（v5.0）：
TDS_W3_LOW  = 0.25  # v5.0：TDS 低於目標（水感）時的動態懲罰權重；最多扣 25%
                     # 設計依據：水感（TDS 偏低）是不可逆的毀滅性缺陷，必須強制制裁
                     # 最差連乘：(1-0.15)×(1-0.12)×(1-0.25)=0.561，最多扣約 44%
TDS_W3_HIGH = 0.10  # v5.0：TDS 高於目標（濃郁）時維持原有寬容權重（v4.1 以來不變）
                     # 高濃度可加冰/加水補救，容忍度較高
CONC_SENSITIVITY_FLOOR = 0.02  # v4.9：微量物質誤差底板
                                 # 防止極低濃度場景（如 L+ 的 MEL ideal≈0.054）中，
                                 # 絕對誤差被轉化為過大的相對懲罰，影響數值穩定性。
                                 # 【觸發條件】僅在 ideal_abs[k] < 0.02 時介入——
                                 # 現有 IDEAL_FLAVOR 表的所有焙度×TDS錨點組合中，
                                 # 所有物質的 ideal_abs 均 > 0.02，正常情況零影響。
                                 # 與 _CONC_FLOOR=1e-8 語意不同：前者防誇大懲罰，後者防除以零。
TDS_BROWN_WATER_FLOOR = 0.80   # v5.8r 新增：褐水防禦底板（TDS %）——由 CLI --tds-floor 覆寫（預設 0.80）
                                 # ⚠️ AGENT 實作指示：此值為個人感官設定，不得假設 0.80 為普適值。
                                 # 使用者首次執行前應先完成 §16 Wave 1 #5 的四杯盲評（§15 第 28 點），
                                 # 以 --tds-floor <實測底線> 傳入；若使用者未提供，維持預設 0.80 並
                                 # 在終端輸出提示：「提示：TDS_BROWN_WATER_FLOOR 使用預設值 0.80%，
                                 # 建議依個人口感以 --tds-floor 調整（說明：§15 第 28 點）」
                                 # 人類對過濾咖啡的味覺認知下限約 TDS 0.80%
                                 # TDS < 0.80 時觸發二次衰減：final *= (tds / 0.80)²
                                 # 搜尋空間邊界（18g/XL 或 9g/Standard, EY≈15%）可產出 TDS≈0.70–0.75%
                                 # 僅靠 TDS_W3_LOW=0.25 不足以斬殺（仍可得 ~67 分）
                                 # 0.75% → ×0.88；0.60% → ×0.56；0.40% → ×0.25


def _huber(x, delta):
    """標準對稱 Huber Loss（內部工具，供比率懲罰層使用）。"""
    ax = abs(x)
    return 0.5 * ax * ax if ax <= delta else delta * (ax - 0.5 * delta)


def _huber_asym(x, delta, compound):
    """
    非對稱 Huber Loss（v4.0）。
    在標準 Huber 基礎上，對感官高度不對稱的物質加入方向性懲罰：
      CA/CGA 過量（x > 0）：× ASYM_BITTER_MULT（1.5）
      SW 不足  （x < 0）：× ASYM_SWEET_MULT （1.5）
    其餘物質維持對稱（倍率 = 1.0）。
    反映人類感官心理學：苦澀過量的破壞力遠大於苦澀不足；甜感不足是嚴重缺陷。
    """
    base = _huber(x, delta)
    if compound in ('CA', 'CGA') and x > 0:
        return base * ASYM_BITTER_MULT
    if compound == 'SW' and x < 0:
        return base * ASYM_SWEET_MULT
    return base


def build_ideal_abs(roast_code, tds):
    """三錨點線性插值推算理想絕對濃度向量（v3.5）。"""
    tds_c = max(0.90, min(tds, 1.50))
    if tds_c <= _TDS_ANCHOR_LIST[0]:
        prop = IDEAL_FLAVOR[(roast_code, 'low')]
    elif tds_c >= _TDS_ANCHOR_LIST[-1]:
        prop = IDEAL_FLAVOR[(roast_code, 'high')]
    else:
        if tds_c <= _TDS_ANCHOR_LIST[1]:
            t  = (tds_c - 1.00) / 0.20
            p0, p1 = IDEAL_FLAVOR[(roast_code, 'low')], IDEAL_FLAVOR[(roast_code, 'mid')]
        else:
            t  = (tds_c - 1.20) / 0.20
            p0, p1 = IDEAL_FLAVOR[(roast_code, 'mid')], IDEAL_FLAVOR[(roast_code, 'high')]
        prop = {k: p0[k] * (1 - t) + p1[k] * t for k in KEYS}
    return {k: prop[k] * tds for k in KEYS}


def flavor_score(actual_raw, ideal_abs, tds, roast_code, water_kh=30, t_slurry=90, temp_initial=90):
    """
    八層評分架構（v5.8）。

    計算流程：
      0. actual_raw 正規化為質量分率（v5.2：總和強制為 1.0）→ × tds → actual_abs
      1. 感知過濾器：
         1a. KH 酸感中和
         1b. 高溫 SW 揮發逸散（v5.8 修正：觸發變數改為 temp_initial 壺溫）
         1c. 高溫劣變懲罰（t_slurry 漿體溫，v4.9）
      2. 加權餘弦相似度（使用 actual_perceived）
      3. 非對稱 Huber Loss 絕對濃度接近度（六維，v4.0）
      4. AC/SW 甜酸比平衡懲罰（v3.7）
      5. PS/(CA+CGA+MEL×coeff) 醇苦比平衡懲罰（v3.9）
      6. TDS 非對稱高斯偏好懲罰（v5.0：動態雙權重）
      7. CGA 澀感指數懲罰（v5.4：絕對濃度錨定至 TDS_PREFER）
      8. 酸澀協同劣變懲罰（v5.5：AC×CGA 交叉乘積）
      9. 焦澀協同劣變懲罰（v5.7：MEL×CGA，僅 MD/D 焙度）
     10. score = cosine × conc × (1-W1+W1×b1) × (1-W2+W2×b2) × tds_factor
               × cga_astringency × harshness_penalty × ashy_penalty × 100

    temp_initial : 壺溫（°C），v5.8 新增——僅用於 SW 揮發逸散觸發判斷
                   芳香閃蒸發生在水柱接觸乾燥粉的瞬間，此時溫度 = 壺溫，非漿體溫
    t_slurry     : 漿體起始溫（°C），仍用於 Scorch 劣變判斷（熱平衡後溫度正確）
    """
    # ── 步驟 0：質量分率正規化 + 絕對濃度計算（v5.2）──────────
    # predict_compounds 回傳的 raw 是六維相對強度向量（總和≈2.5–3.5），
    # 非物理質量分率。強制正規化為總和=1.0 的分率後乘以 TDS，
    # 使 actual_abs 與 ideal_abs（prop 總和≈1.0 × tds）在同一尺度。
    total_raw = sum(actual_raw[k] for k in KEYS)
    if total_raw > 0:
        actual_fraction = {k: actual_raw[k] / total_raw for k in KEYS}
    else:
        actual_fraction = {k: 0.0 for k in KEYS}
    actual_abs = {k: actual_fraction[k] * tds for k in KEYS}

    # ── 步驟 0+1a：KH 感知過濾器（v4.1：指數衰減 KH 懲罰）────
    kh_penalty = max(0.65, math.exp(-water_kh / KH_PERCEPT_DECAY))
    actual_perceived = dict(actual_abs)
    actual_perceived['AC'] = actual_abs['AC'] * kh_penalty

    # ── 步驟 1b：高溫 SW 揮發逸散（v5.8 修正：觸發變數改為 temp_initial）────
    # 物理依據：揮發性芳香物質的閃蒸（Flash Volatilization）發生在水柱接觸
    # 乾燥粉表面的瞬間，此時水溫 = 壺溫（temp_initial），非熱平衡後的漿體溫。
    # v5.7 Bug（大豆量免疫）：使用 t_slurry 時，30g 豆 + 100°C 壺溫
    #   → t_slurry = 100 - 4.5 - 2.5 = 93°C < 閾值 95°C → 完全不觸發（物理錯誤）
    # v5.8 修正：改用 temp_initial，任何豆量使用 100°C 均觸發 −10% SW 感知扣減：
    #   temp_initial=98°C → penalty = 1 - (3×0.02) = 0.94（−6%）
    #   temp_initial=100°C → penalty = 1 - (5×0.02) = 0.90（−10%）
    #   temp_initial=103°C → penalty = 1 - min(8×0.02, 0.30) = 0.84（−16%，沸騰場景上限前）
    # 與 predict_compounds SW 溶出拋物線正交（後者建模質量，本層建模感知）
    if temp_initial > SW_AROMA_THRESH:
        sw_loss = min((temp_initial - SW_AROMA_THRESH) * SW_AROMA_SLOPE, SW_AROMA_CAP)
        actual_perceived['SW'] = actual_abs['SW'] * (1.0 - sw_loss)

    # ── 步驟 1c：高溫劣變感知懲罰（v4.9：改用 t_slurry 漿體溫）────
    scorch_threshold, cga_sens, mel_sens = SCORCH_PARAMS[roast_code]
    if t_slurry > scorch_threshold and (cga_sens > 0 or mel_sens > 0):
        excess = t_slurry - scorch_threshold
        if cga_sens > 0:
            actual_perceived['CGA'] = actual_abs['CGA'] * (1.0 + excess * cga_sens)
        if mel_sens > 0:
            actual_perceived['MEL'] = actual_abs['MEL'] * (1.0 + excess * mel_sens)

    # ── 層 1：加權餘弦相似度 ─────────────────────────────
    dot    = sum(WEIGHTS[k] * actual_perceived[k] * ideal_abs[k] for k in KEYS)
    norm_a = math.sqrt(sum(WEIGHTS[k] * actual_perceived[k] ** 2 for k in KEYS))
    norm_i = math.sqrt(sum(WEIGHTS[k] * ideal_abs[k] ** 2 for k in KEYS))
    cosine_sim = dot / (norm_a * norm_i) if (norm_a > 0 and norm_i > 0) else 0.0

    # ── 層 2：非對稱 Huber Loss 絕對濃度接近度（v4.9）──────
    conc_loss = sum(
        WEIGHTS[k] * _huber_asym(
            (actual_perceived[k] - max(ideal_abs[k], CONC_SENSITIVITY_FLOOR)) /
             max(ideal_abs[k], CONC_SENSITIVITY_FLOOR),
            CONC_HUBER_DELTA, k
        )
        for k in KEYS
    ) / _WEIGHT_TOTAL
    conc_score = math.exp(-conc_loss)

    # ── 層 3：AC/SW 甜酸比平衡懲罰 ──────────────────────
    i_ac_sw = ideal_abs['AC']       / max(ideal_abs['SW'],       _CONC_FLOOR)
    a_ac_sw = actual_perceived['AC'] / max(actual_perceived['SW'], _CONC_FLOOR)
    b_ac_sw = math.exp(-_huber((a_ac_sw - i_ac_sw) / max(i_ac_sw, _CONC_FLOOR),
                                CONC_HUBER_DELTA))

    # ── 層 4：PS/(CA+CGA+MEL×coeff) 醇苦比平衡懲罰（v3.9）──
    mel_coeff = MEL_BITTER_COEFF[roast_code]
    i_bitter = max(ideal_abs['CA']          + ideal_abs['CGA']          + ideal_abs['MEL']          * mel_coeff, _CONC_FLOOR)
    a_bitter = max(actual_perceived['CA']   + actual_perceived['CGA']   + actual_perceived['MEL']   * mel_coeff, _CONC_FLOOR)
    i_ps_r   = ideal_abs['PS']         / i_bitter
    a_ps_r   = actual_perceived['PS']  / a_bitter
    b_ps     = math.exp(-_huber((a_ps_r - i_ps_r) / max(i_ps_r, _CONC_FLOOR),
                                 CONC_HUBER_DELTA))

    # ── 層 5：全局 TDS 動態非對稱高斯懲罰（v5.0：動態雙權重）────
    tds_prefer = TDS_PREFER[roast_code]
    diff       = tds - tds_prefer
    sigma      = TDS_GAUSS_SIGMA_LOW if diff < 0 else TDS_GAUSS_SIGMA_HIGH
    tds_gauss  = math.exp(-0.5 * (diff / sigma) ** 2)
    _w3        = TDS_W3_LOW if diff < 0 else TDS_W3_HIGH
    tds_factor = 1 - _w3 + _w3 * tds_gauss

    # ── 層 6：CGA 澀感指數懲罰（v5.4：絕對濃度錨定）──────────
    # 生物依據：CGA 與唾液 PRP 結合沉澱是絕對濃度觸發的機制。
    # v5.3 以前：ratio = actual/ideal，TDS 對消（正規化後），懲罰完全 TDS 盲。
    # v5.4：分母錨定至 TDS_PREFER 下的理想 CGA 絕對濃度，使懲罰反映真實的口腔 CGA 濃度：
    #   低 TDS（水感杯）→ 分子小、分母不變 → ratio 低 → 不觸發（正確：稀薄杯 CGA 不足以耗盡唾液）
    #   高 TDS（濃縮杯）→ 分子大、分母不變 → ratio 高 → 嚴格觸發（正確：濃縮杯 CGA 具攻擊性）
    #   TDS = TDS_PREFER → 與舊版行為完全一致
    cga_anchor_ideal = build_ideal_abs(roast_code, TDS_PREFER[roast_code])
    cga_ideal_anchor = max(cga_anchor_ideal['CGA'], _CONC_FLOOR)
    cga_actual       = actual_perceived['CGA']
    cga_ratio        = cga_actual / cga_ideal_anchor
    cga_astringency  = 1.0
    if cga_ratio > CGA_ASTRINGENCY_THRESHOLD:
        excess_ratio    = cga_ratio / CGA_ASTRINGENCY_THRESHOLD - 1.0
        cga_astringency = math.exp(-CGA_ASTRINGENCY_SLOPE * excess_ratio ** 2)

    # ── 層 7：酸澀協同劣變懲罰（v5.5：Harshness Synergy）────────
    # 口腔化學依據：AC（高酸值）+ CGA（高澀值）同時超標時，產生乘積性的
    # 「金屬味/胃酸」劣變感（Harshness），感官破壞力遠大於兩者獨立的加總。
    # 單維超標（只有 AC 高或只有 CGA 高）不觸發（乘積為零）——
    # 已有 Huber Loss、甜酸比、澀感閾值等獨立懲罰處理。
    # 雙維同時超標時，交叉乘積捕捉協同效應：
    #   AC=1.3×+CGA=1.3× → product=0.09 → penalty=0.698（−30%）
    #   AC=1.5×+CGA=1.5× → product=0.25 → penalty=0.368（−63%）
    ac_excess_ratio  = max(actual_perceived['AC'] / max(ideal_abs['AC'], _CONC_FLOOR) - 1.0, 0)
    cga_excess_ratio = max(cga_ratio / CGA_ASTRINGENCY_THRESHOLD - 1.0, 0)  # 複用已計算的 cga_ratio
    # ⚠️ AGENT 實作注意：cga_excess_ratio 刻意使用澀感錨定閾值（÷ CGA_ASTRINGENCY_THRESHOLD），
    # 而非對稱的 max(actual/ideal - 1, 0)。
    # 設計意圖：酸澀協同（Harshness）的協同觸發條件與澀感閾值同步——
    #   只有 CGA 已達「唾液 PRP 耗盡」的危險濃度時，AC 才會與之產生毀滅性交互作用。
    #   若改成對稱形式（actual/ideal > 1 即觸發），懲罰門檻大幅降低，任何 CGA 輕微超標
    #   都會引爆酸澀協同，使中淺焙正常高溫組合被過度懲罰。請勿對稱化此計算。
    harshness_product = ac_excess_ratio * cga_excess_ratio
    harshness_penalty = math.exp(-HARSHNESS_SLOPE * harshness_product) if harshness_product > 0 else 1.0

    # ── 層 8：焦澀協同劣變懲罰（v5.7：Ashy Synergy，僅 MD/D）────
    # 感官化學依據：類黑素（MEL，焦苦）+ 綠原酸內酯（CGA，澀感）同時過萃，
    # 競爭唾液 PRP 結合位點，產生「煙灰/燒焦橡膠」感官崩潰（Ashy/Rubbery）。
    # 深焙的 AC 極低（無法觸發層 7 的 AC×CGA），本層補足深焙的協同盲區。
    # 斜率 3.0 < 4.0：焦澀感官閾值比酸澀高約 25%，懲罰略緩。
    # 單維超標不觸發（乘積為零）。
    #   MEL=1.3×+CGA=1.3× → product=0.09 → penalty=0.763（−23%）
    #   MEL=1.5×+CGA=1.5× → product=0.25 → penalty=0.472（−53%）
    ashy_penalty = 1.0
    if roast_code in ('moderately_dark', 'dark', 'very_dark'):
        mel_excess_ratio = max(actual_perceived['MEL'] / max(ideal_abs['MEL'], _CONC_FLOOR) - 1.0, 0)
        ashy_product = mel_excess_ratio * cga_excess_ratio   # 複用 cga_excess_ratio
        ashy_penalty = math.exp(-ASHY_SLOPE * ashy_product) if ashy_product > 0 else 1.0

    # ── 最終評分（八層）─────────────────────────────────────
    final = (cosine_sim * conc_score
             * (1 - _W1 + _W1 * b_ac_sw)
             * (1 - _W2 + _W2 * b_ps)
             * tds_factor
             * cga_astringency
             * harshness_penalty
             * ashy_penalty)

    # ── 褐水防禦底板（v5.8r：極端低 TDS 毀滅性懲罰）──────────────
    # 搜尋空間邊界（最低豆量 + 低 EY）可產出 TDS < 0.80%，
    # 八層評分 + TDS_W3_LOW 不足以將「有咖啡味的洗鍋水」打入地獄。
    # 二次衰減在 TDS_BROWN_WATER_FLOOR 以下額外斬殺。
    if tds < TDS_BROWN_WATER_FLOOR:
        final *= (tds / TDS_BROWN_WATER_FLOOR) ** 2

    return round(final * 100, 1)
```

---

## 10. 主程式（完整可執行版本）

```python
def optimize(roast_code, brewer_size='xl', water_gh=50, water_kh=30, water_mg_frac=0.40, top_n=3):
    """
    四向量窮舉最佳化（Hoffman 法 + AeroPress 標準版/XL）。
    brewer_size：'standard'（200ml, 9–18g）或 'xl'（400ml, 18–30g）
    """
    cfg       = ROAST_TABLE[roast_code]
    base_temp = cfg['base_temp']
    brewer    = BREWER_PRESETS[brewer_size]
    water_ml  = brewer['water_ml']
    dose_min_x2 = int(brewer['dose_min'] * 2)   # 9g→18, 18g→36
    dose_max_x2 = int(brewer['dose_max'] * 2)   # 18g→36, 30g→60

    # v5.5r：注水階段平均接觸延遲（線性注水假設）
    # 第一滴水在 t=0 接觸咖啡粉，最後一滴在 t=pour_time
    # 平均有效浸泡起始時間 = pour_time / 2
    pour_time   = water_ml / POUR_RATE           # Standard: 16.7s, XL: 33.3s
    pour_offset = pour_time / 2.0                # Standard: 8.3s,  XL: 16.7s

    results   = []

    # v4.4 Bug Fix：夾緊溫度上限至 100°C（物理沸點）
    # 原始迴圈在 L+（base_temp=100）時會搜尋 101–103°C，違反物理現實
    max_temp = min(base_temp + 3, TEMP_BOILING_POINT)

    for temp in range(base_temp - 3, max_temp + 1):
        for dial_x10 in range(35, 66):
            dial = dial_x10 / 10
            for steep in range(60, 241, 15):
                for dose_x2 in range(dose_min_x2, dose_max_x2 + 1):  # 機型依賴豆量範圍
                    dose = dose_x2 / 2

                    # v5.3：壓降時間提前計算（不依賴 EY，僅需 dose 與 dial）
                    # v5.5：加入 steep_sec（粉床時間壓實修正）
                    press_sec   = calc_press_time(dose, dial, steep)

                    # v5.4：通道效應阻力崩潰——計算真實壓降時間（移至 press_equiv 之前）
                    # 修復幽靈萃取：通道貫穿後活塞快速壓到底，實際水-粉餅接觸時間為 display_press_sec
                    # 舊設計在 Stall 場景額外注入 1–4s 不存在的「幽靈萃取時間」
                    if press_sec > CHANNELING_PRESS_THRESHOLD:
                        display_press_sec = int(
                            CHANNELING_PRESS_THRESHOLD
                            + (press_sec - CHANNELING_PRESS_THRESHOLD) * CHANNELING_COLLAPSE_RATIO
                        )
                    else:
                        display_press_sec = press_sec

                    # v5.4：press_equiv 基於 display_press_sec（真實接觸時間），非理論 press_sec
                    press_equiv = display_press_sec * PRESS_EQUIV_FRACTION

                    # EY：雙峰動力學 + 動態細粉率 + 三重熱力修正 + Swirl 補償
                    # v5.3：press_equiv 注入 t_kinetic，壓降萃取透過動力學方程式自然分配
                    ey = calc_ey(roast_code, temp, dial, steep, dose, water_ml, water_gh,
                                 press_equiv=press_equiv, pour_offset=pour_offset)
                    if ey < EY_MIN:
                        continue

                    # v5.8r：比熱混合漿體溫度（必須在 predict_compounds 之前計算）
                    # 物質溶出量由漿體溫驅動，非壺溫（calc_ey 已用 T_avg，SCORCH 用 t_slurry）
                    t_slurry_val = round(
                        (water_ml * temp + dose * COFFEE_SPECIFIC_HEAT_RATIO * T_ENV)
                        / (water_ml + dose * COFFEE_SPECIFIC_HEAT_RATIO)
                        - BREWER_TEMP_DROP, 1
                    )

                    # v5.3：predict_compounds 接收 press_equiv，使各物質的時間演變
                    # v5.8r：接收 t_slurry（取代 temp），物質溶出量以漿體溫計算
                    compounds_raw = predict_compounds(roast_code, t_slurry_val, dial, steep, ey, water_kh,
                                                      water_mg_frac, press_equiv=press_equiv,
                                                      pour_offset=pour_offset)

                    # v4.5：通道效應後處理（必須在 calc_tds 前套用，確保 EY/TDS/Compounds 一致）
                    ey, compounds = apply_channeling(ey, compounds_raw, press_sec)

                    # v5.3：移除 v4.6 的齊頭式 EY 加法（ey += press_sec × PRESS_KINETIC_COEFF）
                    # 壓降萃取已透過 press_equiv 注入 calc_ey（動力學自然分配至雙峰）
                    # 與 predict_compounds（物質演變隨 effective_steep 推進）

                    # v4.3：calc_tds 加入 roast_code（截留係數烘焙度修正）
                    tds       = calc_tds(roast_code, dose, ey, dial, water_ml)
                    ideal_abs = build_ideal_abs(roast_code, tds)

                    # t_slurry_val 已在 predict_compounds 之前計算（v5.8r 前移）

                    # flavor_score 加入 roast_code（v3.9：MEL 焦苦修正）
                    # flavor_score 加入 water_kh（v4.0：感知過濾器用於 KH 中和修正）
                    # flavor_score 加入 t_slurry（v4.9：取代 temp，Scorching 用漿體溫判斷）
                    # flavor_score 加入 temp_initial（v5.8：SW 揮發逸散用壺溫觸發）
                    score     = flavor_score(compounds, ideal_abs, tds, roast_code, water_kh, t_slurry_val, temp)

                    # v4.3：動態靜置時間（斯托克斯沉降）
                    swirl_wait = calc_swirl_wait(dial)

                    # display_press_sec 已在迴圈頂端計算（v5.4）

                    results.append({
                        'brewer':            brewer['name'],     # v5.5r：機型名稱
                        'water_ml':          water_ml,           # v5.5r：注水量
                        'temp':              temp,
                        'dial':              dial,
                        'steep_sec':         steep,
                        'dose':              dose,
                        'swirl_sec':         SWIRL_TIME_SEC,
                        'swirl_wait_sec':    swirl_wait,
                        'press_sec':         display_press_sec,   # v5.2：輸出使用阻力崩潰後的顯示時間
                        'press_sec_internal': press_sec,          # v5.2：保留內部計算用原始壓降時間
                        'total_contact_sec': steep + SWIRL_TIME_SEC + swirl_wait + display_press_sec,
                        'ey':                ey,
                        'tds':               tds,
                        'fines_ratio':       calc_fines_ratio(dial),
                        't_slurry':          t_slurry_val,
                        't_kinetic':         round(max(0, steep - pour_offset) + SWIRL_TIME_SEC * (1.0 + SWIRL_CONVECTION_BASE * (SWIRL_DOSE_REF / dose)) + press_equiv, 1),
                        'retention':         calc_retention(roast_code, dial),
                        'compounds':         compounds,
                        'score':             score,
                    })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]
```

---

## 11. 輸出格式規格

### 11.1 終端輸出（Terminal）

```
════════════════════════════════════════════════════════
 AeroPress 四向量最佳化結果（Hoffman 法）
 機型：[標準版 200ml / XL 400ml]  |  烘焙度：中焙 (M)
 水質：GH XXX ppm  /  KH XX ppm
════════════════════════════════════════════════════════

▶ 第 1 名  風味評分：XX.X / 100
  水溫 XX°C → 漿體起始 XX.X°C  |  刻度 X.X（細粉率 XX.X%）
  被動浸泡 X:XX → 動力學等效 X:XX（含 Swirl ×X.X，豆量相依）  |  豆量 XX.Xg
  EY XX.X%  |  實際 TDS X.XXX%  |  截留係數 X.XX g/g

  ── Hoffman 沖煮流程 ─────────────────────────────────────
  T=0:00        注入 XXXml 熱水（XX°C）；正置，不預熱機身、不潤濕濾紙
  T=0:00        立刻插入活塞 1cm，開始浸泡 X:XX
  T=X:XX        被動浸泡結束，輕柔旋轉 5 秒（Swirl）
  T=X:XX+0:10   靜置 30 秒等粉渣沉底
  T=X:XX+0:40   緩慢下壓（XX 秒，依豆量 XX.Xg × 刻度 X.X），壓到底
                 v5.2：若壓降觸發通道效應（>60s），顯示阻力崩潰後的實際操作時間
  全程接觸時間：XXX 秒（X:XX）

  物質絕對強度（raw × TDS）：
  酸(AC) X.XXXX  甜(SW) X.XXXX  醇(PS) X.XXXX
  苦(CA) X.XXXX  澀(CGA) X.XXXX  焦/Body(MEL) X.XXXX
  甜酸比（AC/SW）：實際 X.XX  |  理想 X.XX
  醇苦比（PS/苦澀）：實際 X.XX  |  理想 X.XX  [深焙苦澀含 MEL×0.5]

  說明：[風味特徵一句話說明]
```

### 11.2 JSON 輸出格式

```json
{
  "input": {"roast_code": "M", "roast_name": "中焙", "water_gh_ppm": 50, "water_kh_ppm": 30},
  "hoffman_constants": {
    "water_ml": 400, "position": "standard",
    "swirl_time_sec": "★ 讀取 SWIRL_TIME_SEC 常數（v4.8 定值 = 5，勿硬編碼）",
    "swirl_convection_mult": "dynamic: 1.0 + SWIRL_CONVECTION_BASE × (18/dose)",
    "swirl_wait_sec": 30,
    "press_time_note": "dynamic, 30–60s, f(dose, dial)",
    "press_style": "all_the_way_through_hiss",
    "filter_rinsing": false, "preheating": false
  },
  "results": [
    {
      "rank": 1, "score": 0.0,
      "vectors": {"temp_c": 0, "dial": 0.0, "steep_sec": 0, "dose_g": 0.0},
      "derived": {
        "fines_ratio_pct": 0.0,
        "t_slurry_c": 0.0,
        "t_kinetic_sec": 0.0,
        "mel_bitter_coeff": 0.0
      },
      "hoffman_flow": {
        "steep_sec": 0, "swirl_sec": 10, "swirl_wait_sec": 30,
        "press_sec": 0, "total_contact_sec": 0
      },
      "metrics": {"ey_pct": 0.0, "tds_pct": 0.0, "retention_g_per_g": 0.0},
      "compounds_abs": {
        "AC": 0.0, "SW": 0.0, "PS": 0.0, "CA": 0.0, "CGA": 0.0, "MEL": 0.0,
        "ac_sw_ratio_actual": 0.0, "ac_sw_ratio_ideal": 0.0,
        "ps_bitter_ratio_actual": 0.0, "ps_bitter_ratio_ideal": 0.0
      }
    }
  ]
}
```

---

## 12. CLI 介面規格

> ⚠️ **AGENT 實作強制要求：** 標記 `★必實作` 的參數必須無條件加入，不需等待使用者要求。標記 `★個人化` 的參數在使用者未提供時須輸出提示語（見 §0 對應常數的注釋）。

```bash
python aeropress_optimizer.py \
  --brewer   xl                \   # standard（200ml, 9–18g）| xl（400ml, 18–30g）
  --roast    medium           \   # very_light, light, medium_light, medium, moderately_dark, dark, very_dark
  --preset   aquacode_7l       \   # 可用：ro | aquacode_7l | dr_you_jeju_yongamsoo | tamsaa_jeju_water_j_creation
                                   #       volvic_pure | top1_tamsaa_sweetness | top2_volvic_balance | top3_jeju_structure
  --gh       70                \   # 手動 GH（覆蓋 --preset）
  --kh       50                \   # 手動 KH（覆蓋 --preset）
  --t-env    25                \   # ★必實作  環境室溫（°C），預設 25.0，覆寫常數 T_ENV
                                   #          冬天寒流 15°C / 夏天冷氣房 25°C 均常見
                                   #          量測：沖煮當下用溫度計量室溫即可，免費且即時
  --tds-floor 0.80             \   # ★個人化  褐水防禦底板（TDS %），預設 0.80
                                   #          未提供時終端輸出提示語（見 §0 TDS_BROWN_WATER_FLOOR 注釋）
                                   #          個人化方法：§15 第 28 點四杯盲評後以此參數覆寫
  --altitude  0                \   # ★必實作  海拔高度（公尺），預設 0.0
                                   #          自動計算：TEMP_BOILING_POINT = 100 - altitude/300
                                   #          平地使用者（花蓮 ≈ 10m）：差異可忽略
                                   #          山區使用者（合歡山 3416m）：沸點降至 88.6°C，影響顯著
  --top      3                 \
  --output   terminal          \   # terminal / json / csv
  --mg-frac   0.40             \   # GH 中鎂離子比例（0.0–1.0），預設 0.40（台灣自來水 Ca 偏多）
                                   # 使用 --preset 時自動從預設表讀取，手動 --gh 時需自行指定
                                   # BWT 濾水壺（高 Mg）→ 0.90；一般自來水 → 0.38；Aquacode → 0.73
  --radar                          # 雷達圖（需 matplotlib）
```

### 12.1 CLI 參數 → 程式內部映射表

> ⚠️ **AGENT 實作強制要求：** 下表為 `main.py` 的完整 argparse → 常數/函數 映射規格，必須完整實作，不得遺漏。

| CLI 參數 | 型別 | 預設值 | 注入方式 | 注入時機 |
|---|---|---|---|---|
| `--brewer` | str | `xl` | `optimize(brewer_size=args.brewer)` | 呼叫 optimize() 時傳入 |
| `--roast` | str | `M` | `optimize(roast_code=args.roast)` | 呼叫 optimize() 時傳入 |
| `--preset` | str | `None` | 查 `WATER_PRESETS[args.preset]`，解出 `gh`/`kh`/`mg_frac` | 解析後覆蓋 gh/kh/mg_frac |
| `--gh` | int | `50` | `optimize(water_gh=args.gh)` | 呼叫 optimize() 時傳入 |
| `--kh` | int | `30` | `optimize(water_kh=args.kh)` | 呼叫 optimize() 時傳入 |
| `--mg-frac` | float | `0.40` | `optimize(water_mg_frac=args.mg_frac)` | 呼叫 optimize() 時傳入 |
| `--t-env` | float | `25.0` | `constants.T_ENV = args.t_env` | **argparse 解析後、optimize() 呼叫前，全域覆寫** |
| `--tds-floor` | float | `0.80` | `constants.TDS_BROWN_WATER_FLOOR = args.tds_floor` | **argparse 解析後、optimize() 呼叫前，全域覆寫** |
| `--altitude` | float | `0.0` | `constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0` | **argparse 解析後、optimize() 呼叫前，全域覆寫** |
| `--top` | int | `3` | `optimize(top_n=args.top)` | 呼叫 optimize() 時傳入 |
| `--output` | str | `terminal` | 傳給 output 模組選擇渲染器 | optimize() 結果回傳後 |
| `--radar` | flag | `False` | 傳給 `radar.py` | output 完成後 |

> **全域覆寫的執行順序：**
> ```python
> # main.py 骨架（AGENT 必須依此結構實作）
> import constants                                   # 1. 先 import constants 模組
> args = parser.parse_args()                         # 2. 解析 CLI
> constants.T_ENV = args.t_env                       # 3. 全域覆寫環境參數（三行，順序不限）
> constants.TDS_BROWN_WATER_FLOOR = args.tds_floor
> constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0
> if args.preset:                                    # 4. preset 展開（覆蓋 gh/kh/mg_frac）
>     p = WATER_PRESETS[args.preset]
>     args.gh, args.kh, args.mg_frac = p['gh'], p['kh'], p['mg_frac']
> results = optimize(                                # 5. 執行最佳化
>     roast_code=args.roast, brewer_size=args.brewer,
>     water_gh=args.gh, water_kh=args.kh,
>     water_mg_frac=args.mg_frac, top_n=args.top
> )
> ```
> **注意：** `--tds-floor` 未提供時（使用預設 0.80），`main.py` 須在 argparse 解析後輸出提示：
> `「提示：TDS_BROWN_WATER_FLOOR 使用預設值 0.80%，建議依個人口感以 --tds-floor 調整（說明：§15 第 28 點）」`


---

## 12.1 main.py 完整入口骨架（AGENT 必實作）

> ⚠️ **AGENT 實作指示：** 下方骨架為 `main.py` 的完整 `argparse` + 常數注入 + 輸出路由。**必須逐行實作，不得省略任何步驟。** 三個環境常數（`T_ENV`、`TDS_BROWN_WATER_FLOOR`、`TEMP_BOILING_POINT`）的全域注入**必須在任何模型函數被呼叫之前**完成。

```python
# main.py
import argparse
import sys
import constants                     # §0 所有常數定義於此
from models.ey_model import calc_ey, calc_fines_ratio, _calc_t_eff
from models.tds_model import calc_tds, calc_retention, calc_swirl_wait, calc_press_time, apply_channeling
from models.compounds import predict_compounds
from models.scoring import flavor_score, build_ideal_abs
from optimizer import optimize
from output.terminal import print_terminal
from output.export import export_json, export_csv
from output.radar import plot_radar
from data.water_presets import get_water_preset


def main():
    parser = argparse.ArgumentParser(description='AeroPress 四向量最佳化系統 v5.8r')

    # ── 沖煮參數 ────────────────────────────────────────
    parser.add_argument('--brewer',     default='xl',      choices=['standard', 'xl'])
    parser.add_argument('--roast',      required=True,     choices=['very_light','light','medium_light','medium','moderately_dark','dark','very_dark'])
    parser.add_argument('--preset',     default=None)
    parser.add_argument('--gh',         type=float,        default=None, help='手動 GH ppm（覆蓋 --preset）')
    parser.add_argument('--kh',         type=float,        default=None, help='手動 KH ppm（覆蓋 --preset）')
    parser.add_argument('--mg-frac',    type=float,        default=None,
                        help='GH 中鎂離子比例 0.0–1.0（預設 0.40）；使用 --preset 時自動讀取，手動 --gh/--kh 時建議指定')
    parser.add_argument('--top',        type=int,          default=3)
    parser.add_argument('--output',     default='terminal', choices=['terminal','json','csv'])
    parser.add_argument('--radar',      action='store_true')

    # ── 環境參數（★必實作）───────────────────────────────
    parser.add_argument('--t-env',      type=float, default=25.0,
                        help='環境室溫 °C（預設 25.0）；影響 T_ENV → t_slurry 與牛頓冷卻終態')
    parser.add_argument('--tds-floor',  type=float, default=None,
                        help='褐水防禦底板 TDS%%（預設 0.80）；建議先完成 §15 #28 四杯盲評後設定')
    parser.add_argument('--altitude',   type=float, default=0.0,
                        help='海拔高度 m（預設 0.0）；自動計算 TEMP_BOILING_POINT = 100 - altitude/300')

    args = parser.parse_args()

    # ── 步驟 1：環境常數注入（必須在任何模型函數呼叫前完成）──
    constants.T_ENV = args.t_env
    constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0

    if args.tds_floor is not None:
        constants.TDS_BROWN_WATER_FLOOR = args.tds_floor
    else:
        # ★個人化提示語：使用者未提供時輸出
        print(
            '\n⚠️  提示：TDS_BROWN_WATER_FLOOR 使用預設值 0.80%。'
            '\n    建議依個人口感以 --tds-floor 調整（說明：§15 第 28 點）\n',
            file=sys.stderr
        )

    # ── 步驟 2：水質解析 ────────────────────────────────
    if args.gh is not None and args.kh is not None:
        water_gh, water_kh = args.gh, args.kh
        water_mg_frac = args.mg_frac if args.mg_frac is not None else 0.40
    elif args.preset is not None:
        preset = get_water_preset(args.preset)
        water_gh, water_kh, water_mg_frac = preset['gh'], preset['kh'], preset.get('mg_frac', 0.40)
    else:
        # 預設值：台灣常見自來水估算中位數
        water_gh, water_kh, water_mg_frac = 50.0, 30.0, 0.40
        print('⚠️  未指定水質，使用預設 GH=50 / KH=30 / mg_frac=0.40 ppm。', file=sys.stderr)

    # ── 步驟 3：執行最佳化 ──────────────────────────────
    results = optimize(
        roast_code=args.roast,
        brewer_size=args.brewer,
        water_gh=water_gh,
        water_kh=water_kh,
        water_mg_frac=water_mg_frac,
        top_n=args.top,
    )

    # ── 步驟 4：輸出路由 ────────────────────────────────
    if args.output == 'terminal':
        print_terminal(results, args.roast, water_gh, water_kh)
    elif args.output == 'json':
        export_json(results, args.roast)
    elif args.output == 'csv':
        export_csv(results, args.roast)

    if args.radar:
        plot_radar(results)


if __name__ == '__main__':
    main()
```

---

## 12.2 實作自驗錨點（AGENT 必執行）

> ⚠️ **AGENT 實作指示：** 程式碼實作完成後，**必須執行以下驗證組合，確認輸出數值在容許誤差範圍內後才算實作完成。** 若任何數值超出範圍，表示有函數被錯誤實作，需要回頭排查。

**驗證指令：**
```bash
python main.py --brewer xl --roast M --gh 50 --kh 30 --t-env 25 --altitude 0 --tds-floor 0.80 --top 1
```

**預期輸出範圍（M 焙 / GH=50 / KH=30 / 室溫 25°C / 海平面）：**

| 指標 | 預期範圍 | 說明 |
|---|---|---|
| 最佳水溫 | 89–95°C | M 焙 base_temp=92，搜尋空間 89–95 |
| 最佳研磨刻度 | 4.0–5.5 | 中焙中細研磨典型範圍 |
| 最佳被動浸泡 | 90–180s | M 焙中等浸泡 |
| 最佳豆量 | 20–26g | XL 中段豆量 |
| EY | 18–22% | SCA 最佳萃取率 18–22% |
| TDS | 1.10–1.35% | SCA 最佳濃度 1.15–1.35% |
| 風味評分 | > 70 / 100 | 低於此值表示評分函數異常 |
| `t_slurry` | 比壁溫低 3–7°C | 比熱混合 + 機身熱容，XL 30g 約 −6°C |

**若數值超出範圍，優先檢查：**
1. EY 偏低（< 15%）→ `K_BASE` 注入異常或 `T_ENV` 未正確覆寫
2. TDS 偏高（> 1.5%）→ `calc_retention` 或 `water_ml` 傳參錯誤
3. 風味評分全部 < 50 → `flavor_score` 的 `roast_code` 或 `t_slurry` 傳參順序錯誤
4. `t_slurry` 等於 `temp` → `BREWER_TEMP_DROP` 或比熱混合公式未正確實作

---

## 13. 檔案結構

```
aeropress_optimizer/
├── main.py
├── constants.py             # ⚠️ 所有 §0 常數定義於此；以下為版本摘要（以最新為準）
│                            #   v5.8r：TDS_BROWN_WATER_FLOOR=0.80、COFFEE_SPECIFIC_HEAT_RATIO=0.33
│                            #          T_ENV=25.0（CLI --t-env 覆寫）
│                            #          TEMP_BOILING_POINT=100（CLI --altitude 覆寫）
│                            #   v5.7：SW_AROMA_SLOPE=0.02、ASHY_SLOPE=3.0
│                            #   v5.6：SWIRL_RESET_FRACTION=0.35
│                            #   v5.5：CONC_GRADIENT_COEFF=0.5、BED_COMPACTION_COEFF=0.15、
│                            #          HARSHNESS_SLOPE=4.0、PRESS_EQUIV_FRACTION=0.15、
│                            #          K_CGA_TIME=0.015、CGA_TIME_MAX=0.50、K_AC_DECAY=0.0035
│                            #   v5.3：ARRHENIUS_COEFF=0.05、COOL_RATE=0.0008（修正 0.02）
│                            #   v5.1：K_PS=0.005、PS_TIME_MAX=0.20、CGA_ASTRINGENCY_*、
│                            #          MG_FRAC_AC_SW_MULT=0.16、MG_FRAC_PS_CGA_MULT=0.08
│                            #   v4.x：CHANNELING_*、DARCY_PRESS_EXP、ASYM_*_MULT、
│                            #          TDS_PREFER、TDS_GAUSS_SIGMA_*、KH_PERCEPT_DECAY=150
│                            #          SWIRL_CONVECTION_BASE=1.0（v4.8 修正；v4.7 以前舊值 0.5，已廢棄）
│                            #          SWIRL_DOSE_REF=18
│                            #   v3.9：BREWER_TEMP_DROP=2.5、MEL_BITTER_COEFF dict
├── models/
│   ├── ey_model.py          # calc_ey()（v5.5：有限溶劑 brew_capacity 修正 _ey_max）
│   │                        #           （v5.4：T_avg 時間平均溫度 Arrhenius）
│   │                        # calc_fines_ratio()（v3.8：動態細粉率）
│   │                        # _calc_t_eff()（v3.7，輸入改為 t_slurry + t_kinetic）
│   ├── tds_model.py         # calc_retention(roast_code, dial) → float
│   │                        # calc_tds(roast_code, dose, ey, dial, water_ml=400) → float
│   │                        # calc_swirl_wait(dial) → int
│   │                        # calc_press_time(dose, dial, steep_sec=120) → int   ← v5.4 加入 steep_sec
│   │                        # apply_channeling(ey, compounds, press_sec) → (float, dict)
│   ├── compounds.py         # predict_compounds(roast_code, temp, dial, steep_sec, ey,
│   │                        #                   water_kh=30, water_mg_frac=0.40,
│   │                        #                   press_equiv=0, pour_offset=0) → dict
│   └── scoring.py           # flavor_score(actual_raw, ideal_abs, tds, roast_code,
│                            #              water_kh=30, t_slurry=90, temp_initial=90) → float
│                            #   ⚠️ 八層架構（v5.7 定版）：
│                            #   層1 余弦相似度 | 層2 Huber 濃度接近（非對稱）| 層3 甜酸比
│                            #   層4 醇苦比（MEL 係數）| 層5 TDS 高斯（動態 W3）
│                            #   層6 CGA 澀感絕對閾值 | 層7 酸澀協同（AC×CGA）
│                            #   層8 焦澀協同（MEL×CGA，僅 MD/D）
├── data/
│   ├── roast_table.py       # ⚠️ AGENT 實作指示：ROAST_TABLE 定義於 constants.py（§0）
│   │                        #   此檔可選擇性實作為 from constants import ROAST_TABLE 的重導出
│   │                        #   或直接由各模型 from constants import ROAST_TABLE 使用，二擇一即可
│   ├── ideal_flavor.py      # ⚠️ 同上：IDEAL_FLAVOR、TDS_ANCHORS 定義於 constants.py（§0）
│   │                        #   build_ideal_abs() 於 models/scoring.py，直接 import constants 使用
│   └── water_presets.py     # WATER_PRESETS（含 BWT，v3.6）+ get_water_preset() 函數
├── optimizer.py             # optimize()（v3.9：flavor_score 調用加入 roast_code；
│                            #            輸出新增 t_kinetic、mel_bitter_coeff）
├── output/
│   ├── terminal.py          # 新增漿體溫度、動力學等效時間、焦苦修正顯示
│   ├── export.py            # JSON/CSV 新增 derived 欄位
│   └── radar.py
└── README.md
```

> ⚠️ **AGENT 強制實作規則：全域常數注入的模組隔離（v5.8s 新增）**
>
> `T_ENV`、`TEMP_BOILING_POINT`、`TDS_BROWN_WATER_FLOOR` 三個常數由 `main.py` 在執行期以 CLI 參數覆寫：
> ```python
> constants.T_ENV = args.t_env
> constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0
> constants.TDS_BROWN_WATER_FLOOR = args.tds_floor
> ```
> 此覆寫**只有在子模組以屬性存取方式引用時才生效**。
>
> | 引用方式 | CLI 覆寫是否生效 | 說明 |
> |---|:---:|---|
> | `import constants` → 使用 `constants.T_ENV` | ✅ 生效 | 每次存取都經由模組物件讀取最新值 |
> | `from constants import T_ENV` → 直接使用 `T_ENV` | ❌ 靜默失效 | import 時綁定的是當時的值（25.0），main.py 的覆寫永遠看不到 |
>
> **強制要求：** `ey_model.py`、`tds_model.py`、`compounds.py`、`scoring.py`、`optimizer.py` 中所有存取上述三個常數的程式碼，**必須**以 `constants.T_ENV`（而非 `T_ENV`）的形式存取。違反此規則的函數，`--t-env`、`--altitude`、`--tds-floor` 等 CLI 參數將靜默無效。
>
> **建議的標準引用模式：**
> ```python
> # 各子模組頂端
> import constants
>
> def calc_ey(...):
>     r = constants.COOL_RATE          # 非環境覆寫常數，可也用此模式統一風格
>     t_slurry = t_mix - constants.BREWER_TEMP_DROP
>     T_avg = constants.T_ENV + ...    # ← 必須用 constants.T_ENV
>     ...
>
> def flavor_score(...):
>     if tds < constants.TDS_BROWN_WATER_FLOOR:  # ← 必須用 constants.TDS_BROWN_WATER_FLOOR
>         final *= ...
> ```

---

### 13.1 output 模組函數最小骨架（AGENT 必實作）

> ⚠️ **AGENT 實作指示：** 下列四個函數為 `output/` 模組的最小實作規格，包含完整簽名與各欄位資料來源。**必須逐參數實作，不得自行推斷缺失的欄位來源。**

```python
# output/terminal.py

def print_terminal(results: list[dict], roast_code: str, water_gh: float, water_kh: float) -> None:
    """
    results    : optimize() 回傳的 list[dict]（已依 score 降序排列）
    roast_code : 焙度代號（如 'M'），用於顯示 ROAST_TABLE[roast_code]['name']
    water_gh   : GH ppm（整數或浮點數）
    water_kh   : KH ppm（整數或浮點數）

    各欄位來源對照（§11.1 模板）：
      水溫           → r['temp']
      漿體起始溫     → r['t_slurry']
      刻度           → r['dial']
      細粉率         → r['fines_ratio'] × 100（%）
      被動浸泡       → r['steep_sec']（秒→分:秒格式）
      動力學等效時間 → r['t_kinetic']（秒→分:秒格式）
      Swirl 倍率     → 1.0 + constants.SWIRL_CONVECTION_BASE × (constants.SWIRL_DOSE_REF / r['dose'])
      豆量           → r['dose']
      EY             → r['ey']
      TDS            → r['tds']
      截留係數        → r['retention']
      壓降秒數       → r['press_sec']（阻力崩潰後顯示時間）
      靜置時間       → r['swirl_wait_sec']
      全程接觸時間   → r['total_contact_sec']
      物質絕對強度   → r['compounds']（dict，六個鍵值）
      甜酸比（實際） → r['compounds']['AC'] / r['compounds']['SW']（以 actual_abs 計算）
      甜酸比（理想） → 從 build_ideal_abs(roast_code, r['tds']) 計算
      醇苦比（實際） → r['compounds']['PS'] / (CA + CGA + MEL × MEL_BITTER_COEFF[roast_code])
      醇苦比（理想） → 從 build_ideal_abs(roast_code, r['tds']) 計算
      風味評分       → r['score']
      機型           → r['brewer']
      注水量         → r['water_ml']
    """
    ...


# output/export.py

def export_json(results: list[dict], roast_code: str, filepath: str = 'output.json') -> None:
    """
    results    : optimize() 回傳的 list[dict]
    roast_code : 焙度代號
    filepath   : 輸出路徑（預設 output.json）

    JSON 結構依 §11.2 規格：
      "input"            → roast_code + ROAST_TABLE[roast_code]['name'] + water_gh/kh（從 results[0] 不可得，需由呼叫端傳入或從 constants 讀取——
                           ⚠️ 簡化做法：在 export_json 簽名加入 water_gh, water_kh 參數，main.py 傳入）
      "hoffman_constants"→ water_ml = r['water_ml']、swirl_time_sec = constants.SWIRL_TIME_SEC（★ 不得硬編碼為 10）
      "results[i]"       → 依 §11.2 的 rank / score / vectors / derived / hoffman_flow / metrics / compounds_abs 格式

    mel_bitter_coeff 來源：from constants import MEL_BITTER_COEFF; MEL_BITTER_COEFF[roast_code]
    """
    ...


def export_csv(results: list[dict], roast_code: str, filepath: str = 'output.csv') -> None:
    """
    扁平化輸出：每個 result 為一行，欄位為 results[i] 所有 key + compounds 展開的六個子欄位。
    compounds dict 展開為 compounds_AC、compounds_SW... 等六欄。
    """
    ...


# output/radar.py

def plot_radar(results: list[dict], top_n: int = 3) -> None:
    """
    results : optimize() 回傳的 list[dict]；只繪製前 top_n 筆
    需要 matplotlib（import matplotlib.pyplot as plt）
    雷達圖六維：AC / SW / PS / CA / CGA / MEL
    資料來源：r['compounds']（六個物質的 raw 值），需正規化為 0–1 以供雷達圖顯示

    建議正規化方式：
      six_max = {k: max(r['compounds'][k] for r in results[:top_n]) for k in KEYS}
      normalized = {k: r['compounds'][k] / max(six_max[k], 1e-8) for k in KEYS}
    """
    ...
```

---

## 14. 模型已知限制

| 限制 | 說明 |
|---|---|
| 機身熱容為普適固定常數 | `BREWER_TEMP_DROP = 2.5°C` 基於熱力學比值推導（塑膠質量與水量等比例放大，失溫幅度與機型無關），未考慮環境溫度、注水速度的差異；精確值需量測注水後 5 秒的漿體溫度 |
| Swirl 對流倍率為估算值 | `SWIRL_CONVECTION_BASE = 1.0`（v4.8）無實驗依據；操作時間 `SWIRL_TIME_SEC = 5s` 同樣為估算值（真實手法約 3 下，可能更接近 3–4 秒）；兩者乘積決定等效補償時間，需以折射儀實測同步校正（見 §15 第 13 點）|
| 動態細粉率為線性估算 | `FINES_RATIO_DIAL_SLOPE = 0.04` 基於物理直覺，非 ZP6 實測值；實際分佈可能為非線性 |
| 熱平衡失溫為簡化公式 | 忽略杯體預熱狀態、注水速度、環境溫度等變數 |
| MEL 焦苦係數為主觀設定 | `MEL_BITTER_COEFF['MD'] = 0.5` 為保守估算；實際 MEL 焦苦轉換點取決於烘焙曲線與豆種 |
| 巨觀 EY 與微觀物質解耦 | `calc_ey` 與 `predict_compounds` 底層邏輯獨立，物質加總不等於總 EY（終極解法見 §15 第 10 點）|
| 感知過濾器係數為估算值 | `KH_PERCEPT_DECAY = 150`（v4.1 指數衰減版）基於緩衝化學推算，非感官測試數據；實際感知中和效率受咖啡原始 pH、溫度、個人敏感度影響 |
| Swirl 黏滯度函數為線性近似 | `swirl_mult = 1.0 + 0.5 × (18/dose)` 為一階近似；實際漿體黏滯度隨豆量的變化是非線性的（與溫度、細粉率、粒徑分佈有關），建議未來以實測 EY 反推校正 |
| TDS 偏好峰值為主觀先驗 | `TDS_PREFER` 字典基於一般感官認知（淺焙偏高濃度以突出酸質、深焙偏低以抑制焦苦），非個人化設定；建議實際沖煮後依個人喜好調整各焙度峰值。v4.2 升級為非對稱高斯（`SIGMA_LOW=0.15` / `SIGMA_HIGH=0.25`），兩個 Sigma 值均為主觀估算，建議以盲測評分（對稱偏差量的主觀評分差異）迭代校正 |
| 達西指數壓降為近似值 | `DARCY_PRESS_EXP = 0.6` 未經 AeroPress 實測；實際 Stall 閾值取決於細粉率分佈、濾紙類型（金屬濾紙 vs 紙濾紙）與施壓速率。v4.2 Bug Fix 後，18g 基礎壓降時間也受 `dial_modifier` 影響，極粗研磨（dial=6.5）夾緊至 `PRESS_TIME_MIN_FLOOR=15s` |
| 非對稱懲罰倍率為主觀設定 | `ASYM_BITTER_MULT / ASYM_SWEET_MULT = 1.5` 基於感官心理學直覺；建議未來以盲測評分數據（相同組合、不同苦澀/甜感偏差量）迭代校正 |
| 感官平衡懲罰為線性混合 | W1=0.15、W2=0.12 為主觀設定，建議實際沖煮後對照主觀評分調整 |
| 物質強度為半定量預測 | 基於物理化學原理建模，非 GC-MS 數據 |
| 各物質焙度基礎值為主觀先驗 | `ac_roast`、`sw_roast`、`ps_roast`、`ca_roast`、`cga_roast`、`mel_roast` 六組焙度字典均為感官經驗估算，非 GC-MS 或 HPLC 量測值；建議未來以分段萃取實驗（§15 #10）反推各物質的真實焙度依賴基準值 |
| 六維評分權重為主觀設定 | `WEIGHTS = {AC:1.2, SW:1.8, PS:1.5, CA:1.0, CGA:1.3, MEL:1.0}` 基於感官重要性直覺（甜感最重要、苦感最低），非盲測數據；建議以相同配方不同偏差方向的盲測評分反推各維度的真實感官權重 |
| K_PS/PS_TIME_MAX 為定性設定 | `K_PS=0.005`（大分子極慢擴散）與 `PS_TIME_MAX=0.20`（漸近線飽和值）基於分子量推理，非獨立物理量測；修正幅度受 PS 在六維向量中的權重（WEIGHTS['PS']=1.5）稀釋，對最終排名的邊際影響較小；建議以不同浸泡時間的 Body 感官評分間接校正 |
| K_MAX / EY_MIN 為設計選擇 | `K_MAX=0.060` 為速率常數安全夾緊上限（防止極細粉 + 高溫場景下 k 爆炸），`EY_MIN=14.0` 為搜尋空間過濾門檻（SCA 最低可接受萃取率附近）；兩者均為架構防呆而非物理量測值，若實測顯示正常配方的 k 或 EY 觸及夾緊邊界，應調整而非移除 |
| K_BASE/K_MIN 為暫定校準值 | `K_BASE=0.025`、`K_MIN=0.006` 以 M 焙基準配方（92°C/dial4.5/120s/22g）→ EY≈19% 為目標的二元搜尋校準值；v5.2 原值 0.010/0.003 在 v5.3 COOL_RATE 修正 + v5.4 T_avg 修正後產出不合理的 EY（12.5%）；暫定值待折射儀實測 3–5 組配方後精確校正（見 §15 第 3 點） |
| 注水流速為估算值 | `POUR_RATE=12 ml/s` 基於 Bonavita 鵝頸壺中高速注水的文獻數據推估（Brewista max=24、Fellow Stagg max=20、慢速手沖=3）；Hoffman 法為快速一次注滿（非緩慢繞圈），12 ml/s 為保守預設；實際流速因壺型、傾斜角度、水位高度而異；建議以電子秤+計時器量測「注滿 200/400ml 所需秒數」後直接校正 |
| 理想風味表為主觀先驗 | 建議實際沖煮後迭代校正 IDEAL_FLAVOR |
| 未考慮豆種與處理法差異 | 日曬／水洗／厭氧處理法會移動各類物質的基礎濃度 |
| 烘焙度截留率為推算估值 | `RETENTION_BASE` 字典數值（L+=2.00～D=2.50）基於烘焙物理推理，未經折射儀 + 磅秤實測（量測方法：固定條件沖煮後秤量出杯重，反推截留量）；深焙的研磨斜率（0.08）低於淺焙（0.10）亦為估算 |
| 咖啡因速率常數為估算值 | `K_CA = 0.030` 基於文獻描述（90s 內 85%+ 溶出）推算；實際值受豆種、研磨度、溫度影響；建議以不同浸泡時間（45s/90s/150s）量測折射儀 TDS 後，結合 CA 占比反推校正 |
| 斯托克斯沉降時間為線性近似 | `SWIRL_WAIT_SLOPE = 10`（每格研磨增減 10 秒）為一階線性近似；實際沉降速度與顆粒半徑平方、漿體黏滯度、溫度均有關，真實行為在極細端（dial<4.0）可能非線性加速；建議目視觀察不同研磨度的實際粉渣沉降時間後校正 |
| 沸點夾緊未含高海拔修正 | `TEMP_BOILING_POINT = 100` 預設為海平面值；現已支援 CLI `--altitude`（公尺）自動計算 `100 - altitude/300`。花蓮市區（≈10m）誤差 < 0.03°C 可忽略；台灣中高海拔（梨山 2000m → 93.3°C；合歡山 3416m → 88.6°C）影響顯著，建議山區使用者傳入實際海拔 |
| 高溫劣變閾值為估算值 | `SCORCH_PARAMS` 中各焙度的閾值與靈敏度基於化學知識與感官推理，非盲測數據；CGA 水解速率受豆種、pH 與具體溫度曲線影響。v4.5 改為連續函數後消除評分斷崖，但各焙度靈敏度仍需以高溫 vs 適溫同一食譜的盲測評分差異迭代校正 |
| 通道效應係數為估算值 | `CHANNELING_EY_SLOPE=0.005`（每秒 0.5% EY 衰減）、`CHANNELING_CGA_MULT=2.5`（局部過萃放大倍率）基於流體力學定性推理，非 AeroPress 實測值；實際通道效應的嚴重程度取決於施壓速率、濾紙類型、粉餅均勻度；建議以相同配方在不同施壓速度下量測 EY 與感官澀度後反推校正 |
| PS 溫度係數為估算值 | `PS *= 1.0 + (temp-90) * 0.015` 中斜率 0.015/°C 基於多糖體吸熱溶解的定性推理，未以不同溫度的出杯液體黏度或 Body 感官評分實測校正；各焙度、豆種的多糖體熱力學行為可能存在差異 |
| SW 甜感峰值溫度偏移為估算值 | `optimal_sw_temp = base_temp - 2` 的 `−2` 係數基於烘焙化學推理（M 焙錨點=90°C），未以不同溫度的甜感盲測數據校正；L+（98°C）與 D（83°C）的峰值偏移幅度尤其需要實測驗證 |
| 阿瑞尼斯速率係數為估算值 | `ARRHENIUS_COEFF=0.05`（每 °C ±5% 速率變化）基於一般固液擴散的活化能文獻值推算，非 AeroPress 專用實測值；不同物質（有機酸 vs 多糖體）的活化能可能不同，統一係數為一階近似；建議以不同溫度（82/90/98°C）固定其他參數的 EY 量測反推校正 |
| 質量分率正規化假設物質獨立 | `flavor_score` 入口的 `actual_raw` 正規化假設六大物質加總代表可溶物質的全貌，但實際可溶固體中還包含本系統未建模的微量物質（如脂質、三酸甘油脂等）；正規化後各物質的絕對濃度略低於真實值（因分母膨脹），但比例關係正確 |
| 通道效應阻力崩潰比為估算值 | `CHANNELING_COLLAPSE_RATIO=0.20` 基於流體力學定性推理（通道貫穿後阻力瓦解），非 AeroPress 實測；實際崩潰速度取決於通道直徑、粉餅厚度、施壓力道；建議以極細粉+大豆量場景的實際壓降時間觀察校正 |
| 牛頓冷卻率為估算值 | `COOL_RATE=0.0008` 基於熱力學估算（h×A/(m×c)≈0.00012）加實測經驗修正；合理範圍 0.0005–0.001，取決於活塞密封程度、環境溫度、注水量；建議以 §15 第 2 點的方案實測校正（浸泡開始與結束各量一次水溫，擬合牛頓冷卻曲線）。注意：v5.2 以前的 0.02 比真實值快 25–160 倍，為系統中隱藏最深的物理錯誤 |
| 壓降等效折算比為估算值 | `PRESS_EQUIV_FRACTION=0.15`（壓降效率≈被動浸泡的 15%）基於 v4.6 原始設計推理，非 AeroPress 實測；實際壓降萃取效率取決於流速、溫度、粉餅阻力；建議以相同配方不同壓降速度的 TDS 量測反推校正 |
| CGA/AC 指數常數為校準值 | `K_CGA_TIME=0.015`、`K_AC_DECAY=0.0035` 均以「搜尋空間邊界（240s）匹配舊線性值」為校準目標，非獨立物理推導；飽和極限 `CGA_TIME_MAX=0.50` 為估算值，建議以長浸泡（>300s）的 GC-MS 或感官數據校正 |
| T_avg 近似非精確 Arrhenius 積分 | $T_{avg}$ 是溫度的時間平均值，但阿瑞尼斯方程式中 $\langle e^{f(T)} \rangle \neq e^{\langle f(T) \rangle}$（Jensen 不等式）。在 AeroPress 溫度範圍（82–100°C）與 ARRHENIUS_COEFF=0.05 下，此近似誤差 < 2%，遠小於常數估算本身的不確定性；精確解需數值積分 $\bar{k} = \frac{1}{t}\int_0^t k_0 e^{A(T(\tau)-90)} d\tau$，計算成本高 70,525 倍且收益極低 |
| CGA 絕對閾值依賴 TDS_PREFER 估算 | v5.4 的 CGA 澀感分母錨定至 `build_ideal_abs(roast, TDS_PREFER)['CGA']`，TDS_PREFER 本身為主觀先驗（§14 已列）；TDS_PREFER 偏差會同時影響層 5（TDS 高斯）和層 6（CGA 閾值），建議以盲測校正 TDS_PREFER 後兩層自動同步 |
| 有限溶劑分配係數為估算值 | `CONC_GRADIENT_COEFF=0.5`（溶質分配係數 K_d）為極保守估算值；真實 K_d 取決於豆種、烘焙度、研磨度與水溫；18g→30g 的差異修正僅 ~0.6% EY_max，在搜尋空間中屬微弱修正；建議以不同豆量（18/24/30g）固定其他參數的 EY 量測反推校正 |
| 粉床壓實係數為估算值 | `BED_COMPACTION_COEFF=0.15` 基於斯托克斯沉降的定性推理，未以 AeroPress 實測壓降力道量測；v5.6 改以 `effective_compaction_time` 計算（已納入 Swirl 重置），實際壓實程度取決於細粉率、水溫（影響黏滯度）、容器幾何；建議以不同浸泡時間的壓降阻力（力量感測器或計時）校正 |
| Swirl 重置比例為理論推導值 | `SWIRL_RESET_FRACTION=0.35` 由斯托克斯沉降 + 渦流雷諾數（Re≈500）推導，非 AeroPress 實測；可懸浮粒徑 <80μm 的估算本身依賴細粉粒徑分佈假設；建議以不同浸泡時間（60s/120s/240s）的實際壓降力道量測反推校正 |
| 自由溶劑修正精度受截留率約束 | `free_water = water_ml − dose × calc_retention(roast_code, dial)`；`calc_retention` 本身為推算估值（RETENTION_BASE 未實測），截留率不確定性直接傳播至 `brew_capacity`；30g D 焙的修正差異 −0.9%，在截留率誤差範圍內；建議以磅秤實測出杯重後先校正截留率，再評估 brew_capacity 修正的有效性 |
| 酸澀協同懲罰斜率為估算值 | `HARSHNESS_SLOPE=4.0` 基於感官心理學定性推理（與 CGA_ASTRINGENCY_SLOPE 設計一致），非盲測數據；實際「金屬酸澀」感知閾值因人而異；建議以「AC 與 CGA 同時超標 vs 單一超標」的感官盲測評分差異校正 |
| 焦澀協同懲罰斜率為推導值 | `ASHY_SLOPE=3.0`（v5.7）由酸澀協同按感官閾值比例推導，非盲測數據；僅對 MD/D 焙度啟用；建議以「MEL 與 CGA 同時超標 vs 單一超標」的深焙盲測評分差異校正；若深焙排名在實測中已符合預期可考慮調低 SLOPE |
| 高溫 SW 逸散斜率為估算值 | `SW_AROMA_SLOPE=0.02`（v5.7）及閾值 95°C 基於揮發性芳香物質熱降解的感官化學推理，非量測數據；v5.8 觸發變數改為 `temp_initial`（壺溫），修正大豆量免疫問題；實際逸散率受豆種（含不同揮發物比例）、注水速度、容器開口面積影響；建議以相同配方、不同 temp_initial（90/95/100°C）的感官盲測甜感評分差異校正 |
| 注水湍流等效未實作（澄清） | v5.7 明確不採納注水正向湍流等效，`pour_equiv` 從未寫入程式碼；`t_kinetic = max(0, steep_sec - pour_offset) + SWIRL_TIME_SEC × swirl_mult + press_equiv` 無代數對消問題；Gemini v5.8 壓力測試描述的「`pour_offset` 與 `pour_equiv` 相消」在程式碼中不存在（此為 Gemini 第三次描述不存在的程式碼，前兩次：v4.5 時序悖論、v4.6 漸近線 Bug）；注水湍流等效待折射儀 A/B 實測後決定（§15-18）|
| Spritzer / Jeju GH/KH 為估算值 | `WATER_PRESETS` 中 Spritzer（GH=85, KH=60）與 Jeju（GH=18, KH=15）數值來自品牌公開資料與文獻估算，不同批次、產地可能有差異；建議以水族滴定試劑實測後覆蓋 |
| TDS 動態懲罰權重為主觀設定 | `TDS_W3_LOW=0.25` / `TDS_W3_HIGH=0.10` 基於「水感是不可逆缺陷、濃郁可補救」的感官判斷；實際最佳懲罰強度因人喜好而異，建議以盲測評分（相同輪廓、不同 TDS 的主觀評分差異）迭代校正 |
| 鈣鎂離子萃取偏好係數為估算值 | `MG_FRAC_AC_SW_MULT = 0.16`（Mg²⁺ 對 AC/SW 的最大正向乘數）與 `MG_FRAC_PS_CGA_MULT = 0.08`（Ca²⁺ 對 PS/CGA 的最大正向乘數）均基於「Mg²⁺ 偏好小分子有機酸、Ca²⁺ 偏好大分子多糖體」的化學親和力推理，量級為純粹估算值，非 GC-MS 或感官盲測數據；8%/16% 的實際影響幅度待「純鎂水 vs 純鈣水」對照實驗驗證（見 §15 第 27 點）|
| 細粉/粗粉速率倍率為文獻估算值 | `K_FINES_MULT = 10.0`（細粉萃取速率為粗粉的 10 倍）與 `K_BOULDERS_MULT = 0.55` 均來自文獻經驗法則（Rule of Thumb）；「細粉約快 10 倍」的數值因磨豆機機型與細粉定義（<100μm 或 <200μm）不同，真實倍率可能介於 5–15 倍之間；建議以篩粉器分離細粉後單獨萃取量測 EY，反推真實倍率（見 §15 第 3 點擴充內容）|
| 褐水防禦底板為個人化感官設定 | `TDS_BROWN_WATER_FLOOR = 0.80`（低於此 TDS 觸發二次懲罰）基於大眾對「水感咖啡」的普遍認知底線，非個人化量測值；偏好低濃度茶韻感（Tea-like Elegance）的使用者，0.75% 甚至更低的 TDS 可能屬「優雅」而非「洗鍋水」；建議以實際沖煮 0.70%–0.90% TDS 的對照組，依個人感受調整此閾值（見 §15 第 28 點）|
| Huber Loss 轉折點為數學超參數 | `CONC_HUBER_DELTA = 0.5` 為 Huber Loss 的線性/二次懲罰切換閾值（相對誤差 > 50% 時懲罰從二次改為線性），屬機器學習最佳化超參數（Hyperparameter），**無直接物理意義**；此值控制懲罰曲線的平滑度與極端值防發散能力，不需要物理實測；若感官盲測後發現評分分布過度集中或分散，可以 ±0.1 步進調整此值，無需配合任何量測實驗 |

---

## 15. 後續迭代方向

1. **實測校正 BREWER_TEMP_DROP**：注水後立即（5 秒內）量測漿體溫度，與手沖壺水溫的差值扣除 `dose × 0.15` 即為機身熱容修正量。理論預測此值與機型（標準版/XL）無關，建議在不同室溫下以兩款機身各重複量測，驗證比值不變性。
2. **實測校正 COOL_RATE 與 T_ENV**：在浸泡開始與結束時各量一次水溫，擬合牛頓冷卻曲線。
3. **實測校正 K_BASE 與雙峰參數**：以不同研磨度的 EY 量測（折射儀）反推速率常數；條件允許時可篩網分離細粉（建議 100μm 篩孔）實測細粉率，校正 `FINES_RATIO_DIAL_SLOPE`。
   - **K_FINES_MULT / K_BOULDERS_MULT 擴充實測：** 以篩粉器完整分離細粉後，取等量細粉（佔比對應刻度的估算細粉率）單獨浸泡 15s / 30s / 60s，折射儀量測各時間點 TDS；以全粉對照組擬合一階動力學曲線，再擬合細粉曲線，計算 $k_{fines} / k_{boulders}$ 真實比值。文獻 Rule of Thumb 為 10 倍，ZP6 真實值預期介於 **5–15 倍**（細粉定義 <100μm vs <200μm 對結果影響顯著）；同步反推 `K_BOULDERS_MULT` 相對 `K_BASE` 的實際縮放比例。
4. **FINES_RATIO 升級為二次函數**：細粉率在極細端可能呈加速增長（非線性），校正後改為 $f(dial) = a + b(DIAL_{BASE} - dial) + c(DIAL_{BASE} - dial)^2$。
5. **Swirl 對流倍率實測**：對同一食譜以不同 steep_sec（例如 60s 與 120s）量測 EY，控制 Swirl 強度，反推 `SWIRL_CONVECTION_MULT` 的真實值。
6. **MEL_BITTER_COEFF 細化**：區分 MD 與 D 的 MEL 焦苦係數（目前同為 0.5），或加入 LM/M 的微量 MEL 係數（0.1），使過渡更平滑。
7. **calc_press_time 進一步精細化**：`PRESS_DIAL_FACTOR` 建議實際施壓測試後校正；考慮改為查表而非線性公式。
8. **感官平衡懲罰擴充**：考慮 SW/CA（甜苦比），但注意各項 W 之和不應超過 0.35。
9. **天然礦泉水 GH/KH 實測**：以水族用試劑對 Spritzer、Jeju Samdasoo 等逐一滴定（100ml 直接滴定），確認各離子分量後建立 `WATER_PRESETS` 條目。
10. **終極目標：六大物質獨立動力學（架構替換）**
    - **現狀矛盾：** `calc_ey`（嚴謹雙峰動力學）與 `predict_compounds`（經驗乘數）底層邏輯解耦，物質加總不等於總 EY。
    - **終極解法：** 為六大物質各自建立獨立雙峰動力學方程式，$EY_i(t) = f(k_{i,fines}, k_{i,boulders}, T_{eff,i})$，合計 $\sum EY_i \equiv EY_{total}$。
    - **最小可行校正路徑（MVE）：**
      1. 以可溶性濾紙分段萃取（15s / 60s / 120s / 240s），用 HPLC 或近似儀器量測各時間點的 AC/SW/CA 絕對濃度
      2. 對每個物質擬合一階動力學曲線，推算 $k_i$ 值
      3. 細粉率修正：用篩網分離細粉（< 100μm），各別萃取量測，估算 $k_{i,fines}$ 與 $k_{i,boulders}$ 比值
      4. 以實測 $k_i$ 替換 `predict_compounds` 的經驗乘數
    - **前提條件：** 需要 HPLC 或高精度分離量測設備，或與具備 GC-MS 設備的研究機構合作。在此條件滿足前，v3.9 的混合模型（嚴謹巨觀 + 經驗微觀）是最佳可行近似。

11. **GH 修正移至動力學速率常數（Gemini 建議，理論正確、暫緩實作）**
    - **問題描述：** 現有的 GH 修正以最終 EY 乘數呈現（`ey *= 1.0 + (water_gh - 20) / 800`），在化學動力學上不嚴謹：GH（Ca²⁺/Mg²⁺）作為溶劑催化劑，影響的是萃取速率 $k$，而非熱力學極限 $EY_{max}$。純 RO 水（GH≈0）在 $t\to\infty$ 時仍能完全萃出物質，只是速率極慢。
    - **理論正確修正方向：**
      ```python
      gh_catalyst = 1.0 + (water_gh - 50) / 1000   # 以 50ppm 為基準 1.0
      k_b = (K_BASE * K_BOULDERS_MULT * (1.8 ** ((DIAL_BASE - dial) / 0.5))) * gh_catalyst
      ```
    - **暫緩原因：** GH 影響幅度相對較小（±10%），修改速率常數需重新校正 $k_b$/$k_f$ 的量級關係，且引入另一個估算常數（`gh_catalyst` 的分母 1000）的邊際誤差可能大於原始 EY 乘數的近似誤差。建議待第 10 點六大物質獨立動力學完成後，以實測 $k_i$-GH 對照數據驅動此修正。

12. **Swirl 時溫積分的數學澄清（Gemini 建議，不採納，附數學說明）**
    - **Gemini 的建議：** 拆分 EY_steep + EY_swirl，以末端溫度 $T_{end}$ 計算 Swirl 的萃取貢獻，認為現有公式「以平均溫度計算 Swirl 的低溫對流」。
    - **為何不採納：** `_calc_t_eff` 是速率加權有效溫度的**封閉解析積分**，其本質是：
      $$T_{eff} = \frac{\int_0^t k \cdot e^{-k\tau} \cdot T(\tau) \, d\tau}{\int_0^t k \cdot e^{-k\tau} \, d\tau}, \quad T(\tau) = T_{env} + (T_{slurry} - T_{env}) e^{-r\tau}$$
      積分已完整涵蓋牛頓冷卻曲線——後期 $T(\tau)$ 低，萃取速率 $k \cdot e^{-k\tau}$ 的加權也小，乘積自然遞減，$T_{eff}$ 已被正確拉低。`t_kinetic` 的延伸是速率補償（等效更長浸泡），末端低溫效應**隱含在解析解中，無需另行拆分**。
    - **未來驗證方向：** 實測「相同 steep_sec，Swirl 前後的 EY 差值」與「多 15 秒被動浸泡的 EY 差值」，若一致則現有 `SWIRL_CONVECTION_MULT` 近似成立；若有系統性偏差，再考慮拆分計算。

13. **實測校正 SWIRL_TIME_SEC 與 SWIRL_CONVECTION_BASE（v4.8 新增）**
    - **背景：** v4.8 將 `SWIRL_TIME_SEC` 從 10 修正為 5（真實操作約 3 下），但準確值仍不確定（可能為 3–5 秒）；`SWIRL_CONVECTION_BASE = 1.0` 決定對流補償倍率，同樣無實測依據。
    - **建議實驗方案（折射儀）：**
      1. 固定所有參數（豆種、研磨度、溫度、豆量）
      2. A 組：浸泡 120s + Swirl（正常操作），量測出杯 TDS
      3. B 組：浸泡 120s，**不做 Swirl**，直接靜置等壓，量測出杯 TDS
      4. C 組：浸泡 135s，不做 Swirl（增加 15s 被動浸泡作為對照），量測出杯 TDS
      5. 以 TDS 差值 A−B 代入模型，反推 Swirl 等效補償秒數；與 C−B 比較，確認 `SWIRL_CONVECTION_BASE` 的合理倍率
    - **預期結果：** 若 A−B ≈ C−B，說明 Swirl 等效約 15s 被動浸泡（支持舊值）；若 A−B 明顯小於 C−B，說明等效補償低於 15s（支持 v4.8 新值）。

14. **濾材差異建模（v4.9 新增，Gemini 建議二a 暫緩原因）**
    - **現狀：** 以乘以固定係數 `FILTER_PAPER_PS_RETENTION = 0.90` 修正 PS 的方式不影響組合排名（量對消），屬無效修正，故未採納。
    - **真正有效的濾材建模方向：** 為「紙濾」vs「金屬濾」分別建立 `IDEAL_FLAVOR_PAPER` / `IDEAL_FLAVOR_METAL` 兩套目標向量，在 CLI 加入 `--filter paper|metal` 參數，讓 `build_ideal_abs` 依濾材選擇對應目標。
    - **前提條件：** 需以同一食譜分別用紙濾和金屬濾沖煮，量測 TDS 差值與感官 Body 評分，推算兩套向量的 PS 比例差異。

15. **自由溶劑修正（v5.6 已實作）**
    - **實作內容：** `brew_capacity` 分子改為 `free_water = water_ml − dose × calc_retention(roast_code, dial)`，以真正可自由擴散的溶劑量取代總注水量。
    - **剩餘不確定性：** `calc_retention` 本身為推算估值（§14 已列），截留率誤差直接傳播至此修正；精度提升的前提是先以磅秤實測出杯重校正截留率（§15 第 1 點的附帶收益）。

16. **粉床壓實升級：Swirl 擾動重置（v5.6 已實作）**
    - **實作內容：** `effective_compaction_time = steep_sec × (1 − SWIRL_RESET_FRACTION) + swirl_wait_sec`，`SWIRL_RESET_FRACTION = 0.35`（斯托克斯沉降理論推導，Re≈500 渦流可懸浮 <80μm 顆粒約佔 35%）。
    - **校正方向：** 以不同浸泡時間（60s/120s/240s）量測實際壓降阻力（同施壓速度下計時），反推 SWIRL_RESET_FRACTION 的真實值；若實測值與 0.35 差異 >10%，建議更新常數。

17. **深焙焦澀協同懲罰（v5.7 已實作，第 8 層）**
    - **實作內容：** `ashy_penalty = exp(−3.0 × mel_excess × cga_excess)`，僅 MD/D 啟用，`cga_excess_ratio` 複用層 7 已計算值，零額外 overhead。
    - **校正方向：** 以深焙（D）高溫長浸泡組合（最高風險場景）跑 Top 10 排名，確認無過萃組合入榜；若仍有，可調低 `ASHY_SLOPE` 至 2.5；若排名已符合預期可維持 3.0。

18. **注水湍流等效萃取實測（v5.7 新增，不採納 Gemini 建議後列入）**
    - **問題描述：** Gemini 建議將 `pour_offset`（時間扣減）改為正向湍流等效時間加回 `t_kinetic`，物理方向正確但參數無依據（效率假設 50% 屬估算）。
    - **不採納理由：** 現有 `pour_offset` 已修正「注水時間算入浸泡時間」的系統性偏差；改為正向加法等於多加 ~33s 的估算萃取，在 POUR_RATE 本身就是估算值的情況下屬過擬合。
    - **建議實驗方案：** A 組正常操作（pour_offset 修正）；B 組人工延遲注水（注水後等 33s 才計浸泡時間）；量測 TDS 差值，若 A−B ≈ 0 則 pour_offset 設計正確；若 A > B，說明注水湍流確實有額外萃取貢獻，可考慮加入正向等效項。

19. **蒸發率 TDS 濃縮補償（v5.7 新增）**
    - **問題描述：** 90–100°C 浸泡 2–4 分鐘，AeroPress 敞口部分會蒸發 3–8g 水，導致實際 TDS 比模型預測略高。
    - **建議實作方向（待實測後）：** `effective_water = water_ml − EVAPORATION_RATE × steep_sec`（`EVAPORATION_RATE` 估算約 0.02–0.04 g/s），代入 `calc_tds` 分母。實測方法：固定條件下浸泡前後各秤量 AeroPress 總重，差值扣除出液重即為蒸發量。

20. **細粉率焙度動態補償（v5.7 新增）**
    - **問題描述：** `calc_fines_ratio` 僅依賴研磨刻度，未考慮烘焙度對豆質脆度的影響。深焙（D）結構酥鬆，相同刻度下細粉量比淺焙多 30–50%；現有系統低估深焙的通道效應風險。
    - **建議實作方向（待篩粉實測後）：** 將 `FINES_RATIO_BASE` 從固定常數改為焙度字典矩陣（`L+: 0.10, L: 0.11, LM: 0.13, M: 0.15, MD: 0.18, D: 0.22`，數值為估算），待篩粉器實測後校正各焙度的真實細粉率基準值。

21. **粉床壓實豆量動態補償（v5.8 新增）**
    - **問題描述：** v5.6/v5.7 的 `compaction_mult` 以 `effective_compaction_time` 為唯一變數，未考慮豆量影響。30g 豆量沉積在濾紙的細粉**總質量**是 15g 的兩倍，緻密阻水層厚度亦成比例增加，壓降阻力暴增不只與時間有關。
    - **建議實作方向（待推拉力計實測後）：** 升級為時間與豆量的二元函數：
      ```python
      compaction_mult = 1.0 + (effective_compaction_time / 240) * (dose / 18) * BED_COMPACTION_COEFF
      ```
      實測方法：以推拉力計量測不同豆量（18/24/30g）在相同浸泡時間下的壓降阻力，擬合豆量係數。

22. **水合放熱 T_slurry 截距微調（v5.8 新增）**
    - **問題描述：** v5.8r 的比熱混合方程式假設咖啡粉溫 = T_ENV（25°C），未考慮乾燥多孔咖啡粉吸水時的水合放熱（Hydration Enthalpy）。此放熱反應會微弱抬升實際 t_slurry 約 0.5–1.0°C。
    - **建議實作方向（待溫度計實測後）：** 以高精度數位溫度計量測粉水混合後 5 秒內的漿體溫度，與比熱方程式預測值比較差值；若差值系統性為正，微調 `COFFEE_SPECIFIC_HEAT_RATIO` 或引入微小正偏移常數。

23. **predict_compounds 的 `ey` 參數孤兒化（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** `predict_compounds(roast_code, temp, dial, steep_sec, ey, ...)` 簽名接收 `ey` 但函數內部從未使用——所有物質的推算已解耦為溫度 × 研磨 × 時間的獨立動力學。
    - **暫緩原因：** 移除參數會破壞 §10 `optimize()` 的調用簽名，屬程式碼重構（非邏輯修正）。且 §15 第 10 點「六大物質獨立動力學」未來可能重新需要 EY 參數。
    - **建議處置：** 實作時在函數體內加入 `_ = ey  # reserved for future use` 抑制 linter 警告，不移除參數。

24. **通道效應非線性崩潰（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** `bypass_ratio = (press_sec − 60) × 0.005` 為線性模型，但粉餅裂縫形成後水流集中是連鎖指數反應。
    - **暫緩原因：** 線性斜率在 `CHANNELING_BYPASS_MAX = 0.15` 夾緊下，與指數函數在 press_sec < 90s 的搜尋空間內差異極小（< 0.02）。不確定性遠小於 `CHANNELING_EY_SLOPE` 本身的估算誤差。
    - **建議實測方向：** 以 30g + 極細粉實際壓降，量測不同 press_sec 下的出杯 TDS 衰減曲線，擬合 bypass 函數形狀。

25. **T_ENV 環境溫度參數化（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** `T_ENV = 25.0` 硬編碼為室溫，影響比熱混合方程式（粉溫 = T_ENV）與牛頓冷卻曲線（終態溫度 = T_ENV）。夏天冷氣房（25°C）與冬天寒流（15°C）差 10°C，對 t_slurry 影響約 0.5°C，對長浸泡冷卻速率影響更大。
    - **建議實作方向：** CLI 新增 `--t-env`（預設 25），代入所有使用 T_ENV 的公式。低成本高收益。

26. **CGA 研磨度依賴（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** PS 有 `+= max(4.5 − dial, 0) × 0.15` 的研磨度依賴，但 CGA 完全無 dial 變數。極細粉（dial < 4.0）大量粉碎細胞壁，CGA 釋放率應高於粗粉——即使不發生通道效應（`CHANNELING_CGA_MULT` 僅在 press > 60s 觸發），細粉本身的 CGA 基礎量也更高。
    - **暫緩原因：** 修正幅度（估算 ±10%）小於 CGA 基礎值（`cga_roast` 字典）的估算不確定性。待感官回饋後校正。

27. **鈣鎂離子萃取偏好係數實測（MG_FRAC_AC_SW_MULT / MG_FRAC_PS_CGA_MULT）**
    - **問題描述：** `MG_FRAC_AC_SW_MULT = 0.16` 與 `MG_FRAC_PS_CGA_MULT = 0.08` 的量級為純粹估算值——Mg²⁺ 對酸甜感的正向強化幅度 16%、Ca²⁺ 對醇厚/澀感的提升幅度 8%，均無實驗依據（§14 已列）。
    - **建議實驗方案：** 以相同食譜（固定 roast / temp / dial / steep / dose），分別配製：
      1. 純鎂水：以 MgCl₂ 溶液調製 GH=60 ppm（全由 Mg²⁺ 貢獻，KH ≈ 0）
      2. 純鈣水：以 CaCl₂ 溶液調製相同 GH=60 ppm（全由 Ca²⁺ 貢獻，KH ≈ 0）
      3. 以折射儀確認兩組 TDS 近似相同（排除濃度差異干擾）
      4. 進行感官盲測（酸感 / 甜感 / Body / 澀感四維度打分）
    - **校正方式：** 酸甜感知差異百分比直接對應 `MG_FRAC_AC_SW_MULT`；Body 與澀感差異對應 `MG_FRAC_PS_CGA_MULT`。若兩組在感官上無顯著差異（p>0.1），可考慮移除這兩個係數以簡化模型。

28. **褐水防禦底板個人化校正（TDS_BROWN_WATER_FLOOR）**
    - **問題描述：** `TDS_BROWN_WATER_FLOOR = 0.80` 基於大眾對「水感咖啡」的普遍認知底線，但部分精品咖啡使用者對 L+/L 焙度的極淡萃取（Tea-like Elegance）有不同的感官評價（§14 已列）。
    - **建議個人化方法：** 以相同 L+ 焙度豆，分別沖煮 TDS 落在 0.70% / 0.75% / 0.80% / 0.85% 的四組對照杯（調整豆量：14g / 16g / 18g / 20g，其餘參數固定），依序盲評「哪一杯開始讓你感覺水感/洗鍋水」，所記錄的 TDS 臨界值即為你的個人化 `TDS_BROWN_WATER_FLOOR`；若底線低於 0.80%，直接在 §0 調低此常數即可，無需其他修改。

---

## 16. 校正優先順序路線圖

> 本節將 §14 已知限制與 §15 待辦事項中所有需要實測或人工校正的參數，依**難易度（E）與重要度（I）**統一評分排序，供實作階段按序執行。

### 16.1 評分方法

$$優先分 = E \times 2 + I \times 1$$

**難易度 E（1–5）：** 1 = 需要 GC-MS 等研究級設備，5 = 純代碼或日常廚房器材即可完成。難易度加權×2，因為「做得到」比「影響大」更能決定實際執行順序。

**重要度 I（1–5）：** 1 = 邊際修正（對排名幾乎無感知差異），5 = 核心錨點（偏差會系統性扭曲所有輸出）。

> 同分時以重要度高者優先；純代碼改動（不需量測）標記 ★，可立即執行。

---

### 16.2 完整排序表

| 排名 | 參數 / 參數群 | §15 | E | I | 分 | 所需工具 | 說明 |
|:---:|---|:---:|:---:|:---:|:---:|---|---|
| **1** | `RETENTION_BASE` 字典（各焙度截留率） | #1 | **5** | 4 | **14** | 電子秤 | 量出杯重反推截留量；是 `calc_tds` 與 `brew_capacity` 的共同上游，一次校正兩個模型 |
| **2** | `T_ENV` 參數化 → CLI `--t-env` ★ | #25 | **5** | 3 | **13** | 純代碼 | 無需量測，直接加 CLI 參數；冬夏室溫差 10°C 影響漿體溫及冷卻曲線 |
| **3** | `TDS_PREFER` + `TDS_GAUSS_SIGMA`（TDS 高斯峰值） | — | 4 | 4 | **12** | 折射儀 + 感官杯測 | 直接決定評分系統的「甜蜜點」，偏差會同步拖偏層 5（TDS 高斯）和層 6（CGA 絕對閾值）|
| **4** | `POUR_RATE`（注水流速） | — | **5** | 2 | **12** | 電子秤 + 計時器 | 秤量注滿 400ml 所需秒數；影響 `pour_offset`，從而影響 `t_kinetic` 起始點 |
| **5** | `TDS_BROWN_WATER_FLOOR`（褐水底板） | #28 | **5** | 2 | **12** | 只需沖四杯咖啡 | 盲評 0.70/0.75/0.80/0.85% 四組對照杯，確認個人底線；直接在 §0 覆寫即可 |
| **6** | `BREWER_TEMP_DROP` + `COFFEE_SPECIFIC_HEAT_RATIO`（熱平衡） | #1, #22 | 4 | 3 | **11** | 精密數位溫度計 | 注水後 5 秒內量漿體溫；同一實驗可同時校正兩個熱力常數 |
| **7** | `COOL_RATE`（牛頓冷卻速率） | #2 | 4 | 3 | **11** | 精密數位溫度計 | 浸泡開始與結束各量一次水溫，擬合冷卻曲線；可與第 6 項合並為同一實驗 |
| **8** | `SWIRL_TIME_SEC` + `SWIRL_CONVECTION_BASE`（Swirl 等效倍率） | #13 | 4 | 3 | **11** | 折射儀 | A/B/C 三組 TDS 對照實驗（§15 #13 詳述）；與第 9 項共用折射儀 |
| **9** | `K_BASE` + `ARRHENIUS_COEFF`（萃取速率核心常數） | #3 | 3 | **5** | **11** | 折射儀（多組） | 系統中影響最廣的兩個常數；3–5 組不同溫度 × 研磨度食譜的 EY 量測，反推二元組 |
| **10** | `IDEAL_FLAVOR`（六維理想風味向量） | — | 3 | **5** | **11** | 感官杯測（多焙度） | 整個評分系統的終極目標錨點；建議以「已知好喝的食譜」反推各焙度的物質比例，迭代修正 |
| **11** | `EVAPORATION_RATE`（蒸發率） | #19 | 4 | 2 | **10** | 電子秤 | 沖煮前後秤量總重，差值扣出液重；蒸發 3–8g 使實際 TDS 比預測略高約 1% |
| **12** | `WATER_PRESETS` GH/KH 實測（Spritzer / Jeju） | #9 | 4 | 2 | **10** | 水族 GH/KH 試劑 | 300 元內即可完成；消除品牌公開資料的批次差異 |
| **13** | `WEIGHTS`（六維評分權重） | — | 3 | 4 | **10** | 感官盲測（多次） | 以相同配方、不同偏差方向設計盲測，反推 AC/SW/PS/CA/CGA/MEL 各維度的真實感官權重 |
| **14** | `SCORCH_PARAMS`（高溫劣變閾值與靈敏度） | — | 3 | 3 | **9** | 感官盲測 | 高溫 vs 適溫同一食譜盲測；閾值偏差會讓評分系統對高溫場景過罰或欠罰 |
| **15** | `HARSHNESS_SLOPE` + `ASHY_SLOPE`（協同劣變斜率） | — | 3 | 3 | **9** | 感官盲測 | 「AC×CGA 同時超標」vs「單一超標」的對照評分；深焙場景優先測 ASHY_SLOPE |
| **16** | `SW_AROMA_SLOPE`（高溫甜感逸散斜率） | — | 3 | 3 | **9** | 感官盲測 | 90/95/100°C 相同食譜盲測甜感評分差異；斜率偏高會系統壓制高溫組合 |
| **17** | `MEL_BITTER_COEFF`（深焙焦苦係數） | #6 | 3 | 3 | **9** | 感官盲測 | MD/D 高萃取 vs 正常萃取的焦苦感知對照；目前 MD=D=0.5，可能需區分 |
| **18** | `SWIRL_WAIT_SLOPE`（靜置時間研磨度斜率） | — | 4 | 1 | **9** | 目視觀察 | 對著不同研磨度粉渣計時沉降；成本幾乎為零，但對評分影響極微 |
| **19** | `K_FINES_MULT` + `K_BOULDERS_MULT` + `FINES_RATIO_DIAL_SLOPE`（雙峰核心倍率） | #3 擴充 | 2 | 4 | **8** | 篩粉器（100μm）+ 折射儀 | 篩出細粉單獨萃取，擬合各峰速率常數；真實倍率預期 5–15×（文獻給 10×） |
| **20** | `PRESS_EQUIV_FRACTION`（壓降萃取效率折算） | — | 3 | 2 | **8** | 折射儀 | 相同食譜不同壓降速度的 TDS 差值；影響量約 ±3% EY |
| **21** | `K_CA`（咖啡因萃取速率） | — | 3 | 2 | **8** | 折射儀 | 45s/90s/150s 多時間點 TDS，結合 CA 占比反推；影響層 2 濃度接近度 |
| **22** | `ASYM_BITTER_MULT` / `ASYM_SWEET_MULT`（非對稱懲罰倍率） | — | 3 | 2 | **8** | 感官盲測 | 相同絕對偏差量，苦澀方向 vs 甜感方向的主觀評分差異 |
| **23** | `W1` + `W2` + `TDS_W3`（三組感官懲罰權重） | — | 3 | 2 | **8** | 感官盲測 | 目前 W1=0.15/W2=0.12 為主觀設定；需系統盲測後迭代 |
| **24** | `KH_PERCEPT_DECAY`（KH 感知中和衰減常數） | — | 3 | 2 | **8** | 感官盲測 | 高 KH vs 低 KH 同一食譜的酸感差異盲測；影響 AC 感知層 |
| **25** | `BED_COMPACTION_COEFF` + `SWIRL_RESET_FRACTION`（粉床壓實與重置） | #16, #21 | 3 | 2 | **8** | 計時器（壓降秒數） | 不同浸泡時間（60/120/240s）的壓降秒數計時即可；無需儀器 |
| **26** | `DARCY_PRESS_EXP`（達西壓降指數） | — | 3 | 2 | **8** | 計時器 | 不同研磨度的實際壓降秒數分布，確認 0.6 指數是否合理 |
| **27** | `PS_TIME_MAX` + `K_PS`（多糖體飽和動力學） | — | 3 | 2 | **8** | 感官盲測（Body 評分） | 不同浸泡時間（60/120/180/240s）的 Body 感知差異；PS 貢獻慢，差異可能在 180s 後才顯著 |
| **28** | `FINES_RATIO` 焙度字典（細粉率焙度補償） | #20 | 2 | 3 | **7** | 篩粉器（多焙度） | 深焙豆質酥鬆，相同刻度細粉率可能高 30–50%；篩粉後秤重計算各焙度細粉率 |
| **29** | `CHANNELING` 係數群（EY_SLOPE / CGA_MULT / COLLAPSE_RATIO） | — | 2 | 3 | **7** | 計時器 + 感官觀測 | 30g + 極細粉場景觀測壓降秒數與出杯渾濁度；通道效應難以精確量化，先確認觸發頻率 |
| **30** | `CONC_GRADIENT_COEFF`（有限溶劑分配係數） | — | 3 | 1 | **7** | 折射儀 | 不同豆量固定其他參數的 EY 量測；修正量僅 ~0.6%，優先度極低 |
| **31** | `MG_FRAC_AC_SW_MULT` + `MG_FRAC_PS_CGA_MULT`（鈣鎂離子偏好） | #27 | 2 | 2 | **6** | MgCl₂ + CaCl₂ 化學試劑 + 感官盲測 | 純鎂水 vs 純鈣水對照實驗；修正幅度 8–16%，但需要配製化學試劑，門檻較高 |
| **32** | 六組焙度字典（`ac_roast` / `sw_roast` 等） + 六大物質獨立動力學 | #10 | **1** | **5** | **7** | GC-MS / HPLC（研究設備） | 系統的終極架構問題；影響最大但需要研究機構合作，在此條件具備前維持現有混合模型 |

---

### 16.3 建議執行分波

| 波次 | 門檻 | 含項目（排名） | 預計單次工時 |
|:---:|---|---|---|
| **Wave 1** | 零器材 / 純代碼 | #2（T_ENV）、#5（褐水底板） | < 1 小時 |
| **Wave 2** | 電子秤 + 計時器 | #1（截留率）、#4（注水流速）、#11（蒸發率）、#25（粉床壓實計時）、#26（達西計時）、#18（靜置觀察） | 1–2 小時 |
| **Wave 3** | 精密數位溫度計 | #6（熱平衡）、#7（冷卻速率）——可合併為同一實驗 | 1 小時 |
| **Wave 4** | 折射儀 | #8（Swirl 倍率）、#9（K_BASE+ARRHENIUS）、#3（TDS_PREFER）、#20（壓降效率）、#21（K_CA）、#30（溶劑梯度） | 3–5 小時（多組量測） |
| **Wave 5** | 感官盲測 | #10（IDEAL_FLAVOR）、#13（WEIGHTS）、#14–17（各懲罰斜率）、#22–24（懲罰權重）、#27（PS Body） | 多輪累積，每輪 1–2 小時 |
| **Wave 6** | 水族試劑 | #12（礦泉水 GH/KH） | < 30 分鐘 |
| **Wave 7** | 篩粉器（100μm） | #19（雙峰倍率）、#28（細粉率焙度字典） | 2–3 小時 |
| **Wave 8** | 化學試劑（MgCl₂/CaCl₂） | #31（鈣鎂偏好） | 2 小時 |
| **Wave 9** | GC-MS / HPLC（研究設備） | #32（焙度字典 + 獨立動力學）——長期目標 | 數週 |

> **執行建議：** Wave 1–3 可在第一個沖煮早晨完成，Wave 4 建議集中一個週末，Wave 5 的感官盲測則分散在日常沖煮中逐步迭代。Wave 7 的篩粉器（如 Kruve、OCD 篩杯）投入約 1,500–5,000 元，但能同時校正三個核心雙峰參數，CP 值極高。Wave 9 屬長期目標，在此之前混合模型（嚴謹巨觀 + 經驗微觀）是最佳可行近似。

---

> **v5.8r 企劃書定版聲明：** 本版本基於 v5.8，新增三項修正：①`t_slurry` 從線性近似升級為比熱混合方程式（正確反映 water_ml 影響）；②褐水防禦底板（`TDS_BROWN_WATER_FLOOR = 0.80`）；③`predict_compounds` 的溫度輸入從壺溫 `temp` 修正為漿體溫 `t_slurry`（與 `calc_ey` 使用 T_avg、`SCORCH_PARAMS` 使用 t_slurry 一致，消除內部溫度變數錯位）。§15 共 26 項 → **28 項**（Gemini 最終常數盤點補入）。**企劃書不再升版，進入程式碼實作。**

*企劃書 v5.8r（定版）｜基於 v5.8：①t_slurry 升級為比熱混合方程式；②褐水防禦底板 TDS < 0.80%；③predict_compounds 溫度輸入從壺溫改為漿體溫（XL 30g 100°C 場景 CGA 乘數從 1.240 修正至 1.111，消除 −10% 的系統性高估）。§15 新增 #25 T_ENV 參數化、#26 CGA 研磨度依賴、#27 MG_FRAC 實測方案、#28 TDS_BROWN_WATER_FLOOR 個人化校正；§14 補入四個漏網魔法數字條目（MG_FRAC 係數、K_FINES_MULT/K_BOULDERS_MULT 倍率、TDS_BROWN_WATER_FLOOR 感官底板、CONC_HUBER_DELTA 超參數）。*
*所有模型參數均可在實際沖煮後迭代更新。*


---

## 附錄 A：封閉前漏水（v5.9）


# AeroPress 演算法白皮書 v5.9 相關章節增補

## 0. 本次決策

本版決定將「封閉前漏水（Pre-Seal Drip）」直接整合進現行模型，而不是延後到 §15。

理由有三點：

1. 它對現有模型的主效應是「自由溶劑減少」與「低 TDS、偏酸支流混合」，這兩件事都可以在不拆毀封閉段解析解的前提下納入。
2. `seal_delay` 只改變封閉前的漏水窗口，不改變封閉段牛頓冷卻 + 雙粒徑動力學的數學形式。
3. 目前 `Pre-Seal Drip` 的量級相對總水量仍屬小擾動，採一階混合近似的風險低於全面重寫流體模型的風險。

因此 v5.9 採用「保留封閉解析解主體 + 外掛 Pre-Seal 支流修正」。

---

## 3. 新物理架構：封閉前漏水

### 3.1 時間窗

定義：

- `pour_time = water_ml / POUR_RATE`
- `seal_delay`：注水完成到塞入活塞建立負壓的額外延遲，預設 `5 s`
- `t_drip = pour_time + seal_delay`

這裡 `t_drip` 不是封閉段時間，而是「存在漏水可能」的總時間窗。

### 3.2 漏水體積

建立：

```text
V_drip = min(k_drip * t_drip * (dial / DIAL_BASE)^eta, water_ml * r_max)
```

其中：

- `k_drip = PRE_SEAL_DRIP_RATE_REF`
- `eta = PRE_SEAL_DRIP_DIAL_EXP`
- `r_max = PRE_SEAL_DRIP_MAX_RATIO`

物理解讀（達西定律）：

- 與總漏水時間成正比：時間越長，漏水越多。
- 與研磨度成正比：粒徑越大（粗研磨、dial 越大）粉床阻力越低，相同靜水壓下流速越高，漏水量越多；`dial = DIAL_BASE` 時修正項為 1。
- 加上上限 `r_max`，避免在極細研磨或極長延遲下出現不合理的漏水量。

### 3.3 封閉段自由溶劑修正

原模型的自由溶劑為：

```text
free_water_base = water_ml - dose * retention
```

v5.9 改為：

```text
free_water_main = water_ml - V_drip - dose * retention
```

這代表封閉段真正可用來承載濃度梯度的液相減少。

### 3.4 封閉段主流萃取

封閉段沿用雙粒徑解析式，以 `free_water_main` 輸入：

```text
EY_main = EY_closed_form(free_water_main, t_kinetic)
```

批次平衡 `brew_capacity = free_water_main / (free_water_main + dose×K_d)` 已完整建模 V_drip 造成的溶劑減少；不再額外乘 `(1 - λ×V_drip/water_ml)`，否則構成雙重計算。

### 3.5 漏水支流的低 TDS 滴濾效應

封閉前漏水不是零萃取，而是短接觸時間的弱滴濾支流。

v5.9 用一個低效率支流近似：

```text
t_psd = PRE_SEAL_CONTACT_FRACTION * t_drip
EY_drip_raw = EY_closed_form(V_drip, t_psd)
EY_drip = epsilon_psd * EY_drip_raw
```

其中：

- `PRE_SEAL_CONTACT_FRACTION`：把「漏水窗口」折算成「有效床層停留時間」
- `epsilon_psd = PRE_SEAL_PERCOLATION_EFFICIENCY`：代表此支流為低 TDS、低質量回收效率

因此總萃取率為：

```text
EY_total = GH_adjust(EY_main + EY_drip)
```

這裡保留了使用者要求的三個核心現象：

1. 主壺自由溶劑減少。
2. 漏下去的水確實經歷短暫 percolation，而不是純水旁通。
3. `seal_delay` 直接增加 `t_drip`，因此增加 `V_drip`，並對總 EY 形成保守化修正。

---

## 5. `predict_compounds` 的支流混合

### 5.1 為什麼不用重寫整個風味動力學

現行 `predict_compounds` 是以「主流液相的相對物質向量」為核心，而不是逐滴做質量傳輸方程。

Pre-Seal Drip 對風味的主效應不是整體化學機制翻盤，而是：

- 比主流更偏 AC
- 更低甜感與厚度
- 苦澀生成較少，但會在最終杯中把酸質往前推

因此 v5.9 採用雙流混合：

```text
C_main = compounds_main(effective_steep)
C_drip = compounds_preseal(PRE_SEAL_CONTACT_FRACTION * t_drip)
```

再對 `C_drip` 套偏置：

```text
AC  *= PRE_SEAL_AC_MULT
SW  *= PRE_SEAL_SW_MULT
PS  *= PRE_SEAL_PS_MULT
CA  *= PRE_SEAL_CA_MULT
CGA *= PRE_SEAL_CGA_MULT
MEL *= PRE_SEAL_MEL_MULT
```

最後用體積比分流混合：

```text
phi = V_drip / water_ml
C_total = (1 - phi) * C_main + phi * C_drip
```

這代表：

- 主壺壓降咖啡仍是主體。
- 漏下壺的支流會把整杯往「早段酸質」方向拉。
- 因為 `phi` 小，所以不會摧毀現有風味空間。

---

## 8. 程式接口更新

### 8.1 新增變數

```python
SEAL_DELAY_DEFAULT = 5.0
```

### 8.2 新增函數

```python
calc_drip_volume(water_ml, dial, drip_time) -> float
```

### 8.3 更新函數簽名

```python
calc_ey(..., press_equiv=0, pour_offset=0, seal_delay=SEAL_DELAY_DEFAULT)
predict_compounds(..., press_equiv=0, pour_offset=0, water_ml=400, seal_delay=SEAL_DELAY_DEFAULT)
```

### 8.4 optimizer 新增輸出欄位

- `seal_delay`
- `pre_seal_drip_sec`
- `pre_seal_drip_ml`

---

## 14. 本版近似的邊界

v5.9 已可直接上線，但仍需明確承認以下近似：

1. `calc_drip_volume` 採 `(dial/DIAL_BASE)^eta` 與達西定律方向一致；仍是靜態經驗式，尚未顯式建模濾紙阻力、粉層高度、翻轉角度。
2. 主流程式僅以 `free_water_main` 輸入 `EY_closed_form`，不再乘 `(1 - λ×V_drip/water_ml)`，因 brew_capacity 路徑已完整建模溶劑減少，額外乘項構成雙重計算。
3. `EY_drip` 以低效率因子 `epsilon_psd` 吸收了真實的床層停留時間分布，尚非完整流體模型。
4. `predict_compounds` 的 Pre-Seal 支流偏置目前是物理方向正確的一階混合，仍需以折射儀 + 杯測反推最佳乘數。

這些限制不影響本版整合決策，因為它們屬參數精修，不屬方程結構錯誤。

---

## 15. 後續實測計畫（v5.9 延伸）

雖然本版已直接整合，但仍建議把下列量測列入 §15：

1. 固定 `water_ml / dose / roast`，只改 `seal_delay = 0 / 5 / 10 / 20 s`，量測實際漏水質量，回歸 `PRE_SEAL_DRIP_RATE_REF` 與 `PRE_SEAL_DRIP_DIAL_EXP`。
2. 收集漏下壺的 pre-seal 支流，單獨量測 TDS，校正 `PRE_SEAL_PERCOLATION_EFFICIENCY`。
3. 主流與 pre-seal 支流分杯杯測，檢查 AC/SW 是否真的上升，以及 `PRE_SEAL_AC_MULT` 等偏置是否方向正確。
4. 比較不同濾材與不同翻轉角度，確認 `PRE_SEAL_DRIP_MAX_RATIO` 是否需要按濾材分表。

結論：Pre-Seal Drip 在 v5.9 已是可執行的一階修正模組；後續實測的目標是校正係數，不是決定是否存在這個模組。

---

## 16. 初期漏水計算之再評估（低估／高估）

### 16.1 現行公式與典型數值

- **體積**：`V_drip = min(PRE_SEAL_DRIP_RATE_REF * t_drip * (dial/DIAL_BASE)^η, water_ml * 0.12)`
- **常數**：`PRE_SEAL_DRIP_RATE_REF = 0.30`（ml/s）、`η = 1`、上限 12%。
- **典型（修正前）**：dial=4.5 時 `V_drip≈11.4 ml`（約 2.85%）；dial=6 時約 15 ml。
- **修正後（§16 貼近現實）**：`PRE_SEAL_DRIP_RATE_REF=0.38`、`η=1.2`、上限 18%。dial=4.5 時 `V_drip≈0.38×38×1≈14.4 ml`（約 3.6%）；dial=6 時約 18 ml（約 4.5%）；長 seal_delay 時最多 18% 總水量。

### 16.2 物理與實務對照

| 項目 | 現行設計 | 可能偏差 | 結論 |
|------|----------|----------|------|
| **漏水速率 (0.30 ml/s)** | 固定參考速率 × (dial/4.5) | 直立沖煮時注水階段即開始滴漏，實務常見 5–15% 總水量流失；目前 2.8–4% 落在偏低區間 | **傾向低估** 漏水量，尤其長 seal_delay 或粗研磨 |
| **dial 指數 η=1** | 漏水量 ∝ dial（線性） | 達西定律流速 ∝ 滲透率，粒徑平方級；dial 若近似粒徑，η≈2 更貼近；η=1 使粗研磨漏水量較不敏感 | 粗研磨時 **傾向低估** 漏水量 |
| **上限 12%** | 漏水不超過 water_ml×12% | 若 seal_delay 很長（如 15–20 s），實際可漏 15–25%；12% 會壓低此情境的 V_drip | 長延遲時 **低估** |
| **接觸時間 (CONTACT_FRACTION=0.20)** | 支流有效接觸 = 20%×t_drip | 滴出液體接觸時間分布從近 0 到近 t_drip，0.20 為簡化平均 | 不確定，需實測；若實際平均 >20% 則支流萃取 **低估** |
| **支流萃取效率 (PERCOLATION_EFF=0.03)** | 支流 EY 僅 3% 計入總 EY | 支流偏弱，3% 屬保守；若漏水量被低估，整體支流貢獻也會被低估 | 與漏水量同向，多數情境 **低估** 支流對 EY 的貢獻 |

### 16.3 綜合結論

- **漏水量（V_drip）**：在常見參數下（dial 3.5–6.5、seal_delay 5 s）**傾向低估**；長 seal_delay 或粗研磨時低估更明顯。
- **支流對總 EY／風味的影響**：因 V_drip 偏低且效率係數保守，**整體支流貢獻傾向低估**；主流自由溶劑的減少（`free_water_main = water_ml - V_drip - retention`）也隨之偏小，故封閉段 EY 可能略為 **高估**（因以為可用溶劑比實際多）。
- **已採修正（貼近現實）**：`PRE_SEAL_DRIP_RATE_REF` 0.30 → 0.38、`PRE_SEAL_DRIP_DIAL_EXP` 1.0 → 1.2、`PRE_SEAL_DRIP_MAX_RATIO` 0.12 → 0.18；程式已更新，後續可依 §15 實測再微調。



---

## 附錄 B：口感校正（v5.10 / v5.11）


# AeroPress 演算法 v5.10 口感校正

## 0. 背景與問題描述

實測：以程式輸出 3 組 99 分以上參數實際沖煮，發現共通口感問題：

1. **苦味過於突出**
2. **整體過於濃烈**
3. **Body（醇厚）與尾韻跟不上苦味**

另外觀察到物理現象：Swirl 後，有時氣泡＋水＋咖啡粉會積在液面最上層，不必然全部沉降，影響萃取均勻度。

---

## 1. 問題診斷與成因分析

### 1.1 苦味過於突出

| 可能成因 | 說明 |
| --- | --- |
| **理想苦味分率偏高** | `IDEAL_FLAVOR` 中 CA/CGA/MEL 的分率（CA 約 10–14%、CGA 5–9%）可能是基於「理論平衡」而非多數人偏好；實測顯示這些值對應的口感偏苦 |
| **苦味懲罰不足** | `ASYM_BITTER_MULT=1.5` 對苦味超標有加乘懲罰，但 cosine_sim 與 conc_score 仍可能讓「苦味略高但六維平衡」的配方取得高分 |
| **萃取預測偏樂觀** | CA、CGA、MEL 萃取速率若低估，預測化合物會低於實際，導致模型以為「剛好」的配方，實際偏苦 |
| **絕對濃度效應** | 相同分率下，TDS 越高絕對苦質量越高；TDS_PREFER 1.20–1.35% 配合高 EY，容易造成實際苦感偏高 |

### 1.2 整體過於濃烈

| 可能成因 | 說明 |
| --- | --- |
| **TDS 偏好偏高** | `TDS_PREFER`（L+ 1.35%、M 1.25%、D 1.20%）偏競賽取向；日常飲用常偏好稍低濃度 |
| **濃度懲罰不對稱** | `TDS_GAUSS_SIGMA_HIGH=0.25` > `TDS_GAUSS_SIGMA_LOW=0.15`，對「過濃」的懲罰較溫和 |
| **搜尋空間偏強** | 長浸泡、細研磨、高粉量均推高 TDS；沒有「適飲強度上限」設計 |
| **無個人化強度** | 缺少類似 `--intensity-prefer` 的偏好參數 |

### 1.3 Body／尾韻跟不上苦味

| 可能成因 | 說明 |
| --- | --- |
| **PS 萃取速率高估** | K_PS=0.005 極慢，PS_TIME_MAX=0.20；模型在 180s 可預測顯著 PS 增加，但實測 Body 可能更慢才顯現，造成「預測偏樂觀」 |
| **醇苦比權重不足** | `BODY_BITTER_PENALTY_WEIGHT=0.12`，PS/bitter 偏離時的扣分比例有限 |
| **CA 遠快於 PS** | K_CA=0.030 vs K_PS=0.005，苦味物質先達飽和，PS 滯後；若模型 PS 預測偏高，實際杯中會是「苦先到、醇厚跟不上」 |
| **Swirl 浮層效應** | 見 §1.4、§5 物理推導 |

### 1.4 Swirl 浮層現象

| 現象 | 物理意義 | 模型落差 |
| --- | --- | --- |
| 氣泡＋水＋粉積在液面 | 表面張力、細粉懸浮、CO₂ 聚集，形成「浮層」 | 現有模型假設均勻漿體 |
| 浮層不一定完全沉降 | 部分粉粒未充分浸沒，接觸時間與主漿體不同 | `SWIRL_RESET_FRACTION=0.35` 只處理細粉重置，未考慮浮層持續存在 |
| 萃取不均勻 |  submerged 區可能過萃（苦），浮層區可能欠萃（Body 不足） | 化合物預測依賴 `effective_steep` 均一假設 |
| 壓降時序差異 | 浮層最後被擠壓，可產生不同 TDS/化合物梯度 | 未建模 |

---

## 6. 下壓階段：浮層影響與水/空氣分相

### 6.1 浮層對下壓階段的影響

**是，下壓階段會受浮層影響。** 浮層位於液面最上層，下壓時會最後被擠壓通過粉床：

- **時序**：主流漿體先通過濾網 → 浮層（氣泡＋低 TDS 水＋欠萃粉）最後擠出
- **成分差異**：浮層區接觸時間短、萃取不足，偏向 AC、偏低 Body
- **影響**：最後進入杯中的液體會拉高酸質、稀釋整體 TDS，與 §1.3「Body 跟不上苦味」一致

### 6.2 現行 `press_sec` 的物理定義

| 項目 | 現行設計 | 說明 |
| --- | --- | --- |
| **計算依據** | Darcy 定律，單相液體通過多孔介質 | `calc_press_time` 估計「水穿過粉床」所需時間 |
| **是否含空氣** | **不含** | 公式為水流時間，不含空氣通過階段 |
| **使用者實作** | 壓至「嗤聲」為止 | 嗤聲 = 空氣開始通過幾乎已排空的粉床 |

因此：**模型 `press_sec` 對應的是水流通過時間，不包含空氣階段**。使用者實際操作的總時間 ≈ 水流時間 + 短暫空氣尾段。

### 6.3 是否納入空氣階段與分相估算

**建議納入的項目：**

1. **空氣階段計時**  
   - 定義：`t_water` = 水流通過時間（≈ 現行 `press_sec`）、`t_air` = 嗤聲開始至壓到底的時間  
   - 實測：固定條件下量測 t_water（例如液面接觸濾網為止）與 t_air  
   - 若 t_air / t_total 顯著（例如 >15%），可將 `press_equiv` 改為僅以 t_water 為基礎，避免高估萃取時間

2. **空氣體積估算**  
   - 活塞行程 × 筒身截面積 − 已排出水量 ≈ 被推動的空氣體積  
   - 可用於品質檢核（例如壓力是否異常、是否提早 channel），暫不納入 EY 主計算

3. **擠出水的成分與量**  
   - **水相**：依時序可概分為「主漿體」與「浮層尾段」  
   - 主漿體：TDS 與 compounds 接近現有模型  
   - 浮層尾段：較低 TDS、偏酸、偏低 Body，可視為 Pre-Seal 支流的延續  
   - 若未來建立浮層模型（§5），可再加一尾段混合項，估計最後擠出液對杯中成分的影響

### 6.4 與 v5.10 整合順序

1. **短期**：在 §15 實測中紀錄 `t_water` 與 `t_air`，確認兩者比例  
2. **若 t_air 明顯**：在文件中明確 `press_sec` = 水流時間，`display_press_sec` 可註明為「含空氣尾段之總時間」供使用者參考  
3. **中期**：浮層模型（§5）完成後，再評估是否加入「壓降尾段化合物混合」項

---

## 2.  proposed 修正方向（待 v5.10 決策）

### 2.1 苦味與濃度

| 項目 | 修正方向 | 實作建議 |
| --- | --- | --- |
| 理想苦味下修 | 調低 `IDEAL_FLAVOR` 中 CA/CGA 目標分率 | 微調 mid/high 錨點，或新增 `IDEAL_BITTER_REDUCTION` 乘數（如 0.92） |
| 苦味懲罰加強 | 提高 ASYM_BITTER_MULT 或新增絕對苦味閾值 | ASYM_BITTER_MULT 1.5 → 1.8，或新增 CGA/CA 絕對濃度上限懲罰 |
| TDS 偏好下修 | 降低 TDS_PREFER | 各焙度降 0.05–0.10% 試行 |
| 濃度懲罰對稱化 | 放寬過稀懲罰、收緊過濃懲罰 | 調整 TDS_GAUSS_SIGMA_LOW/HIGH 或 w3 權重 |

### 2.2 Body／醇苦比

| 項目 | 修正方向 | 實作建議 |
| --- | --- | --- |
| PS 預測保守化 | 下修 PS 萃取效率或延長滯後 | K_PS 下調、或 PS 僅在 steep>150s 後才顯著累加 |
| 醇苦比權重提高 | 強化 PS/bitter 偏離懲罰 | BODY_BITTER_PENALTY_WEIGHT 0.12 → 0.18 |
| 理想 PS/bitter 上修 | 提高理想醇苦比 | 在 `IDEAL_FLAVOR` 或 `build_ideal_abs` 中微調 PS 相對 CA/CGA 比例 |

### 2.3 Swirl 浮層（新增物理項）

| 項目 | 修正方向 | 實作建議 |
| --- | --- | --- |
| 浮層比例 | 假設部分粉量形成浮層，萃取效率打折 | `FLOAT_CAP_FRACTION`：浮層粉量比例；該部分 `effective_steep` 打折（如 ×0.6） |
| 有效細粉重置 | 若浮層持續，SWIRL_RESET_FRACTION 實際可能更低 | 增設 `SWIRL_FLOAT_REDUCTION`：浮層存在時，視為 reset 效果減弱 |
| 均勻度懲罰 | 萃取不均導致「苦熱點＋Body 冷區」 | 新增一階懲罰：當 predicted PS/bitter 接近理想但變異度高時輕微扣分（需先有變異度估計） |

**建議先列 §15 實測**：固定配方，比較「浮層明顯」vs「完全沉降」兩組的 TDS、感官 Body、苦感，再決定是否納入模型。

---

## 5. 浮層厚度物理推導（Swirl 前後）

浮層（氣泡＋水＋粉的液面堆積）厚度受以下變數影響，推導方向如下。

### 5.1 相關變數與物理機制

| 變數 | Swirl 前 | Swirl 後 | 物理機制 |
| --- | --- | --- | --- |
| **焙度** | ✓ 正相關 | ✓ 正相關 | 深焙豆孔隙多、殘留 CO₂ 多，注水時釋氣更強；淺焙結構緊密、排氣較少 → 深焙浮層較厚且持久 |
| **水溫** | ✓ 正相關 | 負相關 | 高溫：CO₂ 溶解度低、釋氣快 → Swirl 前浮層厚；高溫水黏度低 → Swirl 後沉降快，殘留浮層變薄 |
| **泥漿溫度** | ✓ 正相關 | ✓ 負相關 | 同水溫；漿體越熱，排氣越劇烈；越熱黏度越低，沉降越快 |
| **水量** | ✓ 正相關 | 弱相關 | 水柱高 → 氣泡浮升路徑長、易聚集於液面；漿體高度影響 Swirl 渦流深度 |
| **豆子排氣量** | ✓ 正相關 | ✓ 正相關 | 新鮮烘焙排氣量大，CO₂ 多 → 泡沫厚；養豆久則排氣少 → 浮層薄（直接驅動因子） |

### 5.2 數學關係（一階近似）

浮層厚度 h_float 可寫為：

```text
h_float ∝ (degas_rate × t_wet) × f_roast × g(T_slurry) × h_column
```

- `degas_rate`：豆子排氣速率（與養豆天數、焙度相關）
- `t_wet`：注水後至 Swirl 的時間
- `f_roast`：焙度係數（very_dark > dark > … > very_light）
- `g(T_slurry)`：泥漿溫度影響（Swirl 前正相關、Swirl 後因黏度下降而加速沉降）
- `h_column`：漿體柱高（與 water_ml、dose 相關）

Swirl 後殘留浮層：

```text
h_float_post ∝ h_float_pre × (1 − swirl_efficacy) × (μ(T_slurry) / μ_ref)
```

黏度 μ 隨溫度上升而下降，沉降速率 ∝ 1/μ → 高溫有利沉降，殘留浮層較薄。

### 5.3 預期偏置方向（可實測驗證）

| 條件 | Swirl 前浮層 | Swirl 後殘留浮層 |
| --- | --- | --- |
| 深焙 vs 淺焙 | 深焙較厚 | 深焙較厚 |
| 高水溫 vs 低水溫 | 高溫較厚 | 高溫較薄（沉降快） |
| 新鮮豆 vs 養豆 | 新鮮較厚 | 新鮮較厚 |
| XL 400ml vs 標準 200ml | 400ml 較厚 | 弱相關 |

### 5.4 與模型整合方向

若實測確認上述趨勢，可納入：

1. **`FLOAT_CAP_BASE`**：基準浮層比例，依焙度查表（very_dark 最高、very_light 最低）
2. **`FLOAT_DEGAS_MULT`**：養豆天數修正（可由 CLI 參數或常數 proxy）
3. **`FLOAT_TEMP_SETTLE`**：泥漿溫度對 Swirl 後沉降的修正；高 T_slurry → 有效浮層比例下降

---

## 3. §15 實測擴充建議

1. **苦味與濃度校正**  
   固定水質與焙度，用目前 99 分參數沖煮，量測 TDS，並記錄主觀苦感、濃度偏好（1–5 分），反推 IDEAL 與 TDS_PREFER 修正量。

2. **醇苦比校正**  
   同一配方，記錄 Body 與尾韻強度；比對程式輸出的 PS/bitter 與實際感受，校正 K_PS、PS_TIME_MAX、BODY_BITTER_PENALTY_WEIGHT。

3. **浮層效應**  
   - 有/無刻意製造浮層（Swirl 後輕敲 vs 不敲）  
   - 分杯量測：浮層明顯杯 vs 沉降完全杯的 TDS、口感差異  
   - 評估是否值得導入 `FLOAT_CAP_FRACTION` 等參數。

4. **浮層厚度物理驗證**（對應 §5 推導）  
   - **變數**：焙度、水溫、泥漿溫度、水量、豆子排氣量（養豆天數 proxy）  
   - **量測**：Swirl 前液面浮層厚度（視覺或標尺）、Swirl 後殘留浮層厚度  
   - **對照**：深焙 vs 淺焙、高水溫 vs 低水溫、新鮮豆 vs 養豆 2 週、XL vs 標準水量  
   - **目的**：驗證 §5 偏置方向，作為 FLOAT_CAP_BASE、FLOAT_DEGAS_MULT、FLOAT_TEMP_SETTLE 的實測依據。

5. **下壓水/空氣分相**（對應 §6）  
   - 量測：水流結束時間（液面觸及濾網或滴速明顯變化）、嗤聲開始時間、壓到底時間  
   - 計算：t_water、t_air、t_air / t_total  
   - 目的：確認 press_sec 是否應限於水相；若 t_air 顯著，調整 press_equiv 或 display 說明。

---

## 4. 修正優先順序（建議）

| 優先級 | 項目 | 風險 | 依賴 |
| --- | --- | --- | --- |
| 1 | TDS_PREFER 下修 | 低 | 無 |
| 2 | ASYM_BITTER_MULT 上調、理想苦味微調 | 中 | 需杯測確認 |
| 3 | BODY_BITTER_PENALTY_WEIGHT 上調 | 低 | 無 |
| 4 | PS 預測保守化（K_PS/PS_TIME_MAX） | 中 | 需折射儀＋感官 |
| 5 | 浮層建模 | 高 | §15 浮層厚度驗證（§5）、下壓分相（§6）|

---

## 7. v5.10 實用性評估與執行決策

### 7.1 評估結論

| 項目 | 實用價值 | 可靠性 | 決策 |
| --- | --- | --- | --- |
| TDS_PREFER 下修 | 高（直接對應過濃） | 高 | **實作** |
| ASYM_BITTER_MULT 上調 | 高（對應苦味突出） | 高 | **實作** |
| BODY_BITTER_PENALTY_WEIGHT 上調 | 高（對應 Body 不足） | 高 | **實作** |
| TDS_GAUSS 收緊過濃 | 高 | 高 | **實作** |
| IDEAL_FLAVOR 苦味微調 | 中 | 中（需杯測） | 延後 |
| PS 預測保守化 | 中 | 低（需折射儀） | 延後 |
| 浮層建模 | 中 | 低（需專案實測） | 延後 |
| 下壓分相 | 低 | 低 | 延後 |

### 7.2 已實作（v5.10 本版）

- TDS_PREFER 各焙度 −0.08（偏日常適飲）
- ASYM_BITTER_MULT 1.5 → 1.8
- BODY_BITTER_PENALTY_WEIGHT 0.12 → 0.18
- TDS_GAUSS_SIGMA_HIGH 0.25 → 0.20（收緊過濃懲罰）

### 7.3 延後（待 §15 實測）

浮層、下壓分相、PS 動力學、IDEAL 微調。

---

## 8. v5.11 口感矯正（RO 實測回饋與水質權重）

### 8.1 實測情境與落差

- **沖煮條件**：RO 水（GH/KH 極低）、程式輸出約 99.5 分參數。
- **實測數據**：TDS 1.28%、EY 15.9%、SW/AC 0.665（Ideal 0.593）、PS/Bitter 1.227（Ideal 1.141）；化合物 AC/SW/PS/CA/CGA/MEL 皆在合理區間。
- **口感回饋**：高溫苦味突出、中溫 body 醇厚、低溫酸出來沒帶出香味；自評最高約 90 分。
- **結論**：模型分數與實感仍有約 10 分落差，需納入（1）高溫苦味懲罰、（2）低溫酸無香懲罰、（3）水質權重（軟水苦感加權）。

### 8.2 物理／化學依據

| 項目 | 依據 |
|------|------|
| **高溫苦突出** | 苦味物質（CA/CGA/MEL）在高溫時感官閾值較低；理想苦味目標略高於多數實感偏好 → 下修理想苦、並將 MEL 納入不對稱苦味懲罰。 |
| **軟水苦感** | 低 GH/KH（如 RO）緩衝不足，苦味離子更易被感知；文獻與實務常見「軟水放大苦感」→ 當 water_gh < 閾值且實際苦味高於理想時，額外懲罰。 |
| **低溫酸無香** | 低溫時揮發性香氣衰減，酸質仍明顯，易出現「酸出但無圓潤/香味」→ 當 AC > 理想且 SW < 理想時，視為酸高甜低，加重懲罰。 |

### 8.3 已實作（v5.11）

| 項目 | 說明 |
|------|------|
| **IDEAL_BITTER_REDUCTION** | 0.95；理想 CA/CGA/MEL 在評分時視為下修 5%，縮小「模型剛好」與「實感仍偏苦」的落差。 |
| **MEL 納入 ASYM_BITTER_MULT** | 濃度偏離項中，MEL 超標與 CA/CGA 同採 1.8× 懲罰。 |
| **水質權重（water_gh）** | `flavor_score` 新增參數 `water_gh`；當 `water_gh < LOW_GH_THRESHOLD`（20 ppm）且實際苦味 > 理想苦味時，乘以 `exp(-SOFT_WATER_BITTER_SLOPE * 超標比)`。 |
| **酸高甜低懲罰** | 當 `AC > ideal_AC` 且 `SW < ideal_SW` 時，乘以 `exp(-AC_WITHOUT_SWEET_SLOPE * min(AC超標比, SW不足比))`，對應低溫酸無香。 |

### 8.4 常數一覽（v5.11 新增）

- `IDEAL_BITTER_REDUCTION = 0.95`
- `LOW_GH_THRESHOLD = 20`
- `SOFT_WATER_BITTER_SLOPE = 2.0`
- `AC_WITHOUT_SWEET_SLOPE = 3.0`

### 8.5 後續建議

- 若仍感高溫苦：可再微調 `IDEAL_BITTER_REDUCTION`（如 0.92）或 `ASYM_BITTER_MULT`（如 2.0）。
- 水質：RO 使用者可維持現有 GH/KH 輸入，程式已依 `water_gh` 自動加權；若使用調水配方，建議如實輸入 GH/KH 以利評分反映水質。



---

## 附錄 C：焙度對照表

焙度採用 SCA 官方分級與 Agtron 數值對照，僅保留物理與光學特徵。

| 內部代號 | SCA 名稱 | Agtron 數值 | 物理外觀特徵 |
| --- | --- | --- | --- |
| very_light | Light/Cinnamon | #85-95 | 淺肉桂色，表面乾燥，無油脂 |
| light | Medium | #75 | 栗子/淺棕色，表面乾燥，無油脂 |
| medium_light | High | #65 | 褐棕色，表面乾燥 |
| medium | City | #55 | 深棕色，可能會出現微量點狀油脂 |
| moderately_dark | Full City | #45 | 暗棕色，帶有光澤，均勻分泌明顯油脂 |
| dark | French | #35 | 深褐色/近黑巧克力色，表面佈滿大量油脂 |
| very_dark | Italian | #25 | 黑褐色至全黑，極度油亮，具碳化光澤 |

## CLI / API 代號

使用上述 snake_case 代號：`very_light` `light` `medium_light` `medium` `moderately_dark` `dark` `very_dark`

