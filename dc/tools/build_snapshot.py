# -*- coding: utf-8 -*-
"""抓取公开数据源，生成 App 用的 snapshot.json.gz。

来源：
  ATLAS  Data centers (c) Ringmast4r - Global-Data-Center-Map
         https://github.com/Ringmast4r/Global-Data-Center-Map
  Epoch AI  AI data centers, CC BY 4.0
         https://epoch.ai/data/ai-data-centers
  AIHOT  https://aihot.news/leaderboard.md （GitHub KKKKhazix/AIHOT, MIT）

用法：
  python3 build_snapshot.py                 # 联网抓取
  python3 build_snapshot.py --offline       # 用 data/raw 里的缓存
"""
import argparse
import collections
import csv
import datetime
import difflib
import gzip
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ATLAS_CSV = "https://raw.githubusercontent.com/Ringmast4r/Global-Data-Center-Map/main/datacenters.csv"
ATLAS_GEO = "https://raw.githubusercontent.com/Ringmast4r/Global-Data-Center-Map/main/datacenters.geojson"
ATLAS_API = "https://api.github.com/repos/Ringmast4r/Global-Data-Center-Map"
EPOCH_ZIP = "https://epoch.ai/data/data_centers/data_centers.zip"
AIHOT_MD = "https://aihot.news/leaderboard.md"

SNAPSHOT_VERSION = 1

