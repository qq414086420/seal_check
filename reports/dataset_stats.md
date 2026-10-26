# SealBench 数据集统计

- 总样本：**782**
- 重复丢弃：0；损坏/过小丢弃：0；重新编码为 RGB JPEG：0

## 子集 × 标签

| 子集 | 标签 | 数量 |
|---|---|---|
| real_transplant | forged | 184 |
| realweb | genuine | 102 |
| synthetic | forged | 295 |
| synthetic | genuine | 165 |
| synthetic | no_seal | 36 |

弱标签（真实网图）中红色印章信号命中：81 / 102

## 伪造类型分布

- seal_transplant: 184
- party_mismatch: 157
- low_quality: 72
- name_altered: 46
- name_truncated: 38
- color_off: 28
- text_flip: 26
- extra_ring: 26
- broken_ring: 23
- distort: 21
- over_ink: 21
- star_deformed: 8
- missing_star: 6

## 成像质量（synthetic）

- -: 286
- clean: 170
- fax: 83
- photo: 105
- scan_skew: 138

## 来源分布

- real_transplant: 184
- synthetic: 496
- web_image_search: 102
