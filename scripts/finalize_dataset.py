# -*- coding: utf-8 -*-
"""汇总四类子集，生成统一 manifest、去重、格式归一化与统计报告。
子集：realweb（网络真实图）/ commons（Wikimedia）/ synthetic（全合成）/ real_transplant（真实章移植伪造）
"""
import glob
import hashlib
import json
import os

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MANI = os.path.join(BASE, "metadata", "manifest.jsonl")
OUT_STATS = os.path.join(BASE, "reports", "dataset_stats.md")
OUT_SOURCES = os.path.join(BASE, "metadata", "sources.json")


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def load_verdicts():
    """多模态审核结果（batch_*.jsonl），key 为文件名。"""
    out = {}
    clf = os.path.join(BASE, "metadata", "classify")
    for p in sorted(glob.glob(os.path.join(clf, "batch_*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                    out[r["file"]] = r
                except Exception:
                    pass
    return out


VERDICTS = load_verdicts()


def weak_label(basename, has_signal):
    """弱标签：优先用多模态审核结论，否则回退红色信号启发式。"""
    v = VERDICTS.get(basename)
    if v is not None and v.get("keep"):
        return ("genuine" if v.get("red_official_seal") else "no_seal"), True
    return ("genuine" if has_signal else "no_seal"), False


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def red_signal(img):
    """红色印章信号：红色像素占比与红色区域外接框。"""
    small = img.resize((256, 256))
    a = np.asarray(small).astype(np.int16)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mask = (r > 110) & (r - g > 40) & (r - b > 40)
    ratio = float(mask.mean())
    if mask.any():
        ys, xs = np.where(mask)
        bbox = [float(xs.min()) / 256, float(ys.min()) / 256,
                float(xs.max()) / 256, float(ys.max()) / 256]
    else:
        bbox = None
    return ratio, bbox


def normalize(img_path):
    """统一为 RGB JPEG；返回 (w, h, reencoded)。"""
    img = Image.open(img_path)
    reencoded = False
    if img.mode != "RGB" or (img.format or "").upper() != "JPEG":
        img = img.convert("RGB")
        img.save(img_path, "JPEG", quality=92)
        reencoded = True
    w, h = img.size
    return w, h, reencoded


def main():
    realweb = {r["file"]: r for r in read_jsonl(os.path.join(BASE, "manifests", "realweb_raw.jsonl"))}
    commons = {os.path.basename(r.get("file", "")): r
               for r in read_jsonl(os.path.join(BASE, "manifests", "commons_raw.jsonl"))}
    synthetic = {r["file"]: r for r in read_jsonl(os.path.join(BASE, "manifests", "synthetic_manifest.jsonl"))}
    realforge = {os.path.basename(r["file"]): r
                 for r in read_jsonl(os.path.join(BASE, "manifests", "realforge_manifest.jsonl"))}

    records = []
    seen_md5 = {}
    dupes, bad, reencoded_n = [], [], 0
    idx = 0

    def add(path, subset, label, label_conf, extra, probe=False):
        nonlocal idx, reencoded_n
        try:
            w, h, reenc = normalize(path)
            if reenc:
                reencoded_n += 1
            if min(w, h) < 300:
                bad.append((path, "too small"))
                return None
            digest = md5(path)
        except Exception as e:
            bad.append((path, str(e)))
            return None
        if digest in seen_md5:
            dupes.append((path, seen_md5[digest]))
            return None
        seen_md5[digest] = path
        idx += 1
        img = Image.open(path).convert("RGB")
        ratio, bbox = red_signal(img)
        rec = {
            "id": "sb-%05d" % idx,
            "file": os.path.relpath(path, BASE).replace("\\", "/"),
            "subset": subset,
            "label": label,
            "label_confidence": label_conf,
            "width": w, "height": h, "md5": digest,
            "red_ratio": round(ratio, 5),
            "has_seal_signal": ratio >= 0.003,
            "red_bbox": [round(v, 3) for v in bbox] if bbox else None,
        }
        rec.update(extra)
        if probe:
            records.append(rec)
            return rec
        records.append(rec)
        return rec

    for p in sorted(glob.glob(os.path.join(BASE, "data", "real", "realweb_*.jpg"))):
        base = os.path.basename(p)
        m = realweb.get(base, {})
        extra = {"source_url": m.get("url"), "search_query": m.get("query"),
                 "origin": "web_image_search"}
        # 弱标签：先算红色信号再定标签——有红章信号 → genuine(weak)，无 → no_seal(weak)
        probe = add(p, "realweb", "genuine", "weak", extra, probe=True)
        if probe is not None:
            probe["label"], reviewed = weak_label(base, probe["has_seal_signal"])
            probe["reviewed"] = reviewed

    for p in sorted(glob.glob(os.path.join(BASE, "data", "real", "commons", "*"))):
        base = os.path.basename(p)
        m = commons.get(base, {})
        extra = {"source_url": m.get("url"), "desc_url": m.get("descurl"),
                 "title": m.get("title"), "license": m.get("license"),
                 "origin": "wikimedia_commons"}
        probe = add(p, "commons", "genuine", "weak", extra, probe=True)
        if probe is not None:
            probe["label"], reviewed = weak_label(base, probe["has_seal_signal"])
            probe["reviewed"] = reviewed

    for p in sorted(glob.glob(os.path.join(BASE, "data", "synthetic", "*.jpg"))):
        base = os.path.basename(p)
        m = synthetic.get(base, {})
        label = {True: "genuine", False: "forged", None: "no_seal"}[m.get("seal_genuine")]
        extra = {"origin": "synthetic", "contract_type": m.get("contract_type"),
                 "seal_mode": m.get("seal_mode"), "forgery_types": m.get("forgery_types"),
                 "quality_mode": m.get("quality_mode"),
                 "seal_detail": m.get("seals"), "signature_detail": m.get("signatures")}
        add(p, "synthetic", label, "clean", extra)

    for p in sorted(glob.glob(os.path.join(BASE, "data", "forged_real", "*.jpg"))):
        base = os.path.basename(p)
        m = realforge.get(base, {})
        extra = {"origin": "real_transplant", "forgery_types": m.get("forgery_types"),
                 "target_file": m.get("target_file"), "seal_assets": m.get("seal_assets"),
                 "quality": "rephotographed_jpeg"}
        add(p, "real_transplant", "forged", "clean", extra)

    os.makedirs(os.path.dirname(OUT_MANI), exist_ok=True)
    with open(OUT_MANI, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- 统计 ----
    def cnt(key_fn):
        out = {}
        for r in records:
            k = key_fn(r)
            out[k] = out.get(k, 0) + 1
        return out

    by_subset_label = {}
    for r in records:
        key = (r["subset"], r["label"])
        by_subset_label[key] = by_subset_label.get(key, 0) + 1

    ft = {}
    for r in records:
        for t in (r.get("forgery_types") or []):
            ft[t] = ft.get(t, 0) + 1

    lines = ["# SealBench 数据集统计", "",
             "- 总样本：**%d**" % len(records),
             "- 重复丢弃：%d；损坏/过小丢弃：%d；重新编码为 RGB JPEG：%d" % (len(dupes), len(bad), reencoded_n),
             "",
             "## 子集 × 标签", "",
             "| 子集 | 标签 | 数量 |", "|---|---|---|"]
    for (s, l), n in sorted(by_subset_label.items()):
        lines.append("| %s | %s | %d |" % (s, l, n))
    weak = sum(1 for r in records if r["label_confidence"] == "weak")
    weak_sig = sum(1 for r in records if r["label_confidence"] == "weak" and r["has_seal_signal"])
    lines += ["", "弱标签（真实网图）中红色印章信号命中：%d / %d" % (weak_sig, weak), "",
              "## 伪造类型分布", ""]
    for t, n in sorted(ft.items(), key=lambda kv: -kv[1]):
        lines.append("- %s: %d" % (t, n))
    lines += ["", "## 成像质量（synthetic）", ""]
    for q, n in sorted(cnt(lambda r: r.get("quality_mode") or "-").items()):
        lines.append("- %s: %d" % (q, n))
    lines += ["", "## 来源分布", ""]
    for o, n in sorted(cnt(lambda r: r.get("origin") or "-").items()):
        lines.append("- %s: %d" % (o, n))
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    sources = {
        "web_image_search": {"count": sum(1 for r in records if r.get("origin") == "web_image_search"),
                             "note": "百度/搜狗/360/Bing 图片搜索，查询词见 search_query；弱标签"},
        "wikimedia_commons": {"count": sum(1 for r in records if r.get("origin") == "wikimedia_commons"),
                              "note": "Wikimedia Commons，自由许可，逐张 license 字段"},
        "docdiff_seal_assets": {"count": 1597, "license": "MIT (c) 2023 Zongyuan Yang",
                                "url": "https://github.com/Royalvice/DocDiff",
                                "note": "真实红章抠图+掩码，源自 ICDAR2023 RRC Seal Title 竞赛数据；用于 real_transplant 伪造合成"},
        "synthetic": {"count": sum(1 for r in records if r.get("origin") == "synthetic"),
                      "note": "Pillow 渲染中文合同+公章+手写签名，种子 20261024 可复现"},
    }
    with open(OUT_SOURCES, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)

    print("records:", len(records))
    print("dupes:", len(dupes), "bad:", len(bad), "reencoded:", reencoded_n)
    for d in dupes[:10]:
        print("  dup:", d)
    for b in bad[:10]:
        print("  bad:", b)


if __name__ == "__main__":
    main()