# ---------------------------------------------------------------------------
# 国家归一：ATLAS 的 country 字段有 345 种写法（含空值、邮编、地址碎片）。
# 只认这里列出的国家，其余计入 unmapped，不猜测。
# ---------------------------------------------------------------------------
COUNTRIES = [
    # iso, 中文, 英文规范名, 其他写法
    ("US", "美国", "United States", "usa|u.s.|us|united states of america|america"),
    ("GB", "英国", "United Kingdom", "uk|great britain|england|scotland|wales|northern ireland"),
    ("DE", "德国", "Germany", "deutschland|allemagne|alemania|duitsland"),
    ("FR", "法国", "France", "francia|frankreich"),
    ("CN", "中国", "China", "prc|mainland china"),
    ("NL", "荷兰", "Netherlands", "nederland|holland|paises bajos|niederlande|países bajos|netherlands antilles"),
    ("CA", "加拿大", "Canada", "canadá"),
    ("AU", "澳大利亚", "Australia", "australia"),
    ("IN", "印度", "India", "bharat"),
    ("BR", "巴西", "Brazil", "brasil"),
    ("IT", "意大利", "Italy", "italia|italie"),
    ("JP", "日本", "Japan", "japón|japon|nippon"),
    ("ES", "西班牙", "Spain", "españa|espana|espagne"),
    ("ID", "印度尼西亚", "Indonesia", "indonesia"),
    ("CH", "瑞士", "Switzerland", "svizzera|schweiz|suisse|suiza"),
    ("SE", "瑞典", "Sweden", "sverige|suecia"),
    ("RU", "俄罗斯", "Russia", "russian federation|россия"),
    ("SG", "新加坡", "Singapore", "singapura"),
    ("ZA", "南非", "South Africa", "south africa|sudáfrica|sudafrica"),
    ("MY", "马来西亚", "Malaysia", "malasia"),
    ("HK", "中国香港", "Hong Kong", "hong kong sar|香港"),
    ("PL", "波兰", "Poland", "polska|pologne"),
    ("IE", "爱尔兰", "Ireland", "eire"),
    ("NZ", "新西兰", "New Zealand", "new zealand|aotearoa"),
    ("BE", "比利时", "Belgium", "belgië|belgie|bélgica|belgica|belgique"),
    ("AT", "奥地利", "Austria", "österreich|osterreich"),
    ("KR", "韩国", "South Korea", "republic of korea|korea|south korea|대한민국"),
    ("DK", "丹麦", "Denmark", "danmark"),
    ("NO", "挪威", "Norway", "norge|noorwegen"),
    ("FI", "芬兰", "Finland", "suomi|finlandia"),
    ("MX", "墨西哥", "Mexico", "méxico|mexico"),
    ("PT", "葡萄牙", "Portugal", "portugal"),
    ("CL", "智利", "Chile", "chile"),
    ("BG", "保加利亚", "Bulgaria", "българия"),
    ("TH", "泰国", "Thailand", "tailandia|siam"),
    ("IL", "以色列", "Israel", "israel"),
    ("SA", "沙特阿拉伯", "Saudi Arabia", "saudi arabia|ksa"),
    ("AR", "阿根廷", "Argentina", "argentina"),
    ("CO", "哥伦比亚", "Colombia", "colombia"),
    ("RO", "罗马尼亚", "Romania", "românia|rumanía|rumania"),
    ("TR", "土耳其", "Turkey", "türkiye|turquía|turquia"),
    ("VN", "越南", "Vietnam", "việt nam|viet nam"),
    ("NG", "尼日利亚", "Nigeria", "nigeria"),
    ("UA", "乌克兰", "Ukraine", "ukraine|україна"),
    ("KE", "肯尼亚", "Kenya", "kenya"),
    ("CZ", "捷克", "Czech Republic", "czechia|czech republic"),
    ("GH", "加纳", "Ghana", "ghana"),
    ("TW", "中国台湾", "Taiwan", "taiwan|taiwán|taiwan province"),
    ("CY", "塞浦路斯", "Cyprus", "chipre|kıbrıs"),
    ("LU", "卢森堡", "Luxembourg", "luxembourg"),
    ("LV", "拉脱维亚", "Latvia", "latvija"),
    ("GR", "希腊", "Greece", "grecia|hellas"),
    ("PK", "巴基斯坦", "Pakistan", "pakistan"),
    ("EE", "爱沙尼亚", "Estonia", "eesti"),
    ("EG", "埃及", "Egypt", "egypt|مصر"),
    ("HU", "匈牙利", "Hungary", "magyarorszag"),
    ("PH", "菲律宾", "Philippines", "pilipinas"),
    ("LT", "立陶宛", "Lithuania", "lietuva"),
    ("SK", "斯洛伐克", "Slovakia", "slovensko"),
    ("TZ", "坦桑尼亚", "Tanzania", "tanzania"),
    ("AE", "阿联酋", "United Arab Emirates", "uae|united arab emirates"),
    ("UG", "乌干达", "Uganda", "uganda"),
    ("MA", "摩洛哥", "Morocco", "maroc|marruecos"),
    ("CI", "科特迪瓦", "Côte d'Ivoire", "ivory coast|cote d'ivoire|côte d'ivoire"),
    ("AO", "安哥拉", "Angola", "angola"),
    ("MU", "毛里求斯", "Mauritius", "mauritius"),
    ("PE", "秘鲁", "Peru", "perú|peru"),
    ("MT", "马耳他", "Malta", "malta"),
    ("MZ", "莫桑比克", "Mozambique", "mozambique"),
    ("CR", "哥斯达黎加", "Costa Rica", "costa rica"),
    ("CM", "喀麦隆", "Cameroon", "cameroun"),
    ("DZ", "阿尔及利亚", "Algeria", "algerie|argelia"),
    ("SI", "斯洛文尼亚", "Slovenia", "slovenija"),
    ("QA", "卡塔尔", "Qatar", "qatar"),
    ("TN", "突尼斯", "Tunisia", "tunisie"),
    ("PA", "巴拿马", "Panama", "panamá"),
    ("ZM", "赞比亚", "Zambia", "zambia"),
    ("IR", "伊朗", "Iran", "iran"),
    ("JO", "约旦", "Jordan", "jordan"),
    ("SN", "塞内加尔", "Senegal", "senegal"),
    ("HR", "克罗地亚", "Croatia", "hrvatska"),
    ("NA", "纳米比亚", "Namibia", "namibia"),
    ("OM", "阿曼", "Oman", "oman"),
    ("BH", "巴林", "Bahrain", "bahrain"),
    ("UY", "乌拉圭", "Uruguay", "uruguay"),
    ("LI", "列支敦士登", "Liechtenstein", "liechtenstein"),
    ("KW", "科威特", "Kuwait", "kuwait"),
    ("AM", "亚美尼亚", "Armenia", "armenia"),
    ("RS", "塞尔维亚", "Serbia", "serbia|serbia and montenegro"),
    ("EC", "厄瓜多尔", "Ecuador", "ecuador"),
    ("RW", "卢旺达", "Rwanda", "rwanda"),
    ("BJ", "贝宁", "Benin", "benin"),
    ("PR", "波多黎各", "Puerto Rico", "puerto rico"),
    ("BW", "博茨瓦纳", "Botswana", "botswana"),
    ("KH", "柬埔寨", "Cambodia", "cambodia"),
    ("BD", "孟加拉国", "Bangladesh", "bangladesh"),
    ("SD", "苏丹", "Sudan", "sudan"),
    ("GU", "关岛", "Guam", "guam"),
    ("DJ", "吉布提", "Djibouti", "djibouti"),
    ("CD", "刚果（金）", "Democratic Republic of the Congo", "democratic republic of the congo|dr congo"),
    ("CG", "刚果（布）", "Republic of the Congo", "republic of the congo|congo"),
    ("TT", "特立尼达和多巴哥", "Trinidad and Tobago", "trinidad and tobago"),
    ("KZ", "哈萨克斯坦", "Kazakhstan", "kazakhstan"),
    ("LB", "黎巴嫩", "Lebanon", "lebanon"),
    ("BY", "白俄罗斯", "Belarus", "belarus"),
    ("ME", "黑山", "Montenegro", "montenegro"),
    ("VE", "委内瑞拉", "Venezuela", "venezuela"),
    ("IS", "冰岛", "Iceland", "iceland"),
    ("BF", "布基纳法索", "Burkina Faso", "burkina faso"),
    ("BO", "玻利维亚", "Bolivia", "bolivia"),
    ("LY", "利比亚", "Libya", "libya"),
    ("GI", "直布罗陀", "Gibraltar", "gibraltar"),
    ("TG", "多哥", "Togo", "togo"),
    ("MG", "马达加斯加", "Madagascar", "madagascar"),
    ("GN", "几内亚", "Guinea", "guinea"),
    ("LR", "利比里亚", "Liberia", "liberia"),
    ("SZ", "斯威士兰", "Eswatini", "eswatini|swaziland"),
    ("MR", "毛里塔尼亚", "Mauritania", "mauritania"),
    ("JE", "泽西", "Jersey", "jersey"),
    ("GG", "根西", "Guernsey", "guernsey"),
    ("IM", "马恩岛", "Isle of Man", "isle of man"),
    ("GA", "加蓬", "Gabon", "gabon"),
    ("MW", "马拉维", "Malawi", "malawi"),
    ("ET", "埃塞俄比亚", "Ethiopia", "ethiopia"),
    ("AF", "阿富汗", "Afghanistan", "afghanistan"),
    ("AZ", "阿塞拜疆", "Azerbaijan", "azerbaijan"),
    ("DO", "多米尼加", "Dominican Republic", "república dominicana|republica dominicana"),
    ("GT", "危地马拉", "Guatemala", "guatemala"),
    ("MD", "摩尔多瓦", "Moldova", "moldávia|moldavia"),
    ("MM", "缅甸", "Myanmar", "myanmar|burma|myanmar (burma)"),
    ("TD", "乍得", "Chad", "chad"),
    ("ZW", "津巴布韦", "Zimbabwe", "zimbabwe"),
    ("MK", "北马其顿", "North Macedonia", "north macedonia|macedonia"),
    ("NP", "尼泊尔", "Nepal", "nepal"),
    ("GE", "格鲁吉亚", "Georgia", "georgia"),
    ("PF", "法属波利尼西亚", "French Polynesia", "french polynesia"),
    ("GL", "格陵兰", "Greenland", "greenland"),
    ("GW", "几内亚比绍", "Guinea-Bissau", "guinea-bissau"),
    ("IQ", "伊拉克", "Iraq", "iraq"),
    ("BA", "波黑", "Bosnia and Herzegovina", "bosnia and herzegovina|bosnia"),
    ("AL", "阿尔巴尼亚", "Albania", "albania"),
    ("LK", "斯里兰卡", "Sri Lanka", "sri lanka"),
    ("MC", "摩纳哥", "Monaco", "monaco"),
    ("ML", "马里", "Mali", "mali"),
    ("SS", "南苏丹", "South Sudan", "south sudan"),
    ("SL", "塞拉利昂", "Sierra Leone", "sierra leone"),
    ("ST", "圣多美和普林西比", "São Tomé and Príncipe", "sao tome and principe"),
    ("GQ", "赤道几内亚", "Equatorial Guinea", "equatorial guinea"),
    ("CV", "佛得角", "Cape Verde", "cape verde|cabo verde"),
    ("UZ", "乌兹别克斯坦", "Uzbekistan", "uzbekistan"),
    ("RE", "留尼汪", "La Réunion", "la reunion|reunion"),
]

