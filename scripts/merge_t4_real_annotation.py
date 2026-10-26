# -*- coding: utf-8 -*-
"""合并双通道标注：两轮独立标注一致的字段进入共识集，分歧项进入人工复核清单。
输出 metadata/annotate/real_t4_consensus.jsonl 与 real_t4_conflicts.jsonl
"""
import glob
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANN = os.path.join(BASE, "metadata", "annotate")


def norm(s):
    if not s:
        return None
    s = s.strip().replace(" ", "").replace("\u3000", "")
    return s.replace("（", "(").replace("）", ")")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


TEXT_FIELDS = ["party_a", "party_b", "legal_rep_a", "legal_rep_b"]
SEAL_FIELDS = ["seal_a", "seal_b"]   # → seal_a_readable/seal_a_text
SIG_FIELDS = ["sig_a", "sig_b"]      # → sig_a_readable/sig_a_name/sig_a_printed


def main():
    recs = {}
    for p in sorted(glob.glob(os.path.join(ANN, "real_t4_pass*.jsonl"))):
        for r in read_jsonl(p):
            recs.setdefault(r["file"], {})[os.path.basename(p)] = r

    consensus, conflicts = [], []
    for f, passes in sorted(recs.items()):
        if len(passes) < 2:
            continue
        vals = list(passes.values())
        p1, p2 = vals[0], vals[1]
        out = {"file": f}
        ok = True
        # 文本字段
        for fld in TEXT_FIELDS:
            v1, v2 = norm(p1.get(fld)), norm(p2.get(fld))
            if v1 and v2:
                if v1 == v2:
                    out[fld] = v1
                else:
                    conflicts.append({"file": f, "field": fld, "pass1": p1.get(fld), "pass2": p2.get(fld)})
                    out[fld] = None
                    ok = False
            else:
                out[fld] = None
        # 印章
        for fld in SEAL_FIELDS:
            r1, r2 = p1.get(fld + "_readable"), p2.get(fld + "_readable")
            t1, t2 = norm(p1.get(fld + "_text")), norm(p2.get(fld + "_text"))
            if r1 and r2 and t1 and t2:
                if t1 == t2:
                    out[fld + "_readable"], out[fld + "_text"] = True, t1
                else:
                    conflicts.append({"file": f, "field": fld + "_text", "pass1": p1.get(fld + "_text"),
                                      "pass2": p2.get(fld + "_text")})
                    out[fld + "_readable"], out[fld + "_text"] = False, None
                    ok = False
            else:
                out[fld + "_readable"], out[fld + "_text"] = False, None
        # 签名
        for fld in SIG_FIELDS:
            r1, r2 = p1.get(fld + "_readable"), p2.get(fld + "_readable")
            if r1 and r2:
                n1, n2 = norm(p1.get(fld + "_name")), norm(p2.get(fld + "_name"))
                pr1, pr2 = bool(p1.get(fld + "_printed")), bool(p2.get(fld + "_printed"))
                if n1 and n2 and n1 == n2 and pr1 == pr2:
                    out[fld + "_readable"], out[fld + "_name"], out[fld + "_printed"] = True, n1, pr1
                else:
                    conflicts.append({"file": f, "field": fld + "_name", "pass1": {"name": p1.get(fld + "_name"), "printed": pr1},
                                      "pass2": {"name": p2.get(fld + "_name"), "printed": pr2}})
                    out[fld + "_readable"], out[fld + "_name"], out[fld + "_printed"] = False, None, False
                    ok = False
            else:
                out[fld + "_readable"], out[fld + "_name"], out[fld + "_printed"] = False, None, False
        out["full_consensus"] = ok
        consensus.append(out)

    with open(os.path.join(ANN, "real_t4_consensus.jsonl"), "w", encoding="utf-8") as f:
        for r in consensus:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(ANN, "real_t4_conflicts.jsonl"), "w", encoding="utf-8") as f:
        for r in conflicts:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_seal = sum(1 for r in consensus if r.get("seal_a_text") or r.get("seal_b_text"))
    n_party = sum(1 for r in consensus if r.get("party_a") or r.get("party_b"))
    print("files with 2 passes:", len(recs))
    print("consensus records:", len(consensus))
    print("records with consensus seal text:", n_seal)
    print("records with consensus party name:", n_party)
    print("conflicts (需人工复核):", len(conflicts))


if __name__ == "__main__":
    main()
