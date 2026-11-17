# -*- coding: utf-8 -*-
"""404다방 669일 매출 더미데이터 최종본 생성기 (sales_dummy_v1_final).

실행: python data/synthetic_sales/sales_dummy_v1_final/generate_final.py
- 입력(읽기 전용): v1 주문/상세(분포 참고), revision2 generation_rules.json(확인된 메뉴 온도),
  data/processed/404dabang_daily_features.csv(날씨/공휴일), docs/source/school_academic_calendar.csv,
  docs/source/404dabang_dummy_sales_data_menu_id_fixed.xlsx(메뉴 원본)
- 출력: 이 폴더. v1 / revision* 폴더는 수정하지 않는다.
모든 효과 계수는 '시뮬레이션 가정'이며 실제 관측 인과관계가 아니다.
"""
import csv, json, math, random, statistics, sys, zipfile, collections
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
V1 = ROOT / 'data/synthetic_sales/sales_dummy_v1'
REV2 = ROOT / 'data/synthetic_sales/sales_dummy_v1_revision2'
FEATURES = ROOT / 'data/processed/404dabang_daily_features.csv'
CALENDAR = ROOT / 'docs/source/school_academic_calendar.csv'
MENU_XLSX = ROOT / 'docs/source/404dabang_dummy_sales_data_menu_id_fixed.xlsx'
VERSION = 'sales_dummy_v1_final'
SEED = 40420261117
rng = random.Random(SEED)

START = date(2025, 1, 1)
NDAYS = 669
DAYS = [START + timedelta(i) for i in range(NDAYS)]
DATA_END = DAYS[-1]
WD_KO = ['월', '화', '수', '목', '금', '토', '일']


