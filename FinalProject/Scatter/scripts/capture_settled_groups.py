"""Extract independently supported groups from existing checked Bullet caches."""
import json
from pathlib import Path
import runpy
import sys
import tempfile
import numpy as np


def ground_support(vertices, center):
    contacts = np.unique(np.round(vertices[vertices[:,1] < .0035][:,[0,2]], 7), axis=0)
    if len(contacts) < 3:
        return False
    # The projected center must be inside the convex polygon of floor contacts.
    vectors = contacts - center[[0,2]]
    angles = np.sort(np.arctan2(vectors[:,1], vectors[:,0]))
    return np.max(np.diff(np.r_[angles, angles[0]+2*np.pi])) < np.pi - .02


def capture_groups(root, keys):
    templates = []
    for key in keys:
        folder = root/'sim/pile_cache'/key
        with tempfile.TemporaryDirectory() as temp:
            args = sys.argv
            try:
                sys.argv = ['validate', str(folder/'visual.bgeo.sc'), str(folder/'proxy.bgeo.sc'), str(Path(temp)/'report.json')]
                state = runpy.run_path(str(root/'scripts/validate_gravity_pile.py'))
            finally:
                sys.argv = args
        report = state['report']
        if report['penetrations_over_0_02mm'] or report['without_support_contact_chain']:
            continue
        pieces, stable, neighbors = {}, set(), {}
        for prim,b in zip(state['visual'].prims(),state['bodies']):
            name = prim.stringAttribValue('name')
            assert name == b['name']
            asset = b['asset']
            m = np.asarray(prim.fullTransform().asTuple()).reshape(4,4)
            render = np.asarray(state['source'][asset]['vertices']) @ m[:3,:3] + m[3,:3]
            vertices = np.concatenate([render]+[h['vertices'] for h in b['parts']])
            if ground_support(render, render.mean(axis=0)):
                stable.add(name)
            if 'OilBarrel' in asset:
                stable.add(name)
            xz = vertices[:,[0,2]]
            _,axes = np.linalg.eigh(np.cov(xz.T))
            plane = xz @ axes
            low, high = plane.min(axis=0), plane.max(axis=0)
            center = ((low+high)*.5) @ axes.T
            # Extremes on the original X/Z axes retain a tight bound at quarter turns.
            pieces[name] = {'asset':asset, 'r':m[:3,:3].tolist(), 'p':m[3,:3].tolist(),
                'xz_min':xz.min(axis=0).tolist(), 'xz_max':xz.max(axis=0).tolist(),
                'center':center.tolist(), 'axes':axes.T.tolist(), 'half':((high-low)*.5+.00005).tolist(),
                'y':[float(vertices[:,1].min()),float(vertices[:,1].max())]}
            neighbors[name] = set()
        for a,b in state['contact_edges']:
            neighbors[a].add(b)
            neighbors[b].add(a)
        def closure(seed, stop_at_ground):
            found, pending = set(), [seed]
            while pending:
                name = pending.pop()
                if name in found:
                    continue
                found.add(name)
                if not stop_at_ground or name not in stable:
                    pending.extend(neighbors[name]-found)
            return tuple(sorted(found))
        groups = {closure(name, limit) for name in pieces for limit in (True,False)}
        if len(pieces) <= 55:
            groups.add(tuple(sorted(pieces)))
        for group in sorted(groups):
            templates.append([pieces[name] for name in group])
        print('CAPTURE',key,'group sizes', sorted(len(g) for g in groups), flush=True)
    return templates
