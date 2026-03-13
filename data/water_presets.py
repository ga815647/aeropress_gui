from __future__ import annotations

WATER_PRESETS = {
    "ro": {"name": "RO 純水（逆滲透）", "gh": 2, "kh": 2, "mg_frac": 0.50, "note": "近乎純水。"},
    "hualien_fenglin_brita": {"name": "花蓮鳳林自來水 + Brita（估算）", "gh": 32, "kh": 15, "mg_frac": 0.38, "note": "東台灣軟水。"},
    "hualien_guangfu_brita": {"name": "花蓮光復自來水 + Brita（估算）", "gh": 41, "kh": 18, "mg_frac": 0.38, "note": "略硬於鳳林。"},
    "hualien_fenglin_bwt": {"name": "花蓮鳳林自來水 + BWT（估算）", "gh": 22, "kh": 4, "mg_frac": 0.90, "note": "幾乎全 Mg²⁺。"},
    "hualien_guangfu_bwt": {"name": "花蓮光復自來水 + BWT（估算）", "gh": 28, "kh": 5, "mg_frac": 0.90, "note": "BWT 後 GH 稍高。"},
    "aquacode_7l": {"name": "Aquacode（1包 + 7L RO 水）", "gh": 65, "kh": 5, "mg_frac": 0.73, "note": "SCA 認證。"},
    "aquacode_5l": {"name": "Aquacode（1包 + 5L RO 水）", "gh": 90, "kh": 7, "mg_frac": 0.73, "note": "礦物質更濃。"},
    "spritzer": {"name": "Spritzer 天然礦泉水（馬來西亞）", "gh": 85, "kh": 60, "mg_frac": 0.30, "note": "Ca 偏多，KH 偏高。"},
    "jeju_samdasoo": {"name": "Jeju 濟州三多水（韓國）", "gh": 18, "kh": 15, "mg_frac": 0.45, "note": "火山岩盤極軟水。"},
}


def get_water_preset(preset_key: str) -> dict:
    if preset_key not in WATER_PRESETS:
        raise ValueError(f"未知水質預設 '{preset_key}'。可用：{', '.join(WATER_PRESETS)}")
    return WATER_PRESETS[preset_key]
