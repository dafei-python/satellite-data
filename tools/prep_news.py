# -*- coding: utf-8 -*-
"""抓取公开报道生成新闻数据。

国内：国家航天局要闻
国外：SpaceNews、Spaceflight Now、Phys.org 太空新闻、NASA 官方 RSS
（这几个源都无需付费/登录；NASASpaceflight 有 Cloudflare 反爬 403、
SpaceX 官网无 RSS 且 403、Rocket Lab 的 feed 是 7MB 非标准页、ESA 的 RSS 已下线，
均未接入。）

英文标题/摘要翻译优先用 Google 公开翻译接口，失败回退 MyMemory；译文由
build_snapshot.py 统一缓存，跨天复用。
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

BASE = os.path.join(os.path.dirname(__file__), '..', 'app', 'src', 'main', 'assets', 'data')
OUT = os.path.join(BASE, 'news.json')
OUT_ZH = os.path.join(BASE, 'news_body_zh.json')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SatScope/1.1 (+news reader)'}

SOURCES = [
    ('SpaceNews', 'https://spacenews.com/feed/'),
    ('Spaceflight Now', 'https://spaceflightnow.com/feed/'),
    ('Phys.org', 'https://phys.org/rss-feed/space-news/'),
    ('NASA', 'https://www.nasa.gov/feed/'),
]


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
    s = re.sub(r'(?is)<script.*?</script>|<style.*?</style>', ' ', s)
    s = re.sub(r'(?is)<[^>]+>', ' ', s)
    s = s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&#8217;', '’')
    s = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), s)
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) <= 100:
        return s
    cut = s[:100].rsplit(' ', 1)[0].strip()
    return (cut if len(cut) > 40 else s[:100]) + '…'


def _title(block):
    m = re.search(r'<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>', block)
    if not m:
        return ''
    t = re.sub(r'\s+', ' ', m.group(1))
    t = t.replace('&amp;', '&').replace('&quot;', '"').replace('&nbsp;', ' ')
    t = t.replace('&#8217;', '’').replace('&#8216;', '‘').replace('&#8220;', '“').replace('&#8221;', '”')
    t = re.sub(r'&#(\d+);', lambda x: chr(int(x.group(1))), t)
    return t.strip()


def _date(block):
    m = re.search(r'<pubDate>([^<]+)</pubDate>', block)
    if not m:
        return ''
    try:
        return parsedate_to_datetime(m.group(1).strip()).strftime('%Y-%m-%d')
    except Exception:
        return ''


def rss(source, url, limit=30):
    """标准 RSS：只取标题、链接、日期、摘要，按日期倒序。"""
    xml = get(url, 40)
    out, seen = [], set()
    for block in re.findall(r'<item[ >]([\s\S]*?)</item>', xml):
        title = _title(block)
        link = re.search(r'<link>\s*([^<]+)</link>', block)
        date = _date(block)
        if not title or not link or not date:
            continue
        u = link.group(1).strip()
        if u in seen:
            continue
        seen.add(u)
        desc = re.search(r'<description>([\s\S]*?)</description>', block)
        out.append({'t': title, 'd': date, 's': source, 'u': u, 'c': 'INT',
                    'a': summary(desc.group(1)) if desc else ''})
        if len(out) >= limit:
            break
    return out


def spacenews(limit=30):
    return rss('SpaceNews', 'https://spacenews.com/feed/', limit)


def spaceflightnow(limit=30):
    return rss('Spaceflight Now', 'https://spaceflightnow.com/feed/', limit)


def physorg(limit=30):
    return rss('Phys.org', 'https://phys.org/rss-feed/space-news/', limit)


def nasa(limit=30):
    return rss('NASA', 'https://www.nasa.gov/feed/', limit)


def _clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def translate(text, retries=1):
    """先 Google 公开接口，失败回退 MyMemory；都失败返回 None。"""
    q = _clean(text)
    if not q:
        return ''
    if re.search(r'[\u4e00-\u9fff]', q):
        return q
    for _ in range(retries):
        out = _google(q)
        if out:
            return out
        time.sleep(0.8)
    for _ in range(retries):
        out = _mymemory(q)
        if out:
            return out
        time.sleep(1.0)
    return None


def _google(q):
    try:
        url = 'https://translate.googleapis.com/translate_a/single?' + urllib.parse.urlencode(
            {'client': 'gtx', 'sl': 'en', 'tl': 'zh-CN', 'dt': 't', 'q': q[:4800]})
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        parts = [seg[0] for seg in (data[0] or []) if seg and seg[0]]
        out = _clean(''.join(parts))
        return out or None
    except Exception:
        return None


def _mymemory(q):
    try:
        url = 'https://api.mymemory.translated.net/get?' + urllib.parse.urlencode(
            {'q': q[:450], 'langpair': 'en|zh-CN', 'de': 'satscope@example.com'})
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.load(r)
        t = (d.get('responseData') or {}).get('translatedText') or ''
        if t and not t.startswith('MYMEMORY WARNING'):
            return _clean(t)
    except Exception:
        pass
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
        t = t.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&#8217;', '’')
        t = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), t)
        t = re.sub(r'\s+', ' ', t).strip()
        if len(t) >= 40 and not any(j in t for j in junk):
            ps.append(t)
    return ps[:10]


def fetch_all(per_source=30):
    """返回 (条目, 每个源的抓取数)。单个源失败不影响其他源。"""
    out, counts = [], {}
    jobs = [('国家航天局', cnsa), ('SpaceNews', spacenews), ('Spaceflight Now', spaceflightnow),
            ('Phys.org', physorg), ('NASA', nasa)]
    for name, fn in jobs:
        try:
            items = fn(per_source)
            counts[name] = len(items)
            out += items
        except Exception as e:
            counts[name] = 0
            print('源抓取失败', name, e)
    return out, counts


def main():
    items, counts = fetch_all()
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
        except Exception as e:
            print('body fail', it['u'], e)
        time.sleep(0.2)
    json.dump(items, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(bodies, open(OUT_ZH, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('news', len(items), 'sources', counts, 'zh bodies', len(bodies))


if __name__ == '__main__':
    main()
