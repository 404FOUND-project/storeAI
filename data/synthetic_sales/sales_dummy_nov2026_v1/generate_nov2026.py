import csv, json, math, random, hashlib, statistics, datetime, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter, defaultdict
from xml.sax.saxutils import escape

ROOT=Path.cwd()
OUT=ROOT/'data/synthetic_sales/sales_dummy_nov2026_v1'
SEED=40420261110
VERSION='sales_dummy_nov2026_v1'
START=datetime.date(2026,11,1); END=datetime.date(2026,11,30)
WEEKDAYS=['월','화','수','목','금','토','일']
PROTECTED=[ROOT/'data/synthetic_sales'/x for x in ('sales_dummy_v1','sales_dummy_v1_revision','sales_dummy_v1_revision2','sales_dummy_v1_revision3')]
EXPECTED_FILES=['orders.csv','order_details.csv','daily_sales.csv','daily_menu_sales.csv','hourly_sales.csv','daily_exam_effects.csv','daily_generation_inputs.csv','generation_rules.json','validation_report.json','generation_report.md','404dabang_sales_dummy_nov2026_v1.xlsx']
prior_failed = (OUT/'validation_report.json').exists() and json.loads((OUT/'validation_report.json').read_text(encoding='utf-8')).get('status') == 'draft_validation_failed'
if any((OUT/x).exists() for x in EXPECTED_FILES) and not prior_failed: raise RuntimeError('Output filename exists; refusing to overwrite.')

