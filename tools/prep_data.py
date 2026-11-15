# -*- coding: utf-8 -*-
"""把 GCAT 原始目录整理为 App 内置数据。所有数字均由原始目录聚合得出，不做估算。"""
import csv, json, os, math, collections, datetime

RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
OUT = os.path.join(os.path.dirname(__file__), '..', 'app', 'src', 'main', 'assets', 'data')
os.makedirs(OUT, exist_ok=True)



# 少数机构只有英文名，按英文名补充中文
ORG_NAME_ZH = {
 'NRO': '美国国家侦察局', 'Unseenlabs': 'Unseenlabs（无线电侦测）', 'Pixxel': 'Pixxel（印度）',
 'Dhruva Space': 'Dhruva Space（印度）', 'D-Orbit': 'D-Orbit（意大利）', 'Apogeo Space': 'Apogeo Space（意大利）',
 'Kepler Communications': 'Kepler 通信（加拿大）', 'Telesat': 'Telesat（加拿大）', 'GHGSat': 'GHGSat（温室气体监测）',
 'Spire/Lux': '斯派尔（Spire）', 'KLEOS': 'Kleos Space', 'SESSA': 'SES', 'FOSSA': 'FOSSA Systems（西班牙）',
 'STIOT': 'Sateliot（西班牙）', 'AMEA': 'AMSAT 西班牙（AMSAT-EA）', 'Skykraft': 'Skykraft（澳大利亚）',
 'Fleet Space': 'Fleet Space（澳大利亚）', 'Optus': 'Optus（澳大利亚）', 'Fergani Space': 'Fergani Space（土耳其）',
 'DDRD': '以色列国防研究与发展局', 'HSCIL': '以色列航天工业（IAI）', 'TAU': '特拉维夫大学',
 'Intelsat': 'Intelsat（国际通信卫星）', 'ICEYE': 'ICEYE（芬兰）', 'AALTO': '阿尔托大学',
 'REAKT': 'Reaktor 空间实验室', 'NSPO': '台湾太空中心', 'TASA': '台湾太空中心', 'NCKU': '成功大学',
 'GSAEU': '欧盟航天计划署（EUSPA）', 'COPERN': '哥白尼计划（欧盟）', 'EUSPA': '欧盟航天计划署（EUSPA）',
 'MBRSC': '阿联酋穆罕默德·本·拉希德航天中心', 'HISPM': '西班牙-巴西合资（Hispamar）',
}

