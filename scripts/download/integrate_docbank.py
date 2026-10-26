# -*- coding: utf-8 -*-
"""接入 DocBank Seal-4（80000 张透明底 PNG 印章，夸克网盘手动下载）。
用法：python integrate_docbank.py [压缩包路径]
- 自动在 raw/dataset/ 下查找 *eal4*/*eal-4*/*docbank* 的 zip
- 扁平化解压到 raw/dataset/docbank_seal4/（超长文件名自动缩短）
"""
import hashlib
import os
import shutil
import sys
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(BASE, "raw", "dataset")
OUT = os.path.join(RAW, "docbank_seal4")


def find_archive():
    if len(sys.argv) > 1:
        return sys.argv[1]
    cands = []
    for f in os.listdir(RAW):
        low = f.lower()
        if low.endswith(".zip") and ("eal4" in low or "eal-4" in low or "docbank" in low):
            cands.append(os.path.join(RAW, f))
    return cands[0] if cands else None


def main():
    if os.path.isdir(OUT) and os.listdir(OUT):
        n = sum(1 for _, _, fs in os.walk(OUT) for f in fs if f.lower().endswith(".png"))
        print("already extracted:", n, "png in", OUT)
        return
    zp = find_archive()
    if not zp:
        print("NOT FOUND: 请把 Seal-4 压缩包放到", RAW)
        sys.exit(1)
    print("using archive:", zp)
    os.makedirs(OUT, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zp) as z:
        for info in z.infolist():
            base = os.path.basename(info.filename)
            if not base or info.is_dir() or not base.lower().endswith(".png"):
                continue
            if len(os.path.join(OUT, base)) > 240:
                stem, ext = os.path.splitext(base)
                base = stem[:60] + "_" + hashlib.md5(info.filename.encode("utf-8")).hexdigest()[:10] + ext
            target = os.path.join(OUT, base)
            if os.path.exists(target):
                continue
            with z.open(info) as src, open(target, "wb") as f:
                shutil.copyfileobj(src, f)
            n += 1
            if n % 5000 == 0:
                print("extracted", n, flush=True)
    print("done. extracted", n, "png ->", OUT)


if __name__ == "__main__":
    main()
