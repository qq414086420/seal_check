# -*- coding: utf-8 -*-
"""从 360 图片搜索接口批量采集真实合同/公章照片，校验去重后存入 data/real/"""
import json, io, os, hashlib, time, sys, random
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, urllib.parse

try:
    from PIL import Image
except ImportError:
    print("PIL missing"); sys.exit(1)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE, "data", "real")
META_PATH = os.path.join(BASE, "manifests", "realweb_raw.jsonl")
BLOCK_DOMAINS = ("alamy", "dreamstime", "istockphoto", "gettyimages", "shutterstock",
                 "51miz", "nipic.", "58pic", "ibaotu", "818ps", "gaoding", "699pic",
                 "photophoto", "nipic", "tofoyes", "pikbest", "觅知网", "摄图")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Referer": "https://image.so.com/"}

QUERIES = ["合同公章", "盖章合同", "公司公章", "劳动合同盖章", "租赁合同盖章", "合同专用章",
           "签合同盖章", "合同红章", "公章扫描件", "协议书盖章", "中标通知书盖章", "授权委托书盖章",
           "合同印鉴", "企业印章合同", "合同盖章照片", "公章合同文件"]

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 450


def fetch_candidates():
    seen, out = set(), []
    for q in QUERIES:
        for sn in range(0, 600, 60):
            url = ("https://image.so.com/j?q=%s&src=srp&correct=&pn=60&sn=%d" %
                   (urllib.parse.quote(q), sn))
            try:
                req = urllib.request.Request(url, headers=UA)
                raw = urllib.request.urlopen(req, timeout=15).read()
                d = json.loads(raw.decode("utf-8", "ignore"))
            except Exception:
                continue
            lst = d.get("list") or []
            new = 0
            for it in lst:
                u = it.get("img")
                if not u or u in seen:
                    continue
                seen.add(u)
                w, h = int(it.get("width") or 0), int(it.get("height") or 0)
                if w < 400 or h < 400 or max(w, h) / max(1, min(w, h)) > 5:
                    continue
                low = u.lower()
                if any(b in low for b in BLOCK_DOMAINS):
                    continue
                out.append({"url": u, "query": q, "w": w, "h": h})
                new += 1
            print("[cand] %s sn=%d new=%d total=%d" % (q, sn, new, len(out)), flush=True)
            if len(out) >= TARGET * 4:
                break
        if len(out) >= TARGET * 4:
            break
    return out


def ahash(img):
    g = img.convert("L").resize((8, 8), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / 64.0
    bits = 0
    for i, p in enumerate(px):
        if p > avg:
            bits |= (1 << i)
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def download_one(job):
    u = job["url"]
    try:
        req = urllib.request.Request(u, headers=UA)
        data = urllib.request.urlopen(req, timeout=18).read()
        if len(data) < 12000:
            return None
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    w, h = img.size
    if w < 300 or h < 300:
        return None
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max(w, h) > 1800:
        r = 1800.0 / max(w, h)
        img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
    arr = list(img.convert("L").resize((64, 64)).getdata())
    mean = sum(arr) / float(len(arr))
    var = sum((p - mean) ** 2 for p in arr) / float(len(arr))
    if var < 120:  # 近乎纯色
        return None
    return job, img


def main():
    random.seed(20261024)
    cands = fetch_candidates()
    random.shuffle(cands)
    print("candidates:", len(cands), flush=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
    hashes, saved, idx, meta_f = [], 0, 0, open(META_PATH, "a", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(download_one, c): c for c in cands[: TARGET * 5]}
        for fut in as_completed(futs):
            r = fut.result()
            if r is None:
                continue
            job, img = r
            hsh = ahash(img)
            if any(hamming(hsh, x) <= 5 for x in hashes):
                continue
            hashes.append(hsh)
            idx += 1
            name = "realweb_%04d.jpg" % idx
            img.save(os.path.join(RAW_DIR, name), "JPEG", quality=90)
            meta_f.write(json.dumps({"file": name, "url": job["url"], "query": job["query"],
                                     "orig_w": job["w"], "orig_h": job["h"]}, ensure_ascii=False) + "\n")
            meta_f.flush()
            saved += 1
            if saved % 20 == 0:
                print("saved %d" % saved, flush=True)
            if saved >= TARGET:
                break
    meta_f.close()
    print("DONE saved=", saved)


if __name__ == "__main__":
    main()