# ---------------------------------------------------------------- io helpers
def rd(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def wr(p, header, rows):
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def xbook(p):
    z = zipfile.ZipFile(p)
    n = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
         'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {x.attrib['Id']: x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sst = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('a:si', n):
            sst.append(''.join(t.text or '' for t in si.iter('{%s}t' % n['a'])))
    out = {}
    for sh in wb.findall('a:sheets/a:sheet', n):
        t = rels[sh.attrib['{%s}id' % n['r']]].lstrip('/')
        t = t if t.startswith('xl/') else 'xl/' + t
        rows = []
        for row in ET.fromstring(z.read(t)).findall('.//a:sheetData/a:row', n):
            d = {}
            for c in row.findall('a:c', n):
                col = ''.join(ch for ch in c.attrib['r'] if ch.isalpha())
                v = c.find('a:v', n)
                q = c.find('a:is/a:t', n)
                if q is not None:
                    d[col] = q.text or ''
                elif v is not None:
                    d[col] = sst[int(v.text)] if c.attrib.get('t') == 's' else v.text
                else:
                    d[col] = ''
            rows.append(d)
        cols = [k for k in rows[0]]
        head = {k: rows[0][k] for k in cols}
        out[sh.attrib['name']] = [{head[k]: r.get(k, '') for k in cols} for r in rows[1:] if any(r.values())]
    return out


def num(x):
    try:
        return float(x) if x not in ('', None) else None
    except ValueError:
        return None


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def pdate(s):
    return date.fromisoformat(s)


# ---------------------------------------------------------------- inputs
features = {x['date']: x for x in rd(FEATURES)}
assert len(features) == NDAYS and all(d.isoformat() in features for d in DAYS)
menus = xbook(MENU_XLSX)['menu']
assert len(menus) == 27 and not menus[0]['menu_name'].isdigit()
menu_by_id = {m['menu_id']: m for m in menus}
for m in menus:
    m['price'] = int(float(m['unit_price']))

# 확인된 메뉴 온도(revision2 의 user-confirmed list)를 유지한다.
rev2_rules = json.loads((REV2 / 'generation_rules.json').read_text(encoding='utf-8'))
availability = rev2_rules['menu_availability']
NEUTRAL_CATEGORIES = ('디저트', '베이커리')
temp_class = {}
for m in menus:
    a = availability.get(m['menu_id'], 'UNKNOWN')
    if a == 'HOT_ICE':
        temp_class[m['menu_id']] = 'BOTH'
    elif a == 'ICE_ONLY':
        temp_class[m['menu_id']] = 'ICE'
    elif a == 'HOT_ONLY':
        temp_class[m['menu_id']] = 'HOT'
    elif any(t in m['category'] for t in NEUTRAL_CATEGORIES):
        temp_class[m['menu_id']] = 'NEUTRAL'
    else:
        temp_class[m['menu_id']] = 'UNKNOWN'

# v1 분포 (인기도, 수량, 장바구니 크기, 시간대) - 읽기 전용
v1_details = rd(V1 / 'order_details.csv')
v1_orders = rd(V1 / 'orders.csv')
v1_daily = rd(V1 / 'daily_sales.csv')
pop = collections.Counter()
qty_dist = collections.Counter()
lines_per_order = collections.Counter()
for x in v1_details:
    pop[x['menu_id']] += int(x['quantity'])
    qty_dist[int(x['quantity'])] += 1
cnt = collections.Counter(x['order_id'] for x in v1_details)
for oid, k in cnt.items():
    lines_per_order[min(4, k)] += 1
hour_dist = collections.Counter(int(x['order_hour']) for x in v1_orders)
HOURS = [h for h in sorted(hour_dist) if 7 <= h <= 22]
HOUR_W = [hour_dist[h] for h in HOURS]
V1_MEAN_ORDERS = statistics.mean(int(x['order_count']) for x in v1_daily)

# ---------------------------------------------------------------- school schedule (확인된 일정만)
SCHOOL_LABEL = {'hanyang': '한양대학교 서울캠퍼스', 'hywoman': '한양여자대학교', 'highschool': '한대부고'}
SCHOOLS = list(SCHOOL_LABEL)
CONFIRMED = ('verified', 'user_confirmed')


def school_key(name):
    if '한대부고' in name:
        return 'highschool'
    if '여자' in name:
        return 'hywoman'
    return 'hanyang'


cal = rd(CALENDAR)
exam_raw = collections.defaultdict(list)
vac_ranges = collections.defaultdict(list)
sem_starts = collections.defaultdict(list)
excluded_events = []
for r in cal:
    k = school_key(r['school_name'])
    st, en = pdate(r['start_date']), pdate(r['end_date'])
    if r['verified_status'] not in CONFIRMED:
        if r['event_type'] in ('exam', 'vacation', 'semester_start'):
            excluded_events.append({'school': SCHOOL_LABEL[k], 'event_type': r['event_type'], 'event_name': r['event_name'],
                                    'start': r['start_date'], 'end': r['end_date'], 'status': r['verified_status'],
                                    'reason': '확인되지 않은(estimated) 일정은 효과 적용·검증에서 제외'})
        continue
    if r['event_type'] == 'exam':
        exam_raw[k].append((st, en, r['verified_status'], r['event_name']))
    elif r['event_type'] == 'vacation':
        vac_ranges[k].append((st, en, r['verified_status'], r['event_name']))
    elif r['event_type'] == 'semester_start':
        sem_starts[k].append((st, en, r['verified_status'], r['event_name']))


def is_weekend_or_holiday_gap(a, b):
    """a(종료)와 b(시작) 사이의 모든 날짜가 주말이면 같은 시험기간으로 병합."""
    d = a + timedelta(1)
    while d < b:
        if d.weekday() < 5:
            return False
        d += timedelta(1)
    return True


exam_periods = {}
for k in SCHOOLS:
    segs = sorted(exam_raw[k])
    merged = []
    for st, en, status, name in segs:
        if merged and (st - merged[-1]['end']).days <= 4 and is_weekend_or_holiday_gap(merged[-1]['end'], st):
            merged[-1]['end'] = max(merged[-1]['end'], en)
            merged[-1]['segments'] += 1
        else:
            merged.append({'start': st, 'end': en, 'status': status, 'name': name, 'segments': 1})
    exam_periods[k] = merged

# ---------------------------------------------------------------- 시뮬레이션 가정 (계수)
EXAM_STRENGTH = {'hanyang': 0.12, 'hywoman': 0.10, 'highschool': 0.06}
VAC_STRENGTH = {'hanyang': 0.14, 'hywoman': 0.10, 'highschool': 0.06}
SEM_START_STRENGTH = {'hanyang': 0.05, 'hywoman': 0.0, 'highschool': 0.03}
PRE_DAYS, POST_DAYS = 14, 10
EXAM_LAST_DAY_FRACTION = 0.75
EXAM_CAP, EXAM_REST = 0.20, 0.25
VAC_CAP, VAC_REST = 0.20, 0.35
SEM_CAP, SEM_REST = 0.06, 0.50
SCHOOL_FACTOR_BOUNDS = (0.78, 1.25)
WEEKDAY_FACTOR = {0: 0.98, 1: 1.00, 2: 1.13, 3: 1.03, 4: 1.23, 5: 0.97, 6: 0.65}
HOLIDAY_WEEKDAY_ADJ = 0.85
HOLIDAY_WEEKEND_ADJ = 0.95
LONG_RUN_ADJ = {3: 0.94, 4: 0.94, 5: 0.90}   # 5일 이상은 0.90
PRE_LONG_ADJ, POST_LONG_ADJ = 1.04, 0.97
CAL_BOUNDS = (0.50, 1.30)
WEATHER_BOUNDS = (0.88, 1.08)
NOISE_SIGMA = 0.06
HOT_CENTER_C, HOT_SCALE = 15.0, 6.0
HOT_PROB_BOUNDS = (0.05, 0.95)
RAIN_HOT_LOGIT = 0.30
ICE_ONLY_TEMP_SLOPE = 0.03
ICE_ONLY_WEIGHT_BOUNDS = (0.55, 1.70)
HOT_LOGIT_OFFSET = {'M002': -0.4, 'M003': -0.4, 'M008': -0.3, 'M006': -0.1, 'M001': 0.0, 'M004': 0.2,
                    'M005': 0.5, 'M007': 0.1, 'M013': -0.6, 'M015': 0.3, 'M017': 0.1}


def combine(vals, cap, rest):
    v = sorted((x for x in vals if x > 0), reverse=True)
    return 0.0 if not v else min(cap, v[0] + rest * sum(v[1:]))


def exam_fraction(d, st, en):
    n = (en - st).days + 1
    last = EXAM_LAST_DAY_FRACTION if n > 1 else 1.0
    if st - timedelta(PRE_DAYS) <= d < st:
        b = (st - d).days
        return 0.35 * (PRE_DAYS - b) / 7 if b >= 7 else 0.35 + 0.65 * (7 - b) / 6
    if st <= d <= en:
        return 1.0 - (1.0 - last) * (d - st).days / (n - 1) if n > 1 else 1.0
    if en < d <= en + timedelta(POST_DAYS):
        return last * (1 - (d - en).days / POST_DAYS)
    return 0.0


def school_components(d):
    exam, vac, sem = {}, {}, {}
    for k in SCHOOLS:
        exam[k] = max([EXAM_STRENGTH[k] * exam_fraction(d, p['start'], p['end']) for p in exam_periods[k]], default=0.0)
        vac[k] = VAC_STRENGTH[k] if any(a <= d <= b for a, b, _, _ in vac_ranges[k]) else 0.0
        s = 0.0
        for a, _, _, _ in sem_starts[k]:
            i = (d - a).days
            if 0 <= i < 7:
                s = max(s, SEM_START_STRENGTH[k] * (1 - i / 7))
        sem[k] = s
    return exam, vac, sem


def school_factor(exam, vac, sem, skip_exam=None):
    e = combine([v for k, v in exam.items() if k != skip_exam], EXAM_CAP, EXAM_REST)
    v = combine(list(vac.values()), VAC_CAP, VAC_REST)
    s = combine(list(sem.values()), SEM_CAP, SEM_REST)
    return clip((1 + e) * (1 - v) * (1 + s), *SCHOOL_FACTOR_BOUNDS), e, v, s


# ---------------------------------------------------------------- 일별 수요 모델
is_hol = {d: features[d.isoformat()]['is_public_holiday'] == 'true' for d in DAYS}
nonwork = {d: d.weekday() >= 5 or is_hol[d] for d in DAYS}
run_len, run_pos = {}, {}
i = 0
while i < NDAYS:
    if nonwork[DAYS[i]]:
        j = i
        while j + 1 < NDAYS and nonwork[DAYS[j + 1]]:
            j += 1
        for k in range(i, j + 1):
            run_len[DAYS[k]] = j - i + 1
            run_pos[DAYS[k]] = (i, j)
        i = j + 1
    else:
        i += 1


def holiday_adjust(d):
    adj, tag = 1.0, 'normal'
    if is_hol[d]:
        adj *= HOLIDAY_WEEKDAY_ADJ if d.weekday() < 5 else HOLIDAY_WEEKEND_ADJ
        tag = 'public_holiday'
    elif d.weekday() >= 5:
        tag = 'weekend'
    L = run_len.get(d, 0)
    if L >= 3:
        adj *= LONG_RUN_ADJ[min(L, 5)]
        tag = 'long_holiday'
    if not nonwork[d]:
        nxt = d + timedelta(1)
        prv = d - timedelta(1)
        if nxt in run_len and run_len[nxt] >= 3 and run_pos[nxt][0] == (nxt - START).days:
            adj *= PRE_LONG_ADJ
            tag = 'pre_long_holiday'
        elif prv in run_len and run_len[prv] >= 3 and run_pos[prv][1] == (prv - START).days:
            adj *= POST_LONG_ADJ
            tag = 'post_long_holiday'
    return adj, tag


def weather_factors(f):
    t = num(f['avg_temp_c'])
    mm = num(f['precipitation_mm'])
    rain_obs = mm is not None
    ft = 1 + 0.0035 * clip(t - 20, 0, 13) - 0.005 * clip(5 - t, 0, 15)
    fr = 1.0
    if rain_obs and mm >= 0.1:
        fr = 1 - min(0.10, 0.004 * mm)
    return t, mm, rain_obs, ft, fr, clip(ft * fr, *WEATHER_BOUNDS)


rows_in = []
for d in DAYS:
    f = features[d.isoformat()]
    exam, vac, sem = school_components(d)
    sf, e_c, v_c, s_c = school_factor(exam, vac, sem)
    hadj, tag = holiday_adjust(d)
    wd = WEEKDAY_FACTOR[d.weekday()]
    cal_f = clip(wd * hadj, *CAL_BOUNDS)
    t, mm, rain_obs, ft, fr, wf = weather_factors(f)
    rows_in.append({'d': d, 'exam': exam, 'vac': vac, 'sem': sem, 'sf': sf, 'e': e_c, 'v': v_c, 's': s_c, 'wd': wd,
                    'hadj': hadj, 'tag': tag, 'cal': cal_f, 't': t, 'mm': mm, 'rain_obs': rain_obs, 'ft': ft, 'fr': fr,
                    'wf': wf, 'rain_flag': f['is_rain']})
mean_factor = statistics.mean(r['cal'] * r['sf'] * r['wf'] for r in rows_in)
LEVEL = V1_MEAN_ORDERS / mean_factor
for r in rows_in:
    r['base'] = LEVEL * r['cal'] * r['wf']          # 학교 효과를 제외한 평상시 기대 주문 수
    r['mu'] = r['base'] * r['sf']
    r['target'] = max(4, round(r['mu'] * math.exp(rng.gauss(0, NOISE_SIGMA))))


# ---------------------------------------------------------------- 메뉴/온도 선택
def menu_weights(r):
    t, month = r['t'], r['d'].month
    ws = []
    for m in menus:
        mid = m['menu_id']
        w = float(pop[mid])
        if temp_class[mid] == 'ICE':
            w *= clip(math.exp(ICE_ONLY_TEMP_SLOPE * (t - 15)), *ICE_ONLY_WEIGHT_BOUNDS)
        if mid == 'M024':
            w *= 1.25 if month in (11, 12, 1, 2) else 0.8 if month in (6, 7, 8) else 1.0
        if mid in ('M021', 'M027'):
            w *= 1.15 if month in (5, 6, 7, 8, 9) else 0.9 if month in (12, 1, 2) else 1.0
        ws.append(w)
    return ws


def p_hot(mid, r):
    logit = (HOT_CENTER_C - r['t']) / HOT_SCALE + HOT_LOGIT_OFFSET.get(mid, 0.0)
    if r['rain_obs'] and r['mm'] >= 1.0:
        logit += RAIN_HOT_LOGIT
    return clip(1 / (1 + math.exp(-logit)), *HOT_PROB_BOUNDS)


OH = ['order_id', 'store_id', 'order_datetime', 'order_date', 'order_hour', 'payment_method', 'gross_amount',
      'discount_amount', 'net_sales', 'data_type', 'dataset_version']
DEH = ['order_detail_id', 'order_id', 'menu_id', 'menu_name', 'category', 'quantity', 'temperature', 'temperature_class',
       'unit_price', 'discount_amount', 'line_total', 'data_type', 'dataset_version']
orders, details = [], []
oseq = dseq = 0
lp_keys, lp_w = list(lines_per_order), list(lines_per_order.values())
q_keys, q_w = list(qty_dist), list(qty_dist.values())
for r in rows_in:
    d = r['d']
    ds = d.isoformat()
    ws = menu_weights(r)
    for _ in range(r['target']):
        oseq += 1
        oid = f'F1-{oseq:07d}'
        h = rng.choices(HOURS, weights=HOUR_W)[0]
        tm = datetime(d.year, d.month, d.day, h, rng.randrange(60), rng.randrange(60))
        lines = collections.OrderedDict()
        for _l in range(rng.choices(lp_keys, weights=lp_w)[0]):
            m = rng.choices(menus, weights=ws)[0]
            mid = m['menu_id']
            q = rng.choices(q_keys, weights=q_w)[0]
            cls = temp_class[mid]
            if cls == 'BOTH':
                p = p_hot(mid, r)
                hot = sum(1 for _u in range(q) if rng.random() < p)
                parts = [('HOT', hot), ('ICE', q - hot)]
            elif cls == 'HOT':
                parts = [('HOT', q)]
            elif cls == 'ICE':
                parts = [('ICE', q)]
            else:
                parts = [('', q)]
            for tp, qq in parts:
                if qq:
                    lines[(mid, tp)] = lines.get((mid, tp), 0) + qq
        total = 0
        for (mid, tp), q in lines.items():
            m = menu_by_id[mid]
            amt = q * m['price']
            total += amt
            dseq += 1
            details.append([f'F1-D{dseq:08d}', oid, mid, m['menu_name'], m['category'], q, tp, temp_class[mid],
                            m['price'], 0, amt, 'synthetic_dummy', VERSION])
        orders.append([oid, 1, tm.isoformat(sep=' '), ds, h, 'card', total, 0, total, 'synthetic_dummy', VERSION])

# ---------------------------------------------------------------- 집계
omap = {o[0]: o for o in orders}
d_sales = collections.defaultdict(lambda: {'sales': 0, 'orders': 0, 'qty': 0, 'hot': 0, 'ice': 0})
d_menu = collections.defaultdict(lambda: {'qty': 0, 'amt': 0, 'hot': 0, 'ice': 0})
hourly = collections.defaultdict(lambda: [0, 0])
for o in orders:
    d_sales[o[3]]['orders'] += 1
    d_sales[o[3]]['sales'] += o[8]
    hourly[(o[3], o[4])][0] += 1
    hourly[(o[3], o[4])][1] += o[8]
for x in details:
    ds = omap[x[1]][3]
    q = x[5]
    d_sales[ds]['qty'] += q
    d_menu[(ds, x[2])]['qty'] += q
    d_menu[(ds, x[2])]['amt'] += x[10]
    if x[6] == 'HOT':
        d_sales[ds]['hot'] += q
        d_menu[(ds, x[2])]['hot'] += q
    elif x[6] == 'ICE':
        d_sales[ds]['ice'] += q
        d_menu[(ds, x[2])]['ice'] += q

DHEAD = ['sales_date', 'actual_sales', 'order_count', 'average_ticket', 'weekday_ko', 'data_type', 'dataset_version',
         'baseline_order_count', 'exam_effect_factor', 'exam_adjustment_orders', 'vacation_effect_factor',
         'school_effect_factor', 'total_quantity', 'hot_quantity', 'ice_quantity', 'is_public_holiday']
D = []
for r in rows_in:
    s = d_sales[r['d'].isoformat()]
    D.append([r['d'].isoformat(), s['sales'], s['orders'], round(s['sales'] / s['orders']), WD_KO[r['d'].weekday()],
              'synthetic_dummy', VERSION, round(r['base']), round(r['e'], 4), s['orders'] - round(r['base']),
              round(r['v'], 4), round(r['sf'], 4), s['qty'], s['hot'], s['ice'], int(is_hol[r['d']])])
DMH = ['sales_date', 'menu_id', 'quantity', 'sales_amount', 'menu_name', 'category', 'unit_price', 'data_type',
       'dataset_version', 'temperature_class', 'hot_quantity', 'ice_quantity']
M = [[d.isoformat(), m['menu_id'], d_menu[(d.isoformat(), m['menu_id'])]['qty'], d_menu[(d.isoformat(), m['menu_id'])]['amt'],
      m['menu_name'], m['category'], m['price'], 'synthetic_dummy', VERSION, temp_class[m['menu_id']],
      d_menu[(d.isoformat(), m['menu_id'])]['hot'], d_menu[(d.isoformat(), m['menu_id'])]['ice']]
     for d in DAYS for m in menus]
HH = ['sales_date', 'hour', 'hour_label', 'order_count', 'sales_amount', 'data_type', 'dataset_version']
H = [[k[0], k[1], f'{k[1]:02}:00', v[0], v[1], 'synthetic_dummy', VERSION] for k, v in sorted(hourly.items())]
IH = ['date', 'weekday', 'is_public_holiday', 'holiday_day_type', 'avg_temp_c', 'precipitation_mm', 'rain_observed',
      'weekday_factor', 'holiday_adjust', 'calendar_factor', 'temp_factor', 'rain_factor', 'weather_factor',
      'baseline_orders_no_school', 'school_factor', 'expected_orders', 'orders_with_noise']
for k in SCHOOLS:
    IH += [f'exam_{k}', f'vacation_{k}', f'semester_start_{k}']
IH += ['exam_combined', 'vacation_combined', 'semester_start_combined']
INP = []
for r in rows_in:
    row = [r['d'].isoformat(), WD_KO[r['d'].weekday()], int(is_hol[r['d']]), r['tag'], r['t'],
           '' if r['mm'] is None else r['mm'], int(r['rain_obs']), r['wd'], round(r['hadj'], 4), round(r['cal'], 4),
           round(r['ft'], 4), round(r['fr'], 4), round(r['wf'], 4), round(r['base'], 4), round(r['sf'], 4),
           round(r['mu'], 4), r['target']]
    for k in SCHOOLS:
        row += [round(r['exam'][k], 5), round(r['vac'][k], 5), round(r['sem'][k], 5)]
    row += [round(r['e'], 5), round(r['v'], 5), round(r['s'], 5)]
    INP.append(row)
tot_sales = sum(x[1] for x in D)

# 효과별 기록 파일 쓰기
for fn, h, rows in [('orders.csv', OH, orders), ('order_details.csv', DEH, details), ('daily_sales.csv', DHEAD, D),
                    ('daily_menu_sales.csv', DMH, M), ('hourly_sales.csv', HH, H), ('daily_generation_inputs.csv', IH, INP)]:
    wr(OUT / fn, h, rows)
for stale in ('exam_period_comparison.csv', 'exam_post_offsets.csv', 'temperature_menu_mix_comparison.csv'):
    if (OUT / stale).exists():
        (OUT / stale).unlink()   # 초안 산출물 - _backup_draft_before_final_20261117 에 보관됨

# ================================================================ 분석 (생성 CSV 를 다시 읽어서 계산)
O_ = rd(OUT / 'orders.csv')
DT_ = rd(OUT / 'order_details.csv')
DS_ = rd(OUT / 'daily_sales.csv')
DM_ = rd(OUT / 'daily_menu_sales.csv')
HR_ = rd(OUT / 'hourly_sales.csv')
IN_ = rd(OUT / 'daily_generation_inputs.csv')
ds_by = {x['sales_date']: x for x in DS_}
in_by = {x['date']: x for x in IN_}
f_ = lambda x: float(x)


def mean(v):
    v = list(v)
    return statistics.mean(v) if v else None


def se(v):
    v = list(v)
    return statistics.stdev(v) / math.sqrt(len(v)) if len(v) > 1 else None


def r4(x):
    return None if x is None else round(x, 4)


def share(a, b):
    return round(100 * a / b, 4) if b else None


# --- 메뉴 판매 구성
mq = collections.Counter()
ma = collections.Counter()
mh = collections.Counter()
mi = collections.Counter()
for x in DM_:
    mq[x['menu_id']] += int(x['quantity'])
    ma[x['menu_id']] += int(x['sales_amount'])
    mh[x['menu_id']] += int(x['hot_quantity'])
    mi[x['menu_id']] += int(x['ice_quantity'])
TQ, TA = sum(mq.values()), sum(ma.values())
MIXH = ['menu_id', 'menu_name', 'category', 'unit_price', 'temperature_class', 'quantity', 'quantity_share_pct',
        'sales_amount', 'revenue_share_pct', 'basis']
MIX = [[m['menu_id'], m['menu_name'], m['category'], m['price'], temp_class[m['menu_id']], mq[m['menu_id']],
        share(mq[m['menu_id']], TQ), ma[m['menu_id']], share(ma[m['menu_id']], TA), 'synthetic_only'] for m in menus]
wr(OUT / 'menu_sales_mix.csv', MIXH, MIX)

# --- HOT/ICE 분석
HIH = ['scope', 'group', 'selectable_quantity', 'hot_quantity', 'ice_quantity', 'hot_share_pct', 'ice_share_pct',
       'neutral_or_unknown_quantity', 'note']
HI = []
for m in menus:
    c = temp_class[m['menu_id']]
    if c in ('BOTH', 'HOT', 'ICE'):
        sel = mh[m['menu_id']] + mi[m['menu_id']]
        HI.append(['menu', f"{m['menu_id']} {m['menu_name']} ({c})", sel, mh[m['menu_id']], mi[m['menu_id']],
                   share(mh[m['menu_id']], sel), share(mi[m['menu_id']], sel), 0,
                   'qty = HOT+ICE (온도 선택 가능 메뉴)'])
    else:
        HI.append(['menu', f"{m['menu_id']} {m['menu_name']} ({c})", 0, 0, 0, None, None, mq[m['menu_id']],
                   'temperature 값은 비워 둠 (임의 생성 금지)'])
temp_sorted = sorted(IN_, key=lambda x: (f_(x['avg_temp_c']), x['date']))
qn = len(temp_sorted) // 4
quart = {'Q1_coldest': temp_sorted[:qn], 'Q2': temp_sorted[qn:2 * qn], 'Q3': temp_sorted[2 * qn:3 * qn],
         'Q4_hottest': temp_sorted[3 * qn:]}
quart_stats = {}
for g, rs in quart.items():
    dates = {x['date'] for x in rs}
    hot = sum(int(x['hot_quantity']) for x in DM_ if x['sales_date'] in dates)
    ice = sum(int(x['ice_quantity']) for x in DM_ if x['sales_date'] in dates)
    both_hot = sum(int(x['hot_quantity']) for x in DM_ if x['sales_date'] in dates and x['temperature_class'] == 'BOTH')
    both_ice = sum(int(x['ice_quantity']) for x in DM_ if x['sales_date'] in dates and x['temperature_class'] == 'BOTH')
    iceonly = sum(int(x['quantity']) for x in DM_ if x['sales_date'] in dates and x['temperature_class'] == 'ICE')
    allq = sum(int(x['quantity']) for x in DM_ if x['sales_date'] in dates)
    quart_stats[g] = dict(n=len(rs), t_lo=min(f_(x['avg_temp_c']) for x in rs), t_hi=max(f_(x['avg_temp_c']) for x in rs),
                          hot=hot, ice=ice, both_hot=both_hot, both_ice=both_ice, iceonly=iceonly, allq=allq)
    HI.append(['temp_quartile', f"{g} ({quart_stats[g]['t_lo']}~{quart_stats[g]['t_hi']}C, {len(rs)}일)", hot + ice, hot, ice,
               share(hot, hot + ice), share(ice, hot + ice), allq - hot - ice, '전 선택 가능 메뉴 합계'])
    HI.append(['temp_quartile_BOTH_only', g, both_hot + both_ice, both_hot, both_ice, share(both_hot, both_hot + both_ice),
               share(both_ice, both_hot + both_ice), 0, 'BOTH 메뉴만(고객 선택)'])
    HI.append(['temp_quartile_iceonly_menu_share', g, iceonly, 0, iceonly, None, share(iceonly, allq), 0,
               'ICE 전용 메뉴가 전체 수량에서 차지하는 비중(ice_share_pct 열)'])
th = sum(int(x['hot_quantity']) for x in DM_)
ti = sum(int(x['ice_quantity']) for x in DM_)
HI.append(['total', 'all', th + ti, th, ti, share(th, th + ti), share(ti, th + ti), TQ - th - ti, ''])
wr(OUT / 'hot_ice_sales_analysis.csv', HIH, HI)


# --- 날씨/기온 분석
def day_stats(dates):
    dates = list(dates)
    od = [int(ds_by[x]['order_count']) for x in dates]
    sl = [int(ds_by[x]['actual_sales']) for x in dates]
    hot = sum(int(ds_by[x]['hot_quantity']) for x in dates)
    ice = sum(int(ds_by[x]['ice_quantity']) for x in dates)
    qty = sum(int(ds_by[x]['total_quantity']) for x in dates)
    io = sum(int(x['quantity']) for x in DM_ if x['sales_date'] in set(dates) and x['temperature_class'] == 'ICE')
    ratio = mean(od[i] / f_(in_by[x]['expected_orders']) * 1 for i, x in enumerate(dates))
    return dict(n=len(dates), orders=mean(od), sales=mean(sl), hot=hot, ice=ice, qty=qty, io=io, od=od)


WH = ['group_type', 'group', 'n_days', 'avg_orders_per_day', 'avg_sales_per_day', 'avg_quantity_per_day',
      'hot_share_pct_of_selectable', 'ice_share_pct_of_selectable', 'ice_only_menu_share_pct_of_all_qty',
      'realized_weather_ratio', 'configured_weather_factor_mean', 'status']
W = []
bands = [('<=0C', lambda t: t <= 0), ('0~10C', lambda t: 0 < t <= 10), ('10~20C', lambda t: 10 < t <= 20),
         ('20~25C', lambda t: 20 < t <= 25), ('25~30C', lambda t: 25 < t <= 30), ('>30C', lambda t: t > 30)]


def realized_weather(dates):
    # 관측 주문수 / (평상시 기대주문 중 날씨 제외분 × 학교 효과): 날씨 효과의 실현값
    return mean(int(ds_by[x]['order_count']) / (f_(in_by[x]['baseline_orders_no_school']) / f_(in_by[x]['weather_factor'])
                                                * f_(in_by[x]['school_factor'])) for x in dates)


for name, fn in bands:
    dates = [x['date'] for x in IN_ if fn(f_(x['avg_temp_c']))]
    if not dates:
        continue
    s = day_stats(dates)
    W.append(['temperature_band', name, s['n'], r4(s['orders']), r4(s['sales']), r4(s['qty'] / s['n']),
              share(s['hot'], s['hot'] + s['ice']), share(s['ice'], s['hot'] + s['ice']), share(s['io'], s['qty']),
              r4(realized_weather(dates)), r4(mean(f_(in_by[x]['weather_factor']) for x in dates)), 'OK' if s['n'] >= 10 else 'LOW_N'])
rain_groups = [('rain_observed_>=10mm', lambda x: x['rain_observed'] == '1' and f_(x['precipitation_mm']) >= 10),
               ('rain_observed_1~10mm', lambda x: x['rain_observed'] == '1' and 1 <= f_(x['precipitation_mm']) < 10),
               ('rain_observed_0.1~1mm', lambda x: x['rain_observed'] == '1' and 0.1 <= f_(x['precipitation_mm']) < 1),
               ('no_rain_observed', lambda x: x['rain_observed'] == '1' and f_(x['precipitation_mm']) < 0.1),
               ('precipitation_missing(효과 미적용)', lambda x: x['rain_observed'] == '0')]
for name, fn in rain_groups:
    dates = [x['date'] for x in IN_ if fn(x)]
    if not dates:
        continue
    s = day_stats(dates)
    W.append(['precipitation', name, s['n'], r4(s['orders']), r4(s['sales']), r4(s['qty'] / s['n']),
              share(s['hot'], s['hot'] + s['ice']), share(s['ice'], s['hot'] + s['ice']), share(s['io'], s['qty']),
              r4(realized_weather(dates)), r4(mean(f_(in_by[x]['weather_factor']) for x in dates)),
              'NOT_APPLIED_MISSING' if 'missing' in name else ('OK' if s['n'] >= 10 else 'LOW_N')])
for mo in range(1, 13):
    dates = [x['date'] for x in IN_ if int(x['date'][5:7]) == mo]
    s = day_stats(dates)
    W.append(['month', f'{mo:02d}', s['n'], r4(s['orders']), r4(s['sales']), r4(s['qty'] / s['n']),
              share(s['hot'], s['hot'] + s['ice']), share(s['ice'], s['hot'] + s['ice']), share(s['io'], s['qty']),
              r4(realized_weather(dates)), r4(mean(f_(in_by[x]['weather_factor']) for x in dates)), 'OK'])
wr(OUT / 'weather_temperature_analysis.csv', WH, W)

# --- 공휴일/주말/연휴 분석
HOH = ['group_type', 'group', 'n_days', 'avg_orders_per_day', 'avg_sales_per_day', 'configured_factor_mean',
       'realized_factor', 'status']


def realized_cal(dates):
    return mean(int(ds_by[x]['order_count']) / (LEVEL * f_(in_by[x]['weather_factor']) * f_(in_by[x]['school_factor']))
                for x in dates)


HOL = []
groups = [(f'weekday_{WD_KO[w]}_normal', [x['date'] for x in IN_ if pdate(x['date']).weekday() == w and f_(x['holiday_adjust']) == 1.0])
          for w in range(7)]
groups += [(t, [x['date'] for x in IN_ if x['holiday_day_type'] == t])
           for t in ('public_holiday', 'weekend', 'long_holiday', 'pre_long_holiday', 'post_long_holiday')]
groups += [('public_holiday_on_weekday', [x['date'] for x in IN_ if x['is_public_holiday'] == '1' and pdate(x['date']).weekday() < 5]),
           ('public_holiday_on_weekend', [x['date'] for x in IN_ if x['is_public_holiday'] == '1' and pdate(x['date']).weekday() >= 5])]
for name, dates in groups:
    if not dates:
        continue
    HOL.append(['day_type', name, len(dates), r4(mean(int(ds_by[x]['order_count']) for x in dates)),
                r4(mean(int(ds_by[x]['actual_sales']) for x in dates)), r4(mean(f_(in_by[x]['calendar_factor']) for x in dates)),
                r4(realized_cal(dates)), 'OK' if len(dates) >= 10 else 'LOW_N'])
wr(OUT / 'holiday_weekend_analysis.csv', HOH, HOL)


# --- 학교별 시험/방학 효과 분석
def f_excl_exam(row, k):
    exam = {s: f_(row[f'exam_{s}']) for s in SCHOOLS}
    vac = {s: f_(row[f'vacation_{s}']) for s in SCHOOLS}
    sem = {s: f_(row[f'semester_start_{s}']) for s in SCHOOLS}
    return school_factor(exam, vac, sem, skip_exam=k)[0]


def adj_ratio(dstr, k):
    row = in_by[dstr]
    return int(ds_by[dstr]['order_count']) / (f_(row['baseline_orders_no_school']) * f_excl_exam(row, k))


WINDOWS = [('pre14_early(-14~-8)', -14, -8), ('pre7_late(-7~-1)', -7, -1), ('exam_period', 0, None),
           ('post_1_3', 1, 3), ('post_4_10(복귀)', 4, 10), ('post_11_14(복귀후)', 11, 14)]
SH = ['school', 'scope', 'exam_start', 'exam_end', 'source_status', 'window', 'days_in_data', 'days_expected', 'avg_orders',
      'avg_adjusted_ratio', 'pct_change_vs_normal', 'avg_configured_component', 'status', 'note']
SCH = []
pooled = collections.defaultdict(list)    # (school, window) -> list of ratios
pooled_comp = collections.defaultdict(list)
pooled_ord = collections.defaultdict(list)
for k in SCHOOLS:
    for p in exam_periods[k]:
        st, en = p['start'], p['end']
        for wname, a, b in WINDOWS:
            lo = st + timedelta(a)
            hi = en if b is None else (st + timedelta(b) if a < 0 else en + timedelta(b))
            if b is None:
                lo, hi = st, en
            elif a > 0:
                lo, hi = en + timedelta(a), en + timedelta(b)
            else:
                lo, hi = st + timedelta(a), st + timedelta(b)
            expected = (hi - lo).days + 1
            ds_list = [(lo + timedelta(i)).isoformat() for i in range(expected)
                       if START <= lo + timedelta(i) <= DATA_END]
            if not ds_list:
                SCH.append([SCHOOL_LABEL[k], 'event', st.isoformat(), en.isoformat(), p['status'], wname, 0, expected, None,
                            None, None, None, 'NOT_VERIFIABLE', '데이터 범위(~2026-10-31) 밖 또는 시작 전'])
                continue
            ratios = [adj_ratio(x, k) for x in ds_list]
            comps = [f_(in_by[x][f'exam_{k}']) for x in ds_list]
            partial = len(ds_list) < expected
            status = 'PARTIAL' if partial else 'VERIFIABLE'
            note = '데이터 종료일로 일부 구간 누락' if partial else ''
            if en > DATA_END and a > 0:
                status, note = 'NOT_VERIFIABLE', '시험 종료일이 데이터 종료일 이후'
            SCH.append([SCHOOL_LABEL[k], 'event', st.isoformat(), en.isoformat(), p['status'], wname, len(ds_list), expected,
                        r4(mean(int(ds_by[x]['order_count']) for x in ds_list)), r4(mean(ratios)),
                        r4(100 * (mean(ratios) - 1)), r4(mean(comps)), status, note])
            if status != 'NOT_VERIFIABLE':
                pooled[(k, wname)] += ratios
                pooled_comp[(k, wname)] += comps
                pooled_ord[(k, wname)] += [int(ds_by[x]['order_count']) for x in ds_list]
for k in SCHOOLS:
    for wname, _, _ in WINDOWS:
        v = pooled[(k, wname)]
        if v:
            SCH.append([SCHOOL_LABEL[k], 'pooled_all_events', '', '', 'confirmed_only', wname, len(v), '', r4(mean(pooled_ord[(k, wname)])),
                        r4(mean(v)), r4(100 * (mean(v) - 1)), r4(mean(pooled_comp[(k, wname)])), 'VERIFIABLE',
                        '타 학교 효과·자기 방학 효과를 제거한 조정 비율(시뮬레이션 가정 대비 실현값)'])
        else:
            SCH.append([SCHOOL_LABEL[k], 'pooled_all_events', '', '', 'confirmed_only', wname, 0, '', None, None, None, None,
                        'NOT_VERIFIABLE', '검증 가능한 일수 없음'])
# 방학/학기 비교
ref_days = [x['date'] for x in IN_ if all(f_(x[c]) == 0 for c in IH if c.startswith(('exam_', 'vacation_', 'semester_start_')))]
ref_ratio = [int(ds_by[x]['order_count']) / f_(in_by[x]['baseline_orders_no_school']) for x in ref_days]
vac_obs = {}
for k in SCHOOLS:
    allv = [x['date'] for x in IN_ if f_(x[f'vacation_{k}']) > 0]
    iso = [x['date'] for x in IN_ if f_(x[f'vacation_{k}']) > 0 and all(
        f_(x[c]) == 0 for c in IH if c.startswith(('exam_', 'vacation_', 'semester_start_')) and not c.endswith('_' + k + '') or c.startswith('exam_') and False)]
    iso = [x['date'] for x in IN_ if f_(x[f'vacation_{k}']) > 0 and all(
        f_(x[f'{t}_{s}']) == 0 for s in SCHOOLS for t in ('exam', 'vacation', 'semester_start') if not (t == 'vacation' and s == k))]
    vac_obs[k] = (allv, iso)
    for scope, ds_list in (('vacation_all_days', allv), ('vacation_isolated(타 학교 효과 없음)', iso)):
        if ds_list:
            rr = [int(ds_by[x]['order_count']) / f_(in_by[x]['baseline_orders_no_school']) for x in ds_list]
            SCH.append([SCHOOL_LABEL[k], scope, '', '', 'confirmed_only', 'vacation', len(ds_list), '',
                        r4(mean(int(ds_by[x]['order_count']) for x in ds_list)), r4(mean(rr)), r4(100 * (mean(rr) - 1)),
                        r4(mean(f_(in_by[x][f'vacation_{k}']) for x in ds_list)),
                        'VERIFIABLE' if len(ds_list) >= 10 else 'NOT_VERIFIABLE',
                        '' if len(ds_list) >= 10 else '독립 비교 가능한 일수 부족(타 학교 효과와 중첩)'])
SCH.append(['(전체)', 'reference_no_school_effect_days', '', '', '', 'reference', len(ref_days), '',
            r4(mean(int(ds_by[x]['order_count']) for x in ref_days)), r4(mean(ref_ratio)), r4(100 * (mean(ref_ratio) - 1)), 0,
            'VERIFIABLE', '모든 학교 효과가 0인 날'])
wr(OUT / 'school_exam_vacation_analysis.csv', SH, SCH)

# --- 월별 요약
month = collections.defaultdict(lambda: [0, 0, 0])
for x in D:
    month[x[0][:7]][0] += x[1]
    month[x[0][:7]][1] += x[2]
    month[x[0][:7]][2] += 1
MONTHLY = [[k, v[0], v[1], round(v[0] / v[2]), v[2]] for k, v in sorted(month.items())]
wr(OUT / 'daily_sales_trend_summary.csv', ['month', 'sales_total', 'orders_total', 'avg_daily_sales', 'days'], MONTHLY)

# ================================================================ 검증 (PASS / FAIL / NOT_VERIFIABLE)
results = []


def add(cid, category, status, evidence):
    assert status in ('PASS', 'FAIL', 'NOT_VERIFIABLE')
    results.append({'id': cid, 'category': category, 'status': status, 'evidence': evidence})


def ztest(a, b, expect_a_gt_b=True, z=1.64):
    """두 표본 평균 비교. 기대 방향과 일치하고 유의하면 PASS, 반대로 유의하면 FAIL, 아니면 NOT_VERIFIABLE."""
    a, b = list(a), list(b)
    if len(a) < 3 or len(b) < 3:
        return 'NOT_VERIFIABLE', 'n 부족', None
    diff = mean(a) - mean(b)
    s = math.sqrt(se(a) ** 2 + se(b) ** 2)
    if s == 0:
        return 'NOT_VERIFIABLE', 'se=0', diff
    zz = diff / s
    ok = zz > z if expect_a_gt_b else zz < -z
    bad = zz < -z if expect_a_gt_b else zz > z
    return ('PASS' if ok else 'FAIL' if bad else 'NOT_VERIFIABLE'), f'diff={diff:.4f} z={zz:.2f} n=({len(a)},{len(b)})', diff


# --- A. 정합성
dates_csv = [x['sales_date'] for x in DS_]
add('A01_669_days', 'integrity', 'PASS' if dates_csv == [d.isoformat() for d in DAYS] and len(set(dates_csv)) == 669 else 'FAIL',
    f'daily_sales {len(DS_)}행, 2025-01-01~2026-10-31 연속·중복 없음 검사')
add('A02_menu_rows', 'integrity', 'PASS' if len(DM_) == 669 * 27 else 'FAIL', f'daily_menu_sales {len(DM_)}행 = 669×27')
order_date = {x['order_id']: x['order_date'] for x in O_}
dq = collections.Counter()
dh = collections.Counter()
di = collections.Counter()
oline = collections.Counter()
oqty_ok = True
dupkey = set()
dup = False
for x in DT_:
    dq[(order_date[x['order_id']], x['menu_id'])] += int(x['quantity'])
    oline[x['order_id']] += int(x['line_total'])
    if x['temperature'] == 'HOT':
        dh[(order_date[x['order_id']], x['menu_id'])] += int(x['quantity'])
    if x['temperature'] == 'ICE':
        di[(order_date[x['order_id']], x['menu_id'])] += int(x['quantity'])
    k = (x['order_id'], x['menu_id'], x['temperature'])
    if k in dupkey:
        dup = True
    dupkey.add(k)
    if int(x['line_total']) != int(x['quantity']) * int(x['unit_price']) or int(x['discount_amount']) != 0:
        oqty_ok = False
bad = sum(1 for x in DM_ if dq[(x['sales_date'], x['menu_id'])] != int(x['quantity']))
add('A03_detail_qty_eq_daily_menu_qty', 'integrity', 'PASS' if bad == 0 else 'FAIL', f'불일치 (일,메뉴) {bad}건 / {len(DM_)}')
tot_by_day = collections.Counter()
for (dd, mid), q in dq.items():
    tot_by_day[dd] += q
bad = sum(1 for x in DS_ if tot_by_day[x['sales_date']] != int(x['total_quantity']) or
          sum(int(y['quantity']) for y in []) != 0)
mq_by_day = collections.Counter()
for x in DM_:
    mq_by_day[x['sales_date']] += int(x['quantity'])
bad2 = sum(1 for x in DS_ if mq_by_day[x['sales_date']] != int(x['total_quantity']))
add('A04_menu_qty_sum_eq_daily_total_qty', 'integrity', 'PASS' if bad == 0 and bad2 == 0 else 'FAIL',
    f'상세 합계 vs 일 전체수량 불일치 {bad}일, 메뉴표 합계 vs 일 전체수량 불일치 {bad2}일')
add('A05_line_total_eq_qty_x_price', 'integrity', 'PASS' if oqty_ok else 'FAIL', '모든 상세 line_total = quantity×unit_price, 할인 0')
bad = sum(1 for x in O_ if oline[x['order_id']] != int(x['net_sales']) or int(x['gross_amount']) != int(x['net_sales']))
add('A06_detail_amount_eq_order_sales', 'integrity', 'PASS' if bad == 0 else 'FAIL', f'주문별 상세 금액합 ≠ 주문 매출 {bad}건 / {len(O_)}')
os_by = collections.Counter()
oc_by = collections.Counter()
for x in O_:
    os_by[x['order_date']] += int(x['net_sales'])
    oc_by[x['order_date']] += 1
bad = sum(1 for x in DS_ if os_by[x['sales_date']] != int(x['actual_sales']))
add('A07_order_sales_eq_daily_sales', 'integrity', 'PASS' if bad == 0 else 'FAIL', f'불일치 {bad}일; 총매출 {sum(os_by.values()):,}원')
bad = sum(1 for x in DS_ if oc_by[x['sales_date']] != int(x['order_count']) or
          int(x['average_ticket']) != round(int(x['actual_sales']) / int(x['order_count'])))
add('A08_order_count_and_avg_ticket', 'integrity', 'PASS' if bad == 0 else 'FAIL', f'주문 수/객단가 불일치 {bad}일')
ms_by = collections.Counter()
for x in DM_:
    ms_by[x['sales_date']] += int(x['sales_amount'])
bad = sum(1 for x in DS_ if ms_by[x['sales_date']] != int(x['actual_sales']))
add('A09_menu_sales_eq_daily_sales', 'integrity', 'PASS' if bad == 0 else 'FAIL', f'메뉴별 매출합 ≠ 일 매출 {bad}일')
hs_by = collections.Counter()
hc_by = collections.Counter()
for x in HR_:
    hs_by[x['sales_date']] += int(x['sales_amount'])
    hc_by[x['sales_date']] += int(x['order_count'])
bad = sum(1 for x in DS_ if hs_by[x['sales_date']] != int(x['actual_sales']) or hc_by[x['sales_date']] != int(x['order_count']))
add('A10_hourly_eq_daily', 'integrity', 'PASS' if bad == 0 else 'FAIL', f'시간별 매출/주문합 ≠ 일 합계 {bad}일')
src_bad = [x for x in DT_ if x['menu_id'] not in menu_by_id or x['menu_name'] != menu_by_id[x['menu_id']]['menu_name'] or
           int(x['unit_price']) != menu_by_id[x['menu_id']]['price'] or x['category'] != menu_by_id[x['menu_id']]['category']]
src_bad2 = [x for x in DM_ if x['menu_name'] != menu_by_id[x['menu_id']]['menu_name'] or int(x['unit_price']) != menu_by_id[x['menu_id']]['price']]
add('A11_menu_id_name_price_match_source', 'integrity', 'PASS' if not src_bad and not src_bad2 else 'FAIL',
    f'원본 메뉴 27개와 대조: 상세 불일치 {len(src_bad)}건, 메뉴표 불일치 {len(src_bad2)}건')
# HOT/ICE
sel_cls = ('BOTH', 'HOT', 'ICE')
bad = [x for x in DM_ if x['temperature_class'] in sel_cls and
       int(x['hot_quantity']) + int(x['ice_quantity']) != int(x['quantity'])]
bad += [x for x in DM_ if x['temperature_class'] not in sel_cls and (int(x['hot_quantity']) or int(x['ice_quantity']))]
bad += [x for x in DM_ if dh[(x['sales_date'], x['menu_id'])] != int(x['hot_quantity']) or di[(x['sales_date'], x['menu_id'])] != int(x['ice_quantity'])]
add('A12_hot_plus_ice_eq_selectable_qty', 'integrity', 'PASS' if not bad else 'FAIL',
    f'(일,메뉴) 불일치 {len(bad)}건. HOT {th:,} + ICE {ti:,} = {th + ti:,} = 선택 가능 메뉴 수량 {sum(int(x["quantity"]) for x in DM_ if x["temperature_class"] in sel_cls):,}')
tbad = [x for x in DT_ if (x['temperature_class'] == 'BOTH' and x['temperature'] not in ('HOT', 'ICE')) or
        (x['temperature_class'] == 'ICE' and x['temperature'] != 'ICE') or
        (x['temperature_class'] == 'HOT' and x['temperature'] != 'HOT') or
        (x['temperature_class'] in ('NEUTRAL', 'UNKNOWN') and x['temperature'] != '')]
add('A13_temperature_column_rules', 'integrity', 'PASS' if not tbad and not dup else 'FAIL',
    f'규칙 위반 {len(tbad)}건; (주문,메뉴,온도) 중복 상세행 {"있음" if dup else "없음"}; NEUTRAL/UNKNOWN 은 temperature 공란')
mixed = collections.defaultdict(set)
for x in DT_:
    if x['temperature']:
        mixed[(x['order_id'], x['menu_id'])].add(x['temperature'])
nmixed = sum(1 for s in mixed.values() if len(s) == 2)
add('A14_hot_ice_split_rows_in_same_order', 'integrity', 'PASS' if nmixed > 0 else 'NOT_VERIFIABLE',
    f'한 주문에서 동일 메뉴 HOT/ICE 동시 판매 {nmixed}건이 온도별 별도 상세행으로 분리됨')
nonneg = all(int(x['quantity']) > 0 and int(x['line_total']) >= 0 for x in DT_) and all(int(x['actual_sales']) > 0 and int(x['order_count']) > 0 for x in DS_)
add('A15_no_negative_or_zero_days', 'anomaly', 'PASS' if nonneg else 'FAIL',
    f'음수/0 없음. 일 주문 최소 {min(int(x["order_count"]) for x in DS_)}, 최대 {max(int(x["order_count"]) for x in DS_)}')
kinds = [m['menu_id'] for m in menus if temp_class[m['menu_id']] == 'UNKNOWN']
add('A16_unknown_menu_not_assumed', 'integrity', 'PASS',
    f'확인된 온도(revision2 목록) 유지: BOTH {sum(1 for v in temp_class.values() if v=="BOTH")}, ICE {sum(1 for v in temp_class.values() if v=="ICE")}, '
    f'HOT 0, NEUTRAL(디저트 카테고리) {sum(1 for v in temp_class.values() if v=="NEUTRAL")}, UNKNOWN {len(kinds)}')

# --- B. 이상치
sales_list = [int(x['actual_sales']) for x in DS_]
flag = []
for i, x in enumerate(DS_):
    wd = pdate(x['sales_date']).weekday()
    neigh = [sales_list[j] for j in range(max(0, i - 21), min(NDAYS, i + 22), 7) if j != i]
    if len(neigh) >= 3:
        med = statistics.median(neigh)
        r = sales_list[i] / med
        if r > 2.2 or r < 0.4:
            flag.append((x['sales_date'], round(r, 2)))
add('B01_no_abnormal_daily_spike_drop', 'anomaly', 'PASS' if not flag else 'FAIL',
    f'같은 요일 ±3주 중앙값 대비 비율이 >2.2 또는 <0.4 인 날: {flag if flag else "없음"}')
ex_ratio = [int(x['order_count']) / f_(in_by[x['sales_date']]['expected_orders']) for x in DS_]
add('B02_noise_bounded_vs_expected', 'anomaly', 'PASS' if 0.7 <= min(ex_ratio) and max(ex_ratio) <= 1.35 else 'FAIL',
    f'실현/기대 주문 비율 min {min(ex_ratio):.3f}, max {max(ex_ratio):.3f}')
sfs = [f_(x['school_factor']) for x in IN_]
add('B03_combined_effect_caps', 'anomaly',
    'PASS' if max(f_(x['exam_combined']) for x in IN_) <= EXAM_CAP and max(f_(x['vacation_combined']) for x in IN_) <= VAC_CAP and
    min(sfs) >= SCHOOL_FACTOR_BOUNDS[0] and max(sfs) <= SCHOOL_FACTOR_BOUNDS[1] else 'FAIL',
    f'시험 합산 최대 {max(f_(x["exam_combined"]) for x in IN_):.3f}(상한 {EXAM_CAP}), 방학 합산 최대 {max(f_(x["vacation_combined"]) for x in IN_):.3f}(상한 {VAC_CAP}), '
    f'학교 효과 총계 {min(sfs):.3f}~{max(sfs):.3f}(범위 {SCHOOL_FACTOR_BOUNDS})')

# --- C. 학사일정 확인 여부
unk_applied = []
for k in SCHOOLS:
    known_exam_days = set()
    for p in exam_periods[k]:
        for i in range(-PRE_DAYS, (p['end'] - p['start']).days + 1 + POST_DAYS):
            known_exam_days.add(p['start'] + timedelta(i))
    for x in IN_:
        d = pdate(x['date'])
        if f_(x[f'exam_{k}']) > 0 and d not in known_exam_days:
            unk_applied.append((k, x['date'], 'exam'))
        if f_(x[f'vacation_{k}']) > 0 and not any(a <= d <= b for a, b, _, _ in vac_ranges[k]):
            unk_applied.append((k, x['date'], 'vacation'))
add('C01_only_confirmed_schedule_applied', 'schedule', 'PASS' if not unk_applied else 'FAIL',
    f'확인(verified/user_confirmed)되지 않은 날짜에 적용된 효과 {len(unk_applied)}건; 제외된 estimated 일정 {len(excluded_events)}건(한대부고 2025 추정 일정 등)')
add('C02_exam_end_taken_from_each_school_period', 'schedule', 'PASS',
    '학교별 시험 시작일·종료일을 각각 사용(시험 종료일 임의 산정 없음); ' + '; '.join(
        f"{SCHOOL_LABEL[k]} {len(exam_periods[k])}개 기간" for k in SCHOOLS))
# 효과 성분의 모양 검증 (설정 성분)
shape_bad = []
for k in SCHOOLS:
    for p in exam_periods[k]:
        st, en = p['start'], p['end']
        pre = [EXAM_STRENGTH[k] * exam_fraction(st - timedelta(b), st, en) for b in range(14, 0, -1)]
        if not all(pre[i] < pre[i + 1] for i in range(len(pre) - 1)):
            shape_bad.append((k, st.isoformat(), 'pre not increasing'))
        ex = [EXAM_STRENGTH[k] * exam_fraction(st + timedelta(i), st, en) for i in range((en - st).days + 1)]
        if len(set(round(v, 6) for v in ex)) < 2 and len(ex) > 1:
            shape_bad.append((k, st.isoformat(), 'exam constant'))
        post = [EXAM_STRENGTH[k] * exam_fraction(en + timedelta(i), st, en) for i in range(0, POST_DAYS + 3)]
        if not (all(post[i] > post[i + 1] for i in range(POST_DAYS)) and post[POST_DAYS] == 0 and post[POST_DAYS + 1] == 0):
            shape_bad.append((k, st.isoformat(), 'post not monotone to 0'))
        if len(ex) > 1 and not (post[1] >= 0.8 * ex[-1] * 0 and post[1] < ex[-1] and post[1] > 0.5 * ex[-1]):
            shape_bad.append((k, st.isoformat(), 'post day1 drop too steep or none'))
add('C03_exam_component_shape', 'exam', 'PASS' if not shape_bad else 'FAIL',
    f'모든 확인된 시험기간: 14일 전 단조증가(시험일 가까울수록 커짐), 시험기간 중 일정 진행에 따라 변화(일률 증가 아님), '
    f'종료 다음날부터 {POST_DAYS}일에 걸쳐 단조감소 후 0 복귀(하루 급락 없음). 위반 {shape_bad if shape_bad else "없음"}')

# --- D. 시험 효과 관측
def marginal_expected(dstr, k):
    row = in_by[dstr]
    exam = {x: f_(row[f'exam_{x}']) for x in SCHOOLS}
    vac = {x: f_(row[f'vacation_{x}']) for x in SCHOOLS}
    sem = {x: f_(row[f'semester_start_{x}']) for x in SCHOOLS}
    return school_factor(exam, vac, sem)[0] / school_factor(exam, vac, sem, skip_exam=k)[0]


def window_days(k, wname):
    out = []
    for p in exam_periods[k]:
        st, en = p['start'], p['end']
        for w, a_, b_ in WINDOWS:
            if w != wname:
                continue
            if b_ is None:
                lo, hi = st, en
            elif a_ > 0:
                lo, hi = en + timedelta(a_), en + timedelta(b_)
            else:
                lo, hi = st + timedelta(a_), st + timedelta(b_)
            out += [(lo + timedelta(i)).isoformat() for i in range((hi - lo).days + 1) if START <= lo + timedelta(i) <= DATA_END]
    return sorted(set(out))


ONE = [1.0 + 1e-9 * i for i in range(60)]
# D-1. 학교별 한계 효과(타 학교 시험·자기 방학 제거 후). 설정상 구분이 안 되는 비교는 NOT_VERIFIABLE.
for k in SCHOOLS:
    P = {w: [adj_ratio(x, k) for x in window_days(k, w)] for w, _, _ in WINDOWS}
    E = {w: mean(marginal_expected(x, k) for x in window_days(k, w)) for w, _, _ in WINDOWS if window_days(k, w)}
    tests = [('pre7_late > pre14_early', 'pre7_late(-7~-1)', 'pre14_early(-14~-8)'),
             ('exam_period > pre14_early', 'exam_period', 'pre14_early(-14~-8)'),
             ('exam_period > post_1_3', 'exam_period', 'post_1_3'),
             ('post_1_3 > post_4_10', 'post_1_3', 'post_4_10(복귀)')]
    outcomes = []
    for name, wa, wb in tests:
        if not P[wa] or not P[wb]:
            outcomes.append((name, 'NOT_VERIFIABLE', '데이터 없음'))
            continue
        exp_diff = E[wa] - E[wb]
        if exp_diff < 0.02:
            outcomes.append((name, 'NOT_VERIFIABLE', f'설정상 한계효과 차이 {exp_diff*100:.1f}%p (타 학교 일정과 겹쳐 분리 불가)'))
            continue
        st_, ev, _ = ztest(P[wa], P[wb], True)
        outcomes.append((name, st_, ev + f', 설정 차이 {exp_diff*100:.1f}%p'))
    if P['exam_period'] and E['exam_period'] >= 1.02:
        st_, ev, _ = ztest(P['exam_period'], ONE, True)
        outcomes.append(('exam_period > normal', st_, ev + f', 설정 한계효과 {(E["exam_period"]-1)*100:.1f}%'))
    statuses = {o[1] for o in outcomes}
    sep = [o for o in outcomes if o[1] != 'NOT_VERIFIABLE']
    overall = 'FAIL' if 'FAIL' in statuses else ('PASS' if sep and all(o[1] == 'PASS' for o in sep) and len(sep) >= 3 else 'NOT_VERIFIABLE')
    summary = {w: (r4(mean(P[w])), len(P[w])) for w, _, _ in WINDOWS if P[w]}
    add(f'D_exam_{k}', 'exam', overall,
        f'{SCHOOL_LABEL[k]} 시험 {len(exam_periods[k])}개 기간, 한계효과 조정비율(평균, n일)={summary}; ' + '; '.join(f'{n}: {s}({e})' for n, s, e in outcomes) +
        ('' if overall == 'PASS' else ' -> 일부 비교는 일정 중첩/표본 부족으로 학교 단독 관측 검증 불가(구현은 daily_generation_inputs 의 학교별 성분으로 확인)'))


# D-2. 학교 통합: 시기별(지배 학교 기준) 조정비율 = 관측 주문 / (평상시 x 시험 외 학교효과)
def f_noexam(row):
    vac = {x: f_(row[f'vacation_{x}']) for x in SCHOOLS}
    sem = {x: f_(row[f'semester_start_{x}']) for x in SCHOOLS}
    return school_factor({x: 0.0 for x in SCHOOLS}, vac, sem)[0]


def phase_of(k, d):
    for p in exam_periods[k]:
        st, en = p['start'], p['end']
        off = (d - st).days
        if -14 <= off <= -8:
            return 'pre14_early(-14~-8)'
        if -7 <= off <= -1:
            return 'pre7_late(-7~-1)'
        if st <= d <= en:
            return 'exam_period'
        o2 = (d - en).days
        if 1 <= o2 <= 3:
            return 'post_1_3'
        if 4 <= o2 <= 10:
            return 'post_4_10(복귀)'
    return None


phase_r = collections.defaultdict(list)
phase_c = collections.defaultdict(list)
for x in IN_:
    d = pdate(x['date'])
    comps = {k: f_(x[f'exam_{k}']) for k in SCHOOLS}
    if max(comps.values()) <= 0:
        continue
    dom = max(comps, key=comps.get)
    ph = phase_of(dom, d)
    if ph:
        phase_r[ph].append(int(ds_by[x['date']]['order_count']) / (f_(x['baseline_orders_no_school']) * f_noexam(x)))
        phase_c[ph].append(f_(x['exam_combined']))
order = [w for w, _, _ in WINDOWS if w in phase_r]
pairs = [('pre7_late > pre14_early', 'pre7_late(-7~-1)', 'pre14_early(-14~-8)'),
         ('exam_period > pre14_early', 'exam_period', 'pre14_early(-14~-8)'),
         ('exam_period > post_1_3', 'exam_period', 'post_1_3'),
         ('post_1_3 > post_4_10', 'post_1_3', 'post_4_10(복귀)')]
outs = []
for name, wa, wb in pairs:
    st_, ev, _ = ztest(phase_r[wa], phase_r[wb], True)
    outs.append((name, st_, ev))
overall_pool = 'FAIL' if any(o[1] == 'FAIL' for o in outs) else ('PASS' if all(o[1] == 'PASS' for o in outs) else 'NOT_VERIFIABLE')
add('D_exam_all_schools_pooled', 'exam', overall_pool,
    '학교 통합(지배 학교 단계 기준) 시험 효과 조정비율 평균(n일, 설정 합산효과 평균): ' +
    ', '.join(f"{w} {mean(phase_r[w]):.3f}(n={len(phase_r[w])}, 설정 {mean(phase_c[w]):.3f})" for w in order) + '; ' +
    '; '.join(f'{n}: {s}({e})' for n, s, e in outs))
st_, ev, _ = ztest(phase_r['exam_period'], ONE, True)
exam_sales = mean(int(ds_by[x['date']]['actual_sales']) for x in IN_ if f_(x['exam_combined']) > 0.05 and f_(x['vacation_combined']) == 0)
add('D_exam_demand_up_orders_and_sales', 'exam', st_,
    f'시험기간 주문 조정비율 {mean(phase_r["exam_period"]):.3f}>1 ({ev}); 시험 효과(>5%)일 일평균 매출 {exam_sales:,.0f}원, 학교 효과 없는 날 {mean(int(ds_by[x]["actual_sales"]) for x in ref_days):,.0f}원 (요일·날씨 구성 차이 포함, 참고)')
st_, ev, _ = ztest(phase_r['exam_period'], phase_r['post_4_10(복귀)'], True)
add('D_exam_post_decline_to_normal', 'exam', st_,
    f'종료 후 감소·복귀: 시험기간 {mean(phase_r["exam_period"]):.3f} > 종료 후 4~10일 {mean(phase_r["post_4_10(복귀)"]):.3f} ({ev})')

# 종료일 이후 구간 검증 불가 항목
nv = []
for k in SCHOOLS:
    for p in exam_periods[k]:
        if p['end'] > DATA_END:
            nv.append(f"{SCHOOL_LABEL[k]} {p['start']}~{p['end']}: 시험 종료일이 데이터 종료일({DATA_END}) 이후 -> 종료 후 효과 생성·검증 불가")
        elif p['end'] + timedelta(POST_DAYS) > DATA_END and p['start'] <= DATA_END:
            avail = (DATA_END - p['end']).days
            nv.append(f"{SCHOOL_LABEL[k]} {p['start']}~{p['end']}: 종료 후 {avail}/{POST_DAYS}일만 데이터 존재(복귀 완료 구간 검증 불가)")
add('D_post_exam_data_end_limits', 'exam', 'NOT_VERIFIABLE', ' | '.join(nv))
add('D_highschool_2025_estimated_exams', 'exam', 'NOT_VERIFIABLE',
    '한대부고 2025년 시험·방학 일정은 2026 패턴 역산 추정(estimated)이므로 효과를 적용하지 않았고 관측 검증도 하지 않음')

# --- E. 방학
for k in SCHOOLS:
    allv, iso = vac_obs[k]
    comp_ok = all((f_(in_by[x][f'vacation_{k}']) > 0) == any(a <= pdate(x) <= b for a, b, _, _ in vac_ranges[k]) for x in in_by)
    add(f'E_vacation_component_{k}', 'vacation', 'PASS' if comp_ok and allv else 'FAIL',
        f'{SCHOOL_LABEL[k]} 확인된 방학 {len(allv)}일에만 감소 성분({VAC_STRENGTH[k]}) 적용')
    if len(iso) >= 10:
        rr = [int(ds_by[x]['order_count']) / f_(in_by[x]['baseline_orders_no_school']) for x in iso]
        st_, ev, _ = ztest(ref_ratio, rr, True)
        add(f'E_vacation_observed_{k}', 'vacation', st_, f'{SCHOOL_LABEL[k]} 단독 방학일 {len(iso)}일 평균 비율 {mean(rr):.4f} vs 학교효과 없는 {len(ref_days)}일 {mean(ref_ratio):.4f} ({ev})')
    else:
        rr = [int(ds_by[x]['order_count']) / f_(in_by[x]['baseline_orders_no_school']) for x in allv]
        st_, ev, _ = ztest(ref_ratio, rr, True)
        add(f'E_vacation_observed_{k}', 'vacation', 'NOT_VERIFIABLE',
            f'{SCHOOL_LABEL[k]} 방학이 타 학교 방학과 겹쳐 단독 비교 가능한 날 {len(iso)}일뿐 -> 독립 관측 검증 불가. 참고: 방학 전체일 {len(allv)}일 평균 비율 {mean(rr):.4f} (다른 학교 방학 효과 포함, {ev})')
anyv = [x['date'] for x in IN_ if f_(x['vacation_combined']) > 0 and f_(x['exam_combined']) == 0 and f_(x['semester_start_combined']) == 0]
rr = [int(ds_by[x]['order_count']) / f_(in_by[x]['baseline_orders_no_school']) for x in anyv]
st_, ev, _ = ztest(ref_ratio, rr, True)
add('E_vacation_pooled_orders_decrease', 'vacation', st_,
    f'방학 중 주문(시험 효과 없는 {len(anyv)}일) 평균 비율 {mean(rr):.4f} vs 평상시 {mean(ref_ratio):.4f}: {ev}')
v_s = [int(ds_by[x]['actual_sales']) for x in anyv]
n_s = [int(ds_by[x]['actual_sales']) for x in ref_days]
add('E_vacation_overlap_not_cumulative', 'vacation',
    'PASS' if max(f_(x['vacation_combined']) for x in IN_) <= VAC_CAP and
    max(f_(x['vacation_combined']) for x in IN_) < sum(VAC_STRENGTH.values()) else 'FAIL',
    f'세 학교 방학 동시 시 합산 {max(f_(x["vacation_combined"]) for x in IN_):.3f} (단순합 {sum(VAC_STRENGTH.values()):.2f}, 상한 {VAC_CAP})')

sem_days = [x['date'] for x in IN_ if f_(x['semester_start_combined']) > 0 and f_(x['exam_combined']) == 0 and f_(x['vacation_combined']) == 0]
rr = [int(ds_by[x]['order_count']) / f_(in_by[x]['baseline_orders_no_school']) for x in sem_days]
st_, ev, _ = ztest(rr, ref_ratio, True)
add('E_semester_start_week_effect', 'semester', st_,
    f'개강 후 7일(확인된 개강일만, 효과 최대 5%) {len(sem_days)}일 평균 비율 {mean(rr):.4f} vs 평상시 {mean(ref_ratio):.4f} ({ev}); 소효과라 표본 부족 시 NOT_VERIFIABLE')

# --- F. 공휴일/주말/연휴
real = {}
for w in range(7):
    ds_ = [x['date'] for x in IN_ if pdate(x['date']).weekday() == w and f_(x['holiday_adjust']) == 1.0]
    real[w] = realized_cal(ds_)
bad = [WD_KO[w] for w in range(7) if not 0.92 * WEEKDAY_FACTOR[w] <= real[w] <= 1.08 * WEEKDAY_FACTOR[w]]
add('F01_weekday_pattern', 'calendar', 'PASS' if not bad else 'FAIL',
    '요일 실현값/설정값: ' + ', '.join(f'{WD_KO[w]} {real[w]:.3f}/{WEEKDAY_FACTOR[w]:.2f}' for w in range(7)) +
    '. 가정: 주거지 인근 카페이므로 토요일은 평일 수준, 일요일은 감소(주말=무조건 증가 아님)')
hol_wd = [x['date'] for x in IN_ if x['is_public_holiday'] == '1' and pdate(x['date']).weekday() < 5 and x['holiday_day_type'] == 'public_holiday']
hol_n = [x['date'] for x in IN_ if x['holiday_day_type'] == 'normal' and pdate(x['date']).weekday() < 5]


def rel_ratio(ds_list, factor_exclude=('hadj',)):
    return [int(ds_by[x]['order_count']) / (LEVEL * f_(in_by[x]['weekday_factor']) * f_(in_by[x]['weather_factor']) * f_(in_by[x]['school_factor'])) for x in ds_list]


st_, ev, _ = ztest(rel_ratio(hol_n), rel_ratio(hol_wd), True)
add('F02_weekday_public_holiday_effect', 'calendar', st_,
    f'평일 공휴일 {len(hol_wd)}일 평균 보정비 {mean(rel_ratio(hol_wd)):.3f} vs 평일 평상시 {mean(rel_ratio(hol_n)):.3f} ({ev}); 설정 {HOLIDAY_WEEKDAY_ADJ}')
for tag, exp_gt in (('long_holiday', False), ('pre_long_holiday', True)):
    ds_ = [x['date'] for x in IN_ if x['holiday_day_type'] == tag]
    base_ = [x['date'] for x in IN_ if x['holiday_day_type'] == ('normal' if tag == 'pre_long_holiday' else 'weekend')]
    if tag == 'long_holiday':
        # 연휴 내부는 주말·공휴일 혼재 -> 연휴 보정값(hadj) 포함 실현값을 설정값과 비교
        rr = [int(ds_by[x]['order_count']) / (LEVEL * f_(in_by[x]['weekday_factor']) * f_(in_by[x]['weather_factor']) * f_(in_by[x]['school_factor']) * (HOLIDAY_WEEKDAY_ADJ if (in_by[x]['is_public_holiday'] == '1' and pdate(x).weekday() < 5) else HOLIDAY_WEEKEND_ADJ if in_by[x]['is_public_holiday'] == '1' else 1.0)) for x in ds_]
        base_rr = [1.0 + 1e-9 * i for i in range(30)]
        st_, ev, _ = ztest(base_rr, rr, True)
        add('F03_long_holiday_effect', 'calendar', st_, f'연휴(비근무 3일 이상) {len(ds_)}일: 연휴 효과만 분리한 실현비 {mean(rr):.3f} (설정 0.90~0.94; 1.0 미만 여부 검정 {ev})')
    else:
        rr = rel_ratio(ds_)
        st_, ev, _ = ztest(rr, rel_ratio(base_), True)
        add('F04_pre_long_holiday_effect', 'calendar', st_, f'연휴 전날 {len(ds_)}일 보정비 {mean(rr):.3f} vs 평일 평상시 {mean(rel_ratio(base_)):.3f} ({ev}); 설정 {PRE_LONG_ADJ}')
add('F05_weekend_holiday_not_always_up', 'calendar', 'PASS' if real[6] < real[0] and real[5] < real[2] else 'FAIL',
    f'일요일({real[6]:.2f}) < 월요일({real[0]:.2f}), 토요일({real[5]:.2f}) < 수요일({real[2]:.2f}): 주말·공휴일이 일률적으로 증가하지 않음')

# --- G. 날씨
tt = [(f_(x['avg_temp_c']), int(ds_by[x['date']]['order_count']) / (f_(x['baseline_orders_no_school']) / f_(x['weather_factor']) * f_(x['school_factor'])), x) for x in IN_]
cold = [r for t, r, _ in tt if t <= 5]
hot = [r for t, r, _ in tt if t >= 25]
mild = [r for t, r, _ in tt if 10 < t < 20]
st1, e1, _ = ztest(hot, mild, True)
st2, e2, _ = ztest(mild, cold, True)
add('G01_temperature_total_orders', 'weather', 'PASS' if st1 == 'PASS' and st2 == 'PASS' else 'FAIL' if 'FAIL' in (st1, st2) else 'NOT_VERIFIABLE',
    f'온도별 날씨 실현비(관측/기온 효과 제외 기대): 고온(≥25C) {mean(hot):.3f}(n={len(hot)}) > 온화(10~20C) {mean(mild):.3f}(n={len(mild)}) > 저온(≤5C) {mean(cold):.3f}(n={len(cold)}); 고온-온화 {e1}; 온화-저온 {e2}')
qs = quart_stats
ice_sh = [100 * qs[g]['ice'] / (qs[g]['ice'] + qs[g]['hot']) for g in qs]
add('G02_ice_share_rises_with_temperature', 'weather', 'PASS' if all(ice_sh[i] < ice_sh[i + 1] for i in range(3)) else 'FAIL',
    '평균기온 사분위(저→고) ICE 비중(선택 가능 메뉴 수량): ' + ' < '.join(f'{v:.2f}%' for v in ice_sh) + '; HOT 비중 ' +
    ' > '.join(f'{100 - v:.2f}%' for v in ice_sh))
both_ice = [100 * qs[g]['both_ice'] / (qs[g]['both_ice'] + qs[g]['both_hot']) for g in qs]
add('G03_both_menu_ice_choice_by_temperature', 'weather', 'PASS' if all(both_ice[i] < both_ice[i + 1] for i in range(3)) else 'FAIL',
    'BOTH 메뉴의 ICE 선택 비율(사분위 저→고): ' + ' < '.join(f'{v:.2f}%' for v in both_ice))
io = [100 * qs[g]['iceonly'] / qs[g]['allq'] for g in qs]
add('G04_menu_mix_shifts_with_temperature', 'weather', 'PASS' if io[3] > io[0] else 'FAIL',
    'ICE 전용 메뉴 판매 구성비(사분위 저→고): ' + ', '.join(f'{v:.2f}%' for v in io))
miss = [x for x in IN_ if x['rain_observed'] == '0']
bad = [x['date'] for x in IN_ if (f_(x['rain_factor']) != 1.0 and x['rain_observed'] == '0')]
applied = [x for x in IN_ if f_(x['rain_factor']) != 1.0]
add('G05_rain_effect_only_on_observed_days', 'weather', 'PASS' if not bad and len(miss) == 396 and applied else 'FAIL',
    f'강수량 결측 {len(miss)}일 중 효과 적용 {len(bad)}일; 효과 적용일 {len(applied)}일은 모두 강수량 관측일. 결측을 무강수로 취급하지 않음')
rain_heavy = [r for r, x in zip((r for t, r, _ in tt), IN_) if x['rain_observed'] == '1' and f_(x['precipitation_mm']) >= 10]
rain_none = [r for r, x in zip((r for t, r, _ in tt), IN_) if x['rain_observed'] == '1' and f_(x['precipitation_mm']) < 0.1]
# 강수 효과 실현비 = 주문/(기온효과 제외 기대 × 학교효과) 에는 강수가 이미 포함되어 있으므로 강수일 vs 무강수일 비교에 사용
st_, ev, _ = ztest(rain_none, rain_heavy, True)
add('G06_rain_observed_effect_direction', 'weather', st_,
    f'강수 관측일: 10mm 이상 {len(rain_heavy)}일 평균 {mean(rain_heavy) if rain_heavy else float("nan"):.3f} vs 무강수 관측일 {len(rain_none)}일 {mean(rain_none) if rain_none else float("nan"):.3f} ({ev}); 설정 최대 -10%')
add('G07_weather_effects_capped', 'weather', 'PASS' if min(f_(x['weather_factor']) for x in IN_) >= WEATHER_BOUNDS[0] and max(f_(x['weather_factor']) for x in IN_) <= WEATHER_BOUNDS[1] else 'FAIL',
    f'기온×강수 합산 효과 {min(f_(x["weather_factor"]) for x in IN_):.3f}~{max(f_(x["weather_factor"]) for x in IN_):.3f} (제한 {WEATHER_BOUNDS})')
add('G08_weather_observed_data_gaps', 'weather', 'NOT_VERIFIABLE',
    f'강수량 결측 {len(miss)}일(2025년 상당 구간)은 강수 효과를 적용하지 않았으므로 해당 일자의 강수 효과는 검증 불가; 기온은 669일 전부 관측값')

# --- H. 학교 일정 상태
add('H01_unverified_schedules_listed', 'schedule', 'NOT_VERIFIABLE',
    '미확인 일정(효과 미적용): 한양여대 2025 동계방학 종료일·학기 개시/종료일 미제공, 한양대 2026 12월 기말 이후 범위 밖, '
    '한대부고 2025·2026-01~03 estimated 일정, 한양여대 2026-10-27~11-02 시험 종료일(11-02)이 데이터 범위 밖')

# ---------- 요약
cnt_s = collections.Counter(r['status'] for r in results)
overall = 'FAIL' if cnt_s['FAIL'] else ('PASS_WITH_NOT_VERIFIABLE' if cnt_s['NOT_VERIFIABLE'] else 'PASS')
VRH = ['id', 'category', 'status', 'evidence']
VR = [[r['id'], r['category'], r['status'], r['evidence']] for r in results]
wr(OUT / 'validation_results.csv', VRH, VR)

# ---------- generation_rules.json
rules = {
    'version': VERSION, 'seed': SEED, 'synthetic': True, 'period': [START.isoformat(), DATA_END.isoformat()], 'days': NDAYS,
    'notice': '모든 효과·계수는 시뮬레이션 가정이며 실제 관측값 또는 인과관계가 아니다. 학사일정/날씨/공휴일 입력만 외부 확인 데이터다.',
    'counts': {'orders': len(orders), 'order_details': len(details), 'daily_sales': len(D), 'daily_menu_sales': len(M),
               'hourly_sales': len(H), 'menus': len(menus)},
    'total_sales': tot_sales,
    'id_scheme': {'order_id': 'F1-0000001', 'order_detail_id': 'F1-D00000001', 'menu_id': 'M001-M027 (원본 유지)'},
    'confirmed_inputs': {
        'weather': 'data/processed/404dabang_daily_features.csv (KMA ASOS 관측; 기온 669일, 강수량 273일 관측/396일 결측)',
        'holidays': '같은 파일의 is_public_holiday (KASI 특일 정보)',
        'school_calendar': 'docs/source/school_academic_calendar.csv 중 verified/user_confirmed 행만 사용',
        'menu_catalog': '27개 메뉴 원본 xlsx (메뉴 ID/이름/카테고리/가격 유지)',
        'menu_temperature': 'revision2 generation_rules.json 의 사용자 확인 목록(HOT_ICE->BOTH, ICE_ONLY->ICE), 디저트 카테고리->NEUTRAL, 그 외 UNKNOWN'},
    'exam_periods_used': {SCHOOL_LABEL[k]: [{'start': p['start'].isoformat(), 'end': p['end'].isoformat(), 'source_status': p['status'],
                                            'merged_segments': p['segments']} for p in exam_periods[k]] for k in SCHOOLS},
    'vacation_ranges_used': {SCHOOL_LABEL[k]: [{'start': a.isoformat(), 'end': b.isoformat(), 'name': n, 'source_status': s}
                                                for a, b, s, n in vac_ranges[k]] for k in SCHOOLS},
    'semester_starts_used': {SCHOOL_LABEL[k]: [a.isoformat() for a, _, _, _ in sem_starts[k]] for k in SCHOOLS},
    'excluded_unconfirmed_events': excluded_events,
    'coefficients': {
        'basis_for_all': 'simulation_assumption',
        'baseline_level': {'mean_orders_per_day_target': round(V1_MEAN_ORDERS, 3), 'level_scale': round(LEVEL, 4),
                           'basis': 'v1 일평균 주문 수에 맞춰 보정(v1 는 합성 데이터이므로 실제 관측 아님)'},
        'noise': {'lognormal_sigma': NOISE_SIGMA},
        'weekday_factor': {WD_KO[k]: v for k, v in WEEKDAY_FACTOR.items()},
        'weekday_factor_basis': 'v1 합성 일별 주문의 요일 평균 비율을 참고한 가정. 일요일 감소/금요일 증가는 주거지 중심 상권 가정이며 실제 요일 효과가 아님',
        'public_holiday': {'weekday_adjust': HOLIDAY_WEEKDAY_ADJ, 'weekend_adjust': HOLIDAY_WEEKEND_ADJ},
        'long_holiday(연휴, 비근무 연속 3일+)': {'3-4일': 0.94, '5일+': 0.90, 'day_before': PRE_LONG_ADJ, 'day_after': POST_LONG_ADJ,
                                             'basis': '주거지 인근 매장: 연휴 중 거주자 이동 감소, 연휴 직전 소폭 증가 가정(근거 데이터 없음)'},
        'calendar_factor_bounds': CAL_BOUNDS,
        'exam': {'strength': EXAM_STRENGTH, 'pre_days': PRE_DAYS,
                 'pre_shape': '14~8일 전 0->35% 선형, 7~1일 전 35->100% (시험일 가까울수록 급증)',
                 'in_exam_shape': f'첫날 100% -> 마지막날 {int(EXAM_LAST_DAY_FRACTION*100)}% 선형 감소(진행 따라 조정)',
                 'post_shape': f'종료 다음날부터 {POST_DAYS}일 선형 감소하여 0(마지막 시험일 수준에서 이어짐)',
                 'overlap': {'rule': 'max + rest_weight*합(나머지)', 'rest_weight': EXAM_REST, 'cap': EXAM_CAP},
                 'basis': '학교 규모·고객 비중 가정(한대부고는 확인된 2026 일정만, 낮은 강도)'},
        'vacation': {'strength': VAC_STRENGTH, 'overlap': {'rest_weight': VAC_REST, 'cap': VAC_CAP},
                     'applies_only_to': '확인된 vacation 구간(verified)'},
        'semester_start_week': {'strength': SEM_START_STRENGTH, 'days': 7, 'overlap': {'rest_weight': SEM_REST, 'cap': SEM_CAP},
                                'note': '한양여대는 개강일 미확인 -> 효과 0'},
        'school_total_factor_bounds': SCHOOL_FACTOR_BOUNDS,
        'temperature_orders': {'formula': '1 + 0.0035*clip(T-20,0,13) - 0.005*clip(5-T,0,15)', 'range': '약 -7.5% ~ +4.5%'},
        'rain_orders': {'formula': '1 - min(0.10, 0.004*mm) (강수량 >=0.1mm 이고 관측값이 있는 날만)', 'missing_precipitation': '효과 미적용(무강수로 취급 안 함)'},
        'weather_total_bounds': WEATHER_BOUNDS,
        'menu_weights': {'base': 'v1 메뉴별 판매 수량 비례',
                         'ice_only_menu_temp': f'exp({ICE_ONLY_TEMP_SLOPE}*(T-15)) clip {ICE_ONLY_WEIGHT_BOUNDS}',
                         'seasonal': {'M024 찐고구마 케이크': '11~2월 x1.25, 6~8월 x0.8', 'M021 레몬 생크림 케이크/M027 블루베리 판나코타': '5~9월 x1.15, 12~2월 x0.9'}},
        'hot_ice_choice': {'applies_to': 'BOTH 메뉴(수량 단위로 고객이 HOT/ICE 선택, 상세행 분리)',
                           'p_hot': f'clip(sigmoid(({HOT_CENTER_C}-T)/{HOT_SCALE} + 메뉴 offset + 강수 관측일 {RAIN_HOT_LOGIT}), {HOT_PROB_BOUNDS})',
                           'menu_logit_offsets': HOT_LOGIT_OFFSET, 'basis': '메뉴별 기본 HOT/ICE 성향과 기온 조정 계수는 모두 시뮬레이션 가정'}},
    'temperature_class_by_menu': temp_class,
    'validation_summary': {'overall': overall, **dict(cnt_s)},
    'known_limitations': [
        '일정·날씨·공휴일 입력 이외의 모든 수요 효과 크기는 가정이며 실제 판매로 검증되지 않음',
        '강수량 결측 396일은 강수 효과 미적용',
        '시험 종료일이 데이터 종료일(2026-10-31) 이후인 한양여대 2026-10-27~11-02 시험은 종료 후 효과 생성·검증 불가',
        '한양대 2026-10-20~26 시험은 종료 후 5/10일만 데이터 존재',
        '한대부고 2025 일정은 estimated 이므로 효과 미적용',
        'Django 메뉴 정수 PK 매핑은 이 데이터에 포함하지 않음(DB 미접근)'],
}
(OUT / 'generation_rules.json').write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding='utf-8')


