# SealBench：中文合同假章检测评测样本集

面向多模态大模型的**中文合同公章真伪识别**能力评测样本集（v0.4，758 张）。
**所有真实图片均经多模态模型逐张审核**，仅保留"现代中文合同/协议文书 + 红色公章"样本；不符合样本移入
`data/excluded/`（原因记录于 `metadata/excluded_manifest.jsonl`），不做删除以便复查。

> 用途声明：本数据集仅用于印章真伪检测/反欺诈算法的**研究与评测**。请勿将本仓库中的伪造方法或样本用于任何伪造印章、伪造文书的违法行为。

## 目录结构

```
seal-bench/
├── data/
│   ├── real/            # 真实图片（realweb_*.jpg 网络采集；commons/ Wikimedia）
│   ├── synthetic/       # 全合成合同页（syn_*.jpg）
│   └── forged_real/     # 真实印章移植伪造（realforge_*.jpg）
├── metadata/
│   ├── manifest.jsonl   # 统一样本清单（评测入口）
│   └── sources.json     # 来源与许可汇总
├── manifests/           # 各子集原始清单（采集层元数据）
├── reports/
│   └── dataset_stats.md # 数量/分布统计报告
├── scripts/
│   ├── download/        # harvest_commons.py 等
│   ├── synthesize/      # gen_synthetic.py（全合成）、forge_transplant.py（移植伪造）
│   └── finalize_dataset.py  # 汇总清单/去重/统计
└── raw/
    ├── dataset/docdiff_seal/   # DocDiff 真实印章抠图+掩码（MIT）
    └── fonts/                  # 中文手写体字体（OFL）
```

## 标签口径（manifest.jsonl 关键字段）

| 字段 | 说明 |
|---|---|
| `subset` | `realweb` / `commons` / `synthetic` / `real_transplant` |
| `label` | `genuine`（真章）/ `forged`（假章）/ `no_seal`（无章，负样本） |
| `label_confidence` | `clean`（合成/移植样本，标签确定）；`weak`（真实网图，弱标签） |
| `has_seal_signal` | 红色印章像素启发式（红色占比 ≥0.3%），用于过滤弱标签中无章图 |
| `forgery_types` | 伪造手法标签，见下表 |
| `red_ratio` / `red_bbox` | 红色印章信号占比与外接框（归一化坐标） |
| `target_file` | real_transplant 样本所用的底图（可与真图配对分组评测） |

### 伪造类型

- **全合成子集**（`seal_mode=forged/party_mismatch`）：
  `party_mismatch`（冒用他公司章）、`name_altered`/`name_truncated`（章面公司名篡改/缺字）、
  `missing_star`/`star_deformed`（星徽缺失/变形）、`broken_ring`（外圈断线）、`extra_ring`（多余内圈）、
  `color_off`（颜色异常）、`text_flip`（章面文字反排）、`over_ink`（印泥过重）、
  `low_quality`（低质模糊）、`distort`（拉伸变形）；另有 `sig_printed`/`sig_mismatch`（签名打印/冒签）。
- **real_transplant 子集**：`seal_transplant` —— 用 DocDiff 真实红章（含掩码）移植到真实合同照片，
  加旋转/缩放/印泥浓度/色偏/模糊/重压缩，模拟常见的"PS 盖章"造假。

## 子集说明与可信度

| 子集 | 数量 | 标签可信度 | 说明 |
|---|---|---|---|
| `realweb` | 102 | 已审核 | 三轮定向搜索共 961 张候选，多模态逐张审核后仅保留"现代中文合同+红色公章"（`reviewed=true`）；其余移入 `data/excluded/`，另有 2 张商务单据在 `data/hold/` 待定。全部参与 T1/T2 误报率考察；其中 22 张要素可读参与 T4-real（63 题，全为正例，测误报；联合体盖章已人工复核豁免）。标签同构文件：`metadata/realweb_labels.jsonl` |
| `commons` | 0 | — | 32 张 Wikimedia 历史契约均属"老地契/私章官印"场景，按口径全部剔除（文件在 `data/excluded/commons/`） |
| `synthetic` | 496 | 确定 | 8 类中文合同 + 公章/合同专用章 + 手写签名。**每侧章独立抽签**（真 58% / 冒用他司 20% / 缺陷伪造 22%），一真一假混合图 202 张；签名侧负例率 30%；伪造手法 1-2 种加权叠加；165 genuine / 295 forged / 36 no_seal；4 种成像退化（clean/scan_skew/photo/fax），种子 20261024 可复现 |
| `real_transplant` | 160 | 确定 | 审核通过的真实合同底图 + DocDiff 真实章移植，每底图 ≤2 变体；`target_file`/`variant` 支持配对分组评测 |

