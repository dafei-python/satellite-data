# -*- coding: utf-8 -*-
"""数据准确性复核：用最新 GCAT 原始目录重算，与 App 内置数据逐字段比对，
并用 CelesTrak SATCAT 做独立交叉校验、抽查六国最近发射、核对政府/商业分类口径。

用法：python3 tools/audit.py [--raw data/raw] [--app app/src/main/assets/data]
"""
import argparse
import collections
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prep_data

TARGETS = [('CN', '中国'), ('US', '美国'), ('RU', '俄罗斯'), ('UK', '英国'), ('J', '日本'), ('IN', '印度')]
CT_OWNER = {'US': ['US'], 'CN': ['PRC'], 'RU': ['CIS'], 'SU': ['CIS'], 'UK': ['UK'], 'J': ['JPN'], 'IN': ['IND']}


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def load_orgs(raw):
    orgs = {}
    with open(os.path.join(raw, 'orgs.tsv'), encoding='utf-8', errors='replace') as f:
        lines = [ln.rstrip('\n') for ln in f]
    clean = [ln for i, ln in enumerate(lines) if not (i < 3 and ln.startswith('# '))]
    for o in csv.DictReader(clean, delimiter='\t'):
        k = (o.get('#Code') or '').strip().rstrip('?')
        if k:
            orgs[k] = o
    return orgs


def all_payloads(raw):
    rows = prep_data.load_cat(os.path.join(raw, 'satcat_full.tsv'))
    for extra in ('satcat100k.tsv', 'satcat070k.tsv'):
        p = os.path.join(raw, extra)
        if os.path.exists(p):
            rows += prep_data.load_cat(p)
    seen = {}
    for r in rows:
        if r[4].startswith('P'):
            seen[r[0].strip()] = r
    return list(seen.values())


def bj_date(r):
    """SDate 按 UTC+8 折算；返回 (北京日期, UTC 原文, 是否跨天)。"""
    p = (r[9] if len(r) > 9 else '').strip().rstrip('?').split()
    if len(p) >= 4 and p[0].isdigit():
        t = p[3].split(':')[0]
        if len(t) == 4 and t.isdigit():
            try:
                dt = datetime.datetime(int(p[0]), prep_data.MON[p[1]], int(p[2]), int(t[:2]), int(t[2:]))
                bj = dt + datetime.timedelta(hours=8)
                return '%04d-%02d-%02d' % (bj.year, bj.month, bj.day), ' '.join(p), bj.date() != dt.date()
            except Exception:
                pass
    d = prep_data.parse_date(r[7])
    return (prep_data.iso(d) if d else ''), r[7].strip(), False


def celestrak(raw):
    path = os.path.join(raw, 'satcat_celestrak.csv')
    if not os.path.exists(path):
        return None
    total = 0
    alive = 0
    by_owner = collections.Counter()
    alive_by_owner = collections.Counter()
    last = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for row in csv.DictReader(f):
            if row.get('OBJECT_TYPE') != 'PAY':
                continue
            total += 1
            owner = row.get('OWNER', '')
            by_owner[owner] += 1
            if not row.get('DECAY_DATE'):
                alive += 1
                alive_by_owner[owner] += 1
            d = (row.get('LAUNCH_DATE') or '')[:10]
            if d > last.get(owner, ''):
                last[owner] = d
    return {'total': total, 'alive': alive, 'byOwner': by_owner, 'aliveByOwner': alive_by_owner, 'last': last}


