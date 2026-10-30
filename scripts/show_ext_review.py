# -*- coding: utf-8 -*-
"""T4-ext 提取基线审查视图：分层展示 考生答案 vs 标准答案 对照。"""
import glob
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys_p = os.path.join(BASE, "scripts")
import sys  # noqa: E402
sys.path.insert(0, sys_p)
from score_agent_run import edit_distance, norm_txt  # noqa: E402


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def main():
    gold = {r["task_id"]: r for r in read_jsonl(os.path.join(BASE, "eval", "T4_extract.jsonl"))}
    preds = {}
    for p in glob.glob(os.path.join(BASE, "eval", "agent_runs", "**", "predictions_*.jsonl"), recursive=True):
        for r in read_jsonl(p):
            if r["task_id"] in gold:
                preds[r["task_id"]] = r["answer"]

    rows = []
    for tid, g in gold.items():
        if tid not in preds:
            continue
        p, go = norm_txt(preds[tid]), norm_txt(g["answer"])
        ed = edit_distance(p, go)
        rows.append({"tid": tid, "img": os.path.basename(g["image"]), "qtype": g["qtype"],
                     "side": g.get("side", ""), "gold": g["answer"], "pred": preds[tid],
                     "ed": ed, "layer": "real" if g["task"] == "T4_ext" and g["image"].startswith("data/real") else "syn",
                     "conf": (g.get("meta") or {}).get("gold_confidence", "")})

    syn = [r for r in rows if r["layer"] == "syn"]
    real = [r for r in rows if r["layer"] == "real"]
    QT = {"seal_text_extract": "章面名", "party_text_extract": "主体名",
          "legal_rep_extract": "法代名", "sig_name_extract": "签名名"}

    def show(tag, rs, limit):
        print("---- %s（%d 条，展示前 %d）----" % (tag, len(rs), min(limit, len(rs))))
        for r in rs[:limit]:
            print("[%s|%s|%s] gold=%s" % (r["tid"], r["img"], QT.get(r["qtype"], r["qtype"]), r["gold"]))
            print("      pred=ED%d %s" % (r["ed"], r["pred"]))

    exact = sorted([r for r in syn if r["ed"] == 0], key=lambda r: -len(r["gold"]))
    near = sorted([r for r in syn if 1 <= r["ed"] <= 2], key=lambda r: r["ed"])
    bad = sorted([r for r in syn if r["ed"] > 5], key=lambda r: -r["ed"])
    show("合成·精确匹配样例", exact, 5)
    show("合成·近似匹配样例（ED1-2）", near, 5)
    show("合成·完全错误样例（ED>5）", bad, 6)

    # 真实图银标准
    print()
    rs = sorted(real, key=lambda r: (r["conf"], -r["ed"]))
    from collections import Counter
    print("==== 真实图提取（银标准）%d 题 ====" % len(real))
    for conf, n in sorted(Counter(r["conf"] for r in real).items(), key=lambda kv: -kv[1]):
        sub = [r for r in real if r["conf"] == conf]
        ex = sum(1 for r in sub if r["ed"] == 0)
        ne = sum(1 for r in sub if r["ed"] <= 2)
        med = sum(r["ed"] for r in sub) / len(sub)
        print("  gold置信=%s: %d 题 | 精确 %d ( %.0f%% ) | ED≤2 %d ( %.0f%% ) | 平均ED %.2f" % (
            conf, len(sub), ex, 100 * ex / len(sub), ne, 100 * ne / len(sub), med))
    print("  ---- 真实图 非精确匹配样例 ----")
    near_real = sorted([r for r in real if r["ed"] > 0], key=lambda r: -r["ed"])
    for r in near_real[:8]:
        print("  [%s|%s|%s|conf=%s] gold=%s" % (r["tid"], r["img"], QT.get(r["qtype"], r["qtype"]), r["conf"], r["gold"]))
        print("        pred=ED%d %s" % (r["ed"], r["pred"]))


if __name__ == "__main__":
    main()
