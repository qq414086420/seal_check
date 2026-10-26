# -*- coding: utf-8 -*-
"""中文合同+公章 合成样本生成器：真实感合同页面、公章/合同专用章、手写签名、伪造变体。
输出 data/synthetic/ 与 manifests/synthetic_manifest.jsonl。Python 3.9 + Pillow 11。
"""
import json, math, os, random, sys, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "data", "synthetic")
MANI_PATH = os.path.join(BASE, "manifests", "synthetic_manifest.jsonl")
FONT_DIR = os.path.join(BASE, "raw", "fonts")
W, H = 1240, 1754  # A4 @150dpi

F_HEI = "C:/Windows/Fonts/simhei.ttf"
F_KAI = "C:/Windows/Fonts/simkai.ttf"
F_FANG = "C:/Windows/Fonts/simfang.ttf"
F_SONG = "C:/Windows/Fonts/simsun.ttc"
F_XINGKAI = "C:/Windows/Fonts/STXINGKA.TTF"
F_HAND = [os.path.join(FONT_DIR, "MaShanZheng-Regular.ttf"),
          os.path.join(FONT_DIR, "ZhiMangXing-Regular.ttf"),
          os.path.join(FONT_DIR, "LiuJianMaoCao-Regular.ttf"), F_XINGKAI]

random.seed(20261024)
np.random.seed(20261024)

# ---------------- 名称池 ----------------
CITY = ["北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉", "西安", "重庆",
        "苏州", "天津", "长沙", "郑州", "青岛", "合肥", "福州", "厦门", "济南", "大连"]
CO_PRE = ["华宇", "中恒", "恒达", "鑫源", "泰和", "联创", "瑞丰", "博远", "天成", "银河",
          "万通", "盛世", "宏图", "正大", "启航", "领航", "云栖", "智联", "卓越", "远航",
          "金桥", "晟安", "铭泰", "汇金", "鸿业", "嘉禾", "锐驰", "辰光", "新纪元", "百川"]
CO_MID = ["科技", "网络信息", "建设工程", "贸易", "实业", "机电设备", "建材", "环保",
          "文化传媒", "商贸", "印务", "食品", "医药", "物流", "咨询管理", "电子技术",
          "软件", "建筑装饰", "人力资源", "农业发展"]
CO_SUF = ["有限公司", "有限公司", "有限公司", "有限责任公司", "股份有限公司"]
SUR = list("王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董潘袁蔡蒋余杜叶程苏魏吕丁任沈姚卢")
GIV = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛",
       "明", "超", "霞", "平", "刚", "建华", "文军", "国华", "志伟", "玉兰", "桂英", "秀兰",
       "晨", "阳", "雪", "松", "楠", "欣然", "子涵", "一鸣", "浩然", "雨欣"]
CODE_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"

CONTRACT_TYPES = ["劳动合同书", "房屋租赁合同", "商品购销合同", "技术服务合同",
                  "建设工程施工合同", "借款合同", "保密协议", "委托代理合同"]


def company():
    return random.choice(CITY) + random.choice(CO_PRE) + random.choice(CO_MID) + random.choice(CO_SUF)


def person():
    return random.choice(SUR) + random.choice(GIV)


def uscc():
    return "9" + "".join(random.choice(CODE_CHARS) for _ in range(17))


def phone():
    return "1" + random.choice("3589") + "".join(str(random.randint(0, 9)) for _ in range(9))