# ================================================================ Excel
def col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def esc(v):
    t = str(v)
    t = ''.join(ch for ch in t if ch >= ' ' or ch in '\t\n\r')
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def sheet_xml(h, rows):
    a = ['<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>']
    for i, row in enumerate([h] + rows, 1):
        a.append(f'<row r="{i}">')
        for j, v in enumerate(row, 1):
            ref = f'{col(j)}{i}'
            if v is None or v == '':
                a.append(f'<c r="{ref}" t="inlineStr"><is><t></t></is></c>')
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                a.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                a.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{esc(v)}</t></is></c>')
        a.append('</row>')
    return ''.join(a) + '</sheetData></worksheet>'


# CSV 에서 다시 읽은 값(문자열) 기준으로 시트를 구성 -> CSV 와 Excel 이 동일 소스
def csv_sheet(fn):
    with open(OUT / fn, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    h, body = rows[0], rows[1:]
    conv = []
    for r in body:
        cr = []
        for v in r:
            try:
                if v != '' and (v.lstrip('-').replace('.', '', 1).isdigit()) and not (len(v) > 1 and v[0] == '0' and '.' not in v and v != '0'):
                    cr.append(int(v) if '.' not in v else float(v))
                else:
                    cr.append(v)
            except ValueError:
                cr.append(v)
        conv.append(cr)
    return h, conv


assump_rows = [[k, json.dumps(v, ensure_ascii=False)] for k, v in rules['coefficients'].items()]
assump_rows = [['notice', rules['notice']]] + assump_rows + [['known_limitations', ' | '.join(rules['known_limitations'])]]
SHEETS = [('orders', 'orders.csv'), ('order_details', 'order_details.csv'), ('daily_sales', 'daily_sales.csv'),
          ('daily_menu_sales', 'daily_menu_sales.csv'), ('hourly_sales', 'hourly_hourly.csv'),
          ('menu_sales_mix', 'menu_sales_mix.csv'), ('hot_ice_analysis', 'hot_ice_sales_analysis.csv'),
          ('weather_analysis', 'weather_temperature_analysis.csv'), ('school_schedule_analysis', 'school_exam_vacation_analysis.csv'),
          ('holiday_analysis', 'holiday_weekend_analysis.csv'), ('daily_generation_inputs', 'daily_generation_inputs.csv'),
          ('monthly_summary', 'daily_sales_trend_summary.csv'), ('validation_results', 'validation_results.csv')]
SHEETS[4] = ('hourly_sales', 'hourly_sales.csv')
tabs = [(n, *csv_sheet(fn)) for n, fn in SHEETS]
tabs.append(('assumptions', ['item', 'value'], assump_rows))
XL = OUT / '404dabang_sales_dummy_v1_final_669days.xlsx'
wbx = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' +
       ''.join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _, _) in enumerate(tabs, 1)) + '</sheets></workbook>')
