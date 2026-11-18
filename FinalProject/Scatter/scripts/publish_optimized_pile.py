import os,json,time,shutil,collections
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
with open(ROOT+'/geo/optimized_pile_validation.json') as f:validation=json.load(f)
assert not validation['penetrations_over_0_02mm'] and not validation['without_support_contact_chain']
assert all(abs(b['bottom_m'])<1e-5 and b['upright_error']<1e-6 for b in validation['barrels'])
with open(ROOT+'/geo/manual_controls_test_results.json') as f:tests=json.load(f)
assert tests['slider_solver_cooks']==0 and tests['cache_hit_solver_cooks']==0 and tests['nonzero_build'] and tests['zero_density'] and tests['failed_build_keeps_previous']
hou.hipFile.load(ROOT+'/Scatter_Pile_Optimized_Candidate.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
obj=hou.node('/obj/SCATTER_PILE')
with open(ROOT+'/sim/pile_cache/'+obj.userData('pile_active_cache')+'/manifest.json') as f:manifest=json.load(f)
with open(ROOT+'/geo/optimization_baseline.json') as f:baseline=json.load(f)
with open(ROOT+'/geo/bullet_proxy_stats.json') as f:old_stats=json.load(f)
with open(ROOT+'/geo/bullet_proxy_stats_optimized.json') as f:new_stats=json.load(f)
counts=collections.Counter(p.stringAttribValue('asset_name') for p in obj.node('OUT_SCATTER').geometry().prims())
# The old drum already used one whole convex hull in Bullet.
old_stats['SM_01_OilBarrel']=1
report={'parameters':manifest['parameters'],'piece_count':manifest['piece_count'],
        'old_compound_count':sum(old_stats[k]*v for k,v in counts.items()),
        'new_compound_count':sum(new_stats[k]*v for k,v in counts.items()),
        'baseline_144_frame_seconds':baseline['simulation_seconds'],
        'optimized_144_frame_seconds':manifest['first_144_simulation_seconds'],
        'same_frame_speedup':baseline['simulation_seconds']/manifest['first_144_simulation_seconds'],
        'optimized_full_build_seconds':manifest['seconds'],'optimized_final_frame':manifest['settled_frame'],
        'substeps_before_after':[20,8],'iterations_before_after':[80,40],
        'zero_intersections':True,'all_pieces_supported':True,'upright_grounded_barrel':True,'tests':tests}
with open(ROOT+'/geo/optimization_results.json','w') as f:json.dump(report,f,indent=2)
obj.node('BULLET_COMPOUND_LIBRARY').setComment('Optimized conservative compound hulls; keep principal holes. Original render geometry is unchanged.')
obj.node('GRAVITY_SETTLE').setComment('8 substeps / 40 iterations. Runs only on Rebuild Pile, with final compound contact check before publishing.')
for note in obj.stickyNotes():
    note.setText('FAST MANUAL BUILD\n1. Select outer SCATTER_PILE GEO.\n2. Set Length / Width / Height / Density.\n3. Click Rebuild Pile. Esc cancels safely.\n\nSliders update only the bounds guide.\nPrevious completed pile remains visible.\nRepeated settings reuse disk cache.\nOptimized compound proxies; unchanged render models.\nBarrels remain upright on ground.\nFinal contacts are checked before publishing.')
rop=hou.node('/out/RENDER_PILE_PREVIEW')
if rop:rop.parm('vm_picture').set('$HIP/render/Scatter_Pile_Preview.png')
backup=ROOT+'/backup/Scatter_Pile_before_collision_optimization_'+time.strftime('%Y%m%d_%H%M%S')+'.hipnc'
shutil.copy2(ROOT+'/Scatter_Pile.hipnc',backup)
obj.setSelected(True,clear_all_selected=True)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
shutil.copy2(ROOT+'/render/Scatter_Pile_Optimized_Preview.png',ROOT+'/render/Scatter_Pile_Preview.png')
print('PUBLISHED',json.dumps(report),flush=True)
print('BACKUP',backup,flush=True)
