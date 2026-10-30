# -*- coding: utf-8 -*-
"""为当前 gold 中尚无有效作答的 T4-ext 题目生成补充试卷。
用法：python make_ext_supplement.py <作答文件1> [作答文件2 ...] <输出批前缀>
排除已有作答的 task_id，按图分组输出 eval/agent_runs/ext/<前缀>_batch_N.jsonl
"""
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("用法: make_ext_supplement.py <作答文件...> <输出前缀>")
        sys.exit(1)
    out_prefix = args[-1]
    answered = set()
    for p in args[:-1]:
        for r in read_jsonl(p):
            answered.add(r["task_id"])
    gold = read_jsonl(os.path.join(BASE, "eval", "T4_extract.jsonl"))
    unanswered = [q for q in gold if q["task_id"] not in answered]
    groups = {}
    for q in unanswered:
        groups.setdefault(q["image"], []).append(
            {"task_id": q["task_id"], "qtype": q["qtype"],
             "question": q["question"], "choices": q["choices"]})
    items = sorted(groups.items())
    out_dir = os.path.join(BASE, "eval", "agent_runs", "ext")
    n = 0
    for i in range(0, len(items), 70):
        n += 1
        with open(os.path.join(out_dir, "%s_batch_%d.jsonl" % (out_prefix, n)), "w", encoding="utf-8") as f:
            for img, qs in items[i:i + 70]:
                f.write(json.dumps({"image": img, "questions": qs}, ensure_ascii=False) + "\n")
    print("未作答题: %d | 图片: %d | 批次: %d (前缀 %s_batch_N)" % (len(unanswered), len(items), n, out_prefix))


if __name__ == "__main__":
    main()
