from __future__ import annotations

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
