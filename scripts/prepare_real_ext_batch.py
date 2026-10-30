# -*- coding: utf-8 -*-
"""生成真实图提取题专用批次（当前 gold 对齐版）：仅 data/real 图片的 T4-ext 题目。"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "eval", "agent_runs", "real_ext")
PER_BATCH = 60


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def main():
    qs = read_jsonl(os.path.join(BASE, "eval", "T4_extract.jsonl"))
    real = [q for q in qs if q["image"].startswith("data/real")]
    groups = {}
    for q in real:
        groups.setdefault(q["image"], []).append(
            {"task_id": q["task_id"], "qtype": q["qtype"],
             "question": q["question"], "choices": q["choices"]})
    items = sorted(groups.items())
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for i in range(0, len(items), PER_BATCH):
        n += 1
        with open(os.path.join(OUT, "real_ext_batch_%d.jsonl" % n), "w", encoding="utf-8") as f:
            for img, question_list in items[i:i + PER_BATCH]:
                f.write(json.dumps({"image": img, "questions": question_list}, ensure_ascii=False) + "\n")
    print("real ext questions: %d | images: %d | batches: %d" % (len(real), len(items), n))


if __name__ == "__main__":
    main()
