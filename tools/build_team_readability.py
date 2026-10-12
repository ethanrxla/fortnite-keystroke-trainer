"""Additive competitive-court accents; dry-run unless --apply.

Owns only KT28_CourtRead_. No new cover, deletion, mode activation or restart.
Optional --repair-volume lowers the existing arena volume only after checking
its exact footprint/height and backing up its transform. Never rebuild KT24.
"""
import argparse
import datetime
import json

import build_map as bm

PREFIX = 'KT28_CourtRead_'
OX, OY, CELL = 71680, -59904, 512


def slab(name, u0, u1, v0, v1, bottom, top, material):
    return dict(label=PREFIX + name,
                bounds=(OX + u0*CELL, OX + u1*CELL,
                        OY + v0*CELL, OY + v1*CELL),
                top=top, thick=top-bottom, mat=material)


def plan():
    """Short fascia bands and objective corners, not new firing angles.

    West warm / east blue distinguish compounds. Lane accents are independent
    of team identity. All geometry fits existing cover heights; disable its
    actor collision so a visual trim can never become a new head-glitch.
    """
    out = []
    for side, u0, u1, material in (('West', 0, 6, 'Edit'), ('East', 10, 16, 'Build')):
        for level in (384, 768):
            for edge, v0, v1 in (('Service', 4.98, 5), ('Loading', 11, 11.02)):
                out.append(slab(f'{side}{edge}{level}', u0, u1, v0, v1,
                                level-18, level-2, material))
        # Exterior crown of each tower, below its existing parapet top.
        tu0, tu1 = (0, 1) if side == 'West' else (15, 16)
        out.append(slab(f'{side}TowerCrown', tu0+.05, tu1-.05, 2.025, 2.04,
                        1190, 1220, material))
    # Distinct perimeter accents: service = amber; loading = teal. They stay
    # below the 384 cm wall silhouette and do not span any player doorway.
    for lane, v0, v1, mat in (('Service', .005, .025, 'Arena'),
                             ('Loading', 15.975, 15.995, 'Aim')):
        for i, (u0, u1) in enumerate(((2, 5), (6, 10), (11, 14))):
            out.append(slab(f'{lane}Band{i}', u0, u1, v0, v1, 290, 314, mat))
    # Four L-shaped ground marks leave centre unobstructed, aligned to the
    # native 2x2 objective footprint. Top is just 2 cm; collision remains off.
    for i, (u, v, dx, dy) in enumerate(((7, 7, 1, 1), (9, 7, -1, 1),
                                       (7, 9, 1, -1), (9, 9, -1, -1))):
        x0, x1 = sorted((u, u+dx*.4)); y0, y1 = sorted((v, v+dy*.4))
        sy0, sy1 = sorted((v, v+dy*.025)); sx0, sx1 = sorted((u, u+dx*.025))
        out.append(slab(f'Objective{i}X', x0, x1, sy0, sy1, 1, 2, 'Arena'))
        out.append(slab(f'Objective{i}Y', sx0, sx1, y0, y1, 1, 2, 'Arena'))
    return out


def bounds_tuple(actor):
    b = actor['bounds']; lo, hi = b['min'], b['max']
    return lo['x'], hi['x'], lo['y'], hi['y'], lo['z'], hi['z']


def expected(s):
    return (*s['bounds'], s['top']-s['thick'], s['top'])


def near(a, b, tolerance=2):
    return len(a) == len(b) and all(abs(x-y) <= tolerance for x, y in zip(a, b))


def validate_plan():
    specs = plan()
    assert len({s['label'] for s in specs}) == len(specs)
    for s in specs:
        x0, x1, y0, y1, z0, z1 = expected(s)
        assert OX <= x0 < x1 <= OX + 16*CELL
        assert OY <= y0 < y1 <= OY + 16*CELL
        assert 0 <= z0 < z1 <= 1262
        assert z1-z0 <= 30


