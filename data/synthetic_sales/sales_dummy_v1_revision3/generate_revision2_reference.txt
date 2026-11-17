
import csv,json,zipfile,xml.etree.ElementTree as ET,random,math,collections,hashlib
from pathlib import Path
from datetime import date
R=Path.cwd();SRC=R/'data/synthetic_sales/sales_dummy_v1_revision';O=R/'data/synthetic_sales/sales_dummy_v1_revision2';rng=random.Random(40420261112)
def U(s):return s.encode('ascii').decode('unicode_escape')
def read(n):
 with open(SRC/n,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(n,h,rows):
 with open(O/n,'w',encoding='utf-8-sig',newline='') as f:w=csv.writer(f);w.writerow(h);w.writerows(rows)
def num(x):
 try:return float(x) if x not in ('',None) else None
 except:return None
dual_ids={'M001','M002','M003','M004','M005','M006','M007','M008','M013','M015','M017'}
ice_ids={'M009','M010','M011','M012','M014','M016','M018'}
unknown_ids={f'M{i:03d}' for i in range(19,28)}
orders=read('orders.csv');details0=read('order_details.csv');daily=read('daily_sales.csv');features0=read_csv=None
with open(R/'data/processed/404dabang_daily_features.csv',encoding='utf-8-sig',newline='') as f:features=list(csv.DictReader(f))
fmap={x['date']:x for x in features}
menus={}
for x in details0:menus[x['menu_id']]={'menu_id':x['menu_id'],'menu_name':x['menu_name'],'category':x['category'],'unit_price':int(x['unit_price'])}
assert len(menus)==27
menu_type={}
for mid,m in menus.items():
 if mid in dual_ids:menu_type[mid]='HOT_ICE'
 elif mid in ice_ids:menu_type[mid]='ICE_ONLY'
 elif mid in unknown_ids:menu_type[mid]='UNKNOWN'
 else:raise ValueError('Unclassified menu ID '+mid)
assert sum(x=='HOT_ICE' for x in menu_type.values())==11
assert sum(x=='ICE_ONLY' for x in menu_type.values())==7
assert sum(x=='UNKNOWN' for x in menu_type.values())==9
# Convert each existing order detail item to a serving-temperature assignment; menu ID, qty and price stay unchanged.
order_dates={o['order_id']:o['order_date'] for o in orders}
details=[]; dual_qty_by_date=collections.defaultdict(lambda:[0,0]); daily_menu=collections.defaultdict(lambda:[0,0,0,0,0,0])
for d in details0:
 ds=order_dates[d['order_id']]
 m=menus[d['menu_id']]; kind=menu_type[d['menu_id']]; temp=num(fmap[ds].get('avg_temp_c'))
 if kind=='ICE_ONLY':serv='ICE'
 elif kind=='UNKNOWN':serv='UNKNOWN'
 else:
  # Synthetic assumption: logistic HOT probability, centered at 16 C with 5 C scale, clipped to [0.10, 0.95].
  p_hot=1/(1+math.exp((temp-16)/5)) if temp is not None else .5
  p_hot=max(.10,min(.95,p_hot))
  serv='HOT' if rng.random()<p_hot else 'ICE'
  q=int(d['quantity'])
  dual_qty_by_date[ds][0]+=q
  dual_qty_by_date[ds][1]+=q if serv=='HOT' else 0
 q=int(d['quantity']);price=int(d['unit_price']);assert price==m['unit_price']
 row=[d['order_detail_id'],d['order_id'],d['menu_id'],d['menu_name'],d['category'],q,serv,price,int(d['discount_amount']),int(d['line_total']),d['data_type'],'sales_dummy_v1_revision2']
 details.append(row)
 a=daily_menu[(ds,d['menu_id'])]
 a[0]+=q;a[1]+=int(d['line_total'])
 if serv=='HOT':a[2]+=q
 elif serv=='ICE':a[3]+=q
 else:a[4]+=q
 a[5]+=int(d['line_total'])
# Add temperature summary fields; daily totals and original orders remain unchanged.
ohead=list(orders[0].keys());orders_out=[[('sales_dummy_v1_revision2' if k=='dataset_version' else o[k]) for k in ohead] for o in orders]
write('orders.csv',ohead,orders_out)
dh=['order_detail_id','order_id','menu_id','menu_name','category','quantity','serving_temperature','unit_price','discount_amount','line_total','data_type','dataset_version']
write('order_details.csv',dh,details)
dmh=['sales_date','menu_id','quantity','sales_amount','menu_name','category','unit_price','data_type','dataset_version','availability_type','hot_quantity','ice_quantity','unknown_quantity','temperature_split_sum']
dm=[]
for ds in sorted({o['order_date'] for o in orders}):
 for mid,m in menus.items():
  q,amt,hot,ice,unk,amt2=daily_menu[(ds,mid)]
  dm.append([ds,mid,q,amt,m['menu_name'],m['category'],m['unit_price'],'synthetic_dummy','sales_dummy_v1_revision2',menu_type[mid],hot,ice,unk,hot+ice+unk])
write('daily_menu_sales.csv',dmh,dm)
# Menu-level quantity/revenue and temperature mix
mt=collections.defaultdict(lambda:[0,0,0,0,0,0])
for x in details:
 a=mt[x[2]];q=x[5];amt=x[9];a[0]+=q;a[1]+=amt
 if x[6]=='HOT':a[2]+=q
 elif x[6]=='ICE':a[3]+=q
 else:a[4]+=q
 a[5]+=q
menu_mix=[]
for mid,m in menus.items():
 a=mt[mid]
 menu_mix.append([mid,m['menu_name'],m['category'],m['unit_price'],menu_type[mid],a[0],a[1],a[2],a[3],a[4],a[2]+a[3]+a[4],round(100*a[2]/max(1,a[0]),4),round(100*a[3]/max(1,a[0]),4),a[0]==a[2]+a[3]+a[4]])
write('menu_temperature_sales.csv',['menu_id','menu_name','category','unit_price','availability_type','total_quantity','sales_amount','hot_quantity','ice_quantity','unknown_quantity','temperature_sum_quantity','hot_share_pct_of_menu','ice_share_pct_of_menu','quantity_reconciles'],menu_mix)
# low/high temperature groups: quartiles; HOT/ICE share denominator is the 11 dual-choice menu units.
tempdays=sorted((num(fmap[x['sales_date']].get('avg_temp_c')),x['sales_date']) for x in daily if num(fmap[x['sales_date']].get('avg_temp_c')) is not None)
q=max(1,len(tempdays)//4);low={x[1] for x in tempdays[:q]};high={x[1] for x in tempdays[-q:]}
def group_stat(ds):
 den=sum(dual_qty_by_date[d][0] for d in ds);hot=sum(dual_qty_by_date[d][1] for d in ds);ice=den-hot
 return den,hot,ice,round(100*hot/max(1,den),4),round(100*ice/max(1,den),4)
cold=group_stat(low);warm=group_stat(high)
temp_compare=[['low_temp_q1',len(low),*cold],['high_temp_q4',len(high),*warm]]
write('temperature_group_comparison.csv',['temperature_group','days_n','dual_menu_quantity','hot_quantity','ice_quantity','hot_share_pct','ice_share_pct'],temp_compare)
ice_rows=[[mid,m['menu_name'],mt[mid][0],mt[mid][1]] for mid,m in menus.items() if menu_type[mid]=='ICE_ONLY']
write('ice_only_menu_sales.csv',['menu_id','menu_name','ice_quantity','sales_amount'],ice_rows)
unknown_rows=[[mid,m['menu_name'],mt[mid][0],mt[mid][1]] for mid,m in menus.items() if menu_type[mid]=='UNKNOWN']
write('unknown_menu_sales.csv',['menu_id','menu_name','unknown_quantity','sales_amount'],unknown_rows)
reconcile=[[mid,m['menu_name'],menu_type[mid],mt[mid][0],mt[mid][2],mt[mid][3],mt[mid][4],mt[mid][2]+mt[mid][3]+mt[mid][4],mt[mid][0]==mt[mid][2]+mt[mid][3]+mt[mid][4],all(int(x[7])==m['unit_price'] and int(x[9])==int(x[5])*m['unit_price'] for x in details if x[2]==mid)] for mid,m in menus.items()]
write('menu_temperature_reconciliation.csv',['menu_id','menu_name','availability_type','total_quantity','hot_quantity','ice_quantity','unknown_quantity','temperature_sum_quantity','quantity_reconciles','price_and_line_amount_valid'],reconcile)
# Exact CSV metrics; source daily and exam scenarios are retained.
order_sum=collections.Counter()
for x in details:order_sum[x[1]]+=x[9]
sales_sum=sum(int(o['net_sales']) for o in orders)
assert all(order_sum[o['order_id']]==int(o['net_sales']) for o in orders)
assert cold[3]>warm[3] and warm[4]>cold[4]
assert all(x[8] for x in reconcile)
# Daily menu totals must reproduce original revision daily sales and full menu qty.
sales_by_day=collections.Counter()
for o in orders:sales_by_day[o['order_date']]+=int(o['net_sales'])
assert all(sales_by_day[x['sales_date']]==int(x['actual_sales']) for x in daily)
# Save untouched aggregates as source structure; add new version labels only to revision2's daily table.
daily2=[]
for x in daily:
 daily2.append([x['sales_date'],x['actual_sales'],x['order_count'],x['average_ticket'],x['weekday_ko'],'synthetic_dummy','sales_dummy_v1_revision2',x.get('baseline_order_count',''),x.get('exam_effect_factor',''),x.get('post_exam_taper_orders','')])
write('daily_sales.csv',['sales_date','actual_sales','order_count','average_ticket','weekday_ko','data_type','dataset_version','baseline_order_count','exam_effect_factor','post_exam_taper_orders'],daily2)
# Copy time series / exam reports so the 669-day demand scenario is preserved.
hour=read('hourly_sales.csv');hh=list(hour[0].keys());write('hourly_sales.csv',hh,[[('sales_dummy_v1_revision2' if k=='dataset_version' else x[k]) for k in hh] for x in hour])
for fn in ('daily_sales_trend_summary.csv','exam_period_comparison.csv','exam_post_offsets.csv'):
 (O/fn).write_bytes((SRC/fn).read_bytes())
# Rules and validation
oldrules=json.loads((SRC/'generation_rules.json').read_text(encoding='utf-8'))
rules={'version':'sales_dummy_v1_revision2','draft_status':'draft_validation_incomplete','store':'404??','store_id':1,'period':['2025-01-01','2026-10-31'],'days':669,'random_seed':40420261112,'synthetic':True,'reviews_included':False,'counts':{'orders':len(orders),'order_details':len(details),'daily_sales':len(daily2),'daily_menu_sales':len(dm),'menus':len(menus)},'total_sales':sales_sum,'inherited_exam_events':oldrules.get('events',[]),'menu_availability':{mid:menu_type[mid] for mid in menus},'temperature_assumption':{'rule':'p(HOT)=clip(1/(1+exp((avg_temp_c-16)/5)),0.10,0.95) for HOT/ICE menus; ICE-only always ICE; desserts UNKNOWN.','interpretation':'Synthetic scenario weighting, not observed causal effect.'},'sources':['sales_dummy_v1_revision generated orders and daily demand profile','user-confirmed menu temperature availability list','data/processed/404dabang_daily_features.csv for daily average temperature'],'constraints':['Menu IDs, prices, quantities, order counts and total sales are inherited; serving_temperature is added at order-detail level.','No DB, Django models, migrations, or Prophet files changed.','Django integer menu PK mapping remains incomplete.','No reviews, costs, or margins included.']}
(O/'generation_rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2),encoding='utf-8')
# Build XLSX workbook with relevant detailed and reconciliation sheets plus inherited exam and summary tabs.
def col(n):
 s=''
 while n:n,r=divmod(n-1,26);s=chr(65+r)+s
 return s
def sx(h,rows):
 out=['<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
 for i,row in enumerate([h]+rows,1):
  out.append(f'<row r="{i}">')
  for j,v in enumerate(row,1):
   ref=f'{col(j)}{i}'
   if isinstance(v,(int,float)):out.append(f'<c r="{ref}"><v>{v}</v></c>')
   else:
    z=str(v).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;');out.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{z}</t></is></c>')
  out.append('</row>')
 return ''.join(out)+'</sheetData></worksheet>'
# load copied report sheets
exam=[['school','exam_start','exam_end','confidence','window','n_days','baseline_mean','revision_mean','added_mean','added_pct']]
exam+= [[x[k] for k in ('school','exam_start','exam_end','confidence','window','n_days','baseline_mean','revision_mean','added_mean','added_pct')] for x in read('exam_period_comparison.csv')]
offset=[['school','exam_start','exam_end','confidence','days_after','baseline_orders','revision_orders','added_orders','exam_factor']]
offset+= [[x[k] for k in ('school','exam_start','exam_end','confidence','days_after','baseline_orders','revision_orders','added_orders','exam_factor')] for x in read('exam_post_offsets.csv')]
monthly=[['month','sales_total','orders_total','avg_daily_sales','days']]
monthly += [[x[k] for k in ('month','sales_total','orders_total','avg_daily_sales','days')] for x in read('daily_sales_trend_summary.csv')]
ohead=list(orders[0].keys()); dailyhead=['sales_date','actual_sales','order_count','average_ticket','weekday_ko','data_type','dataset_version','baseline_order_count','exam_effect_factor','post_exam_taper_orders']
tabs=[('daily_sales',dailyhead,daily2),('daily_menu_sales',dmh,dm),('orders',ohead,orders_out),('order_details',dh,details),('hourly_sales',hh,[[x[k] for k in hh] for x in read('hourly_sales.csv')]),('menu_temperature_sales',['menu_id','menu_name','category','unit_price','availability_type','total_quantity','sales_amount','hot_quantity','ice_quantity','unknown_quantity','temperature_sum_quantity','hot_share_pct_of_menu','ice_share_pct_of_menu','quantity_reconciles'],menu_mix),('temperature_group_comparison',['temperature_group','days_n','dual_menu_quantity','hot_quantity','ice_quantity','hot_share_pct','ice_share_pct'],temp_compare),('ice_only_menu_sales',['menu_id','menu_name','ice_quantity','sales_amount'],ice_rows),('unknown_menu_sales',['menu_id','menu_name','unknown_quantity','sales_amount'],unknown_rows),('menu_temp_reconciliation',['menu_id','menu_name','availability_type','total_quantity','hot_quantity','ice_quantity','unknown_quantity','temperature_sum_quantity','quantity_reconciles','price_and_line_amount_valid'],reconcile),('exam_period_comparison',exam[0],exam[1:]),('exam_post_offsets',offset[0],offset[1:]),('monthly_summary',monthly[0],monthly[1:])]
xp=O/'404dabang_sales_dummy_v1_revision2_669days.xlsx'
wb='<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i,(n,_,_) in enumerate(tabs,1))+'</sheets></workbook>'
with zipfile.ZipFile(xp,'w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(tabs)+1))+'</Types>')
 z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
 z.writestr('xl/workbook.xml',wb);z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(tabs)+1))+'</Relationships>')
 for i,(_,h,r) in enumerate(tabs,1):z.writestr(f'xl/worksheets/sheet{i}.xml',sx(h,r))
z=zipfile.ZipFile(xp);assert z.testzip() is None
for n in z.namelist():
 if n.endswith('.xml') or n.endswith('.rels'):ET.fromstring(z.read(n))
# Cross-check core sums, counts and directional temperature result.
checks={'669_days_and_date_span':len(daily2)==669 and daily2[0][0]=='2025-01-01' and daily2[-1][0]=='2026-10-31','orders_unchanged_from_revision':len(orders)==len(read('orders.csv')),'menu_count_27':len(menus)==27,'dual_menu_count_11':sum(x=='HOT_ICE' for x in menu_type.values())==11,'ice_only_count_7':sum(x=='ICE_ONLY' for x in menu_type.values())==7,'unknown_dessert_count_9':sum(x=='UNKNOWN' for x in menu_type.values())==9,'low_temp_hot_share_higher':cold[3]>warm[3],'high_temp_ice_share_higher':warm[4]>cold[4],'all_menu_qty_reconciles':all(x[8] for x in reconcile),'price_and_line_amounts_match':all(x[9] for x in reconcile),'order_detail_sum_equals_order':all(order_sum[o['order_id']]==int(o['net_sales']) for o in orders),'daily_sales_unchanged':sum(int(x['actual_sales']) for x in daily)==sales_sum,'reviews_excluded':True,'rain_missing_preserved_396':sum(num(fmap[d['sales_date']].get('precipitation_mm')) is None for d in daily)==396}
xlsx_rows=True
for i,(_,h,r) in enumerate(tabs,1):
 root=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
 xlsx_rows &= len(root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'))==len(r)+1
checks['xlsx_xml_rows_match_csv']=xlsx_rows
# report remains incomplete unless all specified validations pass; no HOT selection applies to ICE-only and UNKNOWN separately.
passed=all(checks.values())
validation={'passed':False,'status':'draft_validation_incomplete','checks':checks,'counts':rules['counts'],'total_sales':sales_sum,'order_detail_quantity':sum(int(x[5]) for x in details),'hot_ice_choice_group':{'low_temp_days':len(low),'high_temp_days':len(high),'low_temp_hot_share_pct':cold[3],'high_temp_hot_share_pct':warm[3],'low_temp_ice_share_pct':cold[4],'high_temp_ice_share_pct':warm[4]},'limitations':['Temperature weights are synthetic scenario settings, not observed causal effects.','Serving temperature was not represented in the original menu catalog; per-order choice is simulated.','Django integer Menu PK map remains incomplete; DB not accessed.'],'v1_revision_preserved':True,'unresolved':['Temperature probability curve is a synthetic assumption and remains subject to review.']}
(O/'validation_report.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'folder':str(O),'counts':rules['counts'],'total_sales':sales_sum,'temp_shares':{'low_HOT':cold[3],'high_HOT':warm[3],'low_ICE':cold[4],'high_ICE':warm[4]},'checks':checks},ensure_ascii=False))
