# -*- coding: utf-8 -*-
"""Wikimedia Commons 定向重采（v2）：
- 仅保留标题/描述与中文合同、地契、印章相关的文件（过滤 pork chops / 人名等噪音）
- 标准缩略图宽度 + 放慢节奏 + 429 退避重试
输出 data/real/commons/ 与 manifests/commons_raw.jsonl（重建）。
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(BASE, "data", "real", "commons")
MANI = os.path.join(BASE, "manifests", "commons_raw.jsonl")
API = "https://commons.wikimedia.org/w/api.php"
UA = "SealBench/0.2 (seal-detection research; low-rate academic use)"

QUERIES = [
    "Chinese contract seal red",
    "Chinese contract document",
    "Chinese land deed",
    "地契",
    "Chinese deed chop",
    "Qing dynasty land contract",
    "Republic of China contract",
    "Chinese stamp document seal",
]

# 标题相关词：契约/印章/契/deed/contract/chop/seal，但排除明显无关词
RELEVANT = re.compile(r"(?i)contract|deed|地契|契|seal|chop|stamp|印", re.U)
EXCLUDE = re.compile(r"(?i)pork|meat|food|recipe|asante|guantlett|logo of|flag of|coat of arms|seal of the|insignia|heraldry|postage|philatelic|musical group|band|ship\b", re.U)


def api(params, tries=4):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    for t in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15 * (t + 1)
                print("429, backoff %ds" % wait)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("api retries exhausted")


def fetch(url, path, tries=4):
    for t in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=90) as r, open(path, "wb") as f:
                f.write(r.read())
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 20 * (t + 1)
                print("dl 429, backoff %ds: %s" % (wait, os.path.basename(path)))
                time.sleep(wait)
            else:
                print("dl fail %s: %s" % (e.code, os.path.basename(path)))
                return False
        except Exception as e:
            print("dl error", e)
            return False
    return False


def search(query):
    data = api({
        "action": "query", "generator": "search",
        "gsrnamespace": "6", "gsrsearch": query, "gsrlimit": "40",
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1024",
    })
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        title = p.get("title", "")
        if EXCLUDE.search(title):
            continue
        if not RELEVANT.search(title):
            continue
        ii = (p.get("imageinfo") or [None])[0]
        if not ii or ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if (ii.get("width") or 0) < 600 or (ii.get("height") or 0) < 450:
            continue
        meta = ii.get("extmetadata") or {}
        out.append({
            "pageid": p["pageid"],
            "title": title,
            "url": ii.get("thumburl") or ii.get("url"),
            "descurl": ii.get("descriptionurl"),
            "w": ii.get("width"), "h": ii.get("height"), "mime": ii.get("mime"),
            "license": (meta.get("LicenseShortName") or {}).get("value", ""),
            "query": query,
        })
    return out


def main(target=180):
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    seen, items = set(), []
    for q in QUERIES:
        try:
            found = search(q)
            print("query %-32s -> %d relevant" % (q, len(found)))
            for it in found:
                if it["pageid"] not in seen:
                    seen.add(it["pageid"])
                    items.append(it)
        except Exception as e:
            print("search fail", q, e)
        time.sleep(2.0)
    items.sort(key=lambda it: (it["mime"] != "image/jpeg",
                               abs((it["w"] or 1) / max(1, it["h"] or 1) - 0.77)))
    items = items[:target]
    recs = []
    for i, it in enumerate(items, 1):
        ext = ".png" if it["mime"] == "image/png" else ".jpg"
        path = os.path.join(OUT, "commons_%04d%s" % (i, ext))
        if fetch(it["url"], path):
            it["file"] = os.path.relpath(path, BASE).replace("\\", "/")
            it["source"] = "wikimedia_commons"
            recs.append(it)
        time.sleep(1.6)
    with open(MANI, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("commons saved:", len(recs))


if __name__ == "__main__":
    main()
