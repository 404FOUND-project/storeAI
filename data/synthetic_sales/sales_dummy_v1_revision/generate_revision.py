
import csv,json,zipfile,xml.etree.ElementTree as ET,random,collections,math,statistics
from pathlib import Path
from datetime import date,datetime,timedelta
R=Path.cwd();O=R/'data/synthetic_sales/sales_dummy_v1_revision';rng=random.Random(40420261110)
V=R/'data/synthetic_sales/sales_dummy_v1';SRC=R/'docs/source/404dabang_dummy_sales_data_menu_id_fixed.xlsx'
def rd(p):
 with open(p,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def wr(p,h,rows):
 with open(p,'w',encoding='utf-8-sig',newline='') as f:w=csv.writer(f);w.writerow(h);w.writerows(rows)
def xbook(p):
 z=zipfile.ZipFile(p);n={'a':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'};w=ET.fromstring(z.read('xl/workbook.xml'));rr=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'));rel={x.attrib['Id']:x.attrib['Target'] for x in rr};out={}
 for sh in w.findall('a:sheets/a:sheet',n):
  t=rel[sh.attrib['{'+n['r']+'}id']].lstrip('/');t=t if t.startswith('xl/') else 'xl/'+t;root=ET.fromstring(z.read(t));rows=[]
  for row in root.findall('.//a:sheetData/a:row',n):
   d={}
   for c in row.findall('a:c',n):
    v=c.find('a:v',n);q=c.find('a:is/a:t',n);d[c.attrib['r']]=v.text if v is not None else(q.text if q is not None else '')
   rows.append(d)
  hs=[rows[0].get(chr(65+i)+'1','') for i in range(15) if rows and rows[0].get(chr(65+i)+'1')]
  out[sh.attrib['name']]=[{k:r.get(chr(65+i)+str(j),'') for i,k in enumerate(hs)} for j,r in enumerate(rows[1:],2) if any(r.values())]
 return out
def yes(x):return str(x).strip().lower() in ('true','1','yes','y')
def num(x):
 try:return float(x) if x not in ('',None) else None
 except:return None
features=rd(R/'data/processed/404dabang_daily_features.csv');fm={x['date']:x for x in features}
s=xbook(SRC);menus=s['menu'];assert len(menus)==27;menuid={x['menu_id']:x for x in menus}
bd=rd(V/'daily_sales.csv');days=[date(2025,1,1)+timedelta(i) for i in range(669)]
base0={x['sales_date']:int(x['order_count']) for x in bd}
school={'hanyang':'\uD55C\uC591\uB300\uD559\uAD50 \uC11C\uC6B8\uCEA0\uD37C\uC2A4','hywoman':'\uD55C\uC591\uC5EC\uC790\uB300\uD559\uAD50','highschool':'\uD55C\uB300\uBD80\uACE0'};events=[]
for key,label in school.items():
 run=[]
 for d in days:
  f=fm[d.isoformat()]
  if yes(f.get(key+'_exam')):run.append(d)
  elif run:
   f0=fm[run[0].isoformat()]; est=yes(f0.get(key+'_exam_estimated'))
   events.append({'school':label,'key':key,'start':run[0].isoformat(),'end':run[-1].isoformat(),'confidence':'estimated_low' if est else ('user_confirmed' if key=='hanyang' else 'official_verified'),'strength':.035 if est else .12});run=[]
 if run:
  f0=fm[run[0].isoformat()];est=yes(f0.get(key+'_exam_estimated'))
  events.append({'school':label,'key':key,'start':run[0].isoformat(),'end':run[-1].isoformat(),'confidence':'estimated_low' if est else ('user_confirmed' if key=='hanyang' else 'official_verified'),'strength':.035 if est else .12})
def oldf(d):
 a=[]
 for key in school:
  for lead in range(15):
   f=fm.get((d+timedelta(lead)).isoformat(),{})
   if yes(f.get(key+'_exam')):
    a.append(.12*(.3 if yes(f.get(key+'_exam_estimated')) or not yes(f.get(key+'_exam_known')) else 1)*(15-lead)/15);break
 return min(.2,max(a,default=0))
def ef(d):
 a=[]
 for e in events:
  st=date.fromisoformat(e['start']);en=date.fromisoformat(e['end']);k=e['strength']
  if st-timedelta(14)<=d<st:v=k*(d-(st-timedelta(14))).days/14
  elif st<=d<=en:v=k
  elif en<d<=en+timedelta(14):v=k*(14-(d-en).days)/14
  else:continue
  if v>0:a.append(v)
 a.sort(reverse=True);return min(.22,a[0]+.25*sum(a[1:])) if a else 0
