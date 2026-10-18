"""e-Gov の法令データ（API v2）から、条文の本文を、一字も変えずに取り出す"""
import base64, json, sys
import xml.etree.ElementTree as ET
from pathlib import Path
D = Path(__file__).parent
WANT = {
 "kijun": ["7_3", "22", "39", "40", "42", "43", "52", "53", "61", "68_2", "69"],
 "toshi": ["7", "8", "12_4", "29", "43", "53", "58_2"],
 "doro": ["28"], "morido": ["12", "30"], "kasen": ["30", "56"], "gesui": ["10"],
 "jokaso": ["3_2", "5"], "suido": ["16"], "shobo": ["9", "9_2"], "dosha": ["9"],
}
PFX = {"Part": "Pa", "Chapter": "Ch", "Section": "Se", "Subsection": "Ss", "Division": "Di"}
def txt(e): return "".join(e.itertext()).strip() if e is not None else ""
def sent(e):
    if e is None: return ""
    return "".join(txt(s) if s.tag != "Column" else txt(s) + "　" for s in e.iter() if s.tag in ("Sentence",)) or txt(e)
def lines_of(el, depth=0):
    out = []
    for c in el:
        tag = c.tag
        if tag == "Paragraph":
            num = txt(c.find("ParagraphNum"))
            out.append((num + "　" if num else "") + sent(c.find("ParagraphSentence")))
            out += lines_of(c, depth + 1)
        elif tag == "Item" or tag.startswith("Subitem") and not tag.endswith(("Title", "Sentence")):
            title = txt(c.find("ItemTitle")) or txt(c.find(tag + "Title"))
            body = c.find("ItemSentence") if tag == "Item" else c.find(tag + "Sentence")
            out.append("　" * depth + (title + "　" if title else "") + sent(body))
            out += lines_of(c, depth + 1)
        elif tag in ("TableStruct", "List", "Remarks"):
            t = txt(c)
            if t: out.append("　" * depth + "（表など）" + " ".join(t.split())[:400])
    return out
res = {}
for law, arts in WANT.items():
    d = json.loads((D / f"{law}.json").read_text(encoding="utf-8"))
    xml = base64.b64decode(d["law_full_text"]).decode("utf-8")
    root = ET.fromstring(xml)
    title = d["revision_info"]["law_title"]; date = d["revision_info"].get("amendment_enforcement_date", "")
    main = root.find(".//MainProvision")
    parent = {c: p for p in main.iter() for c in p}
    for a in main.iter("Article"):
        n = a.get("Num")
        if n not in arts: continue
        path = []; p = parent.get(a)
        while p is not None and p is not main:
            if p.tag in PFX: path.append(f"{PFX[p.tag]}_{p.get('Num')}")
            p = parent.get(p)
        anchor = "-".join(["Mp"] + path[::-1] + [f"At_{n}"])
        cap = txt(a.find("ArticleCaption")); at = txt(a.find("ArticleTitle"))
        body = "\n".join([((cap + "\n") if cap else "") + at] + lines_of(a))
        res[f"{law}:{n}"] = {"law": title, "law_id": d["law_info"]["law_id"], "num": n, "title": at, "caption": cap, "anchor": anchor,
                             "url": f"https://laws.e-gov.go.jp/law/{d['law_info']['law_id']}#{anchor}", "date": date, "text": body}
(D / "articles.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in res.items(): print(k, v["title"], v["caption"], v["anchor"], len(v["text"]))
missing = [f"{l}:{n}" for l, ns in WANT.items() for n in ns if f"{l}:{n}" not in res]
print("missing", missing)