# ---------------- 合同正文模板 ----------------
def contract_lines(kind, pa, pb, la, lb, no):
    L = [("title", kind)]
    L.append(("body", "合同编号：%s" % no))
    L.append(("blank", ""))
    head = ("body", "甲方：%s" % pa["name"])
    L.append(head)
    L.append(("body", "统一社会信用代码：%s" % pa["code"]))
    L.append(("body", "法定代表人：%s        联系电话：%s" % (la, pa["phone"])))
    L.append(("body", "住所地：%s市%s区%s路%d号" % (pa["city"], random.choice("东西南北朝阳江汉高新"),
                                               random.choice("和平中山建设人民解放", ), random.randint(1, 299))))
    L.append(("blank", ""))
    L.append(("body", "乙方：%s" % pb["name"]))
    L.append(("body", "统一社会信用代码：%s" % pb["code"]))
    L.append(("body", "法定代表人：%s        联系电话：%s" % (lb, pb["phone"])))
    L.append(("blank", ""))
    L.append(("h2", "根据《中华人民共和国民法典》及相关法律法规，甲乙双方本着平等自愿、诚实信用的原则，"
                    "就相关事项协商一致，订立本合同，以资共同遵守。"))
    L.append(("blank", ""))
    y = random.randint(2024, 2026); m = random.randint(1, 12); amt = random.randint(5, 980) * 1000
    body_map = {
        "劳动合同书": [("h2", "第一条 合同期限"), ("body", "本合同为固定期限劳动合同，自 %d 年 %d 月 1 日起至 %d 年 %d 月 1 日止，"
                  "其中试用期三个月。乙方根据甲方安排，担任%s岗位工作，工作地点为甲方注册地。" %
                  (y, m, y + 2, m, random.choice("技术研发生产管理销售财务行政"))),
                 ("h2", "第二条 劳动报酬"), ("body", "乙方月工资为税前人民币 %d 元，甲方于每月 15 日前以货币形式足额支付，"
                  "不得无故克扣或拖欠。甲方依法为乙方缴纳社会保险费用。" % (amt // 12)),
                 ("h2", "第三条 工作时间与休息休假"), ("body", "甲方实行国家规定的标准工时制度，乙方每日工作不超过八小时，"
                  "每周工作不超过四十小时，依法享受法定节假日及带薪年休假。")],
        "房屋租赁合同": [("h2", "第一条 租赁标的"), ("body", "甲方将位于%s市%s区%s路%d号第%d层%d号的房屋出租给乙方居住使用，"
                    "建筑面积约 %d 平方米，附属设施以双方确认的清单为准。" % (pb["city"], random.choice("东西南北朝阳江汉"),
                    random.choice("和平中山建设人民"), random.randint(1, 299), random.randint(1, 30), random.randint(101, 2504),
                    random.randint(45, 160))),
                 ("h2", "第二条 租金与押金"), ("body", "月租金为人民币 %d 元，乙方应于每月 5 日前支付。签订本合同时乙方"
                  "向甲方支付押金人民币 %d 元，租赁期满且无违约情形的，甲方应全额无息退还。" % (amt // 6, amt // 6)),
                 ("h2", "第三条 租赁期限"), ("body", "租赁期自 %d 年 %d 月 1 日起至 %d 年 %d 月 1 日止。"
                  "租赁期内乙方不得擅自转租、转借房屋。" % (y, m, y + 1, m))],
        "商品购销合同": [("h2", "第一条 标的与价款"), ("body", "甲方向乙方采购%s一批，具体规格、数量以双方确认的订单为准，"
                    "合同总金额为人民币 %d 元（含税）。" % (random.choice(["办公家具钢材水泥电子元器件劳保用品包装材料",
                    "电线电缆五金配件安防设备"]), amt)),
                 ("h2", "第二条 交货方式"), ("body", "乙方应于 %d 年 %d 月 %d 日前将货物运至甲方指定地点并负责卸货，"
                  "运费由乙方承担。甲方应在收货后七日内验收，逾期未提出异议视为验收合格。" % (y, m, random.randint(2, 28))),
                 ("h2", "第三条 结算方式"), ("body", "货款以银行转账方式分期支付，验收合格后十日内支付合同总额的 60%%，"
                  "剩余 40%% 于质保期满后十日内付清。")],
        "技术服务合同": [("h2", "第一条 服务内容"), ("body", "乙方为甲方提供%s系统的技术开发与运维服务，包括需求调研、"
                    "方案设计、开发实施、测试上线及一年免费质保。" % random.choice(["数据中台仓库管理客户关系",
                    "门户网站财务结算移动办公"])),
                 ("h2", "第二条 服务费用"), ("body", "服务费总额为人民币 %d 元，分三期支付：合同生效后十日内支付 30%%，"
                  "阶段成果验收后支付 40%%，终验合格后支付 30%%。" % amt),
                 ("h2", "第三条 知识产权"), ("body", "因履行本合同形成的技术成果，其知识产权归甲方所有，"
                  "乙方享有署名权。乙方保证服务成果不侵犯任何第三方合法权益。")],
        "建设工程施工合同": [("h2", "第一条 工程概况"), ("body", "工程名称：%s市%s区%s家园住宅小区%d号楼土建安装工程；"
                     "工程地点：%s市%s区；承包范围：施工图纸范围内的土建、安装工程。" %
                     (pa["city"], random.choice("东西南北朝阳江汉"), random.choice("瑞和锦绣龙腾"), random.randint(1, 22),
                      pa["city"], random.choice("东西南北朝阳江汉"))),
                  ("h2", "第二条 合同工期与价款"), ("body", "计划开工日期为 %d 年 %d 月 1 日，总工期 %d 个日历天。"
                   "合同价款为人民币 %d 元，采用固定单价合同，按实结算。" % (y, m, random.choice([180, 240, 300, 365]), amt * 8)),
                  ("h2", "第三条 质量与安全"), ("body", "工程质量标准为合格，乙方应严格遵守安全生产管理规定，"
                   "文明施工，因乙方原因造成的安全事故由乙方承担全部责任。")],
        "借款合同": [("h2", "第一条 借款金额与用途"), ("body", "甲方向乙方出借人民币 %d 元整，用于乙方流动资金周转，"
                  "乙方不得挪作他用。" % amt),
                ("h2", "第二条 借款期限与利率"), ("body", "借款期限自 %d 年 %d 月 1 日起至 %d 年 %d 月 1 日止，"
                 "年利率为 %s，按月付息，到期一次性还本。" % (y, m, y + 1, m, random.choice(["3.85%", "4.35%", "5.20%", "6.00%"]))),
                ("h2", "第三条 还款与担保"), ("body", "乙方应按约定按期足额支付利息及本金；乙方以其名下%s提供抵押担保，"
                 "担保范围包括本金、利息及实现债权的费用。" % random.choice(["房产", "机器设备", "车辆"]))],
        "保密协议": [("h2", "第一条 保密内容"), ("body", "双方在合作过程中知悉的对方商业秘密、技术秘密、经营信息、"
                  "客户资料及其他未公开信息，均属于保密信息。"),
                ("h2", "第二条 保密义务"), ("body", "接收方未经披露方书面同意，不得向任何第三方泄露、提供保密信息，"
                  "不得将保密信息用于本合同以外的目的。保密义务不因本合同的解除或终止而失效。"),
                ("h2", "第三条 违约责任"), ("body", "任何一方违反本协议约定的，应向守约方支付违约金人民币 %d 元；"
                  "造成损失超过违约金数额的，还应赔偿差额部分。" % amt)],
        "委托代理合同": [("h2", "第一条 委托事项"), ("body", "甲方委托乙方就%s事宜提供代理服务，乙方应勤勉尽责，"
                   "依法维护甲方合法权益。" % random.choice(["应收账款清收", "商标注册申请", "劳动争议处理", "项目申报"]))],
    }
    L.extend(body_map[kind])
    L.extend([("h2", "第%d条 违约责任" % random.randint(4, 6)),
              ("body", "任何一方违反本合同约定，给对方造成损失的，应依法承担赔偿责任；逾期履行的，"
                       "每逾期一日按合同总额的 0.5‰ 支付违约金。"),
              ("h2", "第%d条 争议解决" % random.randint(7, 9)),
              ("body", "因履行本合同发生的争议，双方应友好协商解决；协商不成的，任何一方可向合同签订地"
                       "人民法院提起诉讼。"),
              ("blank", ""), ("blank", ""),
              ("h2", "（以下无正文，为本合同签署页）"), ("blank", "")])
    return L


def wrap(text, font, maxw, drawer):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if drawer.textlength(cur + ch, font=font) > maxw:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def render_contract(kind, pa, pb, la, lb, no, date_str):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_title = ImageFont.truetype(F_HEI, 46)
    f_h2 = ImageFont.truetype(F_HEI, 29)
    f_body = ImageFont.truetype(F_FANG, 27)
    ml, mr = 112, 112
    maxw = W - ml - mr
    y = 96
    layout = {}
    for sty, txt in contract_lines(kind, pa, pb, la, lb, no):
        if sty == "title":
            d.text((W // 2, y), txt, font=f_title, fill=(15, 15, 15), anchor="mm")
            y += 88
        elif sty == "h2":
            for ln in wrap(txt, f_h2, maxw, d):
                d.text((ml, y), ln, font=f_h2, fill=(20, 20, 20))
                y += 42
        elif sty == "body":
            for ln in wrap(txt, f_body, maxw, d):
                d.text((ml, y), ln, font=f_body, fill=(25, 25, 25))
                y += 41
        elif sty == "blank":
            y += 26
        if y > H - 420:
            break
    # 签署区
    y = max(y + 30, H - 400)
    f_sig = ImageFont.truetype(F_FANG, 28)
    for side, party in (("A", pa), ("B", pb)):
        x = ml if side == "A" else W // 2 + 40
        d.text((x, y), "甲方（盖章）：" if side == "A" else "乙方（盖章）：", font=f_sig, fill=(25, 25, 25))
        layout["seal_" + side] = (x + 240, y - 28)
        d.text((x, y + 66), "法定代表人（签字）：", font=f_sig, fill=(25, 25, 25))
        layout["sig_" + side] = (x + 310, y + 40)
        d.text((x, y + 132), "签订日期：      年      月      日", font=f_sig, fill=(25, 25, 25))
        d.text((x, y + 60), "", font=f_sig)
        layout["date_" + side] = (x + 150, y + 120)
    y += 210
    d.text((ml, y), "本合同一式两份，甲乙双方各执一份，具有同等法律效力。", font=f_body, fill=(25, 25, 25))
    # 手写日期
    if random.random() < 0.75:
        for side in ("A", "B"):
            sx, sy = layout["date_" + side]
            f_hand_d = ImageFont.truetype(random.choice(F_HAND), 34)
            d.text((sx, sy + random.randint(-3, 6)), "%d %d %d" % tuple(random.choice(date_str)),
                   font=f_hand_d, fill=(20, 25, 70))
    # 纸张质感
    arr = np.asarray(img).astype(np.int16)
    noise = np.random.normal(0, 3.2, (H, W, 1)).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    return img, layout


# ---------------- 公章绘制 ----------------
def seal_base_color(color_off=False, over_ink=False):
    if color_off:
        return random.choice([(226, 116, 128), (224, 120, 40), (236, 130, 150)])
    base = (198, 26, 28) if not over_ink else (162, 18, 20)
    return tuple(max(0, min(255, c + random.randint(-10, 10))) for c in base)


def draw_seal(company_name, kind="official", code=None, color_off=False, over_ink=False,
              missing_star=False, broken_ring=False, name_text=None, star_deformed=False,
              extra_ring=False, text_flip=False):
    """绘制一枚印章，返回 RGBA Image（约 250px）。"""
    SS = 2
    R = 118
    dim = int((R + 16) * 2) * SS
    img = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = dim // 2
    Rs = R * SS
    col = seal_base_color(color_off, over_ink) + (255,)
    lw = int((7 if over_ink else 5.5) * SS)
    d.ellipse([c - Rs, c - Rs, c + Rs, c + Rs], outline=col, width=lw)
    if extra_ring:
        r2 = int(Rs * 0.86)
        d.ellipse([c - r2, c - r2, c + r2, c + r2], outline=col, width=int(2.2 * SS))
    text = name_text if name_text else company_name
    if text_flip:
        text = "".join(reversed(text))
    f_arc = ImageFont.truetype(F_HEI, int(33 * SS))
    n = len(text)
    span = math.radians(min(285, 34 + n * 21))
    r_text = Rs - int(25 * SS)
    ch_box = int(46 * SS)
    for i, ch in enumerate(text):
        t = -span / 2 + span * (i / max(1, n - 1))
        px = c + r_text * math.sin(t)
        py = c - r_text * math.cos(t)
        cimg = Image.new("RGBA", (ch_box, ch_box), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cimg)
        cd.text((ch_box // 2, ch_box // 2), ch, font=f_arc, fill=col, anchor="mm")
        cimg = cimg.rotate(-math.degrees(t), resample=Image.BICUBIC)
        img.alpha_composite(cimg, (int(px - ch_box / 2), int(py - ch_box / 2)))
    # 五角星（公章有星，合同专用章按规范不带星）
    if not missing_star and kind == "official":
        ro = Rs * 0.40 if not star_deformed else Rs * random.choice([0.30, 0.47])
        ri = ro * (0.40 if not star_deformed else random.choice([0.18, 0.55]))
        rot0 = 0 if not star_deformed else random.uniform(-14, 14)
        pts = []
        for k in range(10):
            ang = math.radians(rot0 + k * 36)
            rr = ro if k % 2 == 0 else ri
            pts.append((c + rr * math.sin(ang), c - rr * math.cos(ang)))
        d.polygon(pts, fill=col)
    # 底部文字/编码
    if kind == "contract":
        f_b = ImageFont.truetype(F_HEI, int(30 * SS))
        d.text((c, c + int(Rs * 0.60)), "合同专用章", font=f_b, fill=col, anchor="mm")
    if code:
        f_c = ImageFont.truetype(F_HEI, int(19 * SS))
        d.text((c, c + int(Rs * 0.78)), code, font=f_c, fill=col, anchor="mm")
    if broken_ring:
        a = np.asarray(img).copy()
        al = a[:, :, 3].astype(np.float32)
        ys, xs = np.mgrid[0:dim, 0:dim]
        rr = np.sqrt((xs - c) ** 2 + (ys - c) ** 2)
        ring_mask = (np.abs(rr - Rs) < lw * 1.2)
        for _ in range(random.randint(2, 4)):
            a0 = random.uniform(0, 2 * math.pi)
            a1 = a0 + random.uniform(0.25, 0.7)
            aa = np.arctan2(ys - c, xs - c) + math.pi
            seg = (aa >= a0) & (aa <= a1) & ring_mask
            al[seg] = 0
        a[:, :, 3] = al.astype(np.uint8)
        img = Image.fromarray(a)
    # 印泥质感
    a = np.asarray(img).copy()
    al = a[:, :, 3].astype(np.float32)
    small = np.random.rand(dim // 6, dim // 6).astype(np.float32)
    nimg = Image.fromarray((small * 255).astype(np.uint8)).resize((dim, dim), Image.BICUBIC)
    nmap = np.asarray(nimg).astype(np.float32) / 255.0
    strength = 0.30 if over_ink else 0.18
    al *= (1.0 - strength + strength * nmap)
    if random.random() < 0.8:  # 洇墨/飞白斑点
        for _ in range(random.randint(8, 30)):
            x0 = random.randint(0, dim - 4); y0 = random.randint(0, dim - 4)
            r0 = random.randint(1, 3) * SS // 2 + 1
            patch = (slice(max(0, y0), y0 + r0), slice(max(0, x0), x0 + r0))
            if random.random() < 0.5:
                al[patch] *= random.uniform(0.1, 0.5)
            else:
                al[patch] = np.clip(al[patch] + random.uniform(0, 60), 0, 255)
    a[:, :, 3] = np.clip(al, 0, 255).astype(np.uint8)
    img = Image.fromarray(a)
    if over_ink:
        img = img.filter(ImageFilter.MaxFilter(3))
    img = img.resize((dim // SS, dim // SS), Image.LANCZOS)
    return img


# ---------------- 签名 ----------------
_SIG_CACHE = {}

def make_signature(name, printed=False, scale=1.0):
    key = (name, printed, round(scale, 1))
    if key in _SIG_CACHE:
        return _SIG_CACHE[key].copy()
    fsize = int(52 * scale)
    if printed:
        font = ImageFont.truetype(F_SONG, fsize)
    else:
        font = ImageFont.truetype(random.choice(F_HAND), fsize)
    tmp = Image.new("RGBA", (fsize * len(name) + 60, fsize + 80), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    ink = random.choice([(20, 24, 70), (25, 25, 35), (30, 30, 90)])
    td.text((30, 40), name, font=font, fill=ink + (255,))
    tmp = tmp.rotate(random.uniform(-7, 7), expand=True, resample=Image.BICUBIC)
    if not printed:
        a = np.asarray(tmp).copy()
        a[:, :, 3] = (a[:, :, 3].astype(np.float32) * np.random.uniform(0.82, 0.95)).astype(np.uint8)
        tmp = Image.fromarray(a)
    _SIG_CACHE[key] = tmp
    return tmp.copy()


# ---------------- 合成到页面 ----------------
def paste_seal(page, seal, center, rot=None, opacity=None):
    if rot is None:
        rot = random.uniform(-11, 11)
    if opacity is None:
        opacity = random.uniform(0.78, 0.95)
    s = seal.rotate(rot, expand=True, resample=Image.BICUBIC)
    a = np.asarray(s).copy()
    a[:, :, 3] = (a[:, :, 3].astype(np.float32) * opacity).astype(np.uint8)
    s = Image.fromarray(a)
    px, py = int(center[0] - s.width / 2), int(center[1] - s.height / 2)
    page_rgba = page.convert("RGBA")
    page_rgba.alpha_composite(s, (px, py))
    return page_rgba.convert("RGB")


def paste_signature(page, sig, center, opacity=0.88):
    a = np.asarray(sig).copy()
    a[:, :, 3] = (a[:, :, 3].astype(np.float32) * opacity).astype(np.uint8)
    s = Image.fromarray(a)
    page_rgba = page.convert("RGBA")
    page_rgba.alpha_composite(s, (int(center[0]), int(center[1])))
    return page_rgba.convert("RGB")


def degrade(page, mode):
    w, h = page.size
    if mode == "scan_skew":
        page = page.rotate(random.uniform(-2.2, 2.2), expand=True, resample=Image.BICUBIC,
                           fillcolor=(250, 250, 250))
        page = ImageOps.pad(page, (w, h), color=(250, 250, 250))
        arr = np.asarray(page).astype(np.float32)
        gx = np.linspace(-1, 1, w)[None, :]
        arr *= (1.0 + 0.05 * gx)[::-1][:, :, None]
        page = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    elif mode == "photo":
        # PIL QUAD 数据顺序：NW, SW, SE, NE（源图四角），顺序错误会导致镜像
        tl = (random.randint(-38, 10), random.randint(-38, 10))
        bl = (random.randint(-38, 10), h + random.randint(-10, 38))
        br = (w + random.randint(-10, 38), h + random.randint(-10, 38))
        tr = (w + random.randint(-10, 38), random.randint(-38, 10))
        flat = [tl[0], tl[1], bl[0], bl[1], br[0], br[1], tr[0], tr[1]]
        page = page.transform((w, h), Image.QUAD, data=flat, resample=Image.BICUBIC)
        arr = np.asarray(page).astype(np.float32)
        yy, xx = np.mgrid[0:h, 0:w]
        rr = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        arr *= (1.0 - 0.22 * np.clip(rr - 0.45, 0, 1))[:, :, None]
        arr *= random.uniform(0.88, 0.97)
        page = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        page = page.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 0.9)))
    elif mode == "fax":
        page = page.resize((int(w * 0.42), int(h * 0.42)), Image.BILINEAR)
        page = page.resize((w, h), Image.BILINEAR)
    return page


def save_page(page, mode, path):
    q = {"clean": random.randint(72, 90), "scan_skew": random.randint(60, 82),
         "photo": random.randint(45, 68), "fax": random.randint(30, 42)}[mode]
    page.save(path, "JPEG", quality=q)


# ---------------- 主流程 ----------------
def gen_one(idx, spec=None):
    kind = random.choice(CONTRACT_TYPES)
    pa = {"name": company(), "code": uscc(), "phone": phone(), "city": random.choice(CITY)}
    pb = {"name": company(), "code": uscc(), "phone": phone(), "city": random.choice(CITY)}
    la, lb = person(), person()
    no = "%s-%d-HT%04d" % (random.choice(["HT", "XZ", "GC", "ZL"]), random.randint(2019, 2026), idx)
    date_str = [(y, m, d) for y, m, d in
                [(random.randint(2023, 2026), random.randint(1, 12), random.randint(1, 28))]]
    page, layout = render_contract(kind, pa, pb, la, lb, no, date_str)
    mode = random.choices(["clean", "scan_skew", "photo", "fax"], weights=[0.34, 0.30, 0.20, 0.16])[0]

    side_modes = spec.get("side_modes") or {}
    forgery_types, seal_infos = [], []
    sig_forgery = spec.get("sig_forgery", "none")

    # 决定甲乙双方印章（每侧独立抽签，允许"一侧真章一侧假章"混合）
    seal_plan = spec.get("seal_plan", "both")  # both / none / a_only
    for side, party in (("A", pa), ("B", pb)):
        anchor = layout.get("seal_" + side)
        if anchor is None:
            continue
        if seal_plan == "none" or (seal_plan == "a_only" and side == "B"):
            continue
        this_mode = side_modes.get(side, "genuine")
        ft = []
        kwargs = dict(kind=random.choice(["official", "contract"]))
        code = uscc()[:13] if kwargs["kind"] == "official" and random.random() < 0.8 else None
        name_in_seal = party["name"]
        if this_mode == "party_mismatch":
            wrong = company()
            while wrong == party["name"]:
                wrong = company()
            name_in_seal = wrong
            ft.append("party_mismatch")
            if random.random() < 0.30:          # 假章常伴随做工差
                ft.append("low_quality")
        elif this_mode == "forged":
            _types = ["low_quality", "distort", "missing_star", "broken_ring", "name_truncated",
                      "name_altered", "color_off", "text_flip", "over_ink", "star_deformed", "extra_ring"]
            if kwargs["kind"] == "contract":
                _types = [t for t in _types if t not in ("missing_star", "star_deformed")]
            _w = [20 if t in ("name_altered", "name_truncated") else 10 for t in _types]
            n_types = 2 if random.random() < 0.30 else 1   # 30% 概率两种手法叠加
            types = []
            pool = list(zip(_types, _w))
            while len(types) < min(n_types, len(pool)):
                ts, ws = zip(*pool)
                t = random.choices(ts, weights=ws)[0]
                types.append(t)
                pool = [(a, w) for a, w in pool if a != t]
            ft.extend(types)
            for t in types:
                if t == "name_truncated":
                    name_in_seal = name_in_seal[: max(4, len(name_in_seal) - random.randint(2, 3))]
                elif t == "name_altered":
                    pos = random.randrange(2, len(name_in_seal) - 3)
                    alt = name_in_seal[:pos] + random.choice(CO_PRE) + name_in_seal[pos + 2:]
                    name_in_seal = alt[: len(name_in_seal)]
                elif t == "color_off":
                    kwargs["color_off"] = True
                elif t == "over_ink":
                    kwargs["over_ink"] = True
                elif t == "missing_star":
                    kwargs["missing_star"] = True
                elif t == "broken_ring":
                    kwargs["broken_ring"] = True
                elif t == "star_deformed":
                    kwargs["star_deformed"] = True
                elif t == "extra_ring":
                    kwargs["extra_ring"] = True
                elif t == "text_flip":
                    kwargs["text_flip"] = True
        seal = draw_seal(party["name"], name_text=name_in_seal, code=code, **kwargs)
        if "low_quality" in ft:
            w0, h0 = seal.size
            seal = seal.resize((int(w0 * 0.4), int(h0 * 0.4)), Image.BILINEAR).resize((w0, h0), Image.BILINEAR)
            seal = seal.filter(ImageFilter.GaussianBlur(1.6))
        if "distort" in ft:
            w0, h0 = seal.size
            seal = seal.resize((int(w0 * random.uniform(1.1, 1.3)), int(h0 * random.uniform(0.72, 0.9))),
                               Image.BICUBIC).resize((w0, h0), Image.BICUBIC).rotate(random.uniform(6, 18), expand=False)
        # 骑年盖月：印章中心压在落款区
        cx = anchor[0] + random.randint(-14, 22)
        cy = anchor[1] + random.randint(18, 60)
        page = paste_seal(page, seal, (cx, cy))
        seal_infos.append({"side": side, "company": name_in_seal, "kind": kwargs.get("kind"),
                           "code": code, "matches_party": name_in_seal == party["name"],
                           "genuine": this_mode == "genuine"})
        forgery_types.extend(ft if side == "A" else ft)

    # 签名
    sig_infos = []
    for side, lname in (("A", la), ("B", lb)):
        anchor = layout.get("sig_" + side)
        if anchor is None:
            continue
        signed_name = lname
        ft2 = []
        printed = False
        if sig_forgery == "printed" and random.random() < 0.8:
            printed = True
            ft2.append("sig_printed")
        if sig_forgery == "mismatch" and random.random() < 0.6:
            signed_name = person()
            ft2.append("sig_mismatch")
        sig = make_signature(signed_name, printed=printed, scale=random.uniform(0.85, 1.05))
        page = paste_signature(page, sig, (anchor[0], anchor[1] + random.randint(-4, 10)))
        sig_infos.append({"side": side, "name": signed_name, "matches_rep": signed_name == lname,
                          "printed": printed, "forgery": ft2})

    page = degrade(page, mode)
    fname = "syn_%05d.jpg" % idx
    save_page(page, mode, os.path.join(OUT_DIR, fname))
    img_seal_mode = "+".join(sorted(set(side_modes.get(s, "genuine") for s in ("A", "B")))) if seal_plan != "none" else "none"
    rec = {"file": fname, "source": "synthetic", "contract_type": kind,
           "party_a": pa["name"], "party_b": pb["name"], "legal_rep_a": la, "legal_rep_b": lb,
           "seal_present": seal_plan != "none",
           "seal_genuine": None if seal_plan == "none" else all(s["genuine"] for s in seal_infos),
           "seal_mode": img_seal_mode, "forgery_types": sorted(set(forgery_types)),
           "seals": seal_infos, "signatures": sig_infos, "quality_mode": mode, "contract_no": no}
    return rec


def main():
    n_target = int(sys.argv[1]) if len(sys.argv) > 1 else 460
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(MANI_PATH), exist_ok=True)
    recs = []
    idx = 0
    # 每侧独立抽签：genuine 58% / 冒用他司章 20% / 章面缺陷伪造 22%
    # → 双真约 34%、一真一假约 49%（真实场景最常见形态）、双假约 17%
    specs = []
    for _ in range(n_target):
        side_modes = {}
        for s in ("A", "B"):
            r = random.random()
            if r < 0.58:
                side_modes[s] = "genuine"
            elif r < 0.78:
                side_modes[s] = "party_mismatch"
            else:
                side_modes[s] = "forged"
        specs.append({"side_modes": side_modes, "seal_plan": "both",
                      "sig_forgery": random.choices(["none", "printed", "mismatch"], [0.55, 0.25, 0.20])[0]})
    for _ in range(int(n_target * 0.08)):
        specs.append({"side_modes": {"A": "genuine", "B": "genuine"}, "seal_plan": "none", "sig_forgery": "none"})
    random.shuffle(specs)
    for spec in specs:
        idx += 1
        recs.append(gen_one(idx, spec))
    with open(MANI_PATH, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("generated", len(recs))


if __name__ == "__main__":
    main()