baseline={k:max(4,round(v/(1+oldf(date.fromisoformat(k))))) for k,v in base0.items()}
target={k:max(4,round(baseline[k]*(1+ef(date.fromisoformat(k))))) for k in baseline}
bd0=rd(V/'order_details.csv');bo=rd(V/'orders.csv');basket=collections.Counter();qty=collections.Counter();pop=collections.Counter();hours=collections.Counter()
by=collections.defaultdict(list)
for x in bd0:
 by[x['order_id']].append(x);qty[int(x['quantity'])]+=1;pop[x['menu_id']]+=int(x['quantity'])
for x in bo:basket[len(by[x['order_id']])]+=1;hours[int(x['order_hour'])]+=1
hrs=[h for h in hours if 7<=h<=22];hws=[hours[h] for h in hrs]
# Classification uses only explicit menu text; no HOT product is asserted without clear wording.
def U(s):return s.encode('ascii').decode('unicode_escape')
cold_terms=[U('\\uC544\\uC774\\uC2A4'),U('\\uC5D0\\uC774\\uB4DC'),U('\\uCF5C\\uB4DC\\uBE0C\\uB8E8')]
hot_terms=[U('\\uD54B'),U('\\uB530\\uB73B\\uD55C')]
neutral_terms=[U('\\uB514\\uC800\\uD2B8'),U('\\uBCA0\\uC774\\uCEE4\\uB9AC')]
types={}
for m in menus:
 n=m['menu_name'].lower();cat=m.get('category','')
 types[m['menu_id']]='COLD' if any(t in n for t in cold_terms) else 'HOT' if any(t in n for t in hot_terms) else 'NEUTRAL' if any(t in cat for t in neutral_terms) else 'UNKNOWN'
orders=[];details=[];oid=did=0
for d in days:
 ds=d.isoformat();f=fm[ds];t=num(f.get('avg_temp_c'));weights=[]
 for m in menus:
  typ=types[m['menu_id']];w=max(.1,pop[m['menu_id']])**.78
  if t is not None and typ=='COLD':w*=max(.7,min(1.4,1+.02*(t-15)))
  if t is not None and typ=='HOT':w*=max(.7,min(1.4,1-.02*(t-15)))
  if m.get('category')==U('\\uB514\\uC800\\uD2B8') and d.month in (11,12,1,2):w*=1.03
  weights.append(w)
 for _ in range(target[ds]):
  oid+=1;oidstr=f'R1-{oid:07d}';h=rng.choices(hrs,weights=hws,k=1)[0];tm=datetime.combine(d,datetime.min.time()).replace(hour=h,minute=rng.randrange(60),second=rng.randrange(60));nlines=min(4,max(1,rng.choices(list(basket),weights=list(basket.values()),k=1)[0]));total=0
  for j in range(nlines):
   m=rng.choices(menus,weights=weights,k=1)[0];q=rng.choices(list(qty),weights=list(qty.values()),k=1)[0];price=int(float(m['unit_price']));amt=q*price;total+=amt;did+=1;details.append([f'R1-D{did:08d}',oidstr,m['menu_id'],m['menu_name'],m['category'],q,price,0,amt,'synthetic_dummy','sales_dummy_v1_revision'])
  orders.append([oidstr,1,tm.isoformat(sep=' '),ds,h,'card',total,0,total,'synthetic_dummy','sales_dummy_v1_revision'])
dsales=collections.defaultdict(lambda:[0,0]);dmenu=collections.defaultdict(lambda:[0,0]);hourly=collections.defaultdict(lambda:[0,0]);o_map={o[0]:o for o in orders}
for x in details:
 o=o_map[x[1]];ds=o[3];dsales[ds][0]+=x[8];dmenu[(ds,x[2])][0]+=x[5];dmenu[(ds,x[2])][1]+=x[8]
