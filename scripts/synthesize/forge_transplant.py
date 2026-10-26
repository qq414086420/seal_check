# -*- coding: utf-8 -*-
"""真实域伪造样本：把 DocDiff 真实红章（seals/ + masks/，MIT 许可）移植到真实合同/文书照片上。
这是最常见的假章手法之一（P 图盖印/电子章粘贴）。输出 data/forged_real/ 与 manifests/realforge_manifest.jsonl。
"""
import glob
import json
import os
import random

import numpy as np
from PIL import Image, ImageFilter

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEAL_DIR = os.path.join(BASE, "raw", "dataset", "docdiff_seal")
REAL_ROOT = os.path.join(BASE, "data", "real")
OUT = os.path.join(BASE, "data", "forged_real")
MANI = os.path.join(BASE, "manifests", "realforge_manifest.jsonl")


def list_targets():
    """递归收集 data/real 下全部图片（含 realweb/commons/roboflow 导入）。"""
    out = []
    for root, _, files in os.walk(REAL_ROOT):
        for fn in files:
            if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                out.append(os.path.join(root, fn))
    return sorted(out)

random.seed(20261024)
np.random.seed(20261024)


def load_seals_docbank(max_n=600, min_area=12000):
    """DocBank Seal-4 透明底 PNG 印章（alpha 即掩码），随机抽样加载并紧裁剪。"""
    d = os.path.join(BASE, "raw", "dataset", "docbank_seal4")
    if not os.path.isdir(d):
        return []
    files = [p for p in glob.glob(os.path.join(d, "*.png"))]
    if not files:
        return []
    random.shuffle(files)
    seals = []
    for sp in files:
        if len(seals) >= max_n:
            break
        try:
            img = Image.open(sp).convert("RGBA")
        except Exception:
            continue
        a = img.split()[3]
        mask = a.point(lambda v: 255 if v > 127 else 0)
        bbox = mask.getbbox()
        if bbox is None:
            continue
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w * h < min_area or max(w, h) < 100:
            continue
        if not (0.5 <= w / max(1, h) <= 1.8):   # 过滤边缘裁切的碎片（印章应近圆/近椭圆）
            continue
        img = img.crop(bbox)
        name = "docbank_" + os.path.splitext(os.path.basename(sp))[0][:40]
        seals.append((name, img))
    return seals


def load_seals(min_area=12000):
    seals = []
    for sp in sorted(glob.glob(os.path.join(SEAL_DIR, "seals", "*.png"))):
        name = os.path.splitext(os.path.basename(sp))[0]
        mp = os.path.join(SEAL_DIR, "masks", name + ".png")
        if not os.path.exists(mp):
            continue
        try:
            rgb = np.asarray(Image.open(sp).convert("RGB"))
            m = np.asarray(Image.open(mp).convert("L"))
        except Exception:
            continue
        if rgb.shape[0] != m.shape[0] or rgb.shape[1] != m.shape[1]:
            continue
        if int((m > 127).sum()) < min_area:  # 过滤噪声/碎片
            continue
        alpha = np.where(m > 127, 255, 0).astype(np.uint8)
        rgba = np.dstack([rgb, alpha])
        seals.append((name, Image.fromarray(rgba, "RGBA")))
    return seals


def doc_like(img):
    """粗筛：偏亮的、接近文档的图。"""
    w, h = img.size
    if w < 420 or h < 420:
        return False
    g = np.asarray(img.convert("L"), dtype=np.float32)
    return float(g.mean()) > 105.0


def paste_seal(page, seal, first=True):
    w, h = page.size
    scale = random.uniform(0.22, 0.34) * min(w, h) / max(seal.width, seal.height)
    nw, nh = max(24, int(seal.width * scale)), max(24, int(seal.height * scale))
    s = seal.resize((nw, nh), Image.LANCZOS)
    s = s.rotate(random.uniform(-10, 10), expand=True, resample=Image.BICUBIC)
    a = np.asarray(s).astype(np.float32)
    a[:, :, 3] *= random.uniform(0.78, 0.95)  # 印泥浓度
    # 颜色抖动：红通道亮度/轻微色偏
    a[:, :, 0] = np.clip(a[:, :, 0] * random.uniform(0.85, 1.12), 0, 255)
    a[:, :, 1] = np.clip(a[:, :, 1] * random.uniform(0.9, 1.1), 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] * random.uniform(0.9, 1.1), 0, 255)
    s = Image.fromarray(a.astype(np.uint8), "RGBA")
    if random.random() < 0.8:
        s = s.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 0.9)))
    x0 = random.uniform(0.06, 0.58) if first else random.uniform(0.5, 0.88)
    y0 = random.uniform(0.52, 0.86)
    px, py = int(x0 * w - s.width / 2), int(y0 * h - s.height / 2)
    px = max(-s.width // 3, min(px, w - s.width * 2 // 3))
    py = max(-s.height // 4, min(py, h - s.height * 3 // 4))
    page_rgba = page.convert("RGBA")
    page_rgba.alpha_composite(s, (px, py))
    bbox = [int(px), int(py), int(px + s.width), int(py + s.height)]
    return page_rgba.convert("RGB"), bbox


def main(n_target=170, per_target=2):
    os.makedirs(OUT, exist_ok=True)
    seals = load_seals()
    print("usable seals (DocDiff):", len(seals))
    seals_db = load_seals_docbank()
    if seals_db:
        print("usable seals (DocBank Seal-4):", len(seals_db))
        seals = seals + seals_db
    targets = list_targets()
    random.shuffle(targets)
    recs, idx = [], 0
    for tp in targets:
        if idx >= n_target:
            break
        try:
            probe = Image.open(tp).convert("RGB")
        except Exception:
            continue
        if not doc_like(probe):
            continue
        k = min(per_target, n_target - idx)
        for vi in range(k):
            try:
                page = Image.open(tp).convert("RGB")
            except Exception:
                break
            if not doc_like(page):
                break
            n = 1 if random.random() < 0.65 else 2
            chosen = random.sample(seals, n)
            bboxes = []
            for j, (nm, s) in enumerate(chosen):
                page, bb = paste_seal(page, s, first=(j == 0))
                bboxes.append(bb)
            # 全图轻退化，模拟翻拍/扫描
            if random.random() < 0.5:
                page = page.filter(ImageFilter.GaussianBlur(random.uniform(0.2, 0.6)))
            idx += 1
            fname = "realforge_%04d.jpg" % idx
            page.save(os.path.join(OUT, fname), "JPEG", quality=random.randint(55, 85))
            recs.append({
                "file": "data/forged_real/" + fname,
                "source": "real_transplant",
                "target_file": os.path.relpath(tp, BASE).replace("\\", "/"),
                "variant": vi + 1,
                "seal_assets": [nm for nm, _ in chosen],
                "n_seals": n,
                "paste_bboxes": bboxes,
                "forgery_types": ["seal_transplant"],
            })
    with open(MANI, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("real-forgery saved:", len(recs))


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 170
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    main(n, per)
