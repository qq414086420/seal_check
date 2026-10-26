# -*- coding: utf-8 -*-
"""第二轮定向采集：聚焦"合同盖章页/签署页"类查询，补充第一轮清洗后的真实样本缺口。
- 文件名延续 realweb_04XX 编号（finalize 的 realweb_* 通配可直接覆盖）
- 去重：URL 对照已有 manifest，图像 ahash 去重
- 采集层不做内容判断，内容审核由多模态分类轮完成
"""
import hashlib
import io
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE, "data", "real")
META_PATH = os.path.join(BASE, "manifests", "realweb_raw.jsonl")
BLOCK_DOMAINS = ("alamy", "dreamstime", "istockphoto", "gettyimages", "shutterstock",
                 "51miz", "nipic.", "58pic", "ibaotu", "818ps", "gaoding", "699pic",
                 "photophoto", "tofoyes", "pikbest")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Referer": "https://image.so.com/"}

QUERIES = ["补充协议盖章", "合同补充协议", "框架协议盖章", "采购协议盖章", "服务合同盖章",
           "租赁协议盖章", "抵押合同盖章", "担保合同盖章", "分包合同盖章", "劳务合同盖章",
           "股权转让协议盖章", "合同续签盖章", "装修合同盖章", "买卖合同盖章", "承包合同盖章",
           "加盟合同盖章", "协议书双方盖章", "合同盖章扫描件",
           "中标通知书盖章", "工程签证单盖章", "验收报告盖章", "结算单盖章", "对账单盖章",
           "授权委托书盖章", "承诺书盖章", "工程联系单盖章", "投标文件盖章", "报审表盖章"]

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 450


def next_index():
    mx = 0
    for f in os.listdir(RAW_DIR):
        if f.startswith("realweb_") and f.endswith(".jpg"):
            try:
                mx = max(mx, int(f[8:12]))
            except ValueError:
                pass
    return mx + 1


def existing_urls():
    urls = set()
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            for ln in f:
                try:
                    urls.add(json.loads(ln).get("url"))
                except Exception:
                    pass
    return urls


def fetch_candidates(seen_urls):
    seen, out = set(seen_urls), []
    for q in QUERIES:
        for sn in range(0, 420, 60):
            url = ("https://image.so.com/j?q=%s&src=srp&correct=&pn=60&sn=%d" %
                   (urllib.parse.quote(q), sn))
            try:
                req = urllib.request.Request(url, headers=UA)
                raw = urllib.request.urlopen(req, timeout=15).read()
                d = json.loads(raw.decode("utf-8", "ignore"))
            except Exception:
                continue
            new = 0
            for it in d.get("list") or []:
                u = it.get("img")
                if not u or u in seen:
                    continue
                seen.add(u)
                w, h = int(it.get("width") or 0), int(it.get("height") or 0)
                if w < 400 or h < 400 or max(w, h) / max(1, min(w, h)) > 5:
                    continue
                if any(b in u.lower() for b in BLOCK_DOMAINS):
                    continue
                out.append({"url": u, "query": q, "w": w, "h": h})
                new += 1
            print("[cand] %s sn=%d new=%d total=%d" % (q, sn, new, len(out)), flush=True)
            if len(out) >= TARGET * 3:
                break
        if len(out) >= TARGET * 3:
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
    try:
        req = urllib.request.Request(job["url"], headers=UA)
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
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(w, h) > 1800:
        r = 1800.0 / max(w, h)
        img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
    arr = list(img.convert("L").resize((64, 64)).getdata())
    mean = sum(arr) / float(len(arr))
    var = sum((p - mean) ** 2 for p in arr) / float(len(arr))
    if var < 120:
        return None
    return job, img


def main():
    random.seed(20261025)
    idx = next_index()
    print("start index:", idx, flush=True)
    cands = fetch_candidates(existing_urls())
    random.shuffle(cands)
    print("candidates:", len(cands), flush=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    hashes, saved, idx, meta_f = [], 0, idx, open(META_PATH, "a", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(download_one, c): c for c in cands[: TARGET * 4]}
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