def volume_delta(actor):
    x0, x1, y0, y1, z0, z1 = bounds_tuple(actor)
    if not near((x0, x1, y0, y1, z1-z0),
                (OX, OX+16*CELL, OY, OY+16*CELL, 4608)):
        raise RuntimeError('Arena volume footprint/height changed; inspect before repair')
    if abs(z0) <= 2:
        return 0
    if abs(z0-2112) > 2:
        raise RuntimeError('Unrecognized arena volume offset; no automatic move')
    return -z0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--repair-volume', action='store_true')
    args = parser.parse_args()
    validate_plan()
    b = bm.Builder(); m = b.m
    if m.tool(bm.SCENE, 'get_current_level') != bm.MODULE + '/KeystrokeTrainer':
        raise RuntimeError('Wrong open level')
    actors = m.tool(bm.SCENE, 'find_actors', name='', collision_channels=[])
    by_label = {}
    for a in actors:
        by_label.setdefault(a['label'], []).append(a)
    for label in [s['label'] for s in plan()] + ['KT21_Team_Floor', 'KT24_Team_Arena']:
        if len(by_label.get(label, [])) > 1:
            raise RuntimeError('Duplicate label: ' + label)
    floor = by_label.get('KT21_Team_Floor', [])
    if not floor or not near(bounds_tuple(floor[0]), (OX, OX+8192, OY, OY+8192, -100, 0)):
        raise RuntimeError('Arena anchor/size drifted')
    for s in plan():
        old = by_label.get(s['label'])
        if old and not near(bounds_tuple(old[0]), expected(s)):
            raise RuntimeError('Existing accent drifted: ' + s['label'])
    volume = by_label.get('KT24_Team_Arena', [])
    delta = volume_delta(volume[0]) if args.repair_volume and volume else 0
    if args.repair_volume and not volume:
        raise RuntimeError('Missing arena volume')
    print(json.dumps({'new_accents': sum(s['label'] not in by_label for s in plan()),
                      'total_accents': len(plan()), 'volume_delta_z': delta,
                      'apply': args.apply}))
    if not args.apply:
        return
    if m.tool('ValkyrieToolset.SessionToolset', 'GetGameState') not in ('CanStart', 'Unconnected'):
        raise RuntimeError('Stop the session with player approval before applying')
    backup = bm.ROOT / 'backups' / ('court-readability-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
    backup.parent.mkdir(exist_ok=True)
    original = m.tool(bm.ACTOR, 'get_actor_transform', actor={'refPath': volume[0]['actorPath']}) if volume else None
    backup.write_text(json.dumps({'actors': actors, 'arena_volume_transform': original}, indent=2))
    for s in plan():
        old = by_label.get(s['label'])
        path = old[0]['actorPath'] if old else b.slab(s)
        components = m.tool(bm.ACTOR, 'get_components', actor={'refPath': path})
        mesh = next(c for c in components if 'StaticMeshComponent' in c['refPath'])
        m.tool(bm.OBJ, 'list_properties', instance=mesh)
        props = m.tool(bm.OBJ, 'get_properties', instance=mesh, properties=['bodyInstance'])
        props = json.loads(props) if isinstance(props, str) else props
        body = dict(props['bodyInstance'])
        body.update(collisionEnabled='NoCollision', collisionProfileName='NoCollision')
        b.props(mesh['refPath'], {'bUseDefaultCollision': False, 'bodyInstance': body})
        check = m.tool(bm.OBJ, 'get_properties', instance=mesh, properties=['bodyInstance', 'bUseDefaultCollision'])
        check = json.loads(check) if isinstance(check, str) else check
        if check['bodyInstance']['collisionEnabled'] != 'NoCollision' or check['bUseDefaultCollision']:
            raise RuntimeError('Could not disable accent collision: ' + s['label'])
        if not near(bounds_tuple({'bounds': m.tool(bm.ACTOR, 'get_actor_bounds', actor={'refPath': path})}), expected(s)):
            raise RuntimeError('Accent bounds did not match: ' + s['label'])
        m.tool(bm.SCENE, 'save_actor', actor={'refPath': path})
    if delta:
        path = volume[0]['actorPath']
        location = dict(original['location']); location['z'] += delta
        m.tool(bm.ACTOR, 'set_actor_transform', actor={'refPath': path}, xform={'location': location})
        bounds = m.tool(bm.ACTOR, 'get_actor_bounds', actor={'refPath': path})
        if not near(bounds_tuple({'bounds': bounds}), (OX, OX+8192, OY, OY+8192, 0, 4608)):
            m.tool(bm.ACTOR, 'set_actor_transform', actor={'refPath': path}, xform=original)
            raise RuntimeError('Volume verification failed; original transform restored')
        m.tool(bm.SCENE, 'save_actor', actor={'refPath': path})
    print('Saved additive accents. No content push, runtime activation or balance claim.')


if __name__ == '__main__':
    main()
