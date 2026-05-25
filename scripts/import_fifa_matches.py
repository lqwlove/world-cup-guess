#!/usr/bin/env python3
"""
从 FIFA 2026 官网赛程生成 seeds/matches.json（中文队名 + UTC 开球时间）。
数据来源: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures

开球时间换算（面向中国观众）：
  英文站「日期 + 钟面时间」+ 9 小时 → 北京时间（UTC+8），再写入 UTC。
  与 FIFA 中国区 / 中文赛程表一致，例如：
    6/11 19:00 墨西哥 → 6/12 04:00 北京；6/12 02:00 韩国 → 6/12 11:00 北京；
    6/12 19:00 多伦多 → 6/13 04:00 北京。
  勿用场馆当地 IANA 时区直接换算（会偏晚约 5 小时）。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "seeds" / "matches.json"

# 球场城市 -> IANA（与 FIFA 场馆名对应）
VENUE_TZ: dict[str, str] = {
    "Mexico City": "America/Mexico_City",
    "Guadalajara": "America/Mexico_City",
    "Monterrey": "America/Monterrey",
    "Toronto": "America/Toronto",
    "Los Angeles": "America/Los_Angeles",
    "San Francisco Bay Area": "America/Los_Angeles",
    "New York": "America/New_York",
    "Boston": "America/New_York",
    "Vancouver": "America/Vancouver",
    "Houston": "America/Chicago",
    "Dallas": "America/Chicago",
    "Philadelphia": "America/New_York",
    "Atlanta": "America/New_York",
    "Seattle": "America/Los_Angeles",
    "Miami": "America/New_York",
    "Kansas City": "America/Chicago",
}

TEAMS: dict[str, tuple[str, str]] = {
    "MEX": ("墨西哥", "🇲🇽"),
    "RSA": ("南非", "🇿🇦"),
    "KOR": ("韩国", "🇰🇷"),
    "CZE": ("捷克", "🇨🇿"),
    "CAN": ("加拿大", "🇨🇦"),
    "BIH": ("波黑", "🇧🇦"),
    "USA": ("美国", "🇺🇸"),
    "PAR": ("巴拉圭", "🇵🇾"),
    "QAT": ("卡塔尔", "🇶🇦"),
    "SUI": ("瑞士", "🇨🇭"),
    "BRA": ("巴西", "🇧🇷"),
    "MAR": ("摩洛哥", "🇲🇦"),
    "HAI": ("海地", "🇭🇹"),
    "SCO": ("苏格兰", "🏴"),
    "AUS": ("澳大利亚", "🇦🇺"),
    "TUR": ("土耳其", "🇹🇷"),
    "GER": ("德国", "🇩🇪"),
    "CUW": ("库拉索", "🇨🇼"),
    "NED": ("荷兰", "🇳🇱"),
    "JPN": ("日本", "🇯🇵"),
    "CIV": ("科特迪瓦", "🇨🇮"),
    "ECU": ("厄瓜多尔", "🇪🇨"),
    "SWE": ("瑞典", "🇸🇪"),
    "TUN": ("突尼斯", "🇹🇳"),
    "ESP": ("西班牙", "🇪🇸"),
    "CPV": ("佛得角", "🇨🇻"),
    "BEL": ("比利时", "🇧🇪"),
    "EGY": ("埃及", "🇪🇬"),
    "KSA": ("沙特阿拉伯", "🇸🇦"),
    "URU": ("乌拉圭", "🇺🇾"),
    "IRN": ("伊朗", "🇮🇷"),
    "NZL": ("新西兰", "🇳🇿"),
    "FRA": ("法国", "🇫🇷"),
    "SEN": ("塞内加尔", "🇸🇳"),
    "IRQ": ("伊拉克", "🇮🇶"),
    "NOR": ("挪威", "🇳🇴"),
    "ARG": ("阿根廷", "🇦🇷"),
    "ALG": ("阿尔及利亚", "🇩🇿"),
    "AUT": ("奥地利", "🇦🇹"),
    "JOR": ("约旦", "🇯🇴"),
    "POR": ("葡萄牙", "🇵🇹"),
    "COD": ("刚果（金）", "🇨🇩"),
    "ENG": ("英格兰", "🏴"),
    "CRO": ("克罗地亚", "🇭🇷"),
    "GHA": ("加纳", "🇬🇭"),
    "PAN": ("巴拿马", "🇵🇦"),
    "UZB": ("乌兹别克斯坦", "🇺🇿"),
    "COL": ("哥伦比亚", "🇨🇴"),
}

# (fifa_match_id, date YYYY-MM-DD, HH:MM local, home, away, stage, group|None, venue, is_hot)
# stage: group | round32 | round16 | quarter | semifinal | third_place | final
RAW: list[tuple] = [
    # --- A 组 ---
    ("400021443", "2026-06-11", "19:00", "MEX", "RSA", "group", "A", "Mexico City", True),
    ("400021441", "2026-06-12", "02:00", "KOR", "CZE", "group", "A", "Guadalajara", False),
    ("400021440", "2026-06-18", "16:00", "CZE", "RSA", "group", "A", "Atlanta", False),
    ("400021442", "2026-06-19", "01:00", "MEX", "KOR", "group", "A", "Guadalajara", False),
    ("400021444", "2026-06-25", "01:00", "CZE", "MEX", "group", "A", "Mexico City", False),
    ("400021445", "2026-06-25", "01:00", "RSA", "KOR", "group", "A", "Monterrey", False),
    # --- B 组 ---
    ("400021449", "2026-06-12", "19:00", "CAN", "BIH", "group", "B", "Toronto", False),
    ("400021447", "2026-06-13", "19:00", "QAT", "SUI", "group", "B", "San Francisco Bay Area", False),
    ("400021446", "2026-06-18", "19:00", "SUI", "BIH", "group", "B", "Los Angeles", False),
    ("400021450", "2026-06-18", "22:00", "CAN", "QAT", "group", "B", "Vancouver", False),
    ("400021451", "2026-06-24", "19:00", "SUI", "CAN", "group", "B", "Vancouver", False),
    ("400021448", "2026-06-24", "19:00", "BIH", "QAT", "group", "B", "Seattle", False),
    # --- C 组 ---
    ("400021456", "2026-06-13", "22:00", "BRA", "MAR", "group", "C", "New York", True),
    ("400021453", "2026-06-14", "01:00", "HAI", "SCO", "group", "C", "Boston", False),
    ("400021454", "2026-06-19", "22:00", "SCO", "MAR", "group", "C", "Boston", False),
    ("400021457", "2026-06-20", "00:30", "BRA", "HAI", "group", "C", "Philadelphia", False),
    ("400021455", "2026-06-24", "22:00", "SCO", "BRA", "group", "C", "Miami", False),
    ("400021452", "2026-06-24", "22:00", "MAR", "HAI", "group", "C", "Atlanta", False),
    # --- D 组 ---
    ("400021458", "2026-06-13", "01:00", "USA", "PAR", "group", "D", "Los Angeles", True),
    ("400021463", "2026-06-14", "04:00", "AUS", "TUR", "group", "D", "Vancouver", False),
    ("400021462", "2026-06-19", "19:00", "USA", "AUS", "group", "D", "Seattle", False),
    ("400021460", "2026-06-20", "03:00", "TUR", "PAR", "group", "D", "San Francisco Bay Area", False),
    ("400021459", "2026-06-26", "02:00", "TUR", "USA", "group", "D", "Los Angeles", False),
    ("400021461", "2026-06-26", "02:00", "PAR", "AUS", "group", "D", "San Francisco Bay Area", False),
    # --- E 组 ---
    ("400021464", "2026-06-14", "17:00", "GER", "CUW", "group", "E", "Houston", False),
    ("400021467", "2026-06-14", "23:00", "CIV", "ECU", "group", "E", "Philadelphia", False),
    ("400021469", "2026-06-20", "20:00", "GER", "CIV", "group", "E", "Toronto", False),
    ("400021465", "2026-06-21", "00:00", "ECU", "CUW", "group", "E", "Kansas City", False),
    ("400021468", "2026-06-25", "20:00", "CUW", "CIV", "group", "E", "Philadelphia", False),
    ("400021466", "2026-06-25", "20:00", "ECU", "GER", "group", "E", "New York", False),
    # --- F 组 ---
    ("400021470", "2026-06-14", "20:00", "NED", "JPN", "group", "F", "Dallas", False),
    ("400021474", "2026-06-15", "02:00", "SWE", "TUN", "group", "F", "Monterrey", False),
    ("400021472", "2026-06-20", "17:00", "NED", "SWE", "group", "F", "Houston", False),
    ("400021475", "2026-06-21", "04:00", "TUN", "JPN", "group", "F", "Monterrey", False),
    ("400021471", "2026-06-25", "23:00", "JPN", "SWE", "group", "F", "Dallas", False),
    ("400021473", "2026-06-25", "23:00", "TUN", "NED", "group", "F", "Kansas City", False),
    # --- G 组 ---
    ("400021478", "2026-06-15", "19:00", "BEL", "EGY", "group", "G", "Seattle", False),
    ("400021476", "2026-06-16", "01:00", "IRN", "NZL", "group", "G", "Los Angeles", False),
    ("400021477", "2026-06-21", "19:00", "BEL", "IRN", "group", "G", "Los Angeles", False),
    ("400021480", "2026-06-22", "01:00", "NZL", "EGY", "group", "G", "Vancouver", False),
    ("400021479", "2026-06-27", "03:00", "EGY", "IRN", "group", "G", "Seattle", False),
    ("400021481", "2026-06-27", "03:00", "NZL", "BEL", "group", "G", "Vancouver", False),
    # --- H 组 ---
    ("400021482", "2026-06-15", "16:00", "ESP", "CPV", "group", "H", "Atlanta", False),
    ("400021486", "2026-06-15", "22:00", "KSA", "URU", "group", "H", "Miami", False),
    ("400021483", "2026-06-21", "16:00", "ESP", "KSA", "group", "H", "Atlanta", True),
    ("400021487", "2026-06-21", "22:00", "URU", "CPV", "group", "H", "Miami", False),
    ("400021485", "2026-06-27", "00:00", "CPV", "KSA", "group", "H", "Houston", False),
    ("400021484", "2026-06-27", "00:00", "URU", "ESP", "group", "H", "Guadalajara", False),
    # --- I 组 ---
    ("400021490", "2026-06-16", "19:00", "FRA", "SEN", "group", "I", "New York", True),
    ("400021488", "2026-06-16", "22:00", "IRQ", "NOR", "group", "I", "Boston", False),
    ("400021492", "2026-06-22", "21:00", "FRA", "IRQ", "group", "I", "Philadelphia", False),
    ("400021491", "2026-06-23", "00:00", "NOR", "SEN", "group", "I", "New York", False),
    ("400021489", "2026-06-26", "19:00", "NOR", "FRA", "group", "I", "Boston", False),
    ("400021493", "2026-06-26", "19:00", "SEN", "IRQ", "group", "I", "Toronto", False),
    # --- J 组 ---
    ("400021496", "2026-06-17", "01:00", "ARG", "ALG", "group", "J", "Kansas City", True),
    ("400021498", "2026-06-17", "04:00", "AUT", "JOR", "group", "J", "San Francisco Bay Area", False),
    ("400021494", "2026-06-22", "17:00", "ARG", "AUT", "group", "J", "Dallas", False),
    ("400021499", "2026-06-23", "03:00", "JOR", "ALG", "group", "J", "San Francisco Bay Area", False),
    ("400021497", "2026-06-28", "02:00", "ALG", "AUT", "group", "J", "Kansas City", False),
    ("400021495", "2026-06-28", "02:00", "JOR", "ARG", "group", "J", "Dallas", False),
    # --- K 组 ---
    ("400021502", "2026-06-17", "17:00", "POR", "COD", "group", "K", "Houston", False),
    ("400021504", "2026-06-18", "02:00", "UZB", "COL", "group", "K", "Mexico City", False),
    ("400021503", "2026-06-23", "17:00", "POR", "UZB", "group", "K", "Houston", False),
    ("400021501", "2026-06-24", "02:00", "COL", "COD", "group", "K", "Guadalajara", False),
    ("400021505", "2026-06-27", "23:30", "COL", "POR", "group", "K", "Miami", False),
    ("400021500", "2026-06-27", "23:30", "COD", "UZB", "group", "K", "Atlanta", False),
    # --- L 组 ---
    ("400021507", "2026-06-17", "20:00", "ENG", "CRO", "group", "L", "Dallas", True),
    ("400021510", "2026-06-17", "23:00", "GHA", "PAN", "group", "L", "Toronto", False),
    ("400021506", "2026-06-23", "20:00", "ENG", "GHA", "group", "L", "Boston", False),
    ("400021511", "2026-06-23", "23:00", "PAN", "CRO", "group", "L", "Toronto", False),
    ("400021508", "2026-06-27", "21:00", "PAN", "ENG", "group", "L", "New York", False),
    ("400021509", "2026-06-27", "21:00", "CRO", "GHA", "group", "L", "Philadelphia", False),
    # --- 32 强 ---
    ("400021518", "2026-06-28", "19:00", "2A", "2B", "round32", None, "Los Angeles", False),
    ("400021516", "2026-06-29", "17:00", "1C", "2F", "round32", None, "Houston", False),
    ("400021513", "2026-06-29", "20:30", "1E", "3ABCDF", "round32", None, "Boston", False),
    ("400021522", "2026-06-30", "01:00", "1F", "2C", "round32", None, "Monterrey", False),
    ("400021514", "2026-06-30", "17:00", "2E", "2I", "round32", None, "Dallas", False),
    ("400021523", "2026-06-30", "21:00", "1I", "3CDFGH", "round32", None, "New York", False),
    ("400021520", "2026-07-01", "01:00", "1A", "3CEFHI", "round32", None, "Mexico City", False),
    ("400021512", "2026-07-01", "16:00", "1L", "3EHIJK", "round32", None, "Atlanta", False),
    ("400021525", "2026-07-01", "20:00", "1G", "3AEHIJ", "round32", None, "Seattle", False),
    ("400021524", "2026-07-02", "00:00", "1D", "3BEFIJ", "round32", None, "San Francisco Bay Area", False),
    ("400021519", "2026-07-02", "19:00", "1H", "2J", "round32", None, "Los Angeles", False),
    ("400021526", "2026-07-02", "23:00", "2K", "2L", "round32", None, "Toronto", False),
    ("400021527", "2026-07-03", "03:00", "1B", "3EFGIJ", "round32", None, "Vancouver", False),
    ("400021515", "2026-07-03", "18:00", "2D", "2G", "round32", None, "Dallas", False),
    ("400021521", "2026-07-03", "22:00", "1J", "2H", "round32", None, "Miami", False),
    ("400021517", "2026-07-04", "01:30", "1K", "3DEIJL", "round32", None, "Kansas City", False),
    # --- 16 强 ---
    ("400021530", "2026-07-04", "17:00", "W73", "W75", "round16", None, "Houston", False),
    ("400021533", "2026-07-04", "21:00", "W74", "W77", "round16", None, "Philadelphia", False),
    ("400021532", "2026-07-05", "20:00", "W76", "W78", "round16", None, "New York", False),
    ("400021531", "2026-07-06", "00:00", "W79", "W80", "round16", None, "Mexico City", False),
    ("400021529", "2026-07-06", "19:00", "W83", "W84", "round16", None, "Dallas", False),
    ("400021534", "2026-07-07", "00:00", "W81", "W82", "round16", None, "Seattle", False),
    ("400021528", "2026-07-07", "16:00", "W86", "W88", "round16", None, "Atlanta", False),
    ("400021535", "2026-07-07", "20:00", "W85", "W87", "round16", None, "Vancouver", False),
    # --- 8 强（官网 9–11 日）---
    ("400021536", "2026-07-09", "19:00", "W89", "W90", "quarter", None, "Boston", False),
    ("400021538", "2026-07-10", "19:00", "W93", "W94", "quarter", None, "Los Angeles", True),
    ("400021539", "2026-07-11", "19:00", "W91", "W92", "quarter", None, "Miami", False),
    ("400021537", "2026-07-11", "22:00", "W95", "W96", "quarter", None, "Kansas City", False),
    # --- 半决赛（官网 14–15 日，15:00 美东）---
    ("400021541", "2026-07-14", "19:00", "W97", "W98", "semifinal", None, "Dallas", True),
    ("400021540", "2026-07-15", "19:00", "W99", "W100", "semifinal", None, "Atlanta", True),
    # --- 三四名 & 决赛 ---
    ("400021542", "2026-07-18", "21:00", "RU101", "RU102", "third_place", None, "Miami", False),
    ("400021543", "2026-07-19", "19:00", "W101", "W102", "final", None, "New York", True),
]

# 淘汰赛占位符中文
PLACEHOLDER: dict[str, tuple[str, str]] = {
    "2A": ("A组第2名", "🏳️"),
    "2B": ("B组第2名", "🏳️"),
    "1C": ("C组第1名", "🏳️"),
    "2F": ("F组第2名", "🏳️"),
    "1E": ("E组第1名", "🏳️"),
    "3ABCDF": ("E/F/第三候选", "🏳️"),
    "1F": ("F组第1名", "🏳️"),
    "2C": ("C组第2名", "🏳️"),
    "2E": ("E组第2名", "🏳️"),
    "2I": ("I组第2名", "🏳️"),
    "1I": ("I组第1名", "🏳️"),
    "3CDFGH": ("C/D/F/G/第三候选", "🏳️"),
    "1A": ("A组第1名", "🏳️"),
    "3CEFHI": ("C/E/F/H/第三候选", "🏳️"),
    "1L": ("L组第1名", "🏳️"),
    "3EHIJK": ("E/H/I/J/K/第三候选", "🏳️"),
    "1G": ("G组第1名", "🏳️"),
    "3AEHIJ": ("A/E/H/I/J/第三候选", "🏳️"),
    "1D": ("D组第1名", "🏳️"),
    "3BEFIJ": ("B/E/F/I/J/第三候选", "🏳️"),
    "1H": ("H组第1名", "🏳️"),
    "2J": ("J组第2名", "🏳️"),
    "2K": ("K组第2名", "🏳️"),
    "2L": ("L组第2名", "🏳️"),
    "1B": ("B组第1名", "🏳️"),
    "3EFGIJ": ("E/F/G/I/J/第三候选", "🏳️"),
    "2D": ("D组第2名", "🏳️"),
    "2G": ("G组第2名", "🏳️"),
    "1J": ("J组第1名", "🏳️"),
    "2H": ("H组第2名", "🏳️"),
    "1K": ("K组第1名", "🏳️"),
    "3DEIJL": ("D/E/I/J/L/第三候选", "🏳️"),
    "W73": ("32强第73场胜者", "🏳️"),
    "W75": ("32强第75场胜者", "🏳️"),
    "W74": ("32强第74场胜者", "🏳️"),
    "W77": ("32强第77场胜者", "🏳️"),
    "W76": ("32强第76场胜者", "🏳️"),
    "W78": ("32强第78场胜者", "🏳️"),
    "W79": ("32强第79场胜者", "🏳️"),
    "W80": ("32强第80场胜者", "🏳️"),
    "W83": ("32强第83场胜者", "🏳️"),
    "W84": ("32强第84场胜者", "🏳️"),
    "W81": ("32强第81场胜者", "🏳️"),
    "W82": ("32强第82场胜者", "🏳️"),
    "W86": ("32强第86场胜者", "🏳️"),
    "W88": ("32强第88场胜者", "🏳️"),
    "W85": ("32强第85场胜者", "🏳️"),
    "W87": ("32强第87场胜者", "🏳️"),
    "W89": ("16强第89场胜者", "🏳️"),
    "W90": ("16强第90场胜者", "🏳️"),
    "W91": ("16强第91场胜者", "🏳️"),
    "W92": ("16强第92场胜者", "🏳️"),
    "W93": ("16强第93场胜者", "🏳️"),
    "W94": ("16强第94场胜者", "🏳️"),
    "W95": ("16强第95场胜者", "🏳️"),
    "W96": ("16强第96场胜者", "🏳️"),
    "W97": ("8强第97场胜者", "🏳️"),
    "W98": ("8强第98场胜者", "🏳️"),
    "W99": ("8强第99场胜者", "🏳️"),
    "W100": ("8强第100场胜者", "🏳️"),
    "RU101": ("半决赛101负者", "🏳️"),
    "RU102": ("半决赛102负者", "🏳️"),
    "W101": ("半决赛101胜者", "🏳️"),
    "W102": ("半决赛102胜者", "🏳️"),
}


def resolve(code: str) -> tuple[str, str]:
    if code in TEAMS:
        return TEAMS[code]
    if code in PLACEHOLDER:
        return PLACEHOLDER[code]
    return (code, "🏳️")


# 英文站钟面时间 → 北京时间的固定偏移（小时）
_FIFA_EN_TO_BEIJING_HOURS = 9


def to_utc_iso(date_str: str, time_str: str, venue: str) -> str:
    """venue 仅作元数据；换算不依赖场馆时区。"""
    _ = venue
    cn = ZoneInfo("Asia/Shanghai")
    wall = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    beijing = wall + timedelta(hours=_FIFA_EN_TO_BEIJING_HOURS)
    return beijing.replace(tzinfo=cn).astimezone(ZoneInfo("UTC")).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def build_row(
    fifa_id: str,
    date_str: str,
    time_str: str,
    home: str,
    away: str,
    stage: str,
    group: str | None,
    venue: str,
    is_hot: bool,
) -> dict:
    h_name, h_flag = resolve(home)
    a_name, a_flag = resolve(away)
    return {
        "id": f"fifa-{fifa_id}",
        "home_team": h_name,
        "away_team": a_name,
        "home_flag": h_flag,
        "away_flag": a_flag,
        "kickoff_at": to_utc_iso(date_str, time_str, venue),
        "stage": stage,
        "group_code": group,
        "venue": venue,
        "status": "scheduled",
        "is_hot": is_hot,
        "data_version": "fifa-2026-05-cn",
    }


def main() -> None:
    rows = [build_row(*r) for r in RAW]
    rows.sort(key=lambda x: x["kickoff_at"])
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} matches -> {OUT}")


if __name__ == "__main__":
    main()