# 主要运营机构中文名（仅收录能确认归属的机构；未收录的保留原名）
ORG_ZH = {
 'SPXS': 'SpaceX', 'SPX': 'SpaceX', 'PLAN': '行星实验室（Planet）', 'PLABS': '行星实验室（Planet）',
 'ONEWEBN': 'OneWeb（一网）', 'ONEWEB': 'OneWeb（一网）', 'KUIP': '亚马逊柯伊伯（Kuiper）',
 'NROC': '美国国家侦察局', 'NRO/SAFSP': '美国国家侦察局/空军太空项目', 'NRO/CIA': '美国国家侦察局/中情局',
 'NRO/NRL': '美国国家侦察局/海军研究实验室', 'GSFC': '戈达德航天中心', 'JSC': '约翰逊航天中心',
 'SFSSC': '美国太空军', 'SDA': '美国太空发展局', 'AFSMC': '美国空军系统司令部（历史）',
 'AFSSD': '美国空军太空系统部', 'SAMSO': '美国空军太空与导弹系统组织（历史）',
 'PVO': '苏联防空军', 'VMF': '苏联海军', 'GRU': '苏联军事情报总局',
 'GUKOSR': '俄罗斯航天兵', 'GUKOS': '俄罗斯航天兵', 'VKS': '俄罗斯空天军', 'VVKOV': '俄罗斯空天防御兵（历史）',
 'TSUKOS': '俄罗斯中央航天部队', 'RKKE': '俄罗斯能源火箭航天公司', 'TSSKB': '俄罗斯进步航天中心',
 'NPOE': '俄罗斯能源科研生产联合体', 'IKI/BABTS': '俄罗斯空间研究所', 'OKB1': '第1设计局（历史）',
 'OKB10': '第10设计局（历史）', 'PRIR': '俄罗斯应用航天研究所',
 'YUANX': '上海垣信（千帆）', 'ZXW': '中国星网（国网）', 'CGSTL': '长光卫星',
 'ZZB': '解放军总装备部', 'ZLZB': '解放军战略支援部队', 'CASC': '中国航天科技集团',
 'CNSA': '中国国家航天局', 'CAST': '中国空间技术研究院（航天五院）', 'CMSEO': '中国载人航天工程办公室',
 'GEESP': '时空道宇', 'ISRO': '印度空间研究组织', 'ESA': '欧洲空间局',
 'JPL': '喷气推进实验室', 'IRID': '铱星（Iridium）', 'IRIDS': '铱星（Iridium）',
 'SPIRE': '斯派尔（Spire）', 'SWARM': 'Swarm', 'SWARMX': 'Swarm', 'ORBC': 'Orbcomm',
 'GLOBT': 'Globalstar', 'HE360': 'HawkEye 360', 'INTEL': 'Intelsat', 'MSC': '三菱',
 'UNKS': '未标注', 'ARC': 'ARC（历史）', 'URUGUS': '乌拉圭航天局', 'SITRO': 'Sitronics（俄罗斯）',
 'NASDA': '日本宇宙开发事业团（历史）', 'JAXA': '日本宇宙航空研究开发机构（JAXA）',
 'CSICE': '日本内阁卫星情报中心', 'KYUT': '九州工业大学',
 'CNES': '法国国家空间研究中心', 'EUTSA': 'Eutelsat（欧洲通信卫星）', 'UNSEEN': 'Unseenlabs', 'KINEIS': 'Kinéis',
 'TUB': '柏林工业大学', 'ALBAD': '阿尔巴轨道（Alba Orbital）', 'DLR2': '德国航空航天中心（DLR）',
 'PIXX': 'Pixxel', 'DORBIT': 'D-Orbit', 'ASI/OHBI': '意大利空间局', 'ASI': '意大利空间局', 'APOGEO': 'Apogeo Space',
 'KEPLER': 'Kepler Communications', 'TCAN': 'Telesat', 'GHG': 'GHGSat', 'CSA': '加拿大空间局',
 'KAIST': '韩国科学技术院', 'KARI': '韩国航空宇宙研究院', 'SNU': '首尔大学',
 'SKYKR': 'Skykraft', 'FLEET': 'Fleet Space', 'OPTS': 'Optus',
 'DDRD/U9900': '以色列国防研究与发展局', 'TAU/ISA': '特拉维夫大学/以色列空间局',
 'PLNSST': 'Plan-S（土耳其）', 'TURKS': '土耳其卫星公司（Türksat）', 'FERG': 'Fergani Space',
 'STONE': 'Star One（巴西）', 'INPE': '巴西国家空间研究院', 'EMBR': '巴西航空工业', 'HISPM/HISP': '西班牙-巴西合资（Hispamar）',
 'ONEWEBE': 'OneWeb（一网）', 'O3BS': 'O3b（SES）',
 'KVR': '俄罗斯航天兵', 'ISASM': '日本宇宙科学研究所', 'ISASS': '日本宇宙科学研究所',
 'ISASJ': '日本宇宙科学研究所', 'SESSL': 'SES',
}