ISO2ZH = {iso: zh for iso, zh, _, _ in COUNTRIES}
ISO2EN = {iso: en for iso, _, en, _ in COUNTRIES}

# 超大规模 / 云厂商（只用于地图点色，不做功率分类）
HYPERSCALE = [
    "amazon", "aws", "amazon web services", "microsoft", "azure", "google",
    "meta", "facebook", "oracle", "apple", "ibm", "alibaba", "alibaba cloud",
    "aliyun", "tencent", "tencent cloud", "huawei", "huawei cloud", "baidu",
    "bytedance", "volcano engine", "jd cloud", "kingsoft cloud",
]
HYPER_RE = re.compile(r"(?<![a-z])(" + "|".join(re.escape(x) for x in HYPERSCALE) + r")(?![a-z])")

# ---------------------------------------------------------------------------
# 中国省 / 市
# ---------------------------------------------------------------------------
PROVINCES = [
    ("Beijing", "北京", "beijing"),
    ("Tianjin", "天津", "tianjin"),
    ("Hebei", "河北", "hebei"),
    ("Shanxi", "山西", "shanxi"),
    ("Inner Mongolia", "内蒙古", "inner mongolia|nei mongol"),
    ("Liaoning", "辽宁", "liaoning"),
    ("Jilin", "吉林", "jilin"),
    ("Heilongjiang", "黑龙江", "heilongjiang"),
    ("Shanghai", "上海", "shanghai"),
    ("Jiangsu", "江苏", "jiangsu"),
    ("Zhejiang", "浙江", "zhejiang"),
    ("Anhui", "安徽", "anhui"),
    ("Fujian", "福建", "fujian"),
    ("Jiangxi", "江西", "jiangxi"),
    ("Shandong", "山东", "shandong"),
    ("Henan", "河南", "henan"),
    ("Hubei", "湖北", "hubei"),
    ("Hunan", "湖南", "hunan"),
    ("Guangdong", "广东", "guangdong"),
    ("Guangxi", "广西", "guangxi"),
    ("Hainan", "海南", "hainan"),
    ("Chongqing", "重庆", "chongqing"),
    ("Sichuan", "四川", "sichuan"),
    ("Guizhou", "贵州", "guizhou"),
    ("Yunnan", "云南", "yunnan"),
    ("Tibet", "西藏", "tibet|xizang"),
    ("Shaanxi", "陕西", "shaanxi"),
    ("Gansu", "甘肃", "gansu"),
    ("Qinghai", "青海", "qinghai"),
    ("Ningxia", "宁夏", "ningxia"),
    ("Xinjiang", "新疆", "xinjiang|uyghur"),
]
PROV_ZH = {en: zh for en, zh, _ in PROVINCES}
PROV_RX = [(en, re.compile(r"(?<![a-z])(" + alts + r")(?![a-z])")) for en, _, alts in PROVINCES]

