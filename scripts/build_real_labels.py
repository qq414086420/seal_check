# -*- coding: utf-8 -*-
"""把真实图的双通道共识标注 + 人工审核修正转成与 synthetic_manifest 同构的标签格式。
覆盖层级：双通道共识 < 人工复核（manual_review.jsonl，key 级：修正 gold_corrected / 剔除 exclude）。
输出 metadata/realweb_labels.jsonl，字段对齐 synthetic_manifest。
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
    # 人工复核覆盖层（key 级：seal_X_text / party_X / legal_rep_X / sig_X_name）
    overrides = {}
    mr = os.path.join(BASE, "metadata", "annotate", "manual_review.jsonl")
    if os.path.exists(mr):
        for r in read_jsonl(mr):
            key = r.get("key") or ("seal_%s_text" % r["side"] if r.get("field") == "seal" and r.get("side") else None)
            if key:
                overrides[(r["file"], key)] = r
    mani = read_jsonl(os.path.join(BASE, "metadata", "manifest.jsonl"))

    out = []
    for rec in mani:
        if rec["subset"] != "realweb":
            continue
        f = os.path.basename(rec["file"])
        c = cons.get(f)
        if not c:
            continue

        def resolve(kind, side):
            """字段值：共识 < 人工覆盖。返回 (值, 是否被剔除)。"""
            key = "%s_%s" % (kind, side)
            o = overrides.get((f, key))
            base = c.get(key)
            if o:
                if o.get("exclude"):
                    return None, True
                if o.get("gold_corrected"):
                    return o["gold_corrected"], False
            return base, False

        party, legal_rep = {}, {}
        seals, sigs = [], []
        for side in ("a", "b"):
            S = side.upper()
            party[side] = resolve("party", side)[0]
            legal_rep[side] = resolve("legal_rep", side)[0]

            stv, st_ex = resolve("seal_text", side)
            seals.append({
                "side": S,
                "company": stv,
                "readable": bool(stv) and not st_ex,
                "matches_party": (norm(stv) == norm(party[side])) if (stv and party[side]) else None,
                "genuine": True,
                "kind": None,
            })

            snv, sn_ex = resolve("sig_name", side)
            sigs.append({
                "side": S,
                "name": snv,
                "readable": bool(snv) and not sn_ex,
                "matches_rep": (norm(snv) == norm(legal_rep[side])) if (snv and legal_rep[side]) else None,
                "printed": bool(c.get("sig_%s_printed" % side)),
                "forgery": [],
            })

        seal_present = any(s["readable"] for s in seals) or bool(rec.get("has_seal_signal"))
        out.append({
            "file": f,
            "subset": "realweb",
            "contract_type": None,
            "party_a": party["a"], "party_b": party["b"],
            "legal_rep_a": legal_rep["a"], "legal_rep_b": legal_rep["b"],
            "seal_present": seal_present,
            "seal_genuine": True if rec["label"] == "genuine" else None,
            "seal_mode": "genuine_reviewed" if rec["label"] == "genuine" else "no_seal",
            "seals": seals,
            "signatures": sigs,
            "annotation": {"source": "dual_pass_consensus+manual_review", "silver": True,
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
    print("  不一致章面实例（含人工复核修正后）:", n_match)


if __name__ == "__main__":
    main()
