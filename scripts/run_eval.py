# -*- coding: utf-8 -*-
"""SealBench 评测跑分脚本（OpenAI 兼容接口，多模态）。
用法示例：
  uv run --with pillow python scripts/run_eval.py \
    --eval-file eval/T4_balanced.jsonl --model gpt-4o \
    --base-url https://api.openai.com/v1 --api-key sk-xxx --limit 20

特性：
- 图片本地 base64 编码（data URL），不依赖外链
- 并发 + 断点续跑（predictions.jsonl 已有 task_id 自动跳过）
- --dry-run 只打印请求结构不调用 API
- 结束自动输出 report.md（分题型：准确率/正例准确率/负例召回/解析失败率）
"""
import argparse
import base64
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from build_eval import read_jsonl  # noqa: E402

POS_ANS = {"seal_party_open": "一致", "seal_party_named": "一致",
           "sig_rep_match": "一致", "sig_handwritten": "手写"}
SYSTEM_PROMPT = ("你是合同用章审核助手。请根据图片严格作答，"
                 "只输出 JSON：{\"answer\": \"<选项原文>\"}，不要输出任何其他内容。")


def encode_image(rel_path):
    p = os.path.join(BASE, rel_path.replace("/", os.sep))
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(p)[1].lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return "data:image/%s;base64,%s" % (mime, b64)


def build_messages(item):
    text = item["question"] + "\n可选项：%s\n请从可选项中选择唯一答案，输出 JSON。" % " / ".join(item["choices"])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": encode_image(item["image"])}},
        ]},
    ]


def call_api(base_url, api_key, model, messages, timeout=180):
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "messages": messages, "temperature": 0}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % api_key,
    })
    last_err = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            return d["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            time.sleep(3)
    return "__ERROR__:%s" % last_err


def parse_answer(raw, choices):
    """从模型输出解析选项；返回 (answer 或 None, is_parse_error)。"""
    if raw.startswith("__ERROR__"):
        return None, True
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            ans = json.loads(m.group(0)).get("answer")
            if ans in choices:
                return ans, False
        except Exception:
            pass
    for ch in choices:
        if ch in raw:
            return ch, False
    return None, True


def group_key(item):
    return item.get("qtype") or item.get("task") or "unknown"


def score(rows):
    groups = {}
    for r in rows:
        groups.setdefault(group_key(r), []).append(r)
    lines = ["# SealBench 跑分报告", "",
             "- 模型：%s" % rows[0].get("model", "?") if rows else "# empty",
             "- 样本数：%d；解析失败：%d" % (len(rows), sum(1 for r in rows if r.get("parse_error"))), ""]
    for g, rs in sorted(groups.items()):
        n = len(rs)
        acc = sum(1 for r in rs if r["correct"]) / n
        out = ["## %s" % g, "- 题数：%d" % n, "- 准确率：%.1f%%" % (100 * acc)]
        pos_ans = POS_ANS.get(g)
        if pos_ans:
            pos = [r for r in rs if r["answer_gold"] == pos_ans]
            neg = [r for r in rs if r["answer_gold"] != pos_ans]
            if pos:
                out.append("- 正例准确率（%s）：%.1f%%" % (pos_ans, 100 * sum(1 for r in pos if r["correct"]) / len(pos)))
            if neg:
                out.append("- 负例召回（抓假能力）：%.1f%%" % (100 * sum(1 for r in neg if r["correct"]) / len(neg)))
            pred_neg = [r for r in rs if r["answer_model"] != pos_ans]
            if pred_neg:
                nprec = 100 * sum(1 for r in pred_neg if r["answer_gold"] != pos_ans) / len(pred_neg)
                out.append("- 负例精确率（报警准确率）：%.1f%%" % nprec)
                nrec = 100 * sum(1 for r in neg if r["correct"]) / len(neg) if neg else 0
                if nprec + nrec > 0:
                    out.append("- 负例 F1：%.1f%%" % (2 * nprec * nrec / (nprec + nrec)))
        if g == "T1":
            fp = sum(1 for r in rs if r["answer"] == "真章" and r["answer_gold"] == "假章")
            out.append("- 把假章判成真章（漏检）：%d" % fp)
        lines += out + [""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-file", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0=全部）")
    ap.add_argument("--out", default=None, help="输出目录（默认 runs/<model>/<文件名>）")
    ap.add_argument("--dry-run", type=int, default=0, help="只打印前 N 条请求结构，不调用 API")
    args = ap.parse_args()

    items = read_jsonl(os.path.join(BASE, args.eval_file))
    if args.limit:
        items = items[: args.limit]
    tag = os.path.splitext(os.path.basename(args.eval_file))[0]
    out_dir = args.out or os.path.join(BASE, "runs", re.sub(r"[^\w.-]", "_", args.model), tag)
    os.makedirs(out_dir, exist_ok=True)
    pred_path = os.path.join(out_dir, "predictions.jsonl")

    done = set()
    if os.path.exists(pred_path):
        for r in read_jsonl(pred_path):
            done.add(r["task_id"])
    todo = [it for it in items if it["task_id"] not in done]
    print("total=%d done=%d todo=%d -> %s" % (len(items), len(done), len(todo), pred_path))

    if args.dry_run:
        for it in items[: args.dry_run]:
            msgs = build_messages(it)
            slim = [{"role": m["role"], "content": (m["content"] if isinstance(m["content"], str)
                     else [c if c["type"] == "text" else {"type": "image_url", "image_url": {"url": "<base64 %dKB>" % (len(c["image_url"]["url"]) // 1024)}} for c in m["content"]])}
                    for m in msgs]
            print(json.dumps({"task_id": it["task_id"], "messages": slim}, ensure_ascii=False, indent=1))
        return

    if not args.api_key:
        print("缺少 --api-key（或环境变量 OPENAI_API_KEY）")
        sys.exit(1)

    lock = threading.Lock()
    fout = open(pred_path, "a", encoding="utf-8")

    def work(it):
        raw = call_api(args.base_url, args.api_key, args.model, build_messages(it))
        ans, perr = parse_answer(raw, it["choices"])
        rec = {"task_id": it["task_id"], "model": args.model,
               "image": it["image"], "question": it["question"],
               "answer_gold": it["answer"], "answer_model": ans, "raw": raw[:300],
               "parse_error": perr,
               "correct": (ans == it["answer"]),
               "group": group_key(it)}
        with lock:
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(work, it): it for it in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            fut.result()
            if i % 25 == 0 or i == len(todo):
                print("progress %d/%d (%.0fs)" % (i, len(todo), time.time() - t0), flush=True)
    fout.close()

    rows = read_jsonl(pred_path)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(score(rows))
    print("done. report ->", os.path.join(out_dir, "report.md"))


if __name__ == "__main__":
    main()