def audit(raw, appdir):
    countries, meta, _geo, _orgn, _orgmap = prep_data.aggregate(raw)
    orgs = load_orgs(raw)
    payloads = all_payloads(raw)

    app_countries = load_json(os.path.join(appdir, 'countries.json'))
    app_meta = load_json(os.path.join(appdir, 'meta.json'))
    app_map = {c['c']: c for c in app_countries}

    print('=' * 78)
    print('1. 总量逐字段比对（重算 vs App 内置）')
    print('=' * 78)
    fields = ['totalPayloads', 'onOrbit', 'countryCount', 'cutoff', 'classifiedPct']
    ok = True
    for k in fields:
        a, b = meta.get(k), app_meta.get(k)
        flag = 'OK ' if a == b else 'DIFF'
        if a != b:
            ok = False
        print('%-16s 重算=%-22s 内置=%-22s %s' % (k, a, b, flag))

    print()
    print('=' * 78)
    print('2. 分国别逐字段比对（仅列出差异）')
    print('=' * 78)
    reg_map = {c['c']: c for c in countries}
    diffs = 0
    for code in sorted(set(reg_map) | set(app_map)):
        a = reg_map.get(code)
        b = app_map.get(code)
        if a is None or b is None:
            print('仅单边存在：%s 重算=%s 内置=%s' % (code, bool(a), bool(b)))
            diffs += 1
            continue
        for k in ('t', 'o', 'g', 'b', 'u', 'go', 'bo', 'last', 'y'):
            if a.get(k) != b.get(k):
                print('%s %-4s 重算=%-10s 内置=%-10s' % (code, k, a.get(k), b.get(k)))
                diffs += 1
    print('国别差异字段数：%d' % diffs)

    print()
    print('=' * 78)
    print('3. CelesTrak SATCAT 独立交叉校验')
    print('=' * 78)
    ct = celestrak(raw)
    if not ct:
        print('未找到 satcat_celestrak.csv，跳过')
    else:
        print('载荷总数：GCAT=%d  CelesTrak=%d  差=%+d (%.1f%%)'
              % (meta['totalPayloads'], ct['total'], meta['totalPayloads'] - ct['total'],
                 100.0 * (meta['totalPayloads'] - ct['total']) / ct['total']))
        print('在轨数：  GCAT=%d  CelesTrak=%d  差=%+d (%.1f%%)'
              % (meta['onOrbit'], ct['alive'], meta['onOrbit'] - ct['alive'],
                 100.0 * (meta['onOrbit'] - ct['alive']) / max(1, ct['alive'])))
        print('最新发射日期：GCAT=%s  CelesTrak=%s' % (meta['cutoff'], max(ct['last'].values())))
        for code, zh in TARGETS:
            owners = CT_OWNER.get(code, [])
            gc = ['RU', 'SU'] if code == 'RU' else [code]
            g = {k: sum(reg_map.get(x, {}).get(k, 0) for x in gc) for k in ('t', 'o')}
            glast = max([reg_map.get(x, {}).get('last', '') for x in gc] or [''])
            cs = sum(ct['byOwner'][o] for o in owners)
            ca = sum(ct['aliveByOwner'][o] for o in owners)
            print('%s %-4s 载荷：GCAT=%-6d CelesTrak=%-6d 差=%+d (%.1f%%)；在轨：GCAT=%-6d CelesTrak=%-6d；最新发射 GCAT=%s CelesTrak=%s'
                  % (code, zh, g['t'], cs, g['t'] - cs, 100.0 * (g['t'] - cs) / max(1, cs), g['o'], ca,
                     glast, max([ct['last'].get(o, '') for o in owners] or [''])))

    print()
    print('=' * 78)
    print('4. 政府 / 商业分类口径核对（GCAT 机构 Class：B=商业，A/C/D=政府）')
    print('=' * 78)
    by_code = collections.defaultdict(int)
    for r in payloads:
        owner = r[14].strip().rstrip('?')
        o = orgs.get(owner)
        code = owner
        if o is None:
            pre = owner.split('/')[0]
            if pre in orgs:
                o = orgs[pre]
                code = pre
        if o is None:
            continue
        cls = (o.get('Class') or '').strip()
        st = r[15].strip()
        by_code[(st, code, cls)] += 1
    for st in ('CN', 'US', 'RU', 'UK', 'J', 'IN'):
        rows = [(c, cls, n) for (s, c, cls), n in by_code.items() if s == st]
        rows.sort(key=lambda x: -x[2])
        print('%s 载荷最多的机构（Class）：%s' % (st, '，'.join(
            '%s=%s(%d)' % (prep_data.ORG_ZH.get(c, c), cls or '?', n) for c, cls, n in rows[:6])))
    inconsistent = []
    for c in countries:
        if c['g'] + c['b'] + c['u'] != c['t']:
            inconsistent.append('%s 分类合计不等于总数' % c['c'])
        if c['go'] > c['g'] or c['bo'] > c['b']:
            inconsistent.append('%s 在轨分类超过总数' % c['c'])
    print('分类自洽检查：%s' % ('通过' if not inconsistent else '；'.join(inconsistent)))
    # 政府/商业拆分再核对
    total_g = sum(c['g'] for c in countries)
    total_b = sum(c['b'] for c in countries)
    total_u = sum(c['u'] for c in countries)
    print('合计：政府=%d 商业=%d 未标注=%d 总=%d' % (total_g, total_b, total_u, meta['totalPayloads']))

    print()
    print('=' * 78)
    print('5. 六国最近发射抽查（北京时间，含跨天标记；同一 Launch_Tag 归为一次发射）')
    print('=' * 78)
    for code, zh in TARGETS:
        rows = [r for r in payloads if r[15].strip() == code]
        grouped = collections.defaultdict(list)
        for r in rows:
            d, utc, cross = bj_date(r)
            group_tag = r[2].strip()
            grouped[(d, group_tag)].append((r, utc, cross))
        latest = sorted(grouped.items(), key=lambda kv: kv[0][0], reverse=True)[:4]
        print('\n%s %s 最近 %d 次发射：' % (code, zh, len(latest)))
        for (d, tag), items in latest:
            owners = collections.Counter(prep_data.ORG_ZH.get((r[14].strip().rstrip('?')), r[14].strip().rstrip('?')) for r, _, _ in items)
            names = '、'.join(r[5].strip() for r, _, _ in items[:3])
            cross = any(c for _, _, c in items)
            utc = items[0][1]
            print('  %s（UTC %s%s）%s  载荷 %d 颗  机构：%s  例：%s'
                  % (d, utc, '，跨天' if cross else '', tag, len(items),
                     '、'.join('%s×%d' % (k, v) for k, v in owners.most_common(3)), names))

    print()
    print('=' * 78)
    print('6. 重复计数与截止日期检查')
    print('=' * 78)
    dup = len(payloads) - len({r[0].strip() for r in payloads})
    print('按 JCAT 去重后重复条数：%d（应为 0）' % dup)
    max_bj = max(bj_date(r)[0] for r in payloads if bj_date(r)[0])
    print('重算最新发射日期=%s，meta.cutoff=%s，%s' % (max_bj, meta['cutoff'], '一致' if max_bj == meta['cutoff'] else '不一致'))
    print('数据来源标注：%s' % meta['source'])
    print('源目录更新时间：%s' % meta['sourceUpdated'])
    print('交叉校验说明：%s' % meta['crossCheck'])

    bad = (not ok) or diffs > 0 or dup > 0 or max_bj != meta['cutoff']
    print()
    print('结论：%s' % ('存在偏差，需要修正' if bad else '全部通过'))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default=os.path.join(HERE, '..', 'data', 'raw'))
    ap.add_argument('--app', default=os.path.join(HERE, '..', 'app', 'src', 'main', 'assets', 'data'))
    args = ap.parse_args()
    raw = os.path.abspath(args.raw)
    app = os.path.abspath(args.app)
    bad = audit(raw, app)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