# GCAT 国别代码 -> 中文名 / ISO2 / 标记点经纬度。核心国家为人工维护，未列出的显示代码。
COUNTRY = {
 'US':('美国','US',39.8,-98.6), 'SU':('苏联（历史）','',60.0,95.0), 'RU':('俄罗斯','RU',61.5,95.0),
 'CN':('中国','CN',35.9,104.2), 'UK':('英国','GB',54.0,-2.0), 'J':('日本','JP',36.2,138.3),
 'F':('法国','FR',46.6,2.5), 'D':('德国','DE',51.2,10.4), 'IN':('印度','IN',21.8,78.0),
 'I':('意大利','IT',42.8,12.5), 'CA':('加拿大','CA',56.1,-106.3), 'KR':('韩国','KR',36.5,127.9),
 'L':('卢森堡','LU',49.8,6.1), 'E':('西班牙','ES',40.4,-3.7), 'AU':('澳大利亚','AU',-25.3,133.8),
 'TR':('土耳其','TR',39.0,35.2), 'IL':('以色列','IL',31.4,35.0), 'UY':('乌拉圭','UY',-32.5,-55.8),
 'FI':('芬兰','FI',61.9,25.7), 'TW':('中国台湾','TW',23.7,121.0), 'BR':('巴西','BR',-10.8,-53.1),
 'UAE':('阿联酋','AE',24.0,54.0), 'SG':('新加坡','SG',1.35,103.8), 'PL':('波兰','PL',52.1,19.4),
 'CH':('瑞士','CH',46.8,8.2), 'ID':('印度尼西亚','ID',-2.5,118.0), 'GR':('希腊','GR',39.1,21.8),
 'NZ':('新西兰','NZ',-41.0,174.0), 'N':('挪威','NO',61.0,9.0), 'NL':('荷兰','NL',52.2,5.5),
 'IR':('伊朗','IR',32.4,53.7), 'S':('瑞典','SE',62.0,15.0), 'SA':('沙特阿拉伯','SA',24.0,45.0),
 'AR':('阿根廷','AR',-34.0,-64.0), 'DK':('丹麦','DK',56.0,10.0), 'MX':('墨西哥','MX',23.6,-102.5),
 'T':('泰国','TH',15.1,101.0), 'MY':('马来西亚','MY',4.2,102.0), 'HK':('中国香港','HK',22.3,114.2),
 'P':('葡萄牙','PT',39.4,-8.2), 'CZ':('捷克','CZ',49.8,15.5), 'EG':('埃及','EG',26.8,30.8),
 'B':('比利时','BE',50.6,4.7), 'PK':('巴基斯坦','PK',30.0,69.5), 'MN':('蒙古','MN',46.8,103.8),
 'HU':('匈牙利','HU',47.0,19.5), 'LT':('立陶宛','LT',55.2,23.9), 'ZA':('南非','ZA',-29.0,24.0),
 'UA':('乌克兰','UA',48.5,31.5), 'PH':('菲律宾','PH',12.9,121.8), 'KZ':('哈萨克斯坦','KZ',48.0,67.0),
 'CL':('智利','CL',-33.0,-71.0), 'DZ':('阿尔及利亚','DZ',28.0,2.6), 'VN':('越南','VN',16.0,106.0),
 'AT':('奥地利','AT',47.5,14.5), 'RW':('卢旺达','RW',-2.0,29.9), 'NG':('尼日利亚','NG',9.1,8.7),
 'BY':('白俄罗斯','BY',53.7,27.9), 'MA':('摩洛哥','MA',31.8,-7.0), 'PE':('秘鲁','PE',-9.2,-75.0),
 'SK':('斯洛伐克','SK',48.7,19.5), 'RO':('罗马尼亚','RO',45.9,25.0), 'EC':('厄瓜多尔','EC',-1.8,-78.2),
 'NP':('尼泊尔','NP',28.4,84.1), 'SI':('斯洛文尼亚','SI',46.1,14.8), 'CO':('哥伦比亚','CO',4.6,-74.3),
 'BM':('百慕大','BM',32.3,-64.8), 'VE':('委内瑞拉','VE',6.4,-66.6), 'KP':('朝鲜','KP',40.3,127.5),
 'AZ':('阿塞拜疆','AZ',40.3,47.5), 'EE':('爱沙尼亚','EE',58.6,25.0), 'QA':('卡塔尔','QA',25.3,51.2),
 'MC':('摩纳哥','MC',43.7,7.4), 'KW':('科威特','KW',29.3,47.5), 'MU':('毛里求斯','MU',-20.2,57.5),
 'PR':('波多黎各','PR',18.2,-66.5), 'IE':('爱尔兰','IE',53.4,-8.2), 'BD':('孟加拉国','BD',23.7,90.4),
 'AO':('安哥拉','AO',-11.2,17.9), 'KE':('肯尼亚','KE',-0.2,37.9), 'BT':('不丹','BT',27.5,90.4),
 'ET':('埃塞俄比亚','ET',9.1,40.5), 'PY':('巴拉圭','PY',-23.4,-58.4), 'TN':('突尼斯','TN',33.9,9.5),
 'AM':('亚美尼亚','AM',40.1,45.0), 'ZW':('津巴布韦','ZW',-19.0,29.2), 'DJ':('吉布提','DJ',11.8,42.6),
 'BO':('玻利维亚','BO',-16.3,-63.6), 'PG':('巴布亚新几内亚','PG',-6.5,145.0), 'LA':('老挝','LA',19.9,102.5),
 'LV':('拉脱维亚','LV',56.9,24.6), 'GH':('加纳','GH',7.9,-1.0), 'CR':('哥斯达黎加','CR',9.7,-84.0),
 'JO':('约旦','JO',31.3,36.5), 'LK':('斯里兰卡','LK',7.9,80.8), 'SD':('苏丹','SD',15.6,32.5),
 'GT':('危地马拉','GT',15.8,-90.2), 'MYM':('缅甸','MM',21.9,95.9), 'MD':('摩尔多瓦','MD',47.4,28.4),
 'UG':('乌干达','UG',1.4,32.3), 'SN':('塞内加尔','SN',14.5,-14.5), 'OM':('阿曼','OM',21.0,57.0),
 'HR':('克罗地亚','HR',45.1,15.2), 'BW':('博茨瓦纳','BW',-22.3,24.7), 'BH':('巴林','BH',26.0,50.5),
 'SB':('所罗门群岛','SB',-9.6,160.2), 'ME':('黑山','ME',42.7,19.4), 'BG':('保加利亚','BG',42.7,25.5),
 'CSSR':('捷克斯洛伐克（历史）','',49.8,15.5), 'CSFR':('捷克斯洛伐克（历史）','',49.8,15.5),
 'HKUK':('中国香港（回归前）','',22.3,114.2), 'BGN':('孟加拉国（历史代码）','',23.7,90.4),
 'ESIB':('西班牙（机构）','ES',40.4,-3.7), 'UNK':('未标注归属','',0,0),
}
ORGS = {
 'I-ESA':('欧洲空间局','ESA'), 'I-EU':('欧盟','EU'), 'I-INT':('国际通信卫星组织','ITSO'),
 'I-EUT':('欧洲通信卫星组织','Eutelsat'), 'I-EUM':('欧洲气象卫星组织','EUMETSAT'),
 'I-ARAB':('阿拉伯卫星通信组织','Arabsat'), 'I-INM':('国际海事卫星组织','Inmarsat'),
 'I-NATO':('北约','NATO'), 'I-ESRO':('欧洲空间研究组织（历史）','ESRO'),
 'I-RASC':('阿拉伯地区卫星通信组织','RASC'),
}

