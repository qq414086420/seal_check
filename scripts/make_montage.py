# -*- coding: utf-8 -*-
"""为每个 Roboflow 数据集生成 5x5 缩略图蒙太奇，便于快速人工评估内容。"""
import glob
import os
import random

from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "raw", "dataset", "roboflow")
OUT = os.path.join(BASE, "reports")

random.seed(7)
CELL = 300

for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    if not os.path.isdir(d):
        continue
    imgs = [p for p in glob.glob(os.path.join(d, "**", "*"), recursive=True) if p.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not imgs:
        continue
    pick = random.sample(imgs, min(25, len(imgs)))
    grid = Image.new("RGB", (CELL * 5, CELL * 5), (240, 240, 240))
    for i, p in enumerate(pick):
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        im.thumbnail((CELL, CELL))
        x = (i % 5) * CELL + (CELL - im.width) // 2
        y = (i // 5) * CELL + (CELL - im.height) // 2
        grid.paste(im, (x, y))
    name = os.path.basename(d)
    out = os.path.join(OUT, "montage_%s.jpg" % name)
    grid.save(out, "JPEG", quality=82)
    print("%s -> %s (pool %d)" % (name, os.path.basename(out), len(imgs)))
