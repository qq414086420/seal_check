# SealBench 评测集设计（v1 草案）

> **优先级（2026-10-25 用户确认）：T4 一致性核查为业务主场景，优先建设；T1/T2 附带生成；T3 暂缓。**

基于当前 601 张样本（realweb 102 / synthetic 339 / real_transplant 160），
面向"不同检测方式"设计 4 种任务形态 + 4 个诊断分层。所有标准答案均从构造数据自动导出，零人工标注。

## 一、任务形态

### T1 整图二分类（主任务）
- **问法**：这张合同图片上的公章是真章还是假章？（真章/假章）
- **样本**：label ∈ {genuine, forged} 的整图 ≈ 574 张
  - synthetic 312（真 149 / 假 163）
  - real_transplant 160（全假）
  - realweb 102（全真，作为"真实域误报率"考察，真实域无真伪造样本）
- **指标**：Accuracy / Precision / Recall / F1 / 混淆矩阵；分域报告（synthetic / transplant / wild）

### T2 整图三分类（贴近实务问法）
- **问法**：判断该合同的用章状态：真章 / 假章 / 未盖章
- **样本**：T1 全部 + 27 张 no_seal（未盖章合同页）≈ 601 张
- **意义**：考察"无章"是否被误判为"假章"（实务中高危误报）；报告三类 P/R/F1

### T3 印章裁剪图判断（细粒度，排除版式线索）
- **问法**：这是从文档中裁出的印章区域，判断真章/假章
- **构造**：
  1. 红色 HSV 掩码 + 连通域分析（cv2）提取候选章区域，外扩 15% 裁剪
  2. 标签来源：
     - synthetic：图内章标签一致（同 seal_mode），按甲左乙右位置对应 seal_detail[genuine]
     - realweb：真章
     - real_transplant：贴章区域 = 假；底图自带章 = 真
       - 贴章定位：与 `target_file` 底图做像素差分取变化区域（现有 160 张可反推）
       - 新重建的样本 manifest 已记录 `paste_bboxes`，直接使用
- **价值**：纯考"印章本体验真"能力（纹理/字环/星徽/防伪码），不受版式、文字上下文干扰

### T4 跨要素一致性核查（诊断问答，业务主场景）
双层构造，**统一标签格式**（`metadata/realweb_labels.jsonl` 与 `synthetic_manifest` 同构：
party_a/b、legal_rep_a/b、seals[{company, readable, matches_party, genuine}]、signatures[{name, readable, matches_rep, printed}]），
出题逻辑只吃这一种格式，两种来源无差别：
- **金标准层（synthetic 496 张）**：构造字段即账本，负例充足（party_mismatch/name_altered 等），指标绝对可信
- **银标准层（realweb 102 张真实照片）**：两轮独立多模态提取 → 字段级共识 → 按同一格式落账（可读性门控：读不出的字段置 null 不出题；
  分歧项进人工复核清单）。考"真实照片上的提取+比对全链路"（倾斜/模糊/水印/打码）
- **标注规范补充**：联合体签约（多主体联合盖章）、分支机构/部门章视为与主体**语义一致**，豁免字面差异；
  人工复核通过 `metadata/annotate/manual_review.jsonl` 覆盖机器共识（如 realweb_0564 联合体双章案例）
- **真实图分层用途**：102 张全部参与 T1/T2 误报率考察（图级真章标签）；其中要素可读的 22 张（章面）/8 张（签名）
  额外参与 T4-real 63 题。**T4-real 当前无负例**（保留的正常合同字面均一致），只测误报率，不测抓假
- 两层分别报告，不混算；后续新真实图只需产出同格式标签行即可入评测

从构造/标注字段自动出题，考"逻辑核对"能力而非视觉：
- **Q1 章面单位名 ↔ 合同主体一致性**：`seal_detail.matches_party`（party_mismatch 34 张为负例）
  问法：图中红色公章刻制的单位名称，与合同甲方/乙方名称是否一致？
- **Q2 签名 ↔ 法定代表人一致性**：`signature_detail[].matches_rep`（sig_mismatch 负例）
- **Q3 签名是否为打印体**：`signature_detail[].printed`（sig_printed 负例）
- **指标**：逐问准确率；负例召回（能否发现"冒用他公司章""冒签"）

## 二、诊断分层（所有任务共用的切片维度）

| 维度 | 取值 | 用途 |
|---|---|---|
| 伪造手法 | seal_transplant / party_mismatch / name_altered / name_truncated / missing_star / star_deformed / broken_ring / extra_ring / color_off / text_flip / over_ink / low_quality / distort | 细分手法准确率→定位模型盲区 |
| 成像质量 | clean / scan_skew / photo / fax | 抗退化能力 |
| 难度 | easy=clean 合成 / mid=退化合成 / hard=real_transplant | 能力阶梯 |
| 数据域 | synthetic / real_transplant / realweb(wild) | 域泛化 |

## 三、防泄漏与配对设计

- **成对子集（paired）**：real_transplant 的 `target_file` 指向真本底图 → 同一文档"一真一假"配对。
  评测记录 `pair_group` 字段，支持两种聚合：
  1. 独立模式：所有样本独立计分（常规）
  2. 成对模式：只看同底图真假对的判别是否正确（最能反映辨别力，排除内容难易干扰）
- md5 已去重，无重复图。

## 四、交付物

| 文件 | 内容 |
|---|---|
| `scripts/build_eval.py` | 一键从 manifest 生成以下全部 |
| `eval/T1_main.jsonl` | 整图任务（T1/T2 共用，带 task 字段）|
| `eval/T3_crops/` + `eval/T3_crops.jsonl` | 裁剪章 patch + 标签 |
| `eval/T4_consistency.jsonl` | 一致性问答（含标准答案与依据字段）|
| `eval/splits_stats.md` | 分层统计 |
| `eval/prompt_templates.md` | 四种问法的标准中文提示词 + 输出解析规则（JSON 输出约定）|

每条记录 schema（示例 T1）：
```json
{"task_id":"t1-0001","image":"data/synthetic/syn_00002.jpg","task":"T1",
 "question":"这张合同图片上的公章是真章还是假章？","choices":["真章","假章"],
 "answer":"假章","meta":{"subset":"synthetic","forgery_types":["distort"],"quality_mode":"photo","pair_group":null}}
```

## 五、已知缺口（不影响先建）

1. 真实域"非移植"伪造缺失（如真章翻拍打印、激光刻章）——Seal-4 到货后可扩 transplant；真实假章图源仍稀缺
2. 现有 160 张 transplant 无 paste_bboxes → T3 用底图差分反推；下次重建自动带上
3. 签名维度目前只覆盖 printed/mismatch 两类伪造

## 六、执行顺序建议

1. 确认本设计 → 我写 `build_eval.py` 生成 eval/（约 10 分钟）
2. Seal-4 下载完成后：重建 transplant（带坐标）→ 重跑 build_eval 刷新
3. 需要跑分时：再写 `run_eval.py` 接多模态模型 API（OpenAI 兼容格式），输出分域/分层报表
