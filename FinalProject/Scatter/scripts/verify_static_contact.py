import json
from pathlib import Path
import runpy
import sys
import time
import hou

root = Path(__file__).resolve().parents[1]
hou.hipFile.load(str(root/'Scatter_Pile_Static_Test.hipnc'), ignore_load_warnings=True, suppress_save_prompt=True)
obj = hou.node('/obj/SCATTER_PILE')
keys = ['length_cm','width_cm','height_cm','density']
original = [obj.evalParm(key) for key in keys]
solver = obj.node('GRAVITY_SETTLE')
cooks = solver.cookCount()

def build(values):
    for key, value in zip(keys,values):
        obj.parm(key).set(value)
    start = time.perf_counter()
    obj.parm('rebuild_pile').pressButton()
    assert obj.evalParm('build_status').startswith('Ready:'), obj.evalParm('build_status')
    print('BUILT', values, obj.evalParm('build_status'), time.perf_counter()-start, flush=True)

def validate(label):
    folder = root/'sim/pile_cache'/obj.userData('pile_active_cache')
    reportfile = folder/'static_validation.json'
    sys.argv = ['validate',str(folder/'visual.bgeo.sc'),str(folder/'proxy.bgeo.sc'),str(reportfile)]
    runpy.run_path(str(root/'scripts/validate_gravity_pile.py'), run_name='__main__')
    report = json.loads(reportfile.read_text())
    assert not report['without_support_contact_chain'] and not report['penetrations_over_0_02mm'],label
    assert all(abs(b['bottom_m'])<1e-5 and b['upright_error']<1e-6 for b in report['barrels'])
    length,width,height = [obj.evalParm(k)/100 for k in keys[:3]]
    assert all(a>=b-.0002 for a,b in zip(report['bounds_min_m'],[-length/2,0,-width/2]))
    assert all(a<=b+.0002 for a,b in zip(report['bounds_max_m'],[length/2,height,width/2]))

validate('default')
active = obj.userData('pile_active_cache')
for i in range(100):
    obj.parm('length_cm').set(50+i)
    obj.node('BOUNDS_GUIDE').geometry()
    obj.node('OUT_SCATTER').geometry()
assert obj.userData('pile_active_cache')==active and solver.cookCount()==cooks
build(original)
build([50,50,50,100])
validate('min')
build([135,125,125,100])
validate('dense')
build([50,50,50,0])
assert not obj.node('OUT_SCATTER').geometry().prims()
build(original)
assert obj.userData('pile_active_cache')==active and solver.cookCount()==cooks
print('PASSED',flush=True)
rop = hou.node('/out/RENDER_PILE_PREVIEW')
image = root/'render/Scatter_Pile_Static_Preview.png'
rop.parm('vm_picture').set(str(image))
rop.render(frame_range=(1,1))
print('PREVIEW',image,flush=True)