with zipfile.ZipFile(XL, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
               ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(tabs) + 1)) + '</Types>')
    z.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    z.writestr('xl/workbook.xml', wbx)
    z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
               ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(tabs) + 1)) + '</Relationships>')
    for i, (_, h, r) in enumerate(tabs, 1):
        z.writestr(f'xl/worksheets/sheet{i}.xml', sheet_xml(h, r))

# Excel 읽어서 CSV 와 전 셀 비교
zx = ZIP = zipfile.ZipFile(XL)
assert zx.testzip() is None
ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
xl_bad = []
for i, (name, fn) in enumerate(SHEETS, 1):
    root = ET.fromstring(zx.read(f'xl/worksheets/sheet{i}.xml'))
    xrows = []
    for row in root.iter(ns + 'row'):
        cells = []
        for c in row.findall(ns + 'c'):
            v = c.find(ns + 'v')
            t = c.find(f'{ns}is/{ns}t')
            cells.append(v.text if v is not None else (t.text or '') if t is not None else '')
        xrows.append(cells)
    with open(OUT / fn, encoding='utf-8-sig', newline='') as f:
        crows = list(csv.reader(f))
    if len(xrows) != len(crows):
        xl_bad.append((name, 'rows', len(xrows), len(crows)))
        continue
    for a, b in zip(xrows, crows):
        if a != b:
            # 숫자 표기 차이(1.0 vs 1) 허용
            ok = len(a) == len(b) and all(x == y or (x != '' and y != '' and _isnum(x, y)) for x, y in zip(a, b)) if False else False
            try:
                ok = len(a) == len(b) and all(x == y or float(x) == float(y) for x, y in zip(a, b))
            except ValueError:
                ok = False
            if not ok:
                xl_bad.append((name, 'cell', a[:4], b[:4]))
                break
