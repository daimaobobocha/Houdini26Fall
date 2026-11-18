"""Button callback, embedded together with static_contact_pile in the HIP."""
import contextlib
import hashlib
import json
import os
import tempfile
import time
import hou


def rebuild_static(obj):
    if obj.userData('pile_build_running'):
        return
    settings = {name: obj.evalParm(name) for name in ('length_cm', 'width_cm', 'height_cm', 'density')}
    root = hou.expandString('$HIP')
    rest_data = obj.userData('settled_groups')
    digest = hashlib.sha256((obj.userData('manual_build_code') + rest_data).encode())
    digest.update(json.dumps(settings, sort_keys=True).encode())
    for file_name in ('scatter_assets.bgeo.sc', 'scatter_bullet_compounds_optimized.bgeo.sc',
                      'bullet_hull_metadata_optimized.json'):
        stat = os.stat(os.path.join(root, 'geo', file_name))
        digest.update(str((file_name, stat.st_size, stat.st_mtime_ns)).encode())
    key = digest.hexdigest()[:20]
    relative = 'sim/pile_cache/' + key
    directory = os.path.join(root, relative)
    mode = hou.updateModeSetting()
    obj.setUserData('pile_build_running', '1')
    status = obj.parm('build_status')
    start = time.perf_counter()
    stash = obj.node('STATIC_CONTACT_POINTS')
    try:
        manifest_path = os.path.join(directory, 'manifest.json')
        if all(os.path.isfile(os.path.join(directory, name)) for name in
               ('manifest.json', 'visual.bgeo.sc', 'proxy.bgeo.sc')):
            with open(manifest_path) as file:
                result = json.load(file)
        else:
            operation = (hou.InterruptableOperation('Placing scrap pile', open_interrupt_dialog=True)
                         if hou.isUIAvailable() else contextlib.nullcontext(None))
            with operation as progress:
                def report(fraction):
                    if progress:
                        progress.updateProgress(.92 * fraction)
                hou.setUpdateMode(hou.updateMode.AutoUpdate)
                status.set('Arranging settled groups...')


                placements = settle_static(json.loads(rest_data), settings, report)
                points = hou.Geometry()
                name = points.addAttrib(hou.attribType.Point, 'name', '')
                orient = points.addAttrib(hou.attribType.Point, 'orient', (0., 0., 0., 1.))
                identifier = points.addAttrib(hou.attribType.Point, 'id', 0)
                for index, (asset, rotation, position) in enumerate(placements):
                    pt = points.createPoint()
                    pt.setPosition(position.tolist())
                    pt.setAttribValue(name, asset)
                    pt.setAttribValue(identifier, index)
                    pt.setAttribValue(orient, tuple(hou.Quaternion(hou.Matrix3(rotation.ravel().tolist()))))
                stash.parm('stash').set(points)
                os.makedirs(directory, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=directory) as stage:
                    for filename, source in [('visual.bgeo.sc', 'RBD_VISUAL_INITIAL'),
                                             ('proxy.bgeo.sc', 'RBD_PROXY_INITIAL')]:
                        sop = obj.node(source)
                        geometry = sop.geometry()
                        if geometry is None or sop.errors() or len(geometry.prims()) != len(placements):
                            raise RuntimeError('Could not assemble ' + source)
                        geometry.saveToFile(os.path.join(stage, filename))
                    result = {'method': 'settled_groups', 'parameters': settings, 'piece_count': len(placements),
                              'seconds': round(time.perf_counter() - start, 4)}
                    with open(os.path.join(stage, 'manifest.json'), 'w') as file:
                        json.dump(result, file, indent=2)
                    if progress:
                        progress.updateProgress(.99)
                    for filename in ('visual.bgeo.sc', 'proxy.bgeo.sc', 'manifest.json'):
                        os.replace(os.path.join(stage, filename), os.path.join(directory, filename))
        for source, filename in [('SETTLED_DEFAULT_CACHE', 'visual.bgeo.sc'), ('SETTLED_PROXY_CACHE', 'proxy.bgeo.sc')]:
            file_sop = obj.node(source)
            file_sop.parm('file').set('$HIP/' + relative + '/' + filename)
            file_sop.parm('reload').pressButton()
        for name, value in settings.items():
            obj.node('BUILD_SETTINGS').parm(name).set(value)
        obj.setUserData('pile_active_cache', key)
        obj.setUserData('pile_built_settings', json.dumps(settings, sort_keys=True))
        status.set('Ready: %d parts | %.2f s' % (result['piece_count'], time.perf_counter() - start))
    except hou.OperationInterrupted:
        status.set('Cancelled. Previous pile kept.')
    except Exception as error:
        status.set('Build failed. Previous pile kept: ' + str(error))
        raise
    finally:
        hou.setUpdateMode(mode)
        obj.destroyUserData('pile_build_running')


rebuild_static(node)

