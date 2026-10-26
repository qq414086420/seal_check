# SealBench 评测使用指导

## 0. 目录里有什么

| 文件 | 用途 |
|---|---|
| `T4_consistency.jsonl` | T4 金标准全量 2604 题（合成图，最终榜单用） |
| `T4_balanced.jsonl` | **T4 平衡子集 652 题（推荐首选跑这个）**，正负例按题型配平 |
| `T4_real.jsonl` | 真实照片银标准 35 题（考真实场景提取链路） |
| `T1T2_doc.jsonl` | 整图真假/三分类 1175 题（附带） |
| `prompt_templates.md` | 题型与评分口径说明 |
| `splits_stats.md` | 各题型正负例分布 |

每条记录：`task_id / image(相对路径) / question / choices / answer / evidence`。
**注意：`answer` 和 `evidence` 是评分用字段，发送给模型时必须剔除**（`run_eval.py` 已处理）。

## 1. 方式一：脚本一键跑分（推荐）

前置：任意 OpenAI 兼容的多模态接口（vLLM/Ollama/OpenAI/各云厂商均可），能访问图片所用的模型需支持 vision。

```powershell
# 先 dry-run 检查请求构造（不花钱）
uv run --with pillow python scripts/run_eval.py --eval-file eval/T4_balanced.jsonl `
  --model <模型名> --base-url <接口地址>/v1 --api-key <KEY> --dry-run 2

# 小批量试跑 20 题
uv run --with pillow python scripts/run_eval.py --eval-file eval/T4_balanced.jsonl `
  --model <模型名> --base-url <接口地址>/v1 --api-key <KEY> --limit 20

# 全量跑（可中断，重跑同一命令自动断点续跑）
uv run --with pillow python scripts/run_eval.py --eval-file eval/T4_balanced.jsonl `
  --model <模型名> --base-url <接口地址>/v1 --api-key <KEY> --concurrency 8
```

参数说明：
- `--eval-file`：评测集文件（相对 seal-bench 根目录）
- `--limit N`：只跑前 N 题；`--concurrency`：并发数（本地 vLLM 建议 4-8，云 API 按限额定）
- `--out`：输出目录，默认 `runs/<模型名>/<评测集名>/`
- 环境变量 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 可代替命令行参数

输出：
- `predictions.jsonl`：逐题预测（含模型原文、是否解析失败、对错）→ 断点续跑依据
- `report.md`：自动汇总——按题型的准确率、**正例准确率**、**负例召回（抓假能力）**、解析失败数

## 2. 方式二：手动喂给网页版模型（抽查用）

1. 从 JSONL 挑一条记录（每行一个 JSON），取 `image` 字段对应的图片文件
2. 把图片拖进对话框，连同下面模板一起发送（`{question}`、`{choices}` 用记录里的值替换）：

   > 请根据图片严格作答，只输出 JSON：{"answer": "<选项原文>"}，不要输出任何其他内容。
   > {question}
   > 可选项：{choices 用 " / " 连接}

3. 模型回复的 `answer` 与记录里的 `answer` 字段对照，一致=答对
4. 手动抽查建议每题型各看 3-5 条（含负例），快速感受难度；正式数字以脚本跑分为准

## 3. 评分口径

- **解析**：模型输出中的 JSON `answer` 必须与 `choices` 之一严格相等；解析失败计 `parse_error`（单列统计，衡量指令遵循，不算错答也不算对）
- **T4 分题型报告两个数**：
  - 正例准确率（answer=一致/手写 的题上答对的比例）
  - **负例召回**（answer=不一致/打印 的题上答对的比例，即"抓假能力"——业务上最重要的指标）
- **T1** 额外看混淆方向：把假章判成真章（漏检）比误报严重得多
- 全量 T4 负例仅占 12.5%，"永远答一致"就能拿 87.5%——**结论请以 T4_balanced 或分项的正/负例指标为准**，不要只看总准确率

## 4. 成本参考

每题 1 次调用 = 1 张 A4 图（约 1000~1600 视觉 token，按各厂商规则折算）+ 约 200 文本 token。
T4_balanced 652 题约 652 次调用；全量 T4 2604 次。可用 `--limit` 先试跑估算单价。

## 5. 常见问题

- **中断了怎么办**：直接重跑同一条命令，已完成的 task_id 自动跳过
- **换模型对比**：改 `--model`，结果自动存到各自 `runs/<模型名>/` 下，report 可横向对比
- **想加新题型/改题干**：改 `scripts/build_eval.py` 后重新生成，旧 predictions 与新题 version 不混用（建议清空对应 runs 目录）
- **图片路径**：JSONL 中是相对 seal-bench 根目录的路径，评测脚本需以该根目录为基准解析（run_eval.py 已处理）