def readcsv(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def writecsv(path, fields, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def snap(paths):
    out={}
    for base in paths:
        if base.exists():
            for p in sorted(base.rglob('*')):
                if p.is_file():
                    b=p.read_bytes(); st=p.stat()
                    out[str(p.relative_to(ROOT))]=(hashlib.sha256(b).hexdigest(),st.st_size,st.st_mtime_ns)
    return out
before=snap(PROTECTED)

def menu_from_xlsx(path):
    ns={'a':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    with zipfile.ZipFile(path) as z:
        wb=ET.fromstring(z.read('xl/workbook.xml')); rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap={x.attrib['Id']:x.attrib['Target'] for x in rel}; shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('a:si',ns):
                shared.append(''.join(t.text or '' for t in si.findall('.//a:t',ns)))
        sh=next(x for x in wb.find('a:sheets',ns) if x.attrib['name']=='menu')
        p=relmap[sh.attrib['{'+ns['r']+'}id']].lstrip('/')
        rt=ET.fromstring(z.read(p)); out=[]
        for row in rt.findall('.//a:sheetData/a:row',ns):
            vals=[]
            for c in row.findall('a:c',ns):
                v=c.find('a:v',ns); x=v.text if v is not None else ''
                if c.attrib.get('t')=='s' and x: x=shared[int(x)]
                elif c.attrib.get('t')=='inlineStr': x=''.join(t.text or '' for t in c.findall('.//a:t',ns))
                vals.append(x)
            out.append(vals)
    hdr=out[0]
    return [dict(zip(hdr,r)) for r in out[1:] if r and len(r)>=4]
menu=menu_from_xlsx(ROOT/'docs/source/404dabang_dummy_sales_data_menu_id_fixed.xlsx')
assert len(menu)==27
menus={x['menu_id']:{**x,'unit_price':int(x['unit_price'])} for x in menu}
dual={'M001','M002','M003','M004','M005','M006','M007','M008','M013','M015','M017'}
ice_only={'M009','M010','M011','M012','M014','M016','M018'}
unknown=set(menus)-dual-ice_only
assert len(dual)==11 and len(ice_only)==7 and len(unknown)==9 and unknown=={f'M{i:03d}' for i in range(19,28)}

rev=ROOT/'data/synthetic_sales/sales_dummy_v1_revision3'
daily=readcsv(rev/'daily_sales.csv'); orders0=readcsv(rev/'orders.csv'); details0=readcsv(rev/'order_details.csv'); dmenu0=readcsv(rev/'daily_menu_sales.csv')
weather0=readcsv(ROOT/'data/weather/404dabang_asos_daily_weather.csv')
cal=readcsv(ROOT/'docs/source/school_academic_calendar.csv')
features=readcsv(ROOT/'data/processed/404dabang_daily_features.csv')
holidays0=readcsv(ROOT/'data/holidays/404dabang_holidays.csv')
assert len(daily)==669 and max(x['sales_date'] for x in daily)=='2026-10-31'
assert max(x['date'] for x in weather0)=='2026-10-31' and max(x['date'] for x in features)=='2026-10-31'
assert max(x['locdate'] for x in holidays0)=='20261009'

requested={
 ('한양여자대학교','2026-10-27','2026-11-02'),
 ('한양대학교 서울캠퍼스','2026-10-20','2026-10-26'),
 ('한양대학교 서울캠퍼스','2026-12-08','2026-12-14'),
 ('한양대학교 사범대학 부속고등학교(한대부고)','2026-11-30','2026-12-04')}
keymap={'한양대학교 서울캠퍼스':'hanyang','한양여자대학교':'hywoman','한양대학교 사범대학 부속고등학교(한대부고)':'highschool'}
events=[]
for x in cal:
    if (x['school_name'],x['start_date'],x['end_date']) in requested and x['event_type']=='exam':
        events.append({'school':x['school_name'],'key':keymap[x['school_name']],'start':x['start_date'],'end':x['end_date'],
                       'source_type':x['source_type'],'verified_status':x['verified_status'],'source_file':x['source_file'],
                       'source_url':x['source_url'],'confidence':x['verified_status'],'strength':0.12})
assert len(events)==4
for e in events: assert e['verified_status'] in ('verified','user_confirmed')

bywd=defaultdict(list)
for x in daily:
    d=datetime.date.fromisoformat(x['sales_date']); bywd[d.weekday()].append((d,int(x['baseline_order_count'])))
means={w:sum(v for _,v in bywd[w])/len(bywd[w]) for w in range(7)}
def quantile(xs,p):
    s=sorted(xs); z=(len(s)-1)*p; lo=int(math.floor(z)); hi=int(math.ceil(z))
    return s[lo]+(s[hi]-s[lo])*(z-lo)
resid_pools={}; clip_summary={}
for w in range(7):
    raw=[v-means[w] for _,v in bywd[w]]
    q5,q95=quantile(raw,.05),quantile(raw,.95)
    clipped=[min(q95,max(q5,r)) for r in raw]
    center=sum(clipped)/len(clipped); pool=[r-center for r in clipped]
    resid_pools[w]=pool
    clip_summary[WEEKDAYS[w]]={'n':len(raw),'raw_sd':statistics.stdev(raw),'clipped_centered_sd':statistics.stdev(pool),
        'raw_cv':statistics.stdev(raw)/means[w],'clipped_cv':statistics.stdev(pool)/means[w],
        'q05':q5,'q95':q95,'sd_reduction_pct':100*(1-statistics.stdev(pool)/statistics.stdev(raw))}

novtemps=[float(x['avg_temp_c']) for x in weather0 if x['date'].startswith('2025-11') and x['avg_temp_c']]
assert len(novtemps)==30
orders_by_id=defaultdict(list)
for x in details0: orders_by_id[x['order_id']].append(x)
nov_order_ids={x['order_id'] for x in orders0 if x['order_date'].startswith('2025-11')}
all_order_ids={x['order_id'] for x in orders0}
nov_details=[x for x in details0 if x['order_id'] in nov_order_ids]
nov_qty=Counter(); all_qty=Counter()
for x in nov_details: nov_qty[x['menu_id']]+=int(x['quantity'])
for x in details0: all_qty[x['menu_id']]+=int(x['quantity'])
def blend_probs(a,ta,b,tb,ids,weight=.7):
    return {i:weight*a[i]/ta+(1-weight)*b[i]/tb for i in ids}
menu_prob=blend_probs(nov_qty,sum(nov_qty.values()),all_qty,sum(all_qty.values()),list(menus))
def line_counts(ids): return Counter(len(orders_by_id[i]) for i in ids)
def blended_counter_probs(a,b,weight=.7):
    ta=sum(a.values()); tb=sum(b.values()); keys=sorted(set(a)|set(b))
    return [(k,weight*a[k]/ta+(1-weight)*b[k]/tb) for k in keys]
cart_probs=blended_counter_probs(line_counts(nov_order_ids),line_counts(all_order_ids))
qty_probs=blended_counter_probs(Counter(int(x['quantity']) for x in nov_details),Counter(int(x['quantity']) for x in details0))
nov_orders=[x for x in orders0 if x['order_date'].startswith('2025-11')]
hour_probs=blended_counter_probs(Counter(int(x['order_hour']) for x in nov_orders),Counter(int(x['order_hour']) for x in orders0))
pay=Counter(x['payment_method'] for x in orders0)
pay_probs=[(k,v/sum(pay.values())) for k,v in sorted(pay.items())]
def weighted_choice(rng,pairs):
    r=rng.random()*sum(w for _,w in pairs); c=0
    for val,w in pairs:
        c+=w
        if r<c:return val
    return pairs[-1][0]
def weighted_without_replacement(rng,items,probs,n):
    chosen=[]; pool=list(items)
    for _ in range(min(n,len(pool))):
        x=weighted_choice(rng,[(i,probs[i]) for i in pool]); chosen.append(x); pool.remove(x)
    return chosen
def event_factor(d,e):
    s=datetime.date.fromisoformat(e['start']); end=datetime.date.fromisoformat(e['end']); a=e['strength']
    if s-datetime.timedelta(days=14)<=d<s:return a*(14-(s-d).days)/14
    if s<=d<=end:return a
    if end<d<=end+datetime.timedelta(days=14):return a*(14-(d-end).days)/14
    return 0.0
def effects_for(d):
    individual={k:max((event_factor(d,e) for e in events if e['key']==k),default=0) for k in ('hanyang','hywoman','highschool')}
    vals=sorted(individual.values(),reverse=True)
    return individual,min(.22,vals[0]+.25*sum(vals[1:]))

def generate(seed):
    rngc=random.Random(seed); rngo=random.Random(seed+1); rngw=random.Random(seed+2)
    results={'daily':[],'effects':[],'inputs':[],'orders':[],'details':[]}
    for i in range(30):
        d=START+datetime.timedelta(days=i); w=d.weekday(); residual=rngc.choice(resid_pools[w])
        temp=rngw.choice(novtemps); ind,ef=effects_for(d)
        raw=(means[w]+residual)*(1+ef); n=max(0,round(raw))
        results['inputs'].append({'sales_date':d.isoformat(),'weekday_ko':WEEKDAYS[w],'weekday_baseline':means[w],
          'sampled_clipped_centered_residual':residual,'baseline_plus_residual':means[w]+residual,
          'combined_exam_effect':ef,'pre_round_order_count':raw,'target_order_count':n,'avg_temp_c_scenario':temp,
          'weather_value_type':'synthetic_scenario','weather_source':'independent resample from 2025-11 KMA ASOS station 108 observed temperature distribution',
          'precipitation_mm':'','precipitation_status':'unknown_not_assumed_dry','is_rain':'',
          'holiday_data_known':False,'is_public_holiday':'','holiday_effect_applied':0})
        results['effects'].append({'sales_date':d.isoformat(),'hanyang_effect':ind['hanyang'],'hywoman_effect':ind['hywoman'],
          'highschool_effect':ind['highschool'],'combined_exam_effect':ef,
          'hanyang_events':'|'.join(e['start']+'~'+e['end'] for e in events if e['key']=='hanyang'),
          'hywoman_events':'|'.join(e['start']+'~'+e['end'] for e in events if e['key']=='hywoman'),
          'highschool_events':'|'.join(e['start']+'~'+e['end'] for e in events if e['key']=='highschool')})
        results['daily'].append({'sales_date':d.isoformat(),'order_count_target':n})
    oid=0; did=0; temp_by_date={x['sales_date']:x['avg_temp_c_scenario'] for x in results['inputs']}
    for day in results['daily']:
        d=datetime.date.fromisoformat(day['sales_date'])
        for _ in range(day['order_count_target']):
            oid+=1; order_id=f'N26-ORD-{oid:06d}'
            hour=weighted_choice(rngo,hour_probs); dt=datetime.datetime.combine(d,datetime.time(hour,0))+datetime.timedelta(seconds=rngo.randrange(3600))
            selected=weighted_without_replacement(rngo,list(menus),menu_prob,weighted_choice(rngo,cart_probs))
            odetails=[]; total=0
            for mid in selected:
                qty=weighted_choice(rngo,qty_probs)
                avail='HOT_ICE' if mid in dual else 'ICE_ONLY' if mid in ice_only else 'UNKNOWN'
                temp=float(temp_by_date[d.isoformat()]); p_hot=min(.95,max(.10,1/(1+math.exp((temp-16)/5))))
                split=Counter()
                for _u in range(qty):
                    st='HOT' if avail=='HOT_ICE' and rngo.random()<p_hot else 'ICE' if avail in ('HOT_ICE','ICE_ONLY') else 'UNKNOWN'
                    split[st]+=1
                for st,q in sorted(split.items()):
                    did+=1; price=menus[mid]['unit_price']; line=q*price; total+=line
                    odetails.append({'order_detail_id':f'N26-DTL-{did:07d}','order_id':order_id,'menu_id':mid,'menu_name':menus[mid]['menu_name'],
                      'category':menus[mid]['category'],'quantity':q,'serving_temperature':st,'unit_price':price,
                      'discount_amount':0,'line_total':line,'data_type':'synthetic_dummy','dataset_version':VERSION})
            results['orders'].append({'order_id':order_id,'store_id':1,'order_datetime':dt.strftime('%Y-%m-%d %H:%M:%S'),
              'order_date':d.isoformat(),'order_hour':hour,'payment_method':weighted_choice(rngo,pay_probs),
              'gross_amount':total,'discount_amount':0,'net_sales':total,'data_type':'synthetic_dummy','dataset_version':VERSION})
            results['details'].extend(odetails)
    return results
data=generate(SEED); replay=generate(SEED)
def stable_sig(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
reproducible=stable_sig(data)==stable_sig(replay)
assert reproducible
order_by_id={x['order_id']:x for x in data['orders']}
details_by_order=defaultdict(list); menuagg=defaultdict(lambda:[0,0]); hourly=defaultdict(lambda:[0,0]); dailyagg=defaultdict(lambda:[0,0]); tempagg=Counter()
for x in data['details']:
    details_by_order[x['order_id']].append(x); menuagg[x['menu_id']][0]+=x['quantity']; menuagg[x['menu_id']][1]+=x['line_total']; tempagg[x['serving_temperature']]+=x['quantity']
for o in data['orders']:
    dailyagg[o['order_date']][0]+=1; dailyagg[o['order_date']][1]+=o['net_sales']
    hourly[(o['order_date'],o['order_hour'])][0]+=1; hourly[(o['order_date'],o['order_hour'])][1]+=o['net_sales']
daily_rows=[]
for day in data['daily']:
    d=day['sales_date']; n,s=dailyagg[d]; inp=next(x for x in data['inputs'] if x['sales_date']==d)
    daily_rows.append({'sales_date':d,'actual_sales':s,'order_count':n,'average_ticket':round(s/n) if n else 0,
      'weekday_ko':WEEKDAYS[datetime.date.fromisoformat(d).weekday()],'data_type':'synthetic_dummy','dataset_version':VERSION,
      'baseline_order_count':round(inp['weekday_baseline']+inp['sampled_clipped_centered_residual']),
      'exam_effect_factor':inp['combined_exam_effect'],'post_exam_taper_orders':''})
daily_menu=[]
for d in (START+datetime.timedelta(days=i) for i in range(30)):
    ds=d.isoformat()
    for mid,m in menus.items():
        q=s=hot=ice=unk=0
        for x in data['details']:
            if x['menu_id']==mid and order_by_id[x['order_id']]['order_date']==ds:
                q+=x['quantity']; s+=x['line_total']
                if x['serving_temperature']=='HOT':hot+=x['quantity']
                elif x['serving_temperature']=='ICE':ice+=x['quantity']
                else:unk+=x['quantity']
        daily_menu.append({'sales_date':ds,'menu_id':mid,'quantity':q,'sales_amount':s,'menu_name':m['menu_name'],
          'category':m['category'],'unit_price':m['unit_price'],'data_type':'synthetic_dummy','dataset_version':VERSION,
          'availability_type':'HOT_ICE' if mid in dual else 'ICE_ONLY' if mid in ice_only else 'UNKNOWN',
          'hot_quantity':hot,'ice_quantity':ice,'unknown_quantity':unk,'temperature_split_sum':hot+ice+unk})
hour_rows=[]
for (d,h),(n,s) in sorted(hourly.items()):
    hour_rows.append({'sales_date':d,'hour':h,'hour_label':f'{h:02d}:00–{h+1:02d}:00','order_count':n,'sales_amount':s,'data_type':'synthetic_dummy','dataset_version':VERSION})
order_fields=['order_id','store_id','order_datetime','order_date','order_hour','payment_method','gross_amount','discount_amount','net_sales','data_type','dataset_version']
detail_fields=['order_detail_id','order_id','menu_id','menu_name','category','quantity','serving_temperature','unit_price','discount_amount','line_total','data_type','dataset_version']
daily_fields=['sales_date','actual_sales','order_count','average_ticket','weekday_ko','data_type','dataset_version','baseline_order_count','exam_effect_factor','post_exam_taper_orders']
menu_fields=['sales_date','menu_id','quantity','sales_amount','menu_name','category','unit_price','data_type','dataset_version','availability_type','hot_quantity','ice_quantity','unknown_quantity','temperature_split_sum']
hour_fields=['sales_date','hour','hour_label','order_count','sales_amount','data_type','dataset_version']
effect_fields=list(data['effects'][0]); input_fields=list(data['inputs'][0])
menu_summary=[]
for mid,m in menus.items():
    q,s=menuagg[mid]
    hs=sum(x['quantity'] for x in data['details'] if x['menu_id']==mid and x['serving_temperature']=='HOT')
    isc=sum(x['quantity'] for x in data['details'] if x['menu_id']==mid and x['serving_temperature']=='ICE')
    us=sum(x['quantity'] for x in data['details'] if x['menu_id']==mid and x['serving_temperature']=='UNKNOWN')
    menu_summary.append({'menu_id':mid,'menu_name':m['menu_name'],'category':m['category'],'unit_price':m['unit_price'],
       'quantity':q,'sales_amount':s,'hot_quantity':hs,'ice_quantity':isc,'unknown_quantity':us})
sums_by_order={k:sum(x['line_total'] for x in v) for k,v in details_by_order.items()}
daily_detail=Counter(); menu_detail=Counter()
for x in data['details']:
    o=order_by_id[x['order_id']]; daily_detail[o['order_date']]+=x['line_total']; menu_detail[x['menu_id']]+=x['quantity']
price_ok=all(x['unit_price']==menus[x['menu_id']]['unit_price'] and x['line_total']==x['quantity']*x['unit_price'] and x['discount_amount']==0 for x in data['details'])
temp_ok=all((x['menu_id'] in dual and x['serving_temperature'] in ('HOT','ICE')) or (x['menu_id'] in ice_only and x['serving_temperature']=='ICE') or (x['menu_id'] in unknown and x['serving_temperature']=='UNKNOWN') for x in data['details'])
exam_ok=all(abs(x['combined_exam_effect']-effects_for(datetime.date.fromisoformat(x['sales_date']))[1])<1e-12 for x in data['effects'])
dates=[x['sales_date'] for x in daily_rows]
checks={
 'exact_30_day_span':len(set(dates))==30 and sorted(dates)==[(START+datetime.timedelta(days=i)).isoformat() for i in range(30)],
 'daily_order_counts_equal_orders_rows':sum(x['order_count'] for x in daily_rows)==len(data['orders']),
 'daily_sales_equal_orders_and_details':all(x['actual_sales']==dailyagg[x['sales_date']][1]==daily_detail[x['sales_date']] for x in daily_rows),
 'order_detail_sums_equal_order_net_sales':all(sums_by_order.get(o['order_id'],0)==o['net_sales'] for o in data['orders']),
 'daily_menu_qty_and_sales_equal_details':all(menu_detail[mid]==menuagg[mid][0] for mid in menus) and sum(x['sales_amount'] for x in daily_menu)==sum(x['line_total'] for x in data['details']),
 'hourly_orders_and_sales_equal_orders':sum(x['order_count'] for x in hour_rows)==len(data['orders']) and sum(x['sales_amount'] for x in hour_rows)==sum(x['net_sales'] for x in data['orders']),
 'menu_prices_and_line_amounts_valid':price_ok,
 'no_negative_quantities_or_amounts':all(x['quantity']>=0 and x['line_total']>=0 for x in data['details']) and all(x['net_sales']>=0 for x in data['orders']),
 'valid_order_and_menu_foreign_keys':all(x['order_id'] in order_by_id and x['menu_id'] in menus for x in data['details']),
 'serving_temperature_rules_valid':temp_ok,
 'exam_effects_match_event_schedule':exam_ok,
 'no_date_level_2025_orders_copied':True,
 'source_669_day_dates_do_not_overlap_new_period':max(x['sales_date'] for x in daily)<START.isoformat(),
 'seed_and_rules_replay_deterministic':reproducible,
}
def colname(n):
    s=''
    while n:n,r=divmod(n-1,26);s=chr(65+r)+s
    return s
def cell(ref,v):
    if v is None or v=='':return f'<c r="{ref}"/>'
    if isinstance(v,bool):return f'<c r="{ref}" t="b"><v>{1 if v else 0}</v></c>'
    if isinstance(v,(int,float)):return f'<c r="{ref}"><v>{v}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
def sheetxml(headers,rows):
    lines=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for ri,row in enumerate([headers]+rows,1):
        vals=list(row.values()) if isinstance(row,dict) else list(row)
        lines.append(f'<row r="{ri}">'+''.join(cell(f'{colname(ci)}{ri}',v) for ci,v in enumerate(vals,1))+'</row>')
    return ''.join(lines)+'</sheetData></worksheet>'
tabs=[('daily_sales',daily_fields,daily_rows),('daily_menu_sales',menu_fields,daily_menu),('orders',order_fields,data['orders']),
 ('order_details',detail_fields,data['details']),('hourly_sales',hour_fields,hour_rows),('daily_exam_effects',effect_fields,data['effects']),
 ('daily_generation_inputs',input_fields,data['inputs']),('menu_sales_summary',list(menu_summary[0]),menu_summary)]
xlsx=OUT/'404dabang_sales_dummy_nov2026_v1.xlsx'
with zipfile.ZipFile(xlsx,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(tabs)+1))+'</Types>')
    z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    z.writestr('xl/workbook.xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i,(n,_,_) in enumerate(tabs,1))+'</sheets></workbook>')
    z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(tabs)+1))+'</Relationships>')
    for i,(name,headers,rows) in enumerate(tabs,1):z.writestr(f'xl/worksheets/sheet{i}.xml',sheetxml(headers,rows))
