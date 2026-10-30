# -*- coding: utf-8 -*-
"""生成真实图提取结果的人工审核页面（HTML）。
输出 review_real_ext.html 到仓库根目录（与 data\ 同级，保证图片相对路径可用）。
审核方式：默认每条"正确"，发现识别错误改为"错误"并可填备注；点页面底部按钮导出
reviewed_real_ext.jsonl，发回后由 build_real_labels 的人工复核覆盖层吸收。
"""
import glob
import html
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def glob_pred_files():
    d = os.path.join(BASE, "eval", "agent_runs", "real_ext")
    return glob.glob(os.path.join(d, "predictions_*.jsonl"))


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


QT_LABEL = {"seal_text_extract": "印章章面名称", "party_text_extract": "合同主体名称",
            "legal_rep_extract": "法定代表人姓名", "sig_name_extract": "签名姓名"}
CONF_LABEL = {"consensus": "双通道一致", "single_pass": "单通道读取",
              "conflict_near": "双通道近似分歧(≤3字)", "conflict_far": "双通道重大分歧",
              "manual_review": "人工复核豁免(联合体)"}


def main():
    ext = read_jsonl(os.path.join(BASE, "eval", "T4_extract.jsonl"))
    preds = {}
    for p in glob_pred_files():
        for r in read_jsonl(p):
            preds[r["task_id"]] = r["answer"]

    real = [r for r in ext if r["image"].startswith("data/real")]
    groups = {}
    for q in real:
        model_ans = preds.get(q["task_id"], "（无作答）")
        groups.setdefault(q["image"], []).append((q, model_ans))

    cards = []
    for idx, (img, items) in enumerate(sorted(groups.items()), 1):
        rel = html.escape(img)
        cards.append('<div class="imgblock" id="img%d">' % idx)
        cards.append('<h3>%d. %s</h3>' % (idx, html.escape(os.path.basename(img))))
        cards.append('<img src="%s" style="max-width:820px;border:1px solid #ccc">' % rel)
        for q, model_ans in items:
            meta = q.get("meta") or {}
            conf = CONF_LABEL.get(meta.get("gold_confidence"), meta.get("gold_confidence", ""))
            ev = q.get("evidence") or {}
            tid = html.escape(q["task_id"])
            cards.append('<div class="card" data-tid="%s">' % tid)
            cards.append('<div class="qh">[%s] 审核项：%s</div>' % (tid, QT_LABEL.get(q["qtype"], q["qtype"])))
            cards.append('<div class="qq">%s</div>' % html.escape(q["question"]))
            cards.append('<div class="qa">模型识别：<b class="ans">%s</b></div>' % html.escape(str(model_ans)))
            cards.append('<details><summary>参考（双通道共识标注，仅供复核）</summary>'
                         '<div class="gold">标注参考：%s ｜ 标注置信：%s</div></details>' % (
                             html.escape(str(q["answer"])), html.escape(conf)))
            cards.append('<div class="judge">判定：'
                         '<label><input type="radio" name="%s" value="正确" checked>正确</label> '
                         '<label><input type="radio" name="%s" value="错误">错误</label> '
                         '备注：<input type="text" class="note" data-tid="%s" placeholder="错误原因/正确内容（可选）">'
                         '</div>' % (tid, tid, tid))
            cards.append('</div>')
        cards.append('</div>')

    n_items = sum(len(v) for v in groups.values())
    page = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>SealBench 真实图提取结果人工审核</title>
<style>
body{font-family:"Microsoft YaHei",sans-serif;margin:20px;max-width:900px}
h3{background:#eef;padding:6px 10px;border-left:4px solid #36c}
.card{border:1px solid #ddd;border-radius:6px;padding:10px;margin:10px 0;background:#fafafa}
.qh{color:#36c;font-weight:bold}
.qq{color:#333;margin:4px 0}
.qa{margin:6px 0}
.ans{color:#c00;font-size:1.05em}
.gold{color:#060;background:#e8f5e9;padding:4px;border-radius:4px}
.judge{margin-top:6px}
.judge label{margin-right:12px}
.judge input[type=text]{width:420px}
#bar{position:fixed;top:0;left:0;right:0;background:#222;color:#fff;padding:10px;z-index:9}
#bar button{padding:6px 14px;margin-right:10px}
details{margin:4px 0}
</style></head><body>
<div id="bar">
  共 %d 张图 / %d 个审核项。
  <button onclick="markAll()">全部标为正确</button>
  <button onclick="exportJSON()">导出审核结果 reviewed_real_ext.jsonl</button>
  <span id="stat"></span>
</div>
<div style="margin-top:60px">
<h2>审核说明</h2>
<ul>
<li>审核对象是<b>模型识别答案</b>（红字）。对照图片判断它读得对不对。</li>
<li>默认全部"正确"——你只需要把<b>识别错误</b>的项改为"错误"，并在备注里写正确内容。</li>
<li>"参考"折叠里是双通道共识标注值（银标准），仅供对照，不作为你对错的依据。</li>
<li>审完点右上角"导出"，把下载的 reviewed_real_ext.jsonl 放到 seal-bench\\metadata\\annotate\\ 目录，通知助手回写重算。</li>
</ul>
</div>
%s
<script>
function markAll(){
  document.querySelectorAll('input[type=radio][value="正确"]').forEach(function(r){r.checked=true});
  stat();
}
function collect(){
  var out=[];
  document.querySelectorAll('.card').forEach(function(c){
    var tid=c.getAttribute('data-tid');
    var sel=c.querySelector('input[type=radio]:checked');
    var note=c.querySelector('.note').value;
    out.push({task_id:tid, verdict: sel? sel.value : '未审核', note: note});
  });
  return out;
}
function exportJSON(){
  var rows=collect();
  var text=rows.map(function(r){return JSON.stringify(r)}).join('\\n');
  var blob=new Blob([text],{type:'application/json'});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='reviewed_real_ext.jsonl';
  a.click();
}
function stat(){
  var r=collect(); var bad=r.filter(function(x){return x.verdict==='错误'}).length;
  document.getElementById('stat').textContent='已标记错误：'+bad+' 条';
}
document.addEventListener('change', stat);
stat();
</script></body></html>""" % (len(groups), n_items, "\n".join(cards))

    out_p = os.path.join(BASE, "review_real_ext.html")
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(page)
    print("审核页面已生成:", out_p)
    print("审核项: %d 个（%d 张图）" % (n_items, len(groups)))


if __name__ == "__main__":
    main()
