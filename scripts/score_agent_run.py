# -*- coding: utf-8 -*-
"""对照金标准给 agent 考生的作答评分，输出 eval/agent_runs/report.md"""
import glob
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(BASE, "eval", "agent_runs")
POS_ANS = {"seal_party_open": "一致", "seal_party_named": "一致",
           "sig_rep_match": "一致", "sig_handwritten": "手写",
           "T1": "真章"}
QT_NAMES = {"seal_party_open": "章面↔主体（开放式）",
            "seal_party_named": "章面↔主体（点名式）",
            "sig_rep_match": "签名↔法代一致",
            "sig_handwritten": "签名手写/打印",
            "T1": "整图真假（T1）",
            "T2": "整图三分类（T2）"}


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def edit_distance(a, b):
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


def norm_txt(s):
    if not s:
        return ""
    s = s.strip().replace(" ", "").replace("\u3000", "")
    return s.replace("（", "(").replace("）", ")")


def main():
    gold = {}
    for f in ("T4_consistency.jsonl", "T4_real.jsonl", "T1T2_doc.jsonl"):
        for r in read_jsonl(os.path.join(BASE, "eval", f)):
            gold[r["task_id"]] = r
    ext_gold = read_jsonl(os.path.join(BASE, "eval", "T4_extract.jsonl"))

    subset_map = {}
    for r in read_jsonl(os.path.join(BASE, "metadata", "manifest.jsonl")):
        subset_map[os.path.basename(r["file"])] = r["subset"]

    def subset_of(path):
        return subset_map.get(os.path.basename(path), "?")

    preds = {}
    for p in glob.glob(os.path.join(RUNS, "**", "predictions_batch_*.jsonl"), recursive=True):
        for r in read_jsonl(p):
            preds[r["task_id"]] = r["answer"]

    missing = [tid for tid in gold if tid not in preds]
    # T4-ext 为后加的开放作答题型，若本次基线未覆盖则不计入缺失
    if not any(t.startswith("t4x-") for t in preds):
        missing = [t for t in missing if not t.startswith("t4x-")]
    extra = [tid for tid in preds if tid not in gold and not tid.startswith("t4x-")]
    rows = []
    for tid, g in gold.items():
        if tid not in preds:
            continue
        ans = preds[tid]
        task = g.get("task", "")
        qt = g.get("qtype") or task
        if task == "T4_real":
            layer = "real"
        elif task in ("T1", "T2"):
            layer = "doc"
        else:
            layer = "gold"
        rows.append({"task_id": tid, "qtype": qt, "task": task, "layer": layer,
                     "subset": subset_of(g.get("image", "")),
                     "gold": g["answer"], "pred": ans, "correct": ans == g["answer"],
                     "image": g["image"]})

    def metrics(rs):
        n = len(rs)
        if n == 0:
            return None
        acc = sum(1 for r in rs if r["correct"]) / n
        return acc, n

    lines = ["# T4 Agent 考试报告", "",
             "- 考生：iCode 平台子代理（底层多模态模型 + agent 框架）",
             "- 闭卷：仅见图与题干，选项受限；无跳过",
             "- 应答 %d 题，实答 %d 题，缺失 %d，多余 %d" % (len(gold), len(rows), len(missing), len(extra)), ""]
    if missing:
        lines += ["缺失 task_id：", " ".join(missing[:20]), ""]
    if extra:
        lines += ["多余 task_id：", " ".join(extra[:20]), ""]

    for layer, title in (("gold", "T4 金标准（synthetic，构造真值）"),
                         ("real", "T4-real 银标准（真实照片，双通道共识+人工复核）"),
                         ("doc", "整图任务 T1/T2（按子集切片）")):
        rs = [r for r in rows if r["layer"] == layer]
        if not rs:
            continue
        m = metrics(rs)
        correct_n = round(m[0] * m[1])
        lines += ["## %s" % title, "",
                  "- 总准确率：**%.1f%%**（%d/%d）" % (100 * m[0], correct_n, m[1]), ""]
        if layer == "doc":
            gr = {}
            for r in rs:
                gr.setdefault((r["task"], r["subset"]), []).append(r)
            lines += ["| 分组 | 题数 | 准确率 | 真章题正确 | 假章题答对(抓假) | 未盖章题答对 |", "|---|---|---|---|---|---|"]
            for (task, sub), qs in sorted(gr.items()):
                acc = 100 * sum(1 for r in qs if r["correct"]) / len(qs)
                zhen = [r for r in qs if r["gold"] == "真章"]
                jia = [r for r in qs if r["gold"] == "假章"]
                wu = [r for r in qs if r["gold"] == "未盖章"]
                zacc = 100 * sum(1 for r in zhen if r["correct"]) / len(zhen) if zhen else float("nan")
                jacc = 100 * sum(1 for r in jia if r["correct"]) / len(jia) if jia else float("nan")
                wacc = 100 * sum(1 for r in wu if r["correct"]) / len(wu) if wu else float("nan")
                lines.append("| %s / %s | %d | %.1f%% | %s | %s | %s |" % (
                    task, sub, len(qs), acc,
                    ("%.1f%%" % zacc) if zhen else "-", ("%.1f%%" % jacc) if jia else "-",
                    ("%.1f%%" % wacc) if wu else "-"))
            lines.append("")
            continue
        lines += ["| 题型 | 题数 | 准确率 | 正例准确率 | 负例召回（抓假）| 负例精确率 | 负例F1 | 负例漏检数 |", "|---|---|---|---|---|---|---|---|"]
        for qt in ("seal_party_open", "seal_party_named", "sig_rep_match", "sig_handwritten"):
            qs = [r for r in rs if r["qtype"] == qt]
            if not qs:
                continue
            pos_ans = POS_ANS[qt]
            pos = [r for r in qs if r["gold"] == pos_ans]
            neg = [r for r in qs if r["gold"] != pos_ans]
            acc = 100 * sum(1 for r in qs if r["correct"]) / len(qs)
            pacc = 100 * sum(1 for r in pos if r["correct"]) / len(pos) if pos else float("nan")
            nrec = 100 * sum(1 for r in neg if r["correct"]) / len(neg) if neg else float("nan")
            miss = sum(1 for r in neg if not r["correct"])
            pred_neg = [r for r in qs if r["pred"] != pos_ans]
            nprec = 100 * sum(1 for r in pred_neg if r["gold"] != pos_ans) / len(pred_neg) if pred_neg else float("nan")
            f1 = (2 * nprec * nrec / (nprec + nrec)) if (neg and pred_neg and nprec + nrec > 0) else float("nan")
            lines.append("| %s | %d | %.1f%% | %s | %s | %s | %s | %d |" % (
                QT_NAMES[qt], len(qs), acc,
                ("%.1f%%" % pacc) if pos else "-", ("%.1f%%" % nrec) if neg else "-",
                ("%.1f%%" % nprec) if pred_neg else "-", ("%.1f%%" % f1) if pred_neg and neg else "-", miss))
        # 负例漏检明细（错成"一致/手写"的）
        pos_ans_all = ("一致", "手写")
        misses = [r for r in rs if not r["correct"] and r["gold"] in ("不一致", "打印")]
        if misses:
            lines += ["", "把假判成真/把打印判成手写的漏检（前 15 条）：",
                      "| task_id | 图片 | 题型 | 标准答案 | 考生答案 |", "|---|---|---|---|---|"]
            for r in misses[:15]:
                lines.append("| %s | %s | %s | %s | %s |" % (r["task_id"], os.path.basename(r["image"]),
                                                             QT_NAMES.get(r["qtype"], r["qtype"]), r["gold"], r["pred"]))
        lines.append("")

        # 图级聚合（辅助口径）：同一张图的全部题目都答对才算"图对"
        imgs = {}
        for r in rs:
            imgs.setdefault(r["image"], []).append(r)
        img_ok = sum(1 for v in imgs.values() if all(x["correct"] for x in v))
        lines.append("- 图级严格准确率（图内全对才算审对）：%d/%d = %.1f%%" %
                     (img_ok, len(imgs), 100.0 * img_ok / len(imgs)))
        neg_imgs = {k: v for k, v in imgs.items()
                    if any(x["gold"] != POS_ANS.get(x["qtype"], "一致") for x in v)}
        if neg_imgs:
            neg_hit = sum(1 for v in neg_imgs.values()
                          if all(x["correct"] for x in v if x["gold"] != POS_ANS.get(x["qtype"], "一致")))
            lines.append("- 含负例图的负例全抓率（该图负例题全对的比例）：%d/%d = %.1f%%" %
                         (neg_hit, len(neg_imgs), 100.0 * neg_hit / len(neg_imgs)))
        lines.append("")

    # T4-ext 开放作答评分（编辑距离）
    if any(t.startswith("t4x-") for t in preds):
        ex_rows = []
        for g in ext_gold:
            tid = g["task_id"]
            if tid not in preds:
                continue
            p, go = norm_txt(preds[tid]), norm_txt(g["answer"])
            ed = edit_distance(p, go)
            ex_rows.append({"task_id": tid, "ed": ed, "exact": ed == 0, "near": ed <= 2,
                            "image": g["image"], "gold": g["answer"], "pred": preds[tid]})
        if ex_rows:
            n = len(ex_rows)
            exact = sum(1 for r in ex_rows if r["exact"])
            near = sum(1 for r in ex_rows if r["near"])
            mean_ed = sum(r["ed"] for r in ex_rows) / n
            lines += ["## T4-ext 章面文字提取（开放作答，编辑距离评分）", "",
                      "- 题数：%d" % n,
                      "- 精确匹配率：**%.1f%%**" % (100.0 * exact / n),
                      "- 近似匹配率（编辑距离≤2）：**%.1f%%**" % (100.0 * near / n),
                      "- 平均编辑距离：%.2f" % mean_ed,
                      "- 完全错误（ED>5）：%d 题" % sum(1 for r in ex_rows if r["ed"] > 5), "",
                      "| task_id | 图片 | 标准名称 | 考生输出 | ED |", "|---|---|---|---|---|"]
            for r in sorted(ex_rows, key=lambda x: -x["ed"])[:10]:
                lines.append("| %s | %s | %s | %s | %d |" % (r["task_id"], os.path.basename(r["image"]),
                                                             r["gold"], r["pred"], r["ed"]))
            lines.append("")

    with open(os.path.join(RUNS, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
