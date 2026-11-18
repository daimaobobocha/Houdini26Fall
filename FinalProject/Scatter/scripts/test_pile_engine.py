import os,sys,json,time
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.dirname(__file__))
from pile_engine import make_proxy,generate,validate
with open(os.path.join(ROOT,'geo','scatter_asset_library.json')) as f:assets=json.load(f)
t=time.time()
for a in assets:
    a['proxy']=make_proxy(a['vertices'])
    print('PROXY',a['name'],len(a['proxy']['vertices']),len(a['proxy']['edges']),flush=True)
meta=[{k:a[k] for k in ['name','center_m','source_mesh','proxy']} for a in assets]
with open(os.path.join(ROOT,'geo','scatter_collision_library.json'),'w') as f:json.dump(meta,f,separators=(',',':'))
for length,width,height,density in [(2.2,1.8,1.,65),(.5,.5,.5,100),(.5,.5,.5,0),(1.,.7,.5,100)]:
    start=time.time();points,placed,stats=generate(meta,length,width,height,density)
    stats.update(validate(placed,length,width,height));stats['seconds']=round(time.time()-start,3)
    print('CASE',json.dumps(stats),flush=True)
    assert not stats['overlapping_proxy_pairs'] and not stats['outside_bounds']
    if length==2.2:
        with open(os.path.join(ROOT,'geo','pile_preview_transforms.json'),'w') as f:json.dump(points,f,indent=2)
        with open(os.path.join(ROOT,'geo','pile_validation.json'),'w') as f:json.dump(stats,f,indent=2)
print('TOTAL_SECONDS',time.time()-t,flush=True)