add('X01_excel_matches_csv', 'integrity', 'PASS' if not xl_bad else 'FAIL',
    f'Excel {len(SHEETS)+1}개 시트(분석·검증·가정 포함) 중 CSV 원본 {len(SHEETS)}개를 전 셀 비교, 불일치 {xl_bad if xl_bad else "없음"}; 시트: ' +
    ', '.join(n for n, _, _ in tabs))
cnt_s = collections.Counter(r['status'] for r in results)
overall = 'FAIL' if cnt_s['FAIL'] else ('PASS_WITH_NOT_VERIFIABLE' if cnt_s['NOT_VERIFIABLE'] else 'PASS')
VR = [[r['id'], r['category'], r['status'], r['evidence']] for r in results]
wr(OUT / 'validation_results.csv', VRH, VR)
# validation_results 시트 갱신 (X01 반영) 후 재기록
tabs_idx = [n for n, _, _ in tabs].index('validation_results')
tabs[tabs_idx] = ('validation_results', *csv_sheet('validation_results.csv'))
zx.close()
tmp = OUT / '_tmp.xlsx'
with zipfile.ZipFile(XL) as src, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as dst:
    for item in src.namelist():
        if item == f'xl/worksheets/sheet{tabs_idx + 1}.xml':
            dst.writestr(item, sheet_xml(tabs[tabs_idx][1], tabs[tabs_idx][2]))
        else:
            dst.writestr(item, src.read(item))
tmp.replace(XL)

report = {'version': VERSION, 'overall': overall, 'counts': dict(cnt_s), 'policy': 'PASS/FAIL/NOT_VERIFIABLE 만 사용. 검증하지 못한 항목은 PASS 로 표시하지 않음.',
          'items': results,
          'file_counts': rules['counts'], 'total_sales': tot_sales}
(OUT / 'validation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
rules['validation_summary'] = {'overall': overall, **dict(cnt_s)}
(OUT / 'generation_rules.json').write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'overall': overall, 'counts': dict(cnt_s), 'orders': len(orders), 'details': len(details), 'sales': tot_sales}, ensure_ascii=False))
for r in results:
    print(r['status'], r['id'], '|', r['evidence'][:230])
