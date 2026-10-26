# -*- coding: utf-8 -*-
"""按多模态审核结果剔除无效真实样本：
- 不符合"现代中文合同+红色公章"的 realweb/commons 图片移入 data/excluded/<subset>/
- 以被剔除图为底图的 real_transplant 样本一并剔除（移入 data/excluded/transplant/）
- 输出 metadata/excluded_manifest.jsonl 记录剔除原因；realforge_manifest.jsonl 仅保留有效项
"""
import glob
import json
import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLF = os.path.join(BASE, "metadata", "classify")
EXC = os.path.join(BASE, "data", "excluded")


def main():
    verdicts = {}
    for p in sorted(glob.glob(os.path.join(CLF, "batch_*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    r = json.loads(ln)
                    verdicts[r["file"]] = r
    print("verdicts loaded:", len(verdicts))

    excluded = []
    hold = []
    moved = 0
    for sub, pat in (("realweb", os.path.join(BASE, "data", "real", "realweb_*.jpg")),
                     ("commons", os.path.join(BASE, "data", "real", "commons", "*"))):
        for fp in sorted(glob.glob(pat)):
            b = os.path.basename(fp)
            v = verdicts.get(b)
            if v is None or v.get("keep"):
                continue
            if v.get("doc_type") == "business_doc":
                # 合同关联商务单据（中标通知书/签证/验收/结算等）：归入待定区，不进主数据集
                dst_dir = os.path.join(BASE, "data", "hold")
                os.makedirs(dst_dir, exist_ok=True)
                shutil.move(fp, os.path.join(dst_dir, b))
                hold.append({"file": "data/hold/" + b, "orig_file": "data/real/" + b,
                             "doc_type": "business_doc", "reason": v.get("reason")})
                continue
            dst_dir = os.path.join(EXC, sub)
            os.makedirs(dst_dir, exist_ok=True)
            shutil.move(fp, os.path.join(dst_dir, b))
            orig = "data/real/%s" % b if sub == "realweb" else "data/real/commons/%s" % b
            excluded.append({"file": "data/excluded/%s/%s" % (sub, b), "orig_file": orig,
                             "subset": sub, "doc_type": v.get("doc_type"),
                             "chinese": v.get("chinese"), "red_official_seal": v.get("red_official_seal"),
                             "reason": v.get("reason")})
            moved += 1

    mani_p = os.path.join(BASE, "manifests", "realforge_manifest.jsonl")
    kept_recs, dropped_recs = [], []
    with open(mani_p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            tb = os.path.basename(r.get("target_file", ""))
            v = verdicts.get(tb)
            (kept_recs if (v and v.get("keep")) else dropped_recs).append(r)
    for r in dropped_recs:
        fp = os.path.join(BASE, r["file"])
        if os.path.exists(fp):
            dst_dir = os.path.join(EXC, "transplant")
            os.makedirs(dst_dir, exist_ok=True)
            shutil.move(fp, os.path.join(dst_dir, os.path.basename(r["file"])))
        excluded.append({"file": "data/excluded/transplant/" + os.path.basename(r["file"]),
                         "subset": "real_transplant", "doc_type": "dropped_base",
                         "reason": "底图被剔除: " + os.path.basename(r.get("target_file", "")),
                         "target_file": r.get("target_file")})
    with open(mani_p, "w", encoding="utf-8") as f:
        for r in kept_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ex_p = os.path.join(BASE, "metadata", "excluded_manifest.jsonl")
    prev = {}
    if os.path.exists(ex_p):
        with open(ex_p, encoding="utf-8") as f:
            for ln in f:
                try:
                    r0 = json.loads(ln)
                    prev[r0.get("file")] = r0
                except Exception:
                    pass
    for r in excluded:
        prev[r["file"]] = r
    with open(ex_p, "w", encoding="utf-8") as f:
        for r in prev.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if hold:
        hold_p = os.path.join(BASE, "metadata", "hold_manifest.jsonl")
        with open(hold_p, "a", encoding="utf-8") as f:
            for r in hold:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("business_doc -> hold:", len(hold))

    print("real images moved to excluded:", moved)
    print("transplant kept: %d, dropped: %d" % (len(kept_recs), len(dropped_recs)))
    print("excluded total records:", len(excluded))


if __name__ == "__main__":
    main()