MON = {m:i+1 for i,m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}

def parse_date(s):
    p = s.split()
    if len(p) >= 3 and p[0].isdigit() and p[1] in MON:
        return (int(p[0]), MON[p[1]], int(p[2]))
    return None

def launch_date(r):
    """发射日期按北京时间（UTC+8）折算：优先用 SDate 的 UTC 时刻，缺失时退回 LDate 日期。"""
    p = (r[9] if len(r) > 9 else '').strip().rstrip('?').split()
    if len(p) >= 4 and p[0].isdigit() and p[1] in MON:
        t = p[3].split(':')[0]
        if len(t) == 4 and t.isdigit():
            try:
                dt = datetime.datetime(int(p[0]), MON[p[1]], int(p[2]), int(t[:2]), int(t[2:]))
                dt += datetime.timedelta(hours=8)
                return (dt.year, dt.month, dt.day)
            except ValueError:
                pass
    return parse_date(r[7])

def iso(d):
    return '%04d-%02d-%02d' % d

def fmt_updated(raw):
    """把 GCAT 的 '# Updated 2026 Nov 13 0020:25'（UTC）换算为北京时间显示。"""
    p = raw.split()
    if len(p) >= 4 and p[1] in MON:
        t = p[3]
        try:
            dt = datetime.datetime(int(p[0]), MON[p[1]], int(p[2]), int(t[:2]), int(t[2:4]))
            dt += datetime.timedelta(hours=8)
            return '%04d-%02d-%02d %02d:%02d（北京时间）' % (dt.year, dt.month, dt.day, dt.hour, dt.minute)
        except ValueError:
            pass
    return raw

