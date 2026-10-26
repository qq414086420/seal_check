# -*- coding: utf-8 -*-
"""从 Roboflow Universe 下载印章检测数据集（COCO 格式 zip 并解压）。
下载到 raw/dataset/roboflow_<proj>_<ver>.zip，解压到 raw/dataset/roboflow/<ws>_<proj>/。
"""
import json
import os
import time
import urllib.request
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY = "WdCGxgtXNbX3jaaQvKca"
RAW = os.path.join(BASE, "raw", "dataset")
OUT_ROOT = os.path.join(RAW, "roboflow")
UA = "seal-bench-research"

VERSIONS = [
    ("777sealhc1", "seal_detection-3nk2i", "2"),
    ("amar-arxww", "seal-detection-final", "1"),
    ("ali-mustofa-cxrgi", "seal-detection", "5"),
    ("robo-lpmzn", "seal_det-jpkzt", "1"),
]


def get_json(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def download(url, path, tries=5):
    """带断点续传的下载，完成后校验 zip 有效性。"""
    for t in range(tries):
        offset = os.path.getsize(path) if os.path.exists(path) else 0
        headers = {"User-Agent": UA}
        if offset:
            headers["Range"] = "bytes=%d-" % offset
        req = urllib.request.Request(url, headers=headers)
        try:
            mode = "ab" if offset else "wb"
            with urllib.request.urlopen(req, timeout=180) as r, open(path, mode) as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            print("download interrupted at %s bytes: %s" % (os.path.getsize(path) if os.path.exists(path) else 0, e))
        if os.path.exists(path) and zipfile.is_zipfile(path):
            return
        print("zip incomplete (%.1f MB), retry %d" % (os.path.getsize(path) / 1048576 if os.path.exists(path) else 0, t + 1))
        time.sleep(3)
    raise RuntimeError("download failed: " + path)


def main(only=None):
    todo = VERSIONS
    if only:
        keys = set(only)
        todo = [v for v in VERSIONS if "%s,%s,%s" % v in keys]
    os.makedirs(OUT_ROOT, exist_ok=True)
    for ws, proj, ver in todo:
        name = "%s_%s_v%s" % (ws, proj.replace("/", "_"), ver)
        zip_path = os.path.join(RAW, "roboflow_%s.zip" % name)
        out_dir = os.path.join(OUT_ROOT, name)
        if os.path.isdir(out_dir) and os.listdir(out_dir):
            print("skip (exists):", name)
            continue
        api = "https://api.roboflow.com/%s/%s/%s/coco?api_key=%s" % (ws, proj, ver, KEY)
        link = None
        for t in range(15):
            try:
                d = get_json(api)
                exp = d.get("export") or {}
                if exp.get("link"):
                    link = exp["link"]
                    break
                print("export not ready (%s), retry %d" % (exp.get("status"), t + 1))
            except Exception as e:
                print("api error:", e)
            time.sleep(3)
        if not link:
            print("FAILED export link:", name)
            continue
        print("downloading", name, "...")
        t0 = time.time()
        for attempt in range(3):
            try:
                download(link, zip_path)
                break
            except Exception as e:
                print("redownload attempt %d: %s" % (attempt + 1, e))
                link = None
                for t in range(10):
                    try:
                        d = get_json(api)
                        exp = d.get("export") or {}
                        if exp.get("link"):
                            link = exp["link"]
                            break
                    except Exception as e2:
                        print("api error:", e2)
                    time.sleep(3)
                if not link:
                    break
        if not (os.path.exists(zip_path) and zipfile.is_zipfile(zip_path)):
            print("FAILED download:", name)
            continue
        print("downloaded %.1f MB in %.0fs" % (os.path.getsize(zip_path) / 1048576, time.time() - t0))
        os.makedirs(out_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            # 扁平化解压：Windows 路径超长（Roboflow 用原始描述做文件名），全部放平并缩短超长名
            import hashlib
            import shutil
            for info in z.infolist():
                base = os.path.basename(info.filename)
                if not base or info.is_dir():
                    continue
                if not base.lower().endswith((".jpg", ".jpeg", ".png", ".json", ".txt", ".xml", ".csv")):
                    continue
                if len(os.path.join(out_dir, base)) > 240:
                    stem, ext = os.path.splitext(base)
                    base = stem[:60] + "_" + hashlib.md5(info.filename.encode("utf-8")).hexdigest()[:10] + ext
                with z.open(info) as src, open(os.path.join(out_dir, base), "wb") as f:
                    shutil.copyfileobj(src, f)
        os.remove(zip_path)
        n_img = sum(len([f for f in fs if f.lower().endswith((".jpg", ".jpeg", ".png"))])
                    for _, _, fs in os.walk(out_dir))
        print("extracted", name, "images:", n_img)


if __name__ == "__main__":
    import sys
    only = None
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        only = set(sys.argv[i + 1].split(";"))
    main(only)
