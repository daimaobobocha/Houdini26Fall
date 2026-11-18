"""Scatter rigid groups from settled simulations; vertical poses and contacts are preserved."""
import math
import numpy as np


class SettledGroup:
    def __init__(self, pieces):
        self.pieces = pieces
        self.assets = {piece['asset'] for piece in pieces}
        self.barrel = any('OilBarrel' in name for name in self.assets)
        self.centers = np.array([piece['center'] for piece in pieces])
        self.origin = self.centers.mean(axis=0)
        self.centers -= self.origin
        self.axes = np.array([piece['axes'] for piece in pieces])
        self.half = np.array([piece['half'] for piece in pieces])
        self.vertical = np.array([piece['y'] for piece in pieces])
        self.height = self.vertical[:, 1].max()
        self.uses = 0
        lo = np.min([p['xz_min'] for p in pieces], axis=0) - self.origin
        hi = np.max([p['xz_max'] for p in pieces], axis=0) - self.origin
        self.corners = np.array([[lo[0],lo[1]], [lo[0],hi[1]], [hi[0],lo[1]], [hi[0],hi[1]]])

    def orient(self, angle):
        c, s = math.cos(angle), math.sin(angle)
        yaw = np.array([[c, -s], [s, c]])
        centers = self.centers @ yaw
        axes = self.axes @ yaw
        extent = (abs(axes) * self.half[:, :, None]).sum(axis=1)
        return yaw, axes, centers, extent


def settle_static(groups_data, settings, progress):
    length, width, height = [settings[k] * .01 for k in ('length_cm', 'width_cm', 'height_cm')]
    density = settings['density']
    target = min(600, max(1, round(length * width * density * .32))) if density else 0
    if not target:
        return []
    groups = [g for g in map(SettledGroup, groups_data) if g.height <= height + .00001]
    limits = np.array([length, width]) * .5
    rng = np.random.default_rng(73419)
    results, used_assets = [], set()
    previous_centers = np.empty((target, 2))
    previous_axes = np.empty((target, 2, 2))
    previous_half = np.empty((target, 2))
    previous_extent = np.empty((target, 2))
    previous_y = np.empty((target, 2))
    def intersects(group, axes, centers, extent):
        count = len(results)
        for k, center in enumerate(centers):
            delta = previous_centers[:count] - center
            adjacent = (np.all(abs(delta) < previous_extent[:count]+extent[k]+.0003, axis=1)
                        & (group.vertical[k,0] < previous_y[:count,1]+.0003)
                        & (group.vertical[k,1] > previous_y[:count,0]-.0003))
            if not adjacent.any():
                continue
            # Check four horizontal separating axes. Each rectangular prism
            # encloses both the visible mesh and the original compound collider.
            other_axes = previous_axes[:count][adjacent]
            other_half = previous_half[:count][adjacent]
            delta = delta[adjacent]
            basis = np.abs(axes[k] @ other_axes.transpose(0,2,1))
            in_a = np.abs(delta @ axes[k].T) < group.half[k] + (basis @ other_half[:,:,None])[:,:,0] + .0003
            in_b = np.abs((other_axes @ delta[:,:,None])[:,:,0]) < other_half + basis.transpose(0,2,1) @ group.half[k] + .0003
            if (in_a.all(axis=1) & in_b.all(axis=1)).any():
                return True
        return False

    def place(group, preferred_center=False):
        for angle in (rng.uniform(-math.pi, math.pi), rng.uniform(-math.pi, math.pi), 0., math.pi/2):
            yaw, axes, local, extent = group.orient(angle)
            lower = -limits - (local-extent).min(axis=0) + .0001
            upper = limits - (local+extent).max(axis=0) - .0001
            if angle in (0., math.pi/2):
                corners = group.corners @ yaw
                lower = -limits - corners.min(axis=0) + .00003
                upper = limits - corners.max(axis=0) - .00003
            if np.any(lower > upper):
                continue
            for attempt in range(10):
                if preferred_center and attempt == 0:
                    pos = np.clip(-limits*.54, lower, upper)
                elif attempt < 5:
                    pos = np.clip(rng.normal(0,limits*.34), lower, upper)
                else:
                    pos = rng.uniform(lower,upper)
                centers = local + pos
                if intersects(group, axes, centers, extent):
                    continue
                start = len(results)
                slots = slice(start, start+len(group.pieces))
                previous_centers[slots] = centers
                previous_axes[slots] = axes
                previous_half[slots] = group.half
                previous_extent[slots] = extent
                previous_y[slots] = group.vertical
                transform = np.eye(3)
                transform[np.ix_([0,2],[0,2])] = yaw
                for piece in group.pieces:
                    translation = np.array(piece['p'])
                    translation[[0,2]] = (translation[[0,2]] - group.origin) @ yaw + pos
                    results.append((piece['asset'], np.asarray(piece['r']) @ transform, translation))
                used_assets.update(group.assets)
                group.uses += 1
                return True
        return False

    barrels = sorted((g for g in groups if g.barrel and len(g.pieces) <= target), key=lambda g:len(g.pieces))
    if density >= 45:
        barrels.reverse()
    for group in barrels:
        if place(group, preferred_center=True):
            break
    misses = 0
    while len(results) < target and misses < 48:
        progress(len(results)/target)
        available = [g for g in groups if not g.barrel and len(g.pieces) <= target-len(results)]
        if not available:
            break
        # Favor new asset types early and real multi-piece stacks throughout.
        weights = [min(len(g.pieces), 9)**1.7 * (1+2*len(g.assets-used_assets)) / (1+g.uses)**3 for g in available]
        group = available[rng.choice(len(available), p=np.array(weights)/sum(weights))]
        if place(group):
            misses = 0
        else:
            misses += 1
    return results