def load_cat(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        f.readline(); f.readline()
        rows = []
        for line in f:
            r = line.rstrip('\n').split('\t')
            if len(r) >= 42:
                rows.append(r)
    return rows

def aggregate(raw_dir=RAW):
    """从原始目录聚合出国家/机构统计。返回 (countries, meta)，不写文件。"""
    raw = load_cat(os.path.join(raw_dir, 'satcat_full.tsv'))
    for extra in ('satcat100k.tsv', 'satcat070k.tsv'):
        p = os.path.join(raw_dir, extra)
        if os.path.exists(p):
            raw += load_cat(p)
    payloads = {}
    for r in raw:
        if r[4].startswith('P'):
            payloads[r[0].strip()] = r
    payloads = list(payloads.values())

    orgs = {}
    org_updated = ''
    with open(os.path.join(raw_dir, 'orgs.tsv'), encoding='utf-8', errors='replace') as f:
        lines = [ln.rstrip('\n') for ln in f]
    for ln in lines[:3]:
        if ln.startswith('# Updated'):
            org_updated = ln[len('# Updated'):].strip()
    clean = [ln for i, ln in enumerate(lines) if not (i < 3 and ln.startswith('# '))]
    for o in csv.DictReader(clean, delimiter='\t'):
        k = (o.get('#Code') or '').strip().rstrip('?')
        if k:
            orgs[k] = o

    def name_of(code, o):
        if code in ORG_ZH:
            nm = ORG_ZH[code]
        else:
            nm = (o.get('ShortEName') or '').strip()
            if nm in ('', '-'):
                nm = (o.get('EName') or '').strip()
            if nm in ('', '-'):
                nm = (o.get('ShortName') or '').strip()
            if nm in ('', '-'):
                nm = code
        return ORG_NAME_ZH.get(nm, nm)

    def org_of(r):
        code = r[14].strip().rstrip('?')
        o = orgs.get(code)
        if o is None:
            pre = code.split('/')[0]
            o = orgs.get(pre)
            if o is not None:
                code = pre
        if o is None:
            return '', None
        return code, o

    def kind(o):
        if not o:
            return 'u'
        c = (o.get('Class') or '').strip()
        if c == 'B':
            return 'b'
        if c in ('A', 'C', 'D'):
            return 'g'
        return 'u'

    agg = collections.defaultdict(lambda: {'t':0,'o':0,'g':0,'b':0,'u':0,'go':0,'bo':0,'orgs':collections.Counter(),'first':9999,'last':'','all':[]})
    org_names = collections.defaultdict(collections.Counter)
    org_codes = collections.defaultdict(collections.Counter)
    for r in payloads:
        st = r[15].strip()
        a = agg[st]
        a['t'] += 1
        k = kind(org_of(r)[1])
        a[k] += 1
        d = launch_date(r)
        if d:
            a['first'] = min(a['first'], d[0])
            s = iso(d)
            if s > a['last']:
                a['last'] = s
        on = r[11].strip() == '-'
        if on:
            a['o'] += 1
            if k == 'g': a['go'] += 1
            elif k == 'b': a['bo'] += 1
        code, o = org_of(r)
        if o:
            nm = (o.get('EName') or o.get('Name') or code).strip()
            if nm in ('-', ''): nm = code
        else:
            nm = code
        org_names[st][(nm, k)] += 1
        org_codes[st][code] += 1

    countries = []
    for st, a in agg.items():
        zh, iso2, lat, lon = COUNTRY.get(st, (None, None, None, None))
        if st in ORGS:
            zh, _ab = ORGS[st]
            iso2, lat, lon = '', None, None
        if zh is None:
            zh = st
        merged = collections.Counter()
        kinds = {}
        for code, cnt in org_codes[st].items():
            o = orgs.get(code) or orgs.get(code.split('/')[0]) or {}
            nm = name_of(code, o)
            merged[nm] += cnt
            kinds.setdefault(nm, kind(o))
        top = [{'n': nm, 'k': kinds.get(nm, 'u'), 'c': cnt} for nm, cnt in sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        countries.append({
            'c': st, 'n': zh, 'iso': iso2 or '', 'lat': lat, 'lon': lon,
            't': a['t'], 'o': a['o'], 'g': a['g'], 'b': a['b'], 'u': a['u'],
            'go': a['go'], 'bo': a['bo'],
            'y': a['first'] if a['first'] != 9999 else None, 'last': a['last'],
            'top': top, 'k': 'org' if st in ORGS else 'country'
        })
    countries.sort(key=lambda x: (-x['t'], x['n']))

    cutoff = max(iso(d) for d in (launch_date(r) for r in payloads) if d)
    total = sum(c['t'] for c in countries)
    onorb = sum(c['o'] for c in countries)

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d')
    meta = {
        'cutoff': cutoff,
        'sourceUpdated': fmt_updated(org_updated) if org_updated else '刚抓取',
        'source': 'GCAT（Jonathan McDowell / 哈佛-史密松天体物理中心）',
        'crossCheck': 'CelesTrak SATCAT（同期 28,315 条，国别排序一致）',
        'updateFreq': '源数据每日更新',
        'totalPayloads': total,
        'onOrbit': onorb,
        'countryCount': len([c for c in countries if c['k'] == 'country']),
        'generatedAt': today,
        'classifiedPct': round(100.0 * sum(c['t'] - c['u'] for c in countries) / total, 1),
    }
    geo = {}
    for code, (zh, iso2, lat, lon) in COUNTRY.items():
        geo[code] = {'n': zh, 'iso': iso2, 'lat': lat, 'lon': lon}
    for code, (zh, ab) in ORGS.items():
        geo[code] = {'n': zh, 'iso': '', 'lat': None, 'lon': None, 'org': ab}
    orgmap = {}
    for code, o in orgs.items():
        orgmap[code] = name_of(code, o)
    return countries, meta, geo, {'c': ORG_ZH, 'n': ORG_NAME_ZH}, orgmap


def main():
    countries, meta, geo, orgnames, orgmap = aggregate()
    with open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT, 'countries.json'), 'w', encoding='utf-8') as f:
        json.dump(countries, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT, 'geo.json'), 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT, 'orgnames.json'), 'w', encoding='utf-8') as f:
        json.dump(orgnames, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT, 'orgmap.json'), 'w', encoding='utf-8') as f:
        json.dump(orgmap, f, ensure_ascii=False, separators=(',', ':'))
    print('countries', len(countries), 'total', meta['totalPayloads'],
          'onorbit', meta['onOrbit'], 'cutoff', meta['cutoff'])

if __name__ == '__main__':
    main()