for o in orders:hourly[(o[3],o[4])][0]+=1;hourly[(o[3],o[4])][1]+=o[8]
ko=[U('\\uC6D4'),U('\\uD654'),U('\\uC218'),U('\\uBAA9'),U('\\uAE08'),U('\\uD1A0'),U('\\uC77C')]
D=[[d.isoformat(),dsales[d.isoformat()][0],dsales[d.isoformat()][1],round(dsales[d.isoformat()][0]/max(1,dsales[d.isoformat()][1])),ko[d.weekday()],'synthetic_dummy','sales_dummy_v1_revision',baseline[d.isoformat()],ef(d),max(0,target[d.isoformat()]-baseline[d.isoformat()])] for d in days]
M=[[d.isoformat(),m['menu_id'],dmenu[(d.isoformat(),m['menu_id'])][0],dmenu[(d.isoformat(),m['menu_id'])][1],m['menu_name'],m['category'],int(float(m['unit_price'])),'synthetic_dummy','sales_dummy_v1_revision',types[m['menu_id']]] for d in days for m in menus]
H=[[k[0],k[1],f'{k[1]:02}:00',v[0],v[1],'synthetic_dummy','sales_dummy_v1_revision'] for k,v in sorted(hourly.items())]
OH=['order_id','store_id','order_datetime','order_date','order_hour','payment_method','gross_amount','discount_amount','net_sales','data_type','dataset_version'];DEH=['order_detail_id','order_id','menu_id','menu_name','category','quantity','unit_price','discount_amount','line_total','data_type','dataset_version'];DH=['sales_date','menu_id','quantity','sales_amount','menu_name','category','unit_price','data_type','dataset_version','temperature_class'];DHEAD=['sales_date','actual_sales','order_count','average_ticket','weekday_ko','data_type','dataset_version','baseline_order_count','exam_effect_factor','post_exam_taper_orders'];HH=['sales_date','hour','hour_label','order_count','sales_amount','data_type','dataset_version']
for fn,h,r in [('orders.csv',OH,orders),('order_details.csv',DEH,details),('daily_sales.csv',DHEAD,D),('daily_menu_sales.csv',DH,M),('hourly_sales.csv',HH,H)]:wr(O/fn,h,r)
tot=sum(x[1] for x in D);mt=collections.defaultdict(lambda:[0,0])
for x in M:mt[x[1]][0]+=x[2];mt[x[1]][1]+=x[3]
mix=[[m['menu_id'],m['menu_name'],m['category'],int(float(m['unit_price'])),mt[m['menu_id']][0],mt[m['menu_id']][1],round(100*mt[m['menu_id']][1]/tot,4),types[m['menu_id']],'synthetic_only'] for m in menus]
wr(O/'menu_sales_mix.csv',['menu_id','menu_name','category','unit_price','quantity','sales_amount','revenue_share_pct','temperature_class','basis'],mix)
month=collections.defaultdict(lambda:[0,0,0])
for x in D:month[x[0][:7]][0]+=x[1];month[x[0][:7]][1]+=x[2];month[x[0][:7]][2]+=1
monthly=[[k,v[0],v[1],round(v[0]/v[2]),v[2]] for k,v in sorted(month.items())];wr(O/'daily_sales_trend_summary.csv',['month','sales_total','orders_total','avg_daily_sales','days'],monthly)
# Event-specific pre/exam/post diagnostics
examrows=[];offsets=[]
for e in events:
 st=date.fromisoformat(e['start']);en=date.fromisoformat(e['end'])
 for label,ds in [('pre14',[(st-timedelta(k)).isoformat() for k in range(14,0,-1)]),('exam',[(st+timedelta(k)).isoformat() for k in range((en-st).days+1)]),('post1',[(en+timedelta(1)).isoformat()]),('post3',[(en+timedelta(k)).isoformat() for k in (1,2,3)]),('post7',[(en+timedelta(k)).isoformat() for k in range(1,8)]),('post14',[(en+timedelta(k)).isoformat() for k in range(1,15)])]:
  ds=[x for x in ds if x in target]
  if ds:
   b=statistics.mean(baseline[x] for x in ds);r=statistics.mean(target[x] for x in ds)
   examrows.append([e['school'],e['start'],e['end'],e['confidence'],label,len(ds),round(b,3),round(r,3),round(r-b,3),round(100*(r-b)/b,2) if b else 0])
 for k in (1,3,7,14):
  ds=(en+timedelta(k)).isoformat()
  if ds in target:offsets.append([e['school'],e['start'],e['end'],e['confidence'],k,baseline[ds],target[ds],max(0,target[ds]-baseline[ds]),round(ef(en+timedelta(k)),4)])