# 城市：别名 -> (省, 中文市名)。多义城市单列。
CITIES = {
    # 直辖市
    "beijing": ("Beijing", "北京"), "shanghai": ("Shanghai", "上海"),
    "tianjin": ("Tianjin", "天津"), "chongqing": ("Chongqing", "重庆"),
    # 广东
    "guangzhou": ("Guangdong", "广州"), "shenzhen": ("Guangdong", "深圳"),
    "dongguan": ("Guangdong", "东莞"), "foshan": ("Guangdong", "佛山"),
    "zhuhai": ("Guangdong", "珠海"), "huizhou": ("Guangdong", "惠州"),
    "zhongshan": ("Guangdong", "中山"), "jiangmen": ("Guangdong", "江门"),
    "shantou": ("Guangdong", "汕头"), "zhaoqing": ("Guangdong", "肇庆"),
    "qingyuan": ("Guangdong", "清远"), "shaoguan": ("Guangdong", "韶关"),
    "meizhou": ("Guangdong", "梅州"), "heyuan": ("Guangdong", "河源"),
    "yangjiang": ("Guangdong", "阳江"), "maoming": ("Guangdong", "茂名"),
    "zhanjiang": ("Guangdong", "湛江"), "chaozhou": ("Guangdong", "潮州"),
    "jieyang": ("Guangdong", "揭阳"), "yunfu": ("Guangdong", "云浮"),
    "shanwei": ("Guangdong", "汕尾"),
    # 浙江
    "hangzhou": ("Zhejiang", "杭州"), "ningbo": ("Zhejiang", "宁波"),
    "wenzhou": ("Zhejiang", "温州"), "jiaxing": ("Zhejiang", "嘉兴"),
    "huzhou": ("Zhejiang", "湖州"), "shaoxing": ("Zhejiang", "绍兴"),
    "jinhua": ("Zhejiang", "金华"), "quzhou": ("Zhejiang", "衢州"),
    "zhoushan": ("Zhejiang", "舟山"), "lishui": ("Zhejiang", "丽水"),
    "yiwu": ("Zhejiang", "义乌"),
    # 江苏
    "nanjing": ("Jiangsu", "南京"), "wuxi": ("Jiangsu", "无锡"),
    "changzhou": ("Jiangsu", "常州"), "nantong": ("Jiangsu", "南通"),
    "lianyungang": ("Jiangsu", "连云港"), "huaian": ("Jiangsu", "淮安"),
    "yancheng": ("Jiangsu", "盐城"), "yangzhou": ("Jiangsu", "扬州"),
    "zhenjiang": ("Jiangsu", "镇江"), "suqian": ("Jiangsu", "宿迁"),
    "kunshan": ("Jiangsu", "昆山"), "taicang": ("Jiangsu", "太仓"),
    "jiangyin": ("Jiangsu", "江阴"), "zhangjiagang": ("Jiangsu", "张家港"),
    # 河北
    "shijiazhuang": ("Hebei", "石家庄"), "tangshan": ("Hebei", "唐山"),
    "qinhuangdao": ("Hebei", "秦皇岛"), "handan": ("Hebei", "邯郸"),
    "xingtai": ("Hebei", "邢台"), "baoding": ("Hebei", "保定"),
    "zhangjiakou": ("Hebei", "张家口"), "chengde": ("Hebei", "承德"),
    "cangzhou": ("Hebei", "沧州"), "langfang": ("Hebei", "廊坊"),
    "hengshui": ("Hebei", "衡水"), "zhuozhou": ("Hebei", "涿州"),
    "sanhe": ("Hebei", "三河"),
    # 山西
    "taiyuan": ("Shanxi", "太原"), "datong": ("Shanxi", "大同"),
    "yangquan": ("Shanxi", "阳泉"), "changzhi": ("Shanxi", "长治"),
    "jincheng": ("Shanxi", "晋城"), "shuozhou": ("Shanxi", "朔州"),
    "jinzhong": ("Shanxi", "晋中"), "yuncheng": ("Shanxi", "运城"),
    "xinzhou": ("Shanxi", "忻州"), "linfen": ("Shanxi", "临汾"),
    "lvliang": ("Shanxi", "吕梁"),
    # 内蒙古
    "hohhot": ("Inner Mongolia", "呼和浩特"), "baotou": ("Inner Mongolia", "包头"),
    "wuhai": ("Inner Mongolia", "乌海"), "chifeng": ("Inner Mongolia", "赤峰"),
    "tongliao": ("Inner Mongolia", "通辽"), "ordos": ("Inner Mongolia", "鄂尔多斯"),
    "hulunbuir": ("Inner Mongolia", "呼伦贝尔"), "bayannur": ("Inner Mongolia", "巴彦淖尔"),
    "ulanqab": ("Inner Mongolia", "乌兰察布"),
    # 辽宁
    "shenyang": ("Liaoning", "沈阳"), "dalian": ("Liaoning", "大连"),
    "anshan": ("Liaoning", "鞍山"), "fushun": ("Liaoning", "抚顺"),
    "benxi": ("Liaoning", "本溪"), "dandong": ("Liaoning", "丹东"),
    "jinzhou": ("Liaoning", "锦州"), "yingkou": ("Liaoning", "营口"),
    "fuxin": ("Liaoning", "阜新"), "liaoyang": ("Liaoning", "辽阳"),
    "panjin": ("Liaoning", "盘锦"), "tieling": ("Liaoning", "铁岭"),
    "huludao": ("Liaoning", "葫芦岛"),
    # 吉林
    "changchun": ("Jilin", "长春"), "siping": ("Jilin", "四平"),
    "liaoyuan": ("Jilin", "辽源"), "tonghua": ("Jilin", "通化"),
    "baishan": ("Jilin", "白山"), "songyuan": ("Jilin", "松原"),
    "baicheng": ("Jilin", "白城"), "yanbian": ("Jilin", "延边"),
    # 黑龙江
    "harbin": ("Heilongjiang", "哈尔滨"), "qiqihar": ("Heilongjiang", "齐齐哈尔"),
    "jixi": ("Heilongjiang", "鸡西"), "hegang": ("Heilongjiang", "鹤岗"),
    "shuangyashan": ("Heilongjiang", "双鸭山"), "daqing": ("Heilongjiang", "大庆"),
    "yichun": ("Heilongjiang", "伊春"), "jiamusi": ("Heilongjiang", "佳木斯"),
    "qitaihe": ("Heilongjiang", "七台河"), "mudanjiang": ("Heilongjiang", "牡丹江"),
    "heihe": ("Heilongjiang", "黑河"), "suihua": ("Heilongjiang", "绥化"),
    # 安徽
    "hefei": ("Anhui", "合肥"), "wuhu": ("Anhui", "芜湖"),
    "bengbu": ("Anhui", "蚌埠"), "huainan": ("Anhui", "淮南"),
    "maanshan": ("Anhui", "马鞍山"), "huaibei": ("Anhui", "淮北"),
    "tongling": ("Anhui", "铜陵"), "anqing": ("Anhui", "安庆"),
    "huangshan": ("Anhui", "黄山"), "chuzhou": ("Anhui", "滁州"),
    "fuyang": ("Anhui", "阜阳"), "luan": ("Anhui", "六安"),
    "bozhou": ("Anhui", "亳州"), "chizhou": ("Anhui", "池州"),
    "xuancheng": ("Anhui", "宣城"),
    # 福建
    "xiamen": ("Fujian", "厦门"), "putian": ("Fujian", "莆田"),
    "sanming": ("Fujian", "三明"), "quanzhou": ("Fujian", "泉州"),
    "zhangzhou": ("Fujian", "漳州"), "nanping": ("Fujian", "南平"),
    "longyan": ("Fujian", "龙岩"), "ningde": ("Fujian", "宁德"),
    # 江西
    "nanchang": ("Jiangxi", "南昌"), "jingdezhen": ("Jiangxi", "景德镇"),
    "pingxiang": ("Jiangxi", "萍乡"), "jiujiang": ("Jiangxi", "九江"),
    "xinyu": ("Jiangxi", "新余"), "yingtan": ("Jiangxi", "鹰潭"),
    "ganzhou": ("Jiangxi", "赣州"), "jian": ("Jiangxi", "吉安"),
    "shangrao": ("Jiangxi", "上饶"),
    # 山东
    "jinan": ("Shandong", "济南"), "qingdao": ("Shandong", "青岛"),
    "zibo": ("Shandong", "淄博"), "zaozhuang": ("Shandong", "枣庄"),
    "dongying": ("Shandong", "东营"), "yantai": ("Shandong", "烟台"),
    "weifang": ("Shandong", "潍坊"), "jining": ("Shandong", "济宁"),
    "tai an": ("Shandong", "泰安"), "weihai": ("Shandong", "威海"),
    "rizhao": ("Shandong", "日照"), "linyi": ("Shandong", "临沂"),
    "dezhou": ("Shandong", "德州"), "liaocheng": ("Shandong", "聊城"),
    "binzhou": ("Shandong", "滨州"), "heze": ("Shandong", "菏泽"),
    # 河南
    "zhengzhou": ("Henan", "郑州"), "kaifeng": ("Henan", "开封"),
    "luoyang": ("Henan", "洛阳"), "pingdingshan": ("Henan", "平顶山"),
    "anyang": ("Henan", "安阳"), "hebi": ("Henan", "鹤壁"),
    "xinxiang": ("Henan", "新乡"), "jiaozuo": ("Henan", "焦作"),
    "puyang": ("Henan", "濮阳"), "xuchang": ("Henan", "许昌"),
    "luohe": ("Henan", "漯河"), "sanmenxia": ("Henan", "三门峡"),
    "nanyang": ("Henan", "南阳"), "shangqiu": ("Henan", "商丘"),
    "xinyang": ("Henan", "信阳"), "zhoukou": ("Henan", "周口"),
    "zhumadian": ("Henan", "驻马店"),
    # 湖北
    "wuhan": ("Hubei", "武汉"), "huangshi": ("Hubei", "黄石"),
    "shiyan": ("Hubei", "十堰"), "yichang": ("Hubei", "宜昌"),
    "xiangyang": ("Hubei", "襄阳"), "ezhou": ("Hubei", "鄂州"),
    "jingmen": ("Hubei", "荆门"), "xiaogan": ("Hubei", "孝感"),
    "jingzhou": ("Hubei", "荆州"), "huanggang": ("Hubei", "黄冈"),
    "xianning": ("Hubei", "咸宁"), "suizhou": ("Hubei", "随州"),
    "xiantao": ("Hubei", "仙桃"), "qianjiang": ("Hubei", "潜江"),
    "tianmen": ("Hubei", "天门"), "enshi": ("Hubei", "恩施"),
    # 湖南
    "changsha": ("Hunan", "长沙"), "zhuzhou": ("Hunan", "株洲"),
    "xiangtan": ("Hunan", "湘潭"), "hengyang": ("Hunan", "衡阳"),
    "shaoyang": ("Hunan", "邵阳"), "yueyang": ("Hunan", "岳阳"),
    "changde": ("Hunan", "常德"), "zhangjiajie": ("Hunan", "张家界"),
    "yiyang": ("Hunan", "益阳"), "chenzhou": ("Hunan", "郴州"),
    "yongzhou": ("Hunan", "永州"), "huaihua": ("Hunan", "怀化"),
    "loudi": ("Hunan", "娄底"),
    # 广西
    "nanning": ("Guangxi", "南宁"), "liuzhou": ("Guangxi", "柳州"),
    "guilin": ("Guangxi", "桂林"), "wuzhou": ("Guangxi", "梧州"),
    "beihai": ("Guangxi", "北海"), "fangchenggang": ("Guangxi", "防城港"),
    "qinzhou": ("Guangxi", "钦州"), "guigang": ("Guangxi", "贵港"),
    "baise": ("Guangxi", "百色"), "hezhou": ("Guangxi", "贺州"),
    "hechi": ("Guangxi", "河池"), "laibin": ("Guangxi", "来宾"),
    "chongzuo": ("Guangxi", "崇左"),
    # 海南
    "haikou": ("Hainan", "海口"), "sanya": ("Hainan", "三亚"),
    # 四川
    "chengdu": ("Sichuan", "成都"), "zigong": ("Sichuan", "自贡"),
    "panzhihua": ("Sichuan", "攀枝花"), "luzhou": ("Sichuan", "泸州"),
    "deyang": ("Sichuan", "德阳"), "mianyang": ("Sichuan", "绵阳"),
    "guangyuan": ("Sichuan", "广元"), "suining": ("Sichuan", "遂宁"),
    "neijiang": ("Sichuan", "内江"), "leshan": ("Sichuan", "乐山"),
    "nanchong": ("Sichuan", "南充"), "meishan": ("Sichuan", "眉山"),
    "yibin": ("Sichuan", "宜宾"), "guangan": ("Sichuan", "广安"),
    "dazhou": ("Sichuan", "达州"), "yaan": ("Sichuan", "雅安"),
    "bazhong": ("Sichuan", "巴中"), "ziyang": ("Sichuan", "资阳"),
    "liangshan": ("Sichuan", "凉山"),
    # 贵州
    "guiyang": ("Guizhou", "贵阳"), "liupanshui": ("Guizhou", "六盘水"),
    "zunyi": ("Guizhou", "遵义"), "anshun": ("Guizhou", "安顺"),
    "bijie": ("Guizhou", "毕节"), "tongren": ("Guizhou", "铜仁"),
    "kaili": ("Guizhou", "凯里"),
    # 云南
    "kunming": ("Yunnan", "昆明"), "qujing": ("Yunnan", "曲靖"),
    "yuxi": ("Yunnan", "玉溪"), "baoshan": ("Yunnan", "保山"),
    "zhaotong": ("Yunnan", "昭通"), "lijiang": ("Yunnan", "丽江"),
    "pu er": ("Yunnan", "普洱"), "lincang": ("Yunnan", "临沧"),
    "dali": ("Yunnan", "大理"), "xishuangbanna": ("Yunnan", "西双版纳"),
    # 西藏
    "lhasa": ("Tibet", "拉萨"), "shigatse": ("Tibet", "日喀则"),
    # 陕西
    "xian": ("Shaanxi", "西安"), "tongchuan": ("Shaanxi", "铜川"),
    "baoji": ("Shaanxi", "宝鸡"), "xianyang": ("Shaanxi", "咸阳"),
    "weinan": ("Shaanxi", "渭南"), "yanan": ("Shaanxi", "延安"),
    "hanzhong": ("Shaanxi", "汉中"), "ankang": ("Shaanxi", "安康"),
    "shangluo": ("Shaanxi", "商洛"),
    # 甘肃
    "lanzhou": ("Gansu", "兰州"), "jiayuguan": ("Gansu", "嘉峪关"),
    "jinchang": ("Gansu", "金昌"), "baiyin": ("Gansu", "白银"),
    "tianshui": ("Gansu", "天水"), "wuwei": ("Gansu", "武威"),
    "zhangye": ("Gansu", "张掖"), "pingliang": ("Gansu", "平凉"),
    "jiuquan": ("Gansu", "酒泉"), "qingyang": ("Gansu", "庆阳"),
    "dingxi": ("Gansu", "定西"), "longnan": ("Gansu", "陇南"),
    # 青海
    "xining": ("Qinghai", "西宁"), "haidong": ("Qinghai", "海东"),
    # 宁夏
    "yinchuan": ("Ningxia", "银川"), "shizuishan": ("Ningxia", "石嘴山"),
    "wuzhong": ("Ningxia", "吴忠"), "guyuan": ("Ningxia", "固原"),
    "zhongwei": ("Ningxia", "中卫"),
    # 新疆
    "urumqi": ("Xinjiang", "乌鲁木齐"), "karamay": ("Xinjiang", "克拉玛依"),
    "turpan": ("Xinjiang", "吐鲁番"), "hami": ("Xinjiang", "哈密"),
    "kashgar": ("Xinjiang", "喀什"), "hutubi": ("Xinjiang", "呼图壁"),
    "changji": ("Xinjiang", "昌吉"), "korla": ("Xinjiang", "库尔勒"),
    "aksu": ("Xinjiang", "阿克苏"), "hotan": ("Xinjiang", "和田"),
    "ili": ("Xinjiang", "伊犁"),
}
# 重名城市：先看地址里有没有写省，否则按常见归属
AMBIG = {
    "suzhou": [("Jiangsu", "苏州"), ("Anhui", "宿州")],
    "taizhou": [("Jiangsu", "泰州"), ("Zhejiang", "台州")],
    "yulin": [("Shaanxi", "榆林"), ("Guangxi", "玉林")],
    "fuzhou": [("Fujian", "福州"), ("Jiangxi", "抚州")],
    "yichun": [("Jiangxi", "宜春"), ("Heilongjiang", "伊春")],
    "chaoyang": [("Liaoning", "朝阳")],
}
CITY_RX = [(k, re.compile(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])")) for k in list(CITIES) + list(AMBIG)]

# ---------------------------------------------------------------------------
# 模型厂商国籍
# ---------------------------------------------------------------------------
VENDOR_COUNTRY = {
    "openai": "US", "anthropic": "US", "google": "US", "meta": "US", "xai": "US",
    "thinking machines lab": "US", "nvidia": "US", "ibm": "US", "reflection": "US",
    "alibaba": "CN", "deepseek": "CN", "moonshot ai": "CN", "z.ai": "CN",
    "xiaomi": "CN", "minimax": "CN", "tencent": "CN", "stepfun": "CN",
    "mistral ai": "FR",
}


def now_bj():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def fetch(url, dest, offline):
    if offline and os.path.exists(dest):
        print("cached", dest)
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "DCMap/1.0 (data builder)"})
    print("fetch", url)
    with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".tmp", "wb") as f:
        f.write(r.read())
    os.replace(dest + ".tmp", dest)


