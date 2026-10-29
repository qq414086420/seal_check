# -*- coding: utf-8 -*-
"""生成 agent 考生批次文件（v0.4 全量模式）：
合并 T4_consistency + T4_real + T1T2_doc 全部题目，按图分组，
每图一次考试（回答该图全部子题），剔除 answer/evidence 防泄题。
输出 eval/agent_runs/full/full_batch_N_questions.jsonl
每行：{"image": "...", "questions": [{"task_id","qtype","question","choices"}, ...]}
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(BASE, "eval")
EXT_ONLY = "--ext-only" in sys.argv
OUT = os.path.join(EVAL, "agent_runs", "ext" if EXT_ONLY else "full")
PER_BATCH = 70


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def main():
    if EXT_ONLY:
        files = ["T4_extract.jsonl"]
    else:
        files = ["T4_consistency.jsonl", "T4_real.jsonl", "T4_extract.jsonl", "T1T2_doc.jsonl"]
    questions = []
    for f in files:
        for q in read_jsonl(os.path.join(EVAL, f)):
            img = q.get("image") or q.get("file")
            questions.append({
                "image": img,
                "task_id": q["task_id"], "task": q.get("task", ""),
                "qtype": q.get("qtype") or q.get("task"),
                "question": q["question"], "choices": q["choices"],
            })
    groups = {}
    for q in questions:
        img = q.get("image") or q.get("file")
        groups.setdefault(img, []).append(q)
    items = sorted(groups.items())
    os.makedirs(OUT, exist_ok=True)
    n_batch = 0
    total = 0
    for i in range(0, len(items), PER_BATCH):
        n_batch += 1
        path = os.path.join(OUT, "full_batch_%d_questions.jsonl" % n_batch)
        cnt = 0
        with open(path, "w", encoding="utf-8") as f:
            for img, qs in items[i:i + PER_BATCH]:
                f.write(json.dumps({"image": img, "questions": qs}, ensure_ascii=False) + "\n")
                cnt += len(qs)
                total += len(qs)
    print("images: %d -> %d batches (per %d images), questions: %d" % (len(items), n_batch, PER_BATCH, total))


if __name__ == "__main__":
    main()