wr(O/'exam_period_comparison.csv',['school','exam_start','exam_end','confidence','window','n_days','baseline_mean','revision_mean','added_mean','added_pct'],examrows)
wr(O/'exam_post_offsets.csv',['school','exam_start','exam_end','confidence','days_after','baseline_orders','revision_orders','added_orders','exam_factor'],offsets)
# Compare low/high temperature quartiles using total menu quantities by class.
tempdays=sorted((num(fm[x[0]].get('avg_temp_c')),x[0]) for x in D if num(fm[x[0]].get('avg_temp_c')) is not None);q=max(1,len(tempdays)//4);low={x[1] for x in tempdays[:q]};high={x[1] for x in tempdays[-q:]}
def share(ds,typ):
 allq=sum(x[2] for x in M if x[0] in ds);qtyp=sum(x[2] for x in M if x[0] in ds and x[9]==typ);return qtyp,allq,round(100*qtyp/allq,4) if allq else 0
temprows=[[group,typ,len(ds),*share(ds,typ)] for group,ds in [('low_temp_q1',low),('high_temp_q4',high)] for typ in ('HOT','COLD','NEUTRAL','UNKNOWN')]
wr(O/'temperature_menu_mix_comparison.csv',['temperature_group','class','days_n','class_quantity','all_quantity','share_pct'],temprows)
detail_sum=collections.Counter()
for x in details:detail_sum[x[1]]+=x[8]
rainmiss=sum(num(fm[d.isoformat()].get('precipitation_mm')) is None for d in days)
checks={'669_contiguous_days':len(D)==669 and [x[0] for x in D]==[d.isoformat() for d in days],'no_duplicate_dates':len({x[0] for x in D})==669,'daily_sales_equals_order_total':tot==sum(x[8] for x in orders),'order_total_equals_details':all(detail_sum[x[0]]==x[8] for x in orders),'menu_quantities_equal_details':sum(x[2] for x in M)==sum(x[5] for x in details),'27_source_menu_ids':len(menus)==27 and all(x[2] in menuid for x in details),'menu_prices_match':all(int(float(x[6]))==int(float(menuid[x[2]]['unit_price'])) for x in details),'nonnegative':all(x[5]>=0 and x[8]>=0 for x in details),'rain_missing_396':rainmiss==396,'reviews_excluded':True,'exam_schedules_distinct':len({tuple(e['start'] for e in events if e['school']==s) for s in school.values()})>1}
# event factor design checks and observed mean ratios in isolated dates
def event_curve(e,d):
 st=date.fromisoformat(e['start']);en=date.fromisoformat(e['end']);k=e['strength']
 if st-timedelta(14)<=d<st:return k*(d-(st-timedelta(14))).days/14
 if st<=d<=en:return k
 if en<d<=en+timedelta(14):return k*(14-(d-en).days)/14
 return 0
checks['exam_pre_ramp_factor']=all(event_curve(e,date.fromisoformat(e['start'])-timedelta(1))>event_curve(e,date.fromisoformat(e['start'])-timedelta(14)) for e in events)
checks['exam_constant_factor']=all(event_curve(e,date.fromisoformat(e['start']))==e['strength'] for e in events)
checks['post_factor_decay']=all(event_curve(e,date.fromisoformat(e['end'])+timedelta(k))>=event_curve(e,date.fromisoformat(e['end'])+timedelta(k+1)) for e in events for k in range(1,14))
checks['individual_event_day14_component_zero']=all(event_curve(e,date.fromisoformat(e['end'])+timedelta(14))==0 for e in events)
checks['cold_share_high_temp_gt_low']=share(high,'COLD')[2]>share(low,'COLD')[2]
checks['hot_share_low_temp_gt_high']=share(low,'HOT')[2]>share(high,'HOT')[2] if 'HOT' in types.values() else None
checks['unknown_no_temperature_adjustment']=True
# xlsx
def col(n):
 s=''
 while n:n,r=divmod(n-1,26);s=chr(65+r)+s
 return s
def sx(h,rows):
 a=['<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
 for i,row in enumerate([h]+rows,1):
  a.append(f'<row r="{i}">')
  for j,v in enumerate(row,1):
   ref=f'{col(j)}{i}'
   if isinstance(v,(int,float)):a.append(f'<c r="{ref}"><v>{v}</v></c>')
   else:
    t=str(v).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;');a.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{t}</t></is></c>')
  a.append('</row>')
 return ''.join(a)+'</sheetData></worksheet>'
tabs=[('daily_sales',DHEAD,D),('daily_menu_sales',DH,M),('orders',OH,orders),('order_details',DEH,details),('hourly_sales',HH,H),('menu_sales_mix',['menu_id','menu_name','category','unit_price','quantity','sales_amount','revenue_share_pct','temperature_class','basis'],mix),('exam_period_comparison',['school','exam_start','exam_end','confidence','window','n_days','baseline_mean','revision_mean','added_mean','added_pct'],examrows),('exam_post_offsets',['school','exam_start','exam_end','confidence','days_after','baseline_orders','revision_orders','added_orders','exam_factor'],offsets),('temperature_menu_mix_comparison',['temperature_group','class','days_n','class_quantity','all_quantity','share_pct'],temprows),('monthly_summary',['month','sales_total','orders_total','avg_daily_sales','days'],monthly)]
wb='<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i,(n,_,_) in enumerate(tabs,1))+'</sheets></workbook>'
xp=O/'404dabang_sales_dummy_v1_revision_669days.xlsx'
with zipfile.ZipFile(xp,'w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(tabs)+1))+'</Types>')
 z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
 z.writestr('xl/workbook.xml',wb);z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(tabs)+1))+'</Relationships>')
 for i,(_,h,r) in enumerate(tabs,1):z.writestr(f'xl/worksheets/sheet{i}.xml',sx(h,r))
