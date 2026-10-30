# -*- coding: utf-8 -*-
"""把用户人工审核结论落地：
A 类（用户给出正确内容）→ 覆盖对应提取题 gold（key 级覆盖）
不可读/gold 不可靠 → 剔除该题（不出题）
输出：追加 metadata/annotate/manual_review.jsonl（key 级覆盖条目）
      + metadata/annotate/user_review_applied.jsonl（全部 19 条判定留档）
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_jsonl(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def main():
    rev = read_jsonl(os.path.join(BASE, "reviewed_real_ext.jsonl"))
    gold = {r["task_id"]: r for r in read_jsonl(os.path.join(BASE, "eval", "T4_extract.jsonl"))}
    preds = {}
    for p in glob_preds():
        for r in read_jsonl(p):
            preds[r["task_id"]] = r.get("answer")

    def key_of(g):
        side = g.get("side", "a").lower()
        qt = g["qtype"]
        return {"seal_text_extract": "seal_%s_text" % side,
                "party_text_extract": "party_%s" % side,
                "legal_rep_extract": "legal_rep_%s" % side,
                "sig_name_extract": "sig_%s_name" % side}[qt]

    corrections, excluded, kept = [], [], []
    for r in rev:
        if r.get("verdict") != "错误":
            continue
        g = gold.get(r["task_id"])
        if not g:
            continue
        key = key_of(g)
        note = (r.get("note") or "").strip()
        model = preds.get(r["task_id"], "")
        f = os.path.basename(g["image"])
        if not note:
            kept.append({**r, "key": key, "resolution": "保留 gold，计模型识别错误",
                         "model_answer": model})
            continue
        if "不清晰" in note or "看不清" in note:
            excluded.append({"file": f, "key": key, "exclude": True,
                             "reason": note, "source": "user_review",
                             "task_id": r["task_id"]})
            continue
        if note == g["answer"]:
            kept.append({**r, "key": key, "resolution": "备注与 gold 相同：保留 gold，计模型识别错误",
                         "model_answer": model})
            continue
        # A 类：用户给出正确内容 → 覆盖 gold
        corrections.append({"file": f, "key": key, "exclude": False,
                            "gold_corrected": note, "old_gold": g["answer"],
                            "model_answer": model, "source": "user_review",
                            "task_id": r["task_id"]})
    # 04778：甲方法代 gold 错挂乙方名，用户未给正确值 → 剔除
    excluded.append({"file": "realweb_0341.jpg", "key": "legal_rep_a", "exclude": True,
                     "reason": "gold 误挂乙方信息（袁建华），甲方章面为陕西中基电业；正确法代名不可靠，剔除",
                     "source": "user_review", "task_id": "t4x-04778"})

    mr_path = os.path.join(BASE, "metadata", "annotate", "manual_review.jsonl")
    existing = read_jsonl(mr_path)
    # 旧条目迁移：补 key（seal 覆盖的 key = seal_{side}_text）
    for r in existing:
        if not r.get("key") and r.get("field") == "seal" and r.get("side"):
            r["key"] = "seal_%s_text" % r["side"]
    seen = {(r.get("file"), r.get("key")) for r in existing}
    with open(mr_path, "w", encoding="utf-8") as f:
        for r in existing:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for c in corrections:
            if (c["file"], c["key"]) in seen:
                continue
            entry = {"file": c["file"], "key": c["key"],
                     "gold_corrected": c["gold_corrected"], "old_gold": c.get("old_gold"),
                     "exclude": False, "source": "user_review",
                     "reviewer": "用户人工审核", "date": "2026-10-31", "note": c.get("note", "")}
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        for e in excluded:
            if (e["file"], e["key"]) in seen:
                continue
            entry = {"file": e["file"], "key": e["key"], "exclude": True,
                     "reason": e["reason"], "source": "user_review",
                     "reviewer": "用户人工审核", "date": "2026-10-31"}
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    audit = corrections + excluded + kept
    with open(os.path.join(BASE, "metadata", "annotate", "user_review_applied.jsonl"), "w", encoding="utf-8") as f:
        for r in audit:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("gold 修正:", len(corrections))
    print("题目剔除:", len(excluded))
    print("保留 gold 计模型错误:", len(kept))
    print("审核留档:", len(audit), "-> metadata/annotate/user_review_applied.jsonl")


def glob_preds():
    import glob as g
    return g.glob(os.path.join(BASE, "eval", "agent_runs", "**", "predictions_*.jsonl"), recursive=True)


if __name__ == "__main__":
    main()
