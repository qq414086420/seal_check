# -*- coding: utf-8 -*-
"""把真实图的双通道共识标注转成与合成图 synthetic_manifest 同构的标签格式。
输出 metadata/realweb_labels.jsonl，字段对齐 synthetic_manifest：
  file/contract_type/party_a/party_b/legal_rep_a/legal_rep_b/
  seal_present/seal_genuine/seal_mode/
  seals[]: {side, company, readable, matches_party, genuine, kind}
  signatures[]: {side, name, readable, matches_rep, printed, forgery}
真实图特有：annotation 元信息（银标准来源、可读性门控）。
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_jsonl(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def norm(s):
    if not s:
        return None
    s = s.strip().replace(" ", "").replace("\u3000", "")
    return s.replace("（", "(").replace("）", ")")


def main():
    cons = {r["file"]: r for r in read_jsonl(os.path.join(BASE, "metadata", "annotate", "real_t4_consensus.jsonl"))}
    # 人工复核覆盖层：人工判定优先于机器共识（如联合体盖章豁免）
    overrides = {}
    mr = os.path.join(BASE, "metadata", "annotate", "manual_review.jsonl")
    if os.path.exists(mr):
        for r in read_jsonl(mr):
            overrides[(r["file"], r.get("side", ""))] = r
    mani = read_jsonl(os.path.join(BASE, "metadata", "manifest.jsonl"))

    out = []
    for rec in mani:
        if rec["subset"] != "realweb":
            continue
        f = os.path.basename(rec["file"])
        c = cons.get(f)
        if not c:
            continue
        seals, sigs = [], []
        for side in ("a", "b"):
            S = side.upper()
            seal_text = c.get("seal_%s_text" % side)
            party = c.get("party_%s" % side)
            entry = {
                "side": S,
                "company": seal_text,                       # 章面实际刻名（共识转录）
                "readable": bool(c.get("seal_%s_readable" % side)) and bool(seal_text),
                "matches_party": (norm(seal_text) == norm(party)) if (seal_text and party) else None,
                "genuine": True,                            # 审核通过的真实合同，默认真章（弱假设）
                "kind": None,                               # 真实图未标注章种类
            }
            ov = overrides.get((f, side))
            if ov and ov.get("field") == "seal":
                entry["readable"] = bool(ov.get("readable"))
                entry["company"] = ov.get("text")
                entry["matches_party"] = ov.get("matches_party")
                entry["manual_review"] = {"reviewer": ov.get("reviewer"), "date": ov.get("date"),
                                          "note": ov.get("note")}
            seals.append(entry)
            sigs.append({
                "side": S,
                "name": c.get("sig_%s_name" % side),
                "readable": bool(c.get("sig_%s_readable" % side)) and bool(c.get("sig_%s_name" % side)),
                "matches_rep": (norm(c.get("sig_%s_name" % side)) == norm(c.get("legal_rep_%s" % side)))
                               if (c.get("sig_%s_name" % side) and c.get("legal_rep_%s" % side)) else None,
                "printed": bool(c.get("sig_%s_printed" % side)),
                "forgery": [],
            })
        seal_present = any(s["readable"] for s in seals) or bool(rec.get("has_seal_signal"))
        out.append({
            "file": f,
            "subset": "realweb",
            "contract_type": None,
            "party_a": c.get("party_a"), "party_b": c.get("party_b"),
            "legal_rep_a": c.get("legal_rep_a"), "legal_rep_b": c.get("legal_rep_b"),
            "seal_present": seal_present,
            "seal_genuine": True if rec["label"] == "genuine" else None,
            "seal_mode": "genuine_reviewed" if rec["label"] == "genuine" else "no_seal",
            "seals": seals,
            "signatures": sigs,
            "annotation": {"source": "dual_pass_consensus", "silver": True,
                           "full_consensus": bool(c.get("full_consensus"))},
        })

    out_p = os.path.join(BASE, "metadata", "realweb_labels.jsonl")
    with open(out_p, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_seal = sum(1 for r in out if any(s["readable"] and s["matches_party"] is not None for s in r["seals"]))
    n_sig = sum(1 for r in out if any(s["readable"] for s in r["signatures"]))
    n_match = sum(1 for r in out for s in r["seals"] if s["readable"] and s["matches_party"] is False)
    print("realweb labels:", len(out))
    print("  images with readable seal+party (可出章面题):", n_seal)
    print("  images with readable signature (可出签名题):", n_sig)
    print("  consensus 不一致章面实例:", n_match)


if __name__ == "__main__":
    main()