标签分布：genuine 267 / forged 455 / no_seal 36。

**注意**：严谨的主评测建议用 `label_confidence=clean` 的 **656 张**（synthetic 496 + real_transplant 160）；
`realweb` 102 张已审核但仍属真实场景泛化评测集（新闻图可能带水印、拍摄角度任意）。

## 复现方式

```powershell
# 全合成（300 张）
uv run --with pillow --with numpy scripts\gen_synthetic.py 300
# 真实章移植伪造（170 张，依赖 raw/dataset/docdiff_seal）
uv run --with pillow --with numpy scripts\synthesize\forge_transplant.py 170
# 汇总清单 + 去重 + 统计
uv run --with pillow --with numpy scripts\finalize_dataset.py
```

## 来源与许可

- **web 搜索图**：两轮定向采集（百度/搜狗/360/Bing，`scripts/download/harvest_web2.py` 等），逐张记录来源 URL 于 `manifests/realweb_raw.jsonl`；保留样本全部经多模态审核。仅用于研究评测，权利归属原作者。
- **DocDiff 印章素材**：MIT License (c) 2023 Zongyuan Yang，https://github.com/Royalvice/DocDiff ；原始印章大部分来自 ICDAR 2023 RRC "Reading the Seal Title" 竞赛数据集。用于 real_transplant 伪造合成。
- **字体**：Ma Shan Zheng / Zhi Mang Xing / Liu Jian Mao Cao（SIL OFL，Google Fonts）；系统字体 SimHei/SimKai/SimFang/SimSun/STXingkai（随 Windows 分发，仅本地渲染）。

### 外部数据集调研结论（2026-10）

| 来源 | 结论 |
|---|---|
| Roboflow Universe（6 个 "seal-detection" 项目） | **不适用**：实为机械密封圈（industrial seal）、集装箱铅封（container seal）、多国公文票据；无中文合同公章数据 |
| Kaggle（StaVer / Stamp Recognition / document-signature-stamp 等） | **不适用**：西文保险单据/票据印章，非中文合同；数据集 1.9–16GB 未下载 |
| DocBank（GitHub） | 印章数据在百度/夸克网盘（提取码公开于其 README），需手动下载，未脚本接入 |
| Wikimedia Commons | 有历史契约地契（老式私章/官印），不满足"现代合同公章"口径 |

**DocBank 网盘直达（提取码来自其 GitHub README）**：

| 名称 | 内容 | 链接 | 提取码 |
|---|---|---|---|
| doc_img_10000 | 10000 张干净文档底图 | https://pan.baidu.com/s/1zPFHpDYTM0D0yz6BL2dm1g | ibxf |
| seal-1-1 | 10000 张合成盖章文档（含印章框坐标） | https://pan.baidu.com/s/1iotKgCHiO17DxiTNiTbMaw | hc6v |
| Seal-1-2 | 10000 张合成盖章文档 | https://pan.baidu.com/s/1QQCtKhfZCN5wbxfPcZNveQ | esc8 |
| Seal-2 | 20796 张成对印章区域数据 | https://pan.baidu.com/s/11E5WQG6cZTXZQxW_jzHw_Q | 7t19 |
| Seal-3 | 25033 张纯印章图 | https://pan.baidu.com/s/1kBtq-1UiVgmhizqdPSfzxA | 9qpf |
| Seal-4 | 80000 张透明底 PNG 印章（夸克网盘） | https://pan.quark.cn/s/62ddd822ba6d | C4b8 |

页面：https://github.com/liuyifan6613/DocBank-Document-Enhancement-Dataset （仅限学术用途）

## 已知局限

1. 真实"假章"样本稀缺，伪造侧以合成与移植为主，手法覆盖面有限（未含：激光刻章翻拍、真章扫描件二次打印等高难度手法）。
2. `commons` 子集偏历史契约文书，与现代电子合同风格差异较大。
3. 全合成合同排版为程序生成，与真实版式存在分布差异——请勿用 synthetic 单独结论外推真实场景。
4. DocDiff 章素材含少量抠图噪声（作者已声明）。

## 后续可扩展

- Kaggle / Roboflow Universe 上的印章检测数据集（需各自 API Key 后接入）。
- 用 OCR（如 PaddleOCR）对弱标签子集做"合同要素 + 章面公司名一致性"自动校验，提升弱标签质量。