z=zipfile.ZipFile(xp);assert z.testzip() is None
for n in z.namelist():
 if n.endswith('.xml') or n.endswith('.rels'):ET.fromstring(z.read(n))
rowcheck=all(len(ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'))==len(r)+1 for i,(_,h,r) in enumerate(tabs,1))
checks['xlsx_xml_and_rowcounts']=rowcheck
# Catalog has no unambiguous HOT item: that requested behavior remains unverified, never mark it passed.
unresolved=[]
if 'HOT' not in types.values():unresolved.append('No menu name explicitly confirms HOT serving; low-temperature HOT share uplift cannot be validated without owner/menu confirmation.')
if not checks['cold_share_high_temp_gt_low']:unresolved.append('Cold-menu share failed to rise in high-temperature quartile; adjust temperature coefficient or review classification.')
v={'passed':not unresolved and all(x for x in checks.values() if x is not None),'status':'draft_validation_incomplete' if unresolved else 'draft_checks_passed','checks':checks,'unresolved':unresolved,'counts':{'orders':len(orders),'order_details':len(details),'daily_sales':len(D),'daily_menu_sales':len(M),'hourly_sales':len(H),'menus':len(menus)},'total_sales':tot,'rain_missing_days':rainmiss,'temperature_types':types,'crosscheck':'Report counts/totals calculated from order CSV records; workbook sheet row counts and XML parsed.'}
(O/'generation_rules.json').write_text(json.dumps({'version':'sales_dummy_v1_revision','draft_status':v['status'],'seed':40420261110,'synthetic':True,'reviews_included':False,'events':events,'counts':v['counts'],'total_sales':tot,'sources':['v1 draft daily profile only (not 180-day rows merged)','menu catalog from 404dabang_dummy_sales_data_menu_id_fixed.xlsx','daily weather/holiday/academic features from existing prepared CSV'],'assumptions':['Approximate inverse of v1 exam uplift used to estimate baseline; this is a synthetic control, not observed demand.','Per-school 14-day lead ramp, flat exam effect, 14-day linear decay; overlap strongest plus 25% of remaining, capped 22%.','High-school estimated dates have reduced effect and estimated_low source state.','Only explicit HOT/COLD wording classified; desserts/bakery NEUTRAL; ambiguous drinks UNKNOWN.','Weather mix coefficients are synthetic scenario assumptions, not causal facts.','Dessert category has a weak +3% winter preference scenario in Nov-Feb; synthetic only.','Rain-missing days do not receive rain effect. No costs, margins, reviews, or DB identifiers were fabricated.'],'temperature_types':types,'django_menu_mapping':'Source M001-M027 differ from Django integer PK; DB not accessed; mapping incomplete.'},ensure_ascii=False,indent=2),encoding='utf-8')
(O/'validation_report.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'counts':v['counts'],'total_sales':tot,'checks':checks,'unresolved':unresolved,'files':[x.name for x in O.iterdir()]},ensure_ascii=False))
