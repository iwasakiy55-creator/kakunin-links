"""リンク集の画面（リンク集.html）を作る。

実行： py -X utf8 build.py
- data/ の JSON（県ごと）を読んで、1つの HTML にまとめる。見回りの道具が使う一覧 tools/links.json も作る。
- 見回りの結果（tools/status.js）は、画面が開くときに読む（見回りは「リンクを見回る.bat」。Python は要らない）。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE_URL = "https://iwasakiy55-creator.github.io/kakunin-links/"     # 公開の置き場（GitHub Pages）
SITE_DIR = Path(os.environ.get("SITE_DIR") or ROOT.parent)   # 公開する中身（このリポジトリのいちばん上）

# 県ごとの元データ（同じ県の複数ファイルは、まとめる）
SOURCES = [
    ("静岡県", ["shizuoka_src.json", "kankei_shizuoka.json"]),
    ("山梨県", ["yamanashi.json", "kankei_yamanashi.json"]),
    ("神奈川県", ["kanagawa_a.json", "kanagawa_b.json", "kankei_kanagawa.json"]),
]

PURPOSES = [   # (key, 見出し, 中身, まとまり, 根拠の条)  並びは審査で押さえる順。都市計画法 → 建築基準法 → 関係法令（印は付けない。どれも調べる）
    ("都市計画", "都市計画", "区域区分・用途地域・容積率・建蔽率・防火地域", "都市計画法", "都計法8条"),
    ("開発許可", "開発許可", "都市計画法29条・43条・53条", "都市計画法", "都計法29・43・53条"),
    ("地区計画", "地区計画", "地区計画の区域・条例（法68条の2）", "都市計画法", "都計法12条の4"),
    ("白地", "白地地域", "用途地域の指定のない区域の制限", "都市計画法", "基準法52・53条"),
    ("道路", "建築基準法の道路", "42条の道路種別・位置指定道路・2項道路", "建築基準法", "基準法42・43条"),
    ("地形", "地形・がけ", "がけ条例・標高・断面・傾斜", "建築基準法", "基準法40条（条例）"),
    ("災害", "災害", "土砂災害警戒区域・特別警戒区域・災害危険区域", "建築基準法", "基準法39条"),
    ("建築協定", "建築協定", "認可された建築協定の区域", "建築基準法", "基準法69条"),
    ("道路台帳", "道路台帳", "市町村道の認定路線・幅員", "建築基準法", "道路法28条"),
    ("盛土", "宅造・盛土規制法", "宅地造成等工事規制区域・特定盛土等規制区域（旧 宅地造成等規制法）", "関係法令", "盛土規制法12・30条"),
    ("浸水", "特定都市河川", "雨水浸透阻害行為の許可・浸水被害防止区域", "関係法令", "特定都市河川法30条"),
    ("下水道", "下水道", "処理区域・排水設備（下水道法10条）", "関係法令", "下水道法10条"),
    ("浄化槽", "浄化槽", "浄化槽の設置（浄化槽法3条の2）", "関係法令", "浄化槽法3条の2"),
    ("水道", "水道", "給水装置（水道法16条）", "関係法令", "水道法16条"),
    ("消防", "消防", "火災予防条例・住宅用火災警報器（消防法9条）", "関係法令", "消防法9条"),
    ("中間検査", "中間検査", "特定工程の指定（特定行政庁ごとの告示）", "検査", "基準法7条の3"),
    ("そのほか", "そのほか", "景観・まちづくり条例・開発指導 など", "検査", ""),
]


# 全国共通のページ（国土地理院）。どの県・市町村にも出す
NATIONAL = [
    {"label": "地理院地図（標高・断面図・傾斜量図）", "url": "https://maps.gsi.go.jp/", "src": "国土地理院",
     "what": "地図を右クリックで標高。上の「ツール」→「断面図」で、敷地まわりの高低差を線で見られる。傾斜量図・陰影起伏図も重ねられる。がけかどうかの判定ではなく、目安",
     "verified": True, "checked": "2026-10-16", "purpose": "地形", "role": "まずここで調べる"},
    {"label": "地理院地図で得られる値等について（標高の精度）", "url": "https://maps.gsi.go.jp/help/howtouse.html", "src": "国土地理院",
     "what": "標高のデータの細かさ・精度。擁壁や小さな段差は、地図の標高には表れないことがある",
     "verified": True, "checked": "2026-10-16", "purpose": "地形", "role": "補助"},
    {"label": "重ねるハザードマップ（全国）", "url": "https://disaportal.gsi.go.jp/maps/", "src": "国土地理院",
     "what": "土砂災害・洪水・津波などの区域を、1つの地図に重ねて見られる。最新の指定は、県のページで確かめる",
     "verified": True, "checked": "2026-10-16", "purpose": "災害", "role": "補助"},
]

# リンクに事前の許可が要る市町村（2026-10-17 に「リンクについて」で確かめた）。
# 許可をいただくまで、その市町村の自前のサイト（host に名前を含むもの）へのリンクは載せない。県・国などのページは載せる
HOLD = {
    "静岡県": {"御前崎市": "omaezaki", "菊川市": "kikugawa"},
    "神奈川県": {"清川村": "kiyokawa"},
}

# 限定特定行政庁（建築基準法第97条の2）。2026-10-17 に県の公式の一覧で確かめた
# 静岡：扱う範囲は「施行令第148条第1項に該当する建築物に限り市、その他は県」（県の受付窓口一覧表の凡例）。中間検査は県の告示、指定道路図は市
GENTEI = {"静岡県": ["三島市", "御殿場市", "藤枝市", "磐田市", "島田市", "裾野市", "袋井市", "掛川市", "湖西市"]}

# 元データに特定行政庁の一覧がない県（静岡は、申請チェッカーの中間検査の調べ先と同じ6市）
TOKUTEI = {"静岡県": ["静岡市", "浜松市", "沼津市", "富士市", "富士宮市", "焼津市"]}


def load(pref: str, files: list[str]) -> dict:
    out = {"name": pref, "checked_at": "", "tokutei": list(TOKUTEI.get(pref, [])), "guides": {}, "pref": [], "munis": {}}
    for f in files:
        p = DATA / f
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out["checked_at"] = max(out["checked_at"], d.get("checked_at") or "")
        out["tokutei"] += [t for t in d.get("tokutei_gyoseicho") or [] if t not in out["tokutei"]]
        for g in d.get("purposes") or []:
            out["guides"][g["key"]] = g.get("guide", "")
        out["pref"] += d.get("prefecture") or []
        for m, xs in (d.get("municipalities") or {}).items():
            out["munis"].setdefault(m, []).extend(xs)
    out["pref"] += [dict(x) for x in NATIONAL]
    from urllib.parse import urlparse
    for m, key in HOLD.get(pref, {}).items():
        if m in out["munis"]:
            # 市町村の中身（市町村のサイト・地図サイト・例規集）は載せない。県・国のページだけ残す
            # その市町村の中身（自前のサイト・その市町村の地図サイト・例規集）は外す。県・国・ほかの市の消防本部などは残す
            def own(u):
                q = urlparse(u)
                return key in q.netloc or key in q.path or re.search(r"legal-square|g-reiki|d1-law|reiki", q.netloc)
            out["munis"][m] = [x for x in out["munis"][m] if not own(x.get("url", ""))]
    out["hold"] = list(HOLD.get(pref, {}))
    out["gentei"] = list(GENTEI.get(pref, []))
    return out


def main() -> None:
    prefs = [load(p, fs) for p, fs in SOURCES]
    prefs = [p for p in prefs if p["munis"] or p["pref"]]
    sp = ROOT / "tools" / "status.json"
    status = json.loads(sp.read_text(encoding="utf-8-sig")) if sp.exists() else {}
    config = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
    payload = {
        "built": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "purposes": PURPOSES,
        "prefs": prefs,
        "status": status,
        "config": config,
        "kankei": json.loads((DATA / "kankei.json").read_text(encoding="utf-8")),
        "stale_days": 365,
    }
    js = json.dumps(payload, ensure_ascii=False)
    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*DATA*/null", js).replace('/*SITE*/""', json.dumps(SITE_URL))
    (ROOT / "リンク集.html").write_text(html, encoding="utf-8")
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")
    (SITE_DIR / "latest.js").write_text("window.LINK_LATEST = " + js + ";\n", encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    links = [{"url": x["url"], "pref": p["name"], "muni": m, "purpose": x.get("purpose", ""), "label": x.get("label", "")}
             for p in prefs for m, xs in [("（県）", p["pref"])] + list(p["munis"].items()) for x in xs if x.get("url")]
    (ROOT / "tools").mkdir(exist_ok=True)
    (ROOT / "tools" / "links.json").write_text(json.dumps(links, ensure_ascii=False, indent=0), encoding="utf-8")
    n = sum(len(x) for p in prefs for x in p["munis"].values()) + sum(len(p["pref"]) for p in prefs)
    print(f"ok  県 {len(prefs)}・市町村 {sum(len(p['munis']) for p in prefs)}・リンク {n}")


if __name__ == "__main__":
    main()
