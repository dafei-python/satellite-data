# -*- coding: utf-8 -*-
"""把 GCAT 全量目录 + 新闻预处理成 App 可直接使用的小体积快照。

输出（默认 data/snapshot/）：
  snapshot.json.gz       App 更新时只下这一个文件（约 20–40KB）
  filtered_news.log      被过滤新闻明细，便于复核
  news_zh_cache.json     英文标题/摘要译文缓存（跨天复用，省翻译额度）
  news_body_zh_cache.json 正文译文缓存（可选）
  build_info.json        本次构建的统计信息

用法：
  python3 build_snapshot.py --raw ../data/raw --out ../data/snapshot
"""
import argparse
import datetime
import gzip
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prep_data
import prep_news
from news_rules import judge

SNAPSHOT_VERSION = 1


def now_bj():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def scan_recent(raw_dir, cutoff, days=30):
    """统计近 30 天新增载荷与再入载荷数量（用于口径面板展示）。"""
    try:
        y, m, d = [int(x) for x in cutoff.split('-')]
    except Exception:
        return 0, 0
    end = datetime.date(y, m, d)
    start = end - datetime.timedelta(days=days)
    rows = prep_data.load_cat(os.path.join(raw_dir, 'satcat_full.tsv'))
    for extra in ('satcat100k.tsv', 'satcat070k.tsv'):
        p = os.path.join(raw_dir, extra)
        if os.path.exists(p):
            rows += prep_data.load_cat(p)
    seen = {}
    for r in rows:
        if r[4].startswith('P'):
            seen[r[0].strip()] = r
    new_cnt = 0
    reentry_cnt = 0
    for r in seen.values():
        try:
            sd = prep_data.launch_date(r)
        except Exception:
            sd = None
        if sd:
            dt = datetime.date(*sd)
            if start <= dt <= end:
                new_cnt += 1
        try:
            dd = prep_data.parse_date((r[11] if len(r) > 11 else '').replace('?', ''))
        except Exception:
            dd = None
        if dd:
            dt = datetime.date(*dd)
            if start <= dt <= end:
                reentry_cnt += 1
    return new_cnt, reentry_cnt


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


def translate_cached(cache, key, text, budget):
    """只翻译一次；成功后写进缓存，跨天复用。连续失败 3 次后本次不再调用。"""
    if not text:
        return ''
    if cache.get(key):
        return cache[key]
    if budget['fails'] >= 3:
        return ''
    v = prep_news.translate(text)
    if v:
        cache[key] = v
        budget['ok'] += 1
        return v
    budget['fails'] += 1
    return ''