def fetch_json(url, offline, dest):
    fetch(url, dest, offline)
    with open(dest, encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ")
    s = re.sub(r"[\u3000-\u9fff]+", " ", s)      # 中文碎片
    s = re.sub(r"[^a-z0-9'’\- ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -'")
    s = re.sub(r"\s+\d{3,}$", "", s)              # 末尾邮编
    return s.strip()


ALIAS = {}
for iso, zh, en, extra in COUNTRIES:
    for name in [en] + extra.split("|"):
        ALIAS[norm(name)] = iso
CANON = [(norm(en), iso) for iso, _, en, _ in COUNTRIES]
CANON_KEYS = [n for n, _ in CANON]

# 非拉丁文字的国家名（norm 会把它们清空，先按原文精确匹配）
RAW_ALIAS = {
    "Россия": "RU",
    "България": "BG",
    "香港": "HK",
    "日本": "JP",
    "中国": "CN",
    "대한민국": "KR",
}


def canon_country(raw):
    n = norm(raw)
    raw_key = (raw or "").strip()
    if raw_key in RAW_ALIAS:
        return RAW_ALIAS[raw_key]
    if not n:
        return None
    if n in ALIAS:
        return ALIAS[n]
    # "singapore 627753" / "taiwan 114" 之类：命中前缀即算
    for key, iso in CANON:
        if n == key or n.startswith(key + " "):
            return iso
    hit = difflib.get_close_matches(n, CANON_KEYS, n=1, cutoff=0.88)
    if hit:
        return dict(CANON)[hit[0]]
    return None


def parse_china(rows):
    prov = collections.defaultdict(lambda: collections.defaultdict(int))
    unmatched = 0
    detail = {}
    for r in rows:
        text = norm(" ".join([r["name"], r["city"], r["address"]]))
        # 1) 地址里写明省份
        p = None
        for en, rx in PROV_RX:
            if rx.search(text):
                p = en
                break
        # 2) 城市
        city = None
        city_prov = None
        for key, rx in CITY_RX:
            if not rx.search(text):
                continue
            if key in AMBIG:
                options = AMBIG[key]
                match = [o for o in options if o[0] == p]
                if match:
                    city_prov, city = match[0]
                elif city is None:
                    city_prov, city = options[0]
            else:
                cp, cz = CITIES[key]
                if city is None or cp == p:
                    city_prov, city = cp, cz
        if p is None and city_prov is not None:
            p = city_prov
        if p is None:
            unmatched += 1
            continue
        if city is None or city_prov != p:
            city = "未标明城市"
        prov[p][city] += 1
        detail.setdefault(p, []).append(r)
    provinces = []
    for en in PROV_ZH:
        if en not in prov:
            continue
        cities = [{"n": c, "count": n} for c, n in
                  sorted(prov[en].items(), key=lambda kv: (-kv[1], kv[0]))]
        provinces.append({"n": PROV_ZH[en], "count": sum(prov[en].values()), "cities": cities})
    provinces.sort(key=lambda x: (-x["count"], x["n"]))
    return provinces, unmatched, detail


def parse_models(md):
    updated = ""
    m = re.search(r"更新：(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", md)
    if m:
        updated = m.group(1)
    models = []
    for line in md.splitlines():
        mm = re.match(r"\|\s*(\d+)\s*\|\s*\[([^\]]+)\]\([^)]*\)\s*\|\s*([^|]+?)\s*\|\s*([\d.]+)\s*\|\s*([\d-]+)\s*\|", line)
        if not mm:
            continue
        rank, name, vendor, score, date = mm.groups()
        models.append({
            "r": int(rank), "n": name.strip(), "v": vendor.strip(),
            "vc": VENDOR_COUNTRY.get(vendor.strip().lower(), ""),
            "s": float(score), "d": date,
        })
    return updated, models


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "snapshot"))
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    raw = os.path.abspath(args.raw)
    out = os.path.abspath(args.out)
    os.makedirs(raw, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    fetch(ATLAS_CSV, os.path.join(raw, "datacenters.csv"), args.offline)
    fetch(ATLAS_GEO, os.path.join(raw, "datacenters.geojson"), args.offline)
    fetch(EPOCH_ZIP, os.path.join(raw, "data_centers.zip"), args.offline)
    fetch(AIHOT_MD, os.path.join(raw, "leaderboard.md"), args.offline)

    rows = list(csv.DictReader(open(os.path.join(raw, "datacenters.csv"), encoding="utf-8")))
    with open(os.path.join(raw, "datacenters.geojson"), encoding="utf-8") as f:
        geo = json.load(f)
    with zipfile.ZipFile(os.path.join(raw, "data_centers.zip")) as z:
        epoch = list(csv.DictReader(io.TextIOWrapper(z.open("data_centers.csv"), encoding="utf-8")))
    md = open(os.path.join(raw, "leaderboard.md"), encoding="utf-8").read()

    # 逐国计数
    counts = collections.Counter()
    hs = collections.Counter()
    unmapped = collections.Counter()
    for r in rows:
        iso = canon_country(r["country"])
        if iso is None:
            key = (r["country"] or "(空)").strip()
            if key.lower() not in ("", "unknown"):
                unmapped[key] += 1
            continue
        counts[iso] += 1
        if HYPER_RE.search((r["company"] or "").lower()):
            hs[iso] += 1

    # Epoch 国家（名称 -> ISO）
    ai = collections.Counter()
    ai_sites = collections.defaultdict(list)
    for e in epoch:
        iso = canon_country(e["Country"])
        if iso:
            ai[iso] += 1
            ai_sites[iso].append(e["Name"].strip())

    # 地图点 + 国家重心
    points = []
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for f in geo.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        p = f.get("properties") or {}
        kind = 1 if HYPER_RE.search((p.get("company") or "").lower()) else 0
        points.append([round(lon, 3), round(lat, 3), kind])
        iso = canon_country(p.get("country"))
        if iso:
            a = acc[iso]
            a[0] += lon
            a[1] += lat
            a[2] += 1

    countries = []
    for iso, n in counts.most_common():
        a = acc.get(iso)
        countries.append({
            "c": iso, "n": ISO2ZH.get(iso, iso), "e": ISO2EN.get(iso, iso),
            "t": n, "hs": hs.get(iso, 0), "ai": ai.get(iso, 0),
            "lat": round(a[1] / a[2], 3) if a else None,
            "lon": round(a[0] / a[2], 3) if a else None,
            "sites": ai_sites.get(iso, [])[:8],
        })

    china_rows = [r for r in rows if canon_country(r["country"]) == "CN"]
    provinces, cn_unmatched, _ = parse_china(china_rows)

    updated, models = parse_models(md)
    if len(models) < 50:
        raise SystemExit(f"模型榜解析异常：{len(models)} 条")
    if len(countries) < 100:
        raise SystemExit(f"国家数异常：{len(countries)}")
    if len(points) < 5000:
        raise SystemExit(f"点位异常：{len(points)}")

    # ATLAS 仓库更新时间（失败不影响快照）
    atlas_updated = ""
    try:
        meta_api = fetch_json(ATLAS_API, args.offline, os.path.join(raw, "atlas_repo.json"))
        atlas_updated = (meta_api.get("pushed_at") or "")[:10]
    except Exception as e:
        print("atlas repo meta failed:", e)

    now = now_bj()
    by_country = sum(counts.values())
    snapshot = {
        "v": SNAPSHOT_VERSION,
        "cutoff": now.strftime("%Y-%m-%d"),
        "meta": {
            "generatedAt": now.strftime("%Y-%m-%d %H:%M"),
            "atlasUpdated": atlas_updated,
            "atlasTotal": len(rows),
            "mapped": by_country,
            "unmapped": len(rows) - by_country,
            "countryCount": len(countries),
            "points": len(points),
            "chinaTotal": len(china_rows),
            "models": len(models),
            "sources": [
                "ATLAS · data-center-map.com（收录口径）",
                "Epoch AI · AI data centers（CC BY 4.0）",
                "AIHOT 模型榜（MIT）",
            ],
        },
        "countries": countries,
        "points": points,
        "china": {
            "total": len(china_rows),
            "unmatched": cn_unmatched,
            "provinces": provinces,
        },
        "models": {
            "updated": updated,
            "source": "AIHOT",
            "list": models,
        },
    }

    s = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    path = os.path.join(out, "snapshot.json.gz")
    with gzip.open(path, "wb", compresslevel=9) as f:
        f.write(s.encode("utf-8"))

    info = {
        "cutoff": snapshot["cutoff"],
        "atlasTotal": len(rows),
        "mapped": by_country,
        "unmapped": len(rows) - by_country,
        "topUnmapped": unmapped.most_common(12),
        "countries": len(countries),
        "points": len(points),
        "hyperscalePoints": sum(1 for p in points if p[2] == 1),
        "chinaTotal": len(china_rows),
        "chinaProvinces": len(provinces),
        "chinaUnmatched": cn_unmatched,
        "chinaTop": [(p["n"], p["count"]) for p in provinces[:8]],
        "models": len(models),
        "modelsUpdated": updated,
        "bytes": os.path.getsize(path),
    }
    with open(os.path.join(out, "build_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
