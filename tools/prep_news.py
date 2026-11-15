# -*- coding: utf-8 -*-
"""抓取公开报道生成内置新闻：国家航天局要闻 + SpaceNews RSS（英文条目附中文译文）。"""
import json, os, re, time, urllib.parse, urllib.request
from urllib.parse import urljoin

BASE = os.path.join(os.path.dirname(__file__), '..', 'app', 'src', 'main', 'assets', 'data')
OUT = os.path.join(BASE, 'news.json')
OUT_ZH = os.path.join(BASE, 'news_body_zh.json')
UA = {'User-Agent': 'SatScope/1.0 (news; data reader)'}

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

def cnsa(limit=12):
    page = 'https://www.cnsa.gov.cn/n6758823/n6758838/index.html'
    html = get(page)
    out, seen = [], set()
    pat = re.compile(r'<a href= ?"([^"]+)"[^>]*title="([^"]+)"[\s\S]{0,700}?ejlist_cont_tit_rq">(\d{4}-\d{2}-\d{2})')
    for m in pat.finditer(html):
        href, title, date = m.group(1), m.group(2).strip(), m.group(3)
        if title in seen or '发射' not in title or '评论区' in title:
            continue
        seen.add(title)
        url = urljoin(page, href)
        out.append({'t': title, 'd': date, 's': '国家航天局', 'u': url, 'c': 'CN', 'a': ''})
    return out[:limit]

def summary(raw):
    s = re.sub(r'(?is)<!\[CDATA\[|\]\]>', '', raw)
    s = re.sub(r'(?is)<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s).replace('&amp;', '&').replace('&quot;', '"').replace('&#8217;', '’')
    s = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), s)
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) <= 100:
        return s
    cut = s[:100].rsplit(' ', 1)[0].strip()
    return (cut if len(cut) > 40 else s[:100]) + '…'

def spacenews(limit=12):
    xml = get('https://spacenews.com/feed/')
    out = []
    for block in re.findall(r'<item>([\s\S]*?)</item>', xml):
        t = re.search(r'<title>([\s\S]*?)</title>', block)
        l = re.search(r'<link>\s*([^<]+)</link>', block)
        p = re.search(r'<pubDate>([^<]+)</pubDate>', block)
        if not (t and l and p):
            continue
        from email.utils import parsedate_to_datetime
        try:
            d = parsedate_to_datetime(p.group(1).strip()).strftime('%Y-%m-%d')
        except Exception:
            continue
        title = re.sub(r'&amp;', '&', t.group(1)).strip()
        desc = re.search(r'<description>([\s\S]*?)</description>', block)
        out.append({'t': title, 'd': d, 's': 'SpaceNews', 'u': l.group(1).strip(),
                    'c': 'INT', 'a': summary(desc.group(1)) if desc else ''})
        if len(out) >= limit:
            break
    return out

def translate(text, retries=2):
    """MyMemory 公开接口；失败返回 None。"""
    q = re.sub(r'\s+', ' ', text).strip()
    if not q:
        return ''
    if re.search(r'[\u4e00-\u9fff]', q):
        return q
    for _ in range(retries):
        try:
            url = 'https://api.mymemory.translated.net/get?' + urllib.parse.urlencode(
                {'q': q[:450], 'langpair': 'en|zh-CN', 'de': 'satscope@example.com'})
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=18) as r:
                d = json.load(r)
            t = (d.get('responseData') or {}).get('translatedText') or ''
            if t and not t.startswith('MYMEMORY WARNING'):
                return re.sub(r'\s+', ' ', t).strip()
        except Exception:
            pass
        time.sleep(1.2)
    return None

def body_paras(url):
    """与 App 内 Reader 相同的提取规则：只保留正文段落。"""
    html = get(url, 30)
    m = re.search(r'(?is)<div[^>]*class="[^"]*(wz_conten|entry-content)[^"]*"[^>]*>', html)
    if m and m.end() > 0:
        html = html[m.end():]
    for stop in ('jp-relatedposts', '<!-- .entry-content -->', '<footer', '责任编辑：', '分享到'):
        i = html.find(stop)
        if i > 200:
            html = html[:i]
    html = re.sub(r'(?is)<script.*?</script>', ' ', html)
    html = re.sub(r'(?is)<style.*?</style>', ' ', html)
    html = re.sub(r'(?i)<br\s*/?>', '\n', html)
    junk = ('Open dropdown menu', 'Search for:', 'Subscribe', 'Sign In', 'Advertise', 'Newsletters', 'Close')
    ps = []
    for p in re.findall(r'(?is)<p[^>]*>(.*?)</p>', html):
        t = re.sub(r'(?is)<[^>]+>', ' ', p)
        t = re.sub(r'&nbsp;', ' ', t).replace('&amp;', '&').replace('&quot;', '"').replace('&#8217;', '’')
        t = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), t)
        t = re.sub(r'\s+', ' ', t).strip()
        if len(t) >= 40 and not any(j in t for j in junk):
            ps.append(t)
    return ps[:10]

def main():
    items = []
    for fn in (cnsa, spacenews):
        try:
            items += fn()
        except Exception as e:
            print('fail', fn.__name__, e)
    items.sort(key=lambda x: x['d'], reverse=True)

    bodies = {}
    for it in items:
        if it['c'] != 'INT':
            continue
        tc = translate(it['t'])
        if tc:
            it['tc'] = tc
        if it['a']:
            ac = translate(it['a'])
            if ac:
                it['ac'] = ac
        try:
            paras = body_paras(it['u'])
            zh = [translate(p) for p in paras]
            if len(zh) >= 2 and all(zh):
                bodies[it['u']] = zh
                print('body ok', len(zh), it['u'])
            else:
                print('body skip', it['u'])
        except Exception as e:
            print('body fail', it['u'], e)
        time.sleep(0.3)

    json.dump(items, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(bodies, open(OUT_ZH, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('news', len(items), 'zh bodies', len(bodies))

if __name__ == '__main__':
    main()