def fetch_news(zh_cache, body_cache, do_translate=True, per_source=18, keep_max=24, bodies_max=6):
    raw = []
    try:
        raw += prep_news.cnsa(per_source)
    except Exception as e:
        print('CNSA 抓取失败:', e)
    try:
        raw += prep_news.spacenews(per_source)
    except Exception as e:
        print('SpaceNews 抓取失败:', e)

    kept, dropped = [], []
    for it in raw:
        ok, cat, reason = judge(it.get('t', ''), it.get('a', ''))
        if ok:
            it['cat'] = cat
            kept.append(it)
        else:
            dropped.append((it, reason))

    kept.sort(key=lambda x: x.get('d', ''), reverse=True)
    kept = kept[:keep_max]

    budget = {'ok': 0, 'fails': 0}
    if do_translate:
        for it in kept:
            if it.get('c') != 'INT':
                continue
            tc = translate_cached(zh_cache, it['u'] + '#t', it['t'], budget)
            if tc:
                it['tc'] = tc
            if it.get('a'):
                ac = translate_cached(zh_cache, it['u'] + '#s', it['a'], budget)
                if ac:
                    it['ac'] = ac

    bodies = {}
    if do_translate and bodies_max > 0:
        done = 0
        for it in kept:
            if it.get('c') != 'INT' or done >= bodies_max:
                continue
            cached = body_cache.get(it['u'])
            if cached:
                bodies[it['u']] = cached
                done += 1
                continue
            if budget['fails'] >= 3:
                break
            try:
                paras = prep_news.body_paras(it['u'])[:10]
            except Exception as e:
                print('正文抓取失败', it['u'], e)
                continue
            zh = []
            for p in paras:
                if len(p) > 6000:
                    break
                t = prep_news.translate(p)
                if not t:
                    zh = []
                    break
                zh.append(t)
                time.sleep(0.2)
            if len(zh) >= 2:
                bodies[it['u']] = zh
                body_cache[it['u']] = zh
                done += 1
            time.sleep(0.2)

    return kept, dropped, bodies, budget


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default=os.path.join(HERE, '..', 'data', 'raw'))
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'data', 'snapshot'))
    ap.add_argument('--no-translate', action='store_true', help='只抓取筛选，不调用翻译')
    ap.add_argument('--no-news', action='store_true', help='跳过新闻，只做卫星数据')
    ap.add_argument('--bodies', type=int, default=6, help='预翻译正文条数上限')
    args = ap.parse_args()

    raw_dir = os.path.abspath(args.raw)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.time()
    countries, meta, _geo, _orgnames, _orgmap = prep_data.aggregate(raw_dir)
    agg_ms = int((time.time() - t0) * 1000)

    new_cnt, reentry_cnt = scan_recent(raw_dir, meta['cutoff'])
    meta['recentNew'] = new_cnt
    meta['recentReentry'] = reentry_cnt

    zh_cache_path = os.path.join(out_dir, 'news_zh_cache.json')
    body_cache_path = os.path.join(out_dir, 'news_body_zh_cache.json')
    zh_cache = load_json(zh_cache_path, {})
    body_cache = load_json(body_cache_path, {})

    news, dropped, bodies, budget = [], [], {}, {'ok': 0, 'fails': 0}
    if not args.no_news:
        news, dropped, bodies, budget = fetch_news(
            zh_cache, body_cache, do_translate=not args.no_translate, bodies_max=args.bodies)

    snap = {
        'v': SNAPSHOT_VERSION,
        'generatedAt': now_bj().strftime('%Y-%m-%d %H:%M（北京时间）'),
        'cutoff': meta['cutoff'],
        'meta': meta,
        'countries': countries,
        'news': news,
        'newsBodies': bodies,
        'stats': {
            'payloads': meta['totalPayloads'],
            'onOrbit': meta['onOrbit'],
            'countryCount': meta['countryCount'],
            'classifiedPct': meta['classifiedPct'],
            'recentNew': new_cnt,
            'recentReentry': reentry_cnt,
            'newsKept': len(news),
            'newsDropped': len(dropped),
            'newsTranslated': budget['ok'],
        },
    }
    payload = json.dumps(snap, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    gz_path = os.path.join(out_dir, 'snapshot.json.gz')
    with open(gz_path, 'wb') as f:
        with gzip.GzipFile(fileobj=f, mode='wb', compresslevel=9, mtime=0) as gz:
            gz.write(payload)

    save_json(zh_cache_path, zh_cache)
    save_json(body_cache_path, body_cache)

    log_path = os.path.join(out_dir, 'filtered_news.log')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('# 筛选口径：仅保留发射类（国家/机构/公司、时间、火箭、载荷、数量、任务）'
                '与国际规则/监管类（发射、轨道、频率）；其余过滤。\n')
        f.write('# 生成时间 %s；候选 %d 条，保留 %d 条，过滤 %d 条。\n'
                % (snap['generatedAt'], len(news) + len(dropped), len(news), len(dropped)))
        for it, reason in dropped:
            f.write('%s\t%s\tDROP\t%s\t%s\t%s\n'
                    % (it.get('d', ''), it.get('s', ''), reason, it.get('t', ''), it.get('u', '')))
        for it in news:
            f.write('%s\t%s\tKEEP\t%s\t%s\t%s\n'
                    % (it.get('d', ''), it.get('s', ''), it.get('cat', ''), it.get('t', ''), it.get('u', '')))

    info = {
        'builtAt': snap['generatedAt'],
        'cutoff': meta['cutoff'],
        'aggregateMs': agg_ms,
        'snapshotBytes': len(payload),
        'gzipBytes': os.path.getsize(gz_path),
        'newsKept': len(news),
        'newsDropped': len(dropped),
        'newsTranslated': budget['ok'],
        'translateFails': budget['fails'],
        'bodies': len(bodies),
    }
    save_json(os.path.join(out_dir, 'build_info.json'), info)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
