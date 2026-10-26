# SealBench v0.4 测试集打包说明

## 包内容

解压后得到以下目录/文件（解压到同一目录即可还原完整结构）：

| 路径 | 内容 |
|---|---|
| `README.md` | 数据集总说明：子集构成、标签口径、来源与许可、已知局限 |
| `PACKAGE_INFO.md` | 本文件 |
| `data/real/` | **102 张**真实合同照片（三轮网络采集 + 多模态逐张审核，全部为"现代中文合同+红色公章"真章样本） |
| `data/synthetic/` | **496 张**全合成中文合同（程序生成，账本式标注，负例可控） |
| `data/forged_real/` | **184 张**真实域伪造（真实底图 + DocDiff/DocBank 真实红章移植，`paste_bboxes` 记录贴章位置） |
| `data/hold/` | 2 张待定商务单据（未入评测） |
| `metadata/manifest.jsonl` | **统一标注清单（758 条）**——每张图一行：label（genuine/forged/no_seal）、label_confidence、forgery_types、quality_mode、seal_detail[]（每枚章的真值）、signature_detail[]（每个签名的真值）、red_bbox 等 |
| `metadata/realweb_labels.jsonl` | 真实图标签（与合成账本同构格式） |
| `metadata/annotate/` | 真实图双通道提取标注、共识、分歧复核、人工复核记录 |
| `metadata/excluded_manifest.jsonl` | 清洗剔除记录（原因可追溯） |
| `manifests/` | 各子集采集层原始清单（URL/查询词等溯源信息） |
| `eval/` | **评测题与报表**：T4_consistency.jsonl（3824 题）、T4_balanced.jsonl（1632 题配平版）、T4_real.jsonl（63 题）、T1T2_doc.jsonl（1480 题）、DESIGN.md（评测设计）、USAGE.md（**测试方法与使用指导**）、prompt_templates.md（提示词模板）、splits_stats.md（正负例统计）、agent_runs/report.md（基线成绩单） |
| `scripts/` | 全部生成/出题/评分脚本（可复现，随机种子固定） |
| `reports/` | 统计与抽查图 |

## 测试方法（详见 eval/USAGE.md）

1. 每条评测记录 = 一张图 + 一道封闭选择题（选项见 `choices`，标准答案见 `answer`）
2. 把图片（base64 或文件）与题干发给被测多模态模型，要求只回 `{"answer":"<选项原文>"}`
3. 与 `answer` 严格比对计分；解析失败计 `parse_error` 单列
4. 指标：分题型的总准确率、正例准确率、**负例召回（抓假）**、负例精确率、负例 F1；另附图级严格口径（图内全对才算审对）

## 数据标注说明

- **合成图（496）**：账本式标注——生成前先抽"作弊方案"（44% 一侧造假 / 图级分布见 README），画图照账执行，所以 `seal_detail[].company`（章面实际刻名）、`matches_party`、`forgery_types`（13 种手法）与图**构造性一致**，标签绝对可信
- **真实图（102）**：三轮采集 → 多模态逐张审核（只保留"现代中文合同+红色公章"）→ 图级标签 `genuine (reviewed)`；其中 22 张要素可读者另有双通道共识提取的要素级标注（party/章面名/签名），**T4-real 全为正例，只测误报率**
- **移植伪造（184）**：真实底图 + 真实红章抠图合成，`target_file` 指向真本底图（支持一真一假配对评测）

## 基线成绩（iCode 平台底层多模态模型 + agent 框架，闭卷）

| 数据层 | 题数 | 总准确率 | 关键分项 |
|---|---|---|---|
| T4 金标准（合成 496 图） | 3824 | 87.9% | 章面比对抓假 72.2%；签名↔法代抓假 97.0%；手写/打印抓假 65.2%（精确率仅 37.1%，报警过激） |
| T4-real 银标准（真实 26 图） | 63 | 95.2% | 全正例，只测误报（误报 4.8%） |
| T1 真假（782 图） | 746 | — | synthetic 抓假 67.8%；transplant 抓假 73.9%；realweb 误报 1% |
| T2 三分类（782 图） | 782 | — | 未盖章识别 100%；其余同 T1 |
| 图级严格口径（合成） | 496 图 | 48.8% | 图内全对才算审对 |

完整成绩单见 `eval/agent_runs/report.md`，逐题作答见 `eval/agent_runs/full/predictions_batch_*.jsonl`。

## 用途与合规

仅用于印章真伪检测/反欺诈算法的研究与评测。请勿将本仓库中的伪造方法或样本用于任何伪造印章、伪造文书的违法行为。
