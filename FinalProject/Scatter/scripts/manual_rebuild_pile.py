"""Embedded GEO button callback. Slider edits never invoke this code."""
import os,json,time,hashlib,contextlib
import hou
import numpy as np

PARAMS=('length_cm','width_cm','height_cm','density')
CACHE_VERSION='manual-gravity-v3-optimized'

def values(obj):
    return {k:max(50.,float(obj.evalParm(k))) if k!='density' else max(0.,min(100.,float(obj.evalParm(k)))) for k in PARAMS}

def status(obj,message):
    obj.parm('build_status').set(message)

def rebuild(obj):
    if obj.userData('pile_build_running')=='1':return
    committed=obj.node('BUILD_SETTINGS')
    old_committed={k:committed.evalParm(k) for k in PARAMS}
    update_mode=hou.updateModeSetting();old_frame=hou.frame()
    request=values(obj);root=hou.expandString('$HIP').replace('\\','/')
    fingerprints=[]
    for path in ['geo/scatter_assets.bgeo.sc','geo/scatter_bullet_compounds_optimized.bgeo.sc','geo/bullet_hull_metadata_optimized.json']:
        st=os.stat(os.path.join(root,path));fingerprints.append((path,st.st_size,st.st_mtime_ns))
    key=hashlib.sha256(json.dumps([CACHE_VERSION,request,fingerprints],sort_keys=True).encode()).hexdigest()[:20]
    relative='sim/pile_cache/'+key
    folder=os.path.join(root,relative);visual_path=folder+'/visual.bgeo.sc';proxy_path=folder+'/proxy.bgeo.sc'
    manifest_path=folder+'/manifest.json'
    obj.setUserData('pile_build_running','1')
    solver=obj.node('GRAVITY_SETTLE')
    published=False;elapsed=time.time()

    def publish(manifest):
        obj.node('SETTLED_DEFAULT_CACHE').parm('file').set('$HIP/'+relative+'/visual.bgeo.sc')
        obj.node('SETTLED_PROXY_CACHE').parm('file').set('$HIP/'+relative+'/proxy.bgeo.sc')
        obj.node('SETTLED_DEFAULT_CACHE').parm('reload').pressButton()
        obj.node('SETTLED_PROXY_CACHE').parm('reload').pressButton()
        obj.setUserData('pile_built_settings',json.dumps(request,sort_keys=True))
        obj.setUserData('pile_active_cache',key)
        for k,v in request.items():committed.parm(k).set(v)
        status(obj,'Ready: %d parts | sliders preview only; click Rebuild to apply.'%manifest['piece_count'])

    try:
        hou.setUpdateMode(hou.updateMode.Manual)
        if all(os.path.isfile(p) for p in [manifest_path,visual_path,proxy_path]):
            with open(manifest_path) as f:manifest=json.load(f)
            publish(manifest);published=True
            print('PILE_CACHE_HIT',key,manifest['piece_count'],flush=True)
            return
        for k,v in request.items():committed.parm(k).set(v)
        # Outputs are already disconnected from the solver, so AutoUpdate is safe.
        # Manual mode would return uncooked/empty SOP geometry from geometry().
        hou.setUpdateMode(hou.updateMode.AutoUpdate)
        operation=hou.InterruptableOperation('Generating scrap pile','Prepare / settle / check contacts',open_interrupt_dialog=True) if hou.isUIAvailable() else contextlib.nullcontext(None)
        with operation as progress:
            def report(fraction,message):
                if progress:progress.updateLongProgress(fraction,message);progress.updateProgress(fraction)
                status(obj,message)
            report(.01,'Preparing fixed simulation inputs...')
            hou.setFrame(1)
            visual_input=obj.node('RBD_VISUAL_INITIAL').geometry().freeze()
            proxy_input=obj.node('RBD_PROXY_INITIAL').geometry().freeze()
            wall_input=obj.node('PACK_WALLS').geometry().freeze()
            # Data stashes have no SOP inputs. They isolate the simulation from all slider/source cooks.
            for name,geo in [('SIM_INPUT_VISUAL',visual_input),('SIM_INPUT_PROXY',proxy_input),('SIM_INPUT_WALLS',wall_input)]:
                obj.node(name).parm('stash').set(geo)
            solver.parm('resetsim').pressButton()
            piece_count=len(visual_input.prims());last_frame=1;stable_checks=0
            preparation_seconds=time.time()-elapsed;simulation_start=time.time();first_144_seconds=None
            max_frame=int(obj.node('SETTLED_FRAME').evalParm('frame'))
            if piece_count:
                for frame in range(1,max_frame+1):
                    report(.05+.82*(frame-1)/max(1,max_frame-1),'Settling frame %d / %d — Esc cancels'%(frame,max_frame))
                    hou.setFrame(frame);proxy_geometry=solver.geometry(output_index=2)
                    if proxy_geometry is None or solver.errors():raise RuntimeError(str(solver.errors()))
                    last_frame=frame
                    if frame==144:first_144_seconds=time.time()-simulation_start
                    if frame%24==0:
                        speed=max([np.linalg.norm(p.attribValue('v')) for p in proxy_geometry.points()],default=0.)
                        spin=max([np.linalg.norm(p.attribValue('w')) for p in proxy_geometry.points()],default=0.)
                        stable_checks=stable_checks+1 if frame>=96 and speed<.025 and spin<.25 else 0
                        if not hou.isUIAvailable():print('PILE_BUILD_FRAME',frame,'v',round(float(speed),5),'w',round(float(spin),5),flush=True)
                        if stable_checks>=3:break
                visual=solver.geometry().freeze();proxy=solver.geometry(output_index=2).freeze()
            else:visual=visual_input;proxy=proxy_input
            simulation_seconds=time.time()-simulation_start;cleanup_start=time.time()
            report(.9,'Checking final contacts...')
            with open(root+'/geo/bullet_hull_metadata_optimized.json') as f:metadata=json.load(f)
            scope={};exec(obj.userData('contact_cleanup_code'),scope)
            visual,proxy,corrections=scope['clean_contacts'](visual,proxy,metadata,request['length_cm']*.01,request['width_cm']*.01,request['height_cm']*.01)
            # Publish only complete files. Cancellation or failure leaves the previous result connected.
            os.makedirs(folder,exist_ok=True)
            for geo,path in [(visual,visual_path),(proxy,proxy_path)]:
                temp=path+'.pending.bgeo.sc';geo.saveToFile(temp);os.replace(temp,path)
            manifest={'version':CACHE_VERSION,'parameters':request,'piece_count':len(visual.prims()),'settled_frame':last_frame,
                      'seconds':round(time.time()-elapsed,3),'contact_cleanup':corrections,
                      'preparation_seconds':preparation_seconds,'simulation_seconds':simulation_seconds,
                      'first_144_simulation_seconds':first_144_seconds,
                      'cleanup_seconds':time.time()-cleanup_start}
            temp_manifest=manifest_path+'.pending'
            with open(temp_manifest,'w') as f:json.dump(manifest,f,indent=2)
            os.replace(temp_manifest,manifest_path)
            report(.99,'Loading completed pile...')
            publish(manifest);published=True
            print('PILE_BUILD_COMPLETE',json.dumps(manifest),flush=True)
    except hou.OperationInterrupted:
        status(obj,'Cancelled. Previous pile kept. Click Rebuild to try again.')
        print('PILE_BUILD_CANCELLED',flush=True)
    except Exception as exc:
        status(obj,'Build failed; previous pile kept: '+str(exc))
        raise
    finally:
        if not published:
            for k,v in old_committed.items():committed.parm(k).set(v)
        # No per-frame simulation cache is needed to display the published static result.
        solver.parm('resetsim').pressButton()
        hou.setFrame(old_frame);hou.setUpdateMode(update_mode)
        obj.destroyUserData('pile_build_running')

rebuild(node)
