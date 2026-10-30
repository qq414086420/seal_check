# -*- coding: utf-8 -*-
"""从 manifest 构造评测集。优先 T4 一致性核查（业务主场景），附带 T1/T2 整图任务。
输出：eval/T4_consistency.jsonl / eval/T1T2_doc.jsonl / eval/splits_stats.md / eval/prompt_templates.md
"""
import glob
import json
import os
import random

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(BASE, "eval")
random.seed(20261025)


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def _norm(s):
    if not s:
        return ""
    s = s.strip().replace(" ", "").replace("\u3000", "")
    return s.replace("（", "(").replace("）", ")")


def _edit_distance(a, b):
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != b[j - 1]))
        prev = cur
    return prev[lb]


def norm_cmp(s):
    if not s:
        return None
    s = s.strip().replace(" ", "").replace("\u3000", "")
    return s.replace("（", "(").replace("）", ")")


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    mani = read_jsonl(os.path.join(BASE, "metadata", "manifest.jsonl"))
    syn_raw = {os.path.basename(r["file"]): r for r in read_jsonl(os.path.join(BASE, "manifests", "synthetic_manifest.jsonl"))}

    # ---------- T4：一致性核查（synthetic 全部 339 张） ----------
    t4 = []
    qid = 0
    for rec in mani:
        if rec["subset"] != "synthetic":
            continue
        raw = syn_raw.get(os.path.basename(rec["file"]), {})
        party = {"A": raw.get("party_a"), "B": raw.get("party_b")}
        rep = {"A": raw.get("legal_rep_a"), "B": raw.get("legal_rep_b")}
        img = rec["file"]

        for side in ("A", "B"):
            tag = "甲方" if side == "A" else "乙方"
            sd = next((s for s in rec.get("seal_detail", []) if s.get("side") == side), None)
            if sd and party[side]:
                ans = "一致" if sd.get("matches_party") else "不一致"
                qid += 1
                # V2 开放式：不给名称，模型需同时读合同主体与章面
                t4.append({
                    "task_id": "t4-%04d" % qid, "image": img, "task": "T4",
                    "qtype": "seal_party_open", "side": side, "variant": "open",
                    "question": "这是一份合同文件图片。请读出图中%s（盖章）处红色印章上刻制的单位名称，并判断该名称与合同%s名称是否一致。" % (tag, tag),
                    "choices": ["一致", "不一致"], "answer": ans,
                    "evidence": {"party": party[side], "seal_company": sd.get("company"),
                                 "seal_kind": sd.get("kind")},
                })
                qid += 1
                # V1 点名式：给出名称，只需读章面核对（诊断章面 OCR 能力）
                t4.append({
                    "task_id": "t4-%04d" % qid, "image": img, "task": "T4",
                    "qtype": "seal_party_named", "side": side, "variant": "named",
                    "question": "合同%s为「%s」。图中%s（盖章）处红色印章上刻制的单位名称是否为「%s」？" % (
                        tag, party[side], tag, party[side]),
                    "choices": ["一致", "不一致"], "answer": ans,
                    "evidence": {"party": party[side], "seal_company": sd.get("company"),
                                 "seal_kind": sd.get("kind")},
                })
            sg = next((s for s in rec.get("signature_detail", []) if s.get("side") == side), None)
            if sg:
                qid += 1
                t4.append({
                    "task_id": "t4-%04d" % qid, "image": img, "task": "T4",
                    "qtype": "sig_rep_match", "side": side, "variant": "open",
                    "question": "图中%s法定代表人（签字）处的签名，与其法定代表人姓名「%s」是否一致？" % (
                        tag, rep[side]),
                    "choices": ["一致", "不一致"],
                    "answer": "一致" if sg.get("matches_rep") else "不一致",
                    "evidence": {"legal_rep": rep[side], "signed_name": sg.get("name")},
                })
                qid += 1
                t4.append({
                    "task_id": "t4-%04d" % qid, "image": img, "task": "T4",
                    "qtype": "sig_handwritten", "side": side, "variant": "open",
                    "question": "图中%s法定代表人（签字）处的签名是手写签名还是打印文字？" % tag,
                    "choices": ["手写", "打印"],
                    "answer": "打印" if sg.get("printed") else "手写",
                    "evidence": {"printed": sg.get("printed"), "signed_name": sg.get("name")},
                })

    write_jsonl(os.path.join(EVAL, "T4_consistency.jsonl"), t4)

    # ---------- T4 平衡子集：负例全保留 + 每题型等量正例采样 ----------
    balanced = []
    by_type = {}
    for r in t4:
        by_type.setdefault(r["qtype"], {"pos": [], "neg": []})
        pos_ans = "手写" if r["qtype"] == "sig_handwritten" else "一致"
        by_type[r["qtype"]]["pos" if r["answer"] == pos_ans else "neg"].append(r)
    for qt, g in sorted(by_type.items()):
        k = min(len(g["pos"]), len(g["neg"]))
        balanced.extend(g["neg"])
        balanced.extend(random.sample(g["pos"], k))
    write_jsonl(os.path.join(EVAL, "T4_balanced.jsonl"), balanced)

    # ---------- T4-real：真实图一致性核查（银标准，与合成图同一标签格式出题） ----------
    real_labels = {r["file"]: r for r in read_jsonl(os.path.join(BASE, "metadata", "realweb_labels.jsonl"))}
    t4r = []
    for rec in mani:
        if rec["subset"] != "realweb":
            continue
        u = real_labels.get(os.path.basename(rec["file"]))
        if not u:
            continue
        img = "data/real/" + u["file"]
        for side in ("A", "B"):
            tag = "甲方" if side == "A" else "乙方"
            sd = next((s for s in u["seals"] if s["side"] == side), None)
            if sd and sd.get("readable") and sd.get("company") and u.get("party_" + side.lower()):
                ans = "一致" if sd.get("matches_party") else "不一致"
                party_name = u.get("party_" + side.lower())
                qid += 1
                t4r.append({
                    "task_id": "t4r-%04d" % qid, "image": img, "task": "T4_real",
                    "qtype": "seal_party_open", "side": side, "variant": "open",
                    "question": "这是一份合同文件图片。请读出图中%s（盖章）处红色印章上刻制的单位名称，并判断该名称与合同%s名称是否一致。" % (tag, tag),
                    "choices": ["一致", "不一致"], "answer": ans,
                    "evidence": {"party": party_name, "seal_company": sd["company"]},
                    "meta": {"label_source": "dual_pass_consensus", "silver": True},
                })
                qid += 1
                t4r.append({
                    "task_id": "t4r-%04d" % qid, "image": img, "task": "T4_real",
                    "qtype": "seal_party_named", "side": side, "variant": "named",
                    "question": "合同%s为「%s」。图中%s（盖章）处红色印章上刻制的单位名称是否为「%s」？" % (
                        tag, party_name, tag, party_name),
                    "choices": ["一致", "不一致"], "answer": ans,
                    "evidence": {"party": party_name, "seal_company": sd["company"]},
                    "meta": {"label_source": "dual_pass_consensus", "silver": True},
                })
            sg = next((s for s in u["signatures"] if s["side"] == side), None)
            if sg and sg.get("readable"):
                rep = u.get("legal_rep_" + side.lower())
                if rep:
                    qid += 1
                    t4r.append({
                        "task_id": "t4r-%04d" % qid, "image": img, "task": "T4_real",
                        "qtype": "sig_rep_match", "side": side, "variant": "open",
                        "question": "图中%s法定代表人（签字）处的签名，与其法定代表人姓名「%s」是否一致？" % (tag, rep),
                        "choices": ["一致", "不一致"],
                        "answer": "一致" if sg.get("matches_rep") else "不一致",
                        "evidence": {"legal_rep": rep, "signed_name": sg.get("name")},
                        "meta": {"label_source": "dual_pass_consensus", "silver": True},
                    })
                qid += 1
                t4r.append({
                    "task_id": "t4r-%04d" % qid, "image": img, "task": "T4_real",
                    "qtype": "sig_handwritten", "side": side, "variant": "open",
                    "question": "图中%s法定代表人（签字）处的签名是手写签名还是打印文字？" % tag,
                    "choices": ["手写", "打印"],
                    "answer": "打印" if sg.get("printed") else "手写",
                    "evidence": {"signed_name": sg.get("name")},
                    "meta": {"label_source": "dual_pass_consensus", "silver": True},
                })
    write_jsonl(os.path.join(EVAL, "T4_real.jsonl"), t4r)

    # ---------- T4-ext：章面文字提取（开放作答，考章面 OCR；真值=构造/共识的章面刻名） ----------
    ext = []
    for rec in mani:
        if rec["subset"] != "synthetic":
            continue
        if "text_flip" in (rec.get("forgery_types") or []):
            continue  # 反排章的"正确读法"有歧义，跳过
        raw = syn_raw.get(os.path.basename(rec["file"]), {})
        img = rec["file"]
        for side in ("A", "B"):
            sd = next((s for s in rec.get("seal_detail", []) if s.get("side") == side), None)
            if not sd or not sd.get("company"):
                continue
            tag = "甲方" if side == "A" else "乙方"
            qid += 1
            ext.append({
                "task_id": "t4x-%05d" % qid, "image": img, "task": "T4_ext",
                "qtype": "seal_text_extract", "side": side,
                "question": "这是一份合同文件图片。请读出图中%s（盖章）处红色印章上刻制的单位名称，只输出该名称本身，不要加任何前缀、后缀或解释。" % tag,
                "choices": None, "answer": sd["company"],
                "evidence": {"party": raw.get("party_" + side.lower()),
                             "matches_party": sd.get("matches_party")},
                "meta": {"note": "开放作答；评分=归一化编辑距离"},
            })
    # ---------- T4-ext 真实图扩展：共识 / 双通道近似冲突 / 单通道 三级 gold ----------
    ann = os.path.join(BASE, "metadata", "annotate")

    def load_pass_set(pattern):
        recs = {}
        for p in glob.glob(os.path.join(ann, pattern)):
            for r in read_jsonl(p):
                recs[r["file"]] = r
        return recs

    ch1 = {**load_pass_set("real_t4_pass1_A.jsonl"), **load_pass_set("real_t4_pass1_B.jsonl")}
    ch2 = {**load_pass_set("real_t4_pass2_A.jsonl"), **load_pass_set("real_t4_pass2_B.jsonl")}
    mr_path = os.path.join(ann, "manual_review.jsonl")
    manual = {}
    if os.path.exists(mr_path):
        for r in read_jsonl(mr_path):
            manual[(r["file"], r.get("side", ""))] = r

    def pick_gold(f, key, side):
        # key 级人工覆盖（用户审核修正/剔除）对所有提取题型生效
        ov = manual.get((f, key))
        if ov:
            if ov.get("exclude"):
                return None, "excluded"
            if ov.get("gold_corrected"):
                return ov["gold_corrected"], "manual"
        v1, v2 = ch1.get(f, {}).get(key), ch2.get(f, {}).get(key)
        if v1 and v2:
            if _norm(v1) == _norm(v2):
                return v1, "consensus"
            if _edit_distance(_norm(v1), _norm(v2)) <= 3:
                return v1, "conflict_near"
            return v1, "conflict_far"
        if v1:
            return v1, "single_pass"
        if v2:
            return v2, "single_pass"
        return None, None

    for rec in mani:
        if rec["subset"] != "realweb":
            continue
        f = os.path.basename(rec["file"])
        img = rec["file"]
        for side, tag in (("a", "甲方"), ("b", "乙方")):
            fields = [
                ("seal_text_extract", "seal_%s_text" % side,
                 "请读出图中%s（盖章）处红色印章上刻制的单位名称，只输出该名称本身，不要加任何前缀、后缀或解释。" % tag),
                ("party_text_extract", "party_%s" % side,
                 "请读出这份合同中%s的单位名称，只输出该名称本身，不要加任何前缀、后缀或解释。" % tag),
                ("legal_rep_extract", "legal_rep_%s" % side,
                 "请读出这份合同中%s法定代表人的姓名，只输出姓名本身，不要加任何前缀、后缀或解释。" % tag),
                ("sig_name_extract", "sig_%s_name" % side,
                 "请读出图中%s法定代表人（签字）处签名的姓名，只输出姓名本身，不要加任何前缀、后缀或解释。" % tag),
            ]
            for qt, key, stem in fields:
                gold_txt, conf = pick_gold(f, key, side)
                if not gold_txt:
                    continue
                qid += 1
                ext.append({
                    "task_id": "t4x-%05d" % qid, "image": img, "task": "T4_ext",
                    "qtype": qt, "side": side.upper(),
                    "question": "这是一份真实合同照片。" + stem,
                    "choices": None, "answer": gold_txt,
                    "meta": {"gold_confidence": conf, "silver": True},
                })
    write_jsonl(os.path.join(EVAL, "T4_extract.jsonl"), ext)

    # ---------- T1/T2：整图任务（附带生成） ----------
    t12 = []
    qid = 0
    for rec in mani:
        if rec["label"] == "no_seal":
            continue
        qid += 1
        t12.append({
            "task_id": "t1-%04d" % qid, "image": rec["file"], "task": "T1",
            "question": "这张合同图片上的公章是真章还是假章？", "choices": ["真章", "假章"],
            "answer": "真章" if rec["label"] == "genuine" else "假章",
            "meta": {"subset": rec["subset"], "forgery_types": rec.get("forgery_types"),
                     "quality_mode": rec.get("quality_mode"), "label_confidence": rec["label_confidence"],
                     "pair_group": rec.get("target_file")},
        })
    for rec in mani:
        qid += 1
        t12.append({
            "task_id": "t2-%04d" % qid, "image": rec["file"], "task": "T2",
            "question": "判断这张合同图片的用章状态：真章 / 假章 / 未盖章。",
            "choices": ["真章", "假章", "未盖章"],
            "answer": {"genuine": "真章", "forged": "假章", "no_seal": "未盖章"}[rec["label"]],
            "meta": {"subset": rec["subset"], "forgery_types": rec.get("forgery_types"),
                     "quality_mode": rec.get("quality_mode"), "label_confidence": rec["label_confidence"]},
        })
    write_jsonl(os.path.join(EVAL, "T1T2_doc.jsonl"), t12)

    # ---------- 统计 ----------
    def qstat(qtype):
        rs = [r for r in t4 if r["qtype"] == qtype]
        pos = sum(1 for r in rs if r["answer"] == ("一致" if "match" in qtype or qtype.startswith("seal") else "手写"))
        if qtype == "sig_handwritten":
            pos = sum(1 for r in rs if r["answer"] == "手写")
        return len(rs), pos, len(rs) - pos

    lines = ["# 评测集统计", ""]
    n4 = len(t4)
    n_syn = sum(1 for r in mani if r["subset"] == "synthetic")
    lines += ["## T4 一致性核查（主场景，synthetic %d 张出题）" % n_syn, "",
              "总题数：%d" % n4, "", "| 题型 | 题数 | 正例(一致/手写) | 负例 | 负例占比 |", "|---|---|---|---|---|"]
    for qt in ("seal_party_open", "seal_party_named", "sig_rep_match", "sig_handwritten"):
        n, pos, neg = qstat(qt)
        lines.append("| %s | %d | %d | %d | %.1f%% |" % (qt, n, pos, neg, 100.0 * neg / max(1, n)))
    neg_all = sum(1 for r in t4 if r["answer"] in ("不一致", "打印"))
    lines += ["", "T4 负例总占比：%.1f%%（%d/%d）" % (100.0 * neg_all / max(1, n4), neg_all, n4), "",
              "平衡子集 T4_balanced.jsonl：%d 题（每题型正例下采样至负例数，负例全保留）" % len(balanced), "",
              "## T4-real 真实图一致性核查（银标准，双通道共识标注）", "",
              "- 题数：%d（其中 负例[不一致/打印] %d）" % (len(t4r), sum(1 for r in t4r if r["answer"] in ("不一致", "打印"))),
              "- 标注来源：两轮独立多模态提取的字段级共识；分歧项见 metadata/annotate/real_t4_conflicts.jsonl", "",
              "## T1/T2 整图任务（附带）", "",
              "- T1 真章/假章：%d 题（realweb 102 全为真章，作为误报率考察）" % sum(1 for r in t12 if r["task"] == "T1"),
              "- T2 三分类：%d 题（含 27 张未盖章）" % sum(1 for r in t12 if r["task"] == "T2"), "",
              "## 说明", "",
              "- T4 仅覆盖 synthetic（其余子集无章面/签名真值，无法自动出题）",
              "- 评分建议：分别报告正例准确率与负例召回（负例召回 = 抓假能力），并给出平衡子集指标",
              "- 平衡子集：正例随机下采样至负例数（种子 20261025）"]
    with open(os.path.join(EVAL, "splits_stats.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # ---------- 提示词模板 ----------
    tmpl = """# 评测提示词模板（中文）

统一约定：要求模型只输出 JSON，便于解析评分。
system: 你是合同用章审核助手，只输出 JSON，不要输出其他内容。

## T4 一致性核查（主场景）

user: {question}
请从以下选项中选择唯一答案，输出：{"answer": "<选项原文>"}

可选加问（诊断用，答案不计分）：
输出格式：{"answer": "<选项原文>", "evidence": "<你作出判断的依据，30字内>"}

## T1 整图二分类
user: 这张合同图片上的公章是真章还是假章？
输出：{"answer": "真章"} 或 {"answer": "假章"}

## T2 整图三分类
user: 判断这张合同图片的用章状态：真章 / 假章 / 未盖章。
输出：{"answer": "真章" | "假章" | "未盖章"}

## 评分规则
- 解析模型输出 JSON，answer 与标注 answer 严格相等计 1 分，否则 0 分
- JSON 解析失败计 0 分并记入 parse_error（单独统计，用于衡量指令遵循）
- T4 按题型分别汇总：正例准确率、负例召回率（抓假能力）、宏平均
- 建议同时报告 named/open 两个变体：named 只考章面 OCR，open 考完整核对链路
"""
    with open(os.path.join(EVAL, "prompt_templates.md"), "w", encoding="utf-8") as f:
        f.write(tmpl)

    print("T4 questions:", len(t4))
    print("T1/T2 questions:", len(t12))


if __name__ == "__main__":
    main()