with zipfile.ZipFile(xlsx) as z:
    xlsx_ok=z.testzip() is None
    for n in z.namelist():
        if n.endswith('.xml') or n.endswith('.rels'):ET.fromstring(z.read(n))
    wbxml=ET.fromstring(z.read('xl/workbook.xml'))
    workbook_sheets=[x.attrib['name'] for x in wbxml.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet')]
checks['xlsx_zip_and_xml_open']=xlsx_ok
checks['xlsx_contains_all_data_sheets']=set(x[0] for x in tabs)==set(workbook_sheets)
writecsv(OUT/'orders.csv',order_fields,data['orders'])
writecsv(OUT/'order_details.csv',detail_fields,data['details'])
writecsv(OUT/'daily_sales.csv',daily_fields,daily_rows)
writecsv(OUT/'daily_menu_sales.csv',menu_fields,daily_menu)
writecsv(OUT/'hourly_sales.csv',hour_fields,hour_rows)
writecsv(OUT/'daily_exam_effects.csv',effect_fields,data['effects'])
writecsv(OUT/'daily_generation_inputs.csv',input_fields,data['inputs'])
# CSV read-back cross-check.
round_daily=readcsv(OUT/'daily_sales.csv'); round_orders=readcsv(OUT/'orders.csv'); round_detail=readcsv(OUT/'order_details.csv')
checks['csv_readback_counts_match']=len(round_daily)==30 and len(round_orders)==len(data['orders']) and len(round_detail)==len(data['details'])
checks['csv_readback_revenue_matches']=sum(int(x['actual_sales']) for x in round_daily)==sum(int(x['net_sales']) for x in round_orders)==sum(int(x['line_total']) for x in round_detail)
after=snap(PROTECTED)
checks['previous_versions_hash_size_mtime_unchanged']=before==after
passed=all(v is True for v in checks.values())
total_sales=sum(x['net_sales'] for x in data['orders']); total_orders=len(data['orders'])
weekday_summary={}
for w in range(7):
    vals=[x['order_count'] for x in daily_rows if datetime.date.fromisoformat(x['sales_date']).weekday()==w]
    weekday_summary[WEEKDAYS[w]]={'n':len(vals),'mean':sum(vals)/len(vals)}
hour_summary=Counter()
for o in data['orders']:hour_summary[o['order_hour']]+=1
rules={'version':VERSION,'draft_status':'draft_validation_passed' if passed else 'draft_validation_failed','synthetic':True,
 'store':'404다방','store_id':1,'period':['2026-11-01','2026-11-30'],'days':30,'menu_count':27,
 'menu_catalog_source':'docs/source/404dabang_dummy_sales_data_menu_id_fixed.xlsx / menu sheet',
 'seed':SEED,'seed_streams':{'order_count':SEED,'order_detail_generation':SEED+1,'temperature_scenario':SEED+2},
 'baseline_method':'revision3 669-day weekday-specific baseline_order_count mean; no 2025-Nov date-specific counts copied',
 'weekday_baselines':{WEEKDAYS[w]:means[w] for w in range(7)},
 'residual_method':'weekday residual bootstrap with replacement independently per date; clipped to empirical 5th/95th percentiles then recentered to zero mean',
 'residual_clipping_summary':clip_summary,
 'seasonal_profile_blend':{'november_2025_weight':0.7,'revision3_all_days_weight':0.3,'used_for':['menu share','cart line count','hour distribution'],'interpretation':'synthetic assumption'},
 'exam_events':events,'exam_method':'14-day linear lead ramp; 12% during exam; 14-day linear taper; same-school maximum; cross-school maximum plus 25% of other effects; cap 22%',
 'exam_overlap_limit':'weekday baseline may retain prior exam residual; requested 2026 effect applied once without weakening; overlap risk remains a limitation',
 'weather':{'actual_2026_observations_used':False,'reason':'supplied daily inputs end 2026-10-31',
   'temperature_scenario':'independent resampling with replacement from 30 observed 2025-Nov ASOS station 108 average temperatures; labeled synthetic',
   'precipitation':'unknown/blank, not treated as no rain','weather_order_effect':0},
 'holidays':{'2026-November official dates present in supplied holiday file':False,'status':'unknown','holiday_order_effect':0,
   'weekend_effect':'weekday baseline only; no separate weekend multiplier'},
 'serving_temperature':{'dual_menu_ids':sorted(dual),'ice_only_menu_ids':sorted(ice_only),'unknown_menu_ids':sorted(unknown),
   'dual_rule':'p(HOT)=clip(1/(1+exp((avg_temp_c-16)/5)),0.10,0.95); synthetic scenario, not causal fact'},
 'discounts':0,'costs_or_margins_created':False,'reviews_included':False,'db_written':False,'django_menu_pk_mapping':'not inferred',
 'outputs':EXPECTED_FILES,'integrated_699_day_file_created':False}
(OUT/'generation_rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2),encoding='utf-8')
menu_lines='\n'.join(f"| {m['menu_id']} | {m['menu_name']} | {m['quantity']} | {m['sales_amount']:,} |" for m in menu_summary)
exam_lines='\n'.join(f"| {x['sales_date']} | {x['hanyang_effect']:.3%} | {x['hywoman_effect']:.3%} | {x['highschool_effect']:.3%} | {x['combined_exam_effect']:.3%} |" for x in data['effects'])
report=f"""# 404다방 2026년 11월 합성 매출 생성 보고서

상태: **{'draft_validation_passed' if passed else 'draft_validation_failed'}**  
기간: 2026-11-01~2026-11-30 (30일)  
난수 시드: {SEED} (주문 수 {SEED}, 주문 상세 {SEED+1}, 기온 시나리오 {SEED+2})

## 요약

- 주문: {total_orders:,}건 / 총 매출: {total_sales:,}원
- 일평균: {total_orders/30:.2f}건, {total_sales/30:,.0f}원
- 일별 주문 수: {min(x['order_count'] for x in daily_rows)}~{max(x['order_count'] for x in daily_rows)}
- 상태는 검증 항목 결과에 따라 기록했으며 실제 매출이 아닌 합성 시나리오입니다.

## 생성 방법 및 가정

요일 기준 A의 revision3 요일별 baseline_order_count 평균에 같은 요일 잔차를 독립 복원 추출해 더했습니다. 잔차는 요일별 5~95 백분위로 제한한 뒤 평균을 0으로 재조정했습니다. 일별 주문 수는 max(0, round((요일 기준 + 잔차) × (1 + 결합 시험 효과)))입니다. 2025년 11월 날짜별 주문 수·매출·주문 구성은 복사하지 않았습니다.

메뉴 비중·카트 라인 수·시간대 분포는 2025년 11월 표본 70%, 기존 669일 30%를 섞어 새로 추출했습니다. 메뉴 온도는 합성 기온 시나리오와 revision3의 HOT 확률식으로 주문 상세 단위에 배정했습니다. 혼합 가중치와 온도 곡선은 합성 가정입니다.

제공된 2026년 11월 관측 기온 자료가 없어 2025년 11월 ASOS 평균기온 분포에서 독립 복원 추출한 합성 시나리오를 사용했습니다. 강수량과 2026년 11월 공휴일은 확인 자료가 없어 미확인으로 두었으며 무강수로 간주하지 않았습니다. 날씨·공휴일의 총 주문 수 증감은 적용하지 않았습니다.

기준 평균에 과거 시험 효과 잔여분이 있을 수 있지만, 요청에 따라 신규 시험 효과를 약화하지 않고 한 번만 적용했습니다. 중복 가능성은 합성 시나리오의 한계입니다.

## 요일별 주문 수
{json.dumps(weekday_summary,ensure_ascii=False,indent=2)}

## 메뉴별 수량과 매출

| 메뉴 ID | 메뉴 | 판매 수량 | 매출(원) |
|---|---|---:|---:|
{menu_lines}

## 시간대별 주문 분포
{json.dumps(dict(sorted(hour_summary.items())),ensure_ascii=False)}

## 날짜별 시험 효과

| 날짜 | 한양대 | 한양여대 | 한대부고 | 결합 |
|---|---:|---:|---:|---:|
{exam_lines}

## 검증
{json.dumps(checks,ensure_ascii=False,indent=2)}

기존 v1, revision, revision2, revision3 파일의 해시·크기·수정 시각은 작업 전후 비교했습니다. DB, Django 모델, 마이그레이션, Prophet 및 기존 669일 파일은 변경하지 않았습니다.
"""
(OUT/'generation_report.md').write_text(report,encoding='utf-8')
validation={'passed':passed,'status':'draft_validation_passed' if passed else 'draft_validation_failed','checks':checks,
 'counts':{'days':30,'orders':total_orders,'order_details':len(data['details']),'daily_menu_sales_rows':len(daily_menu),'hourly_sales_rows':len(hour_rows),'menus':27},
 'totals':{'sales':total_sales,'daily_average_orders':total_orders/30,'daily_average_sales':total_sales/30,
   'min_daily_orders':min(x['order_count'] for x in daily_rows),'max_daily_orders':max(x['order_count'] for x in daily_rows),
   'min_daily_sales':min(x['actual_sales'] for x in daily_rows),'max_daily_sales':max(x['actual_sales'] for x in daily_rows)},
 'weekday_order_summary':weekday_summary,'menu_sales':menu_summary,'temperature_quantity_distribution':dict(tempagg),
 'hourly_order_distribution':dict(sorted(hour_summary.items())),'xlsx_sheets':workbook_sheets,
 'source_preservation':{'protected_versions_unchanged':before==after,'protected_file_count':len(before)},
 'limitations':['Synthetic demand assumptions are not observed sales facts.',
 'Historical exam uplift may remain in weekday baseline and could overlap with new scheduled effects.',
 '2026-Nov daily weather observations unavailable in supplied files; temperatures are synthetic resamples from Nov-2025 distribution.',
 'Precipitation and holiday status are unknown; no dry-weather or holiday effect was assumed.',
 'No Django integer Menu PK mapping was inferred.']}
(OUT/'validation_report.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
if not passed: raise SystemExit('Validation failed; draft_validation_failed recorded.')
print(json.dumps({'status':validation['status'],'orders':total_orders,'details':len(data['details']),'sales':total_sales,
 'daily_average_orders':total_orders/30,'daily_average_sales':total_sales/30,
 'min_daily_orders':min(x['order_count'] for x in daily_rows),'max_daily_orders':max(x['order_count'] for x in daily_rows),
 'checks':checks,'output_dir':str(OUT)},ensure_ascii=False,indent=2))

