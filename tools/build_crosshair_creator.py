"""Add an interactable crosshair terminal beside armory presets, and the devices that hide Fortnite's own reticle while a
player's custom crosshair is on (class designers 8 / 9, two class selectors, a HUD Controller). Owns KT42_Crosshair_* only.

Run after compiling CrosshairSettings/Creator/Tests. Re-runnable, no deletion/rebuild.
--tests enables only the pure crosshair tests on the next game start.
"""
import argparse
import json
import build_map as bm

PREFIX = 'KT42_Crosshair_'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tests', action='store_true')
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    if m.tool(bm.SCENE, 'get_current_level') != bm.MODULE + '/KeystrokeTrainer':
        raise RuntimeError('Unexpected level')
    state = m.tool('ValkyrieToolset.SessionToolset', 'GetGameState')
    if state not in ('Unconnected', 'CanStart'):
        raise RuntimeError('Stop the match before placing the terminal')
    actors = m.tool(bm.SCENE, 'find_actors', name=PREFIX, collision_channels=[]) or []
    existing = {}
    for a in actors:
        if a['label'] in existing and existing[a['label']] != a['actorPath']:
            raise RuntimeError('Duplicate owned label: ' + a['label'])
        existing[a['label']] = a['actorPath']

    def device(asset, suffix, x, y, z, yaw=0):
        label = PREFIX + suffix
        new = label not in existing
        path = existing.get(label) or b.device(asset, label, x, y, z)
        m.tool(bm.ACTOR, 'set_actor_transform', actor={'refPath': path}, xform=bm.xform(x, y, z, yaw=yaw))
        return path, new

    # 350 cm north of PRESET 1, away from the mod bench. Below the portrait row.
    terminal, new = device(bm.BUTTON, 'Open', 3480, -63350, 210, 180)
    m.tool(bm.ACTOR, 'set_actor_transform', actor={'refPath': terminal},
           xform=bm.xform(3480, -63350, 210, sx=2.0, sy=2.0, sz=2.0, yaw=180))
    b.props(terminal, {'interaction Text': 'Create my crosshair', 'interactionRadius': 1.25,
                       'interactTime': 0.0, 'enabledAtGameStart': True,
                       'delay': 0.0, 'resetDelay': 0.25, 'visibleDuringGame': True})
    if new:
        b.tag(terminal, 'kt_crosshair_creator_tag')
    label, _ = device(bm.BILLBOARD, 'Label', 3515, -63350, 285, 270)
    b.props(label, {'text': 'CROSSHAIR\nINTERACT TO CUSTOMIZE', 'textSize': 24,
                   'showBorder': False, 'textColor': {'r': 0.2, 'g': 1.0, 'b': 0.8, 'a': 1},
                   'backgroundColor': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
    controller, _ = device(bm.MODULE + '/_Verse.KeystrokeTrainer-kt_crosshair_creator_device',
                           'Controller', 3200, -63350, -1500)
    m.tool(bm.DEVICE, 'SetDeviceProperty', device={'refPath': controller}, propertyName='RunSelfTests', value=json.dumps(args.tests))
    # Fortnite's own reticle off for players with a custom crosshair (player 2026-10-20): class 9 = custom crosshair on,
    # class 8 = stock reticle. Designers override nothing; the selectors sit 15 m under the floor (nobody walks in),
    # hidden and silent, and change nothing but the class; the HUD Controller hides the reticle for class 9 only.
    stock = []
    for slot, suffix in ((8, 'ClassStock'), (9, 'ClassCustom')):
        d, _ = device('/CreativeCoreDevices/SetupAssets/PID_Device_ClassDesigner.PID_Device_ClassDesigner', suffix,
                      3200 + slot * 60, -63500, -1500)
        b.props(d, {'classIdentifier': {'classType': 'ClassSlot', 'classSlot': slot}, 'bVisibleDuringGame': False,
                    'bGrantItemsOnRespawn': False})
        stock.append(d)
    for slot, suffix, tag in ((9, 'HideStock', 'kt_crosshair_stock_hidden_tag'), (8, 'ShowStock', 'kt_crosshair_stock_shown_tag')):
        sel, fresh = device('/CreativeCoreDevices/SetupAssets/PID_Device_ClassSelector.PID_Device_ClassSelector', suffix,
                            3200 + slot * 60, -63700, -1500)
        b.props(sel, {'classToSwitchTo': {'classType': 'ClassSlot', 'classSlot': slot}, 'visibleDuringGame': False,
                      'volumeVisibleInGame': False, 'zoneAudio': False, 'zoneActivationVFX': False,
                      'restoreHealthAndShieldsOnSwitch': False, 'clearItemsOnSwitch': False,
                      'bRespawnPlayerOnSwitch': False, 'timeToSwitch': 0.0})
        if fresh:
            b.tag(sel, tag)
        stock.append(sel)
    hud, _ = device('/CRD_HUDController/SetupAssets/PID_Device_HUDController_V2.PID_Device_HUDController_V2', 'HudReticle',
                    3200, -63900, -1500)
    b.props(hud, {'displayReticle': 'HideAlways', 'affectedClass': {'classType': 'ClassSlot', 'classSlot': 9},
                  'enabledDuringPhase': 'Always'})
    stock.append(hud)
    print(json.dumps({'hud': m.tool(bm.OBJ, 'get_properties', instance={'refPath': hud},
                                    properties=['displayReticle', 'affectedClass', 'showWeaponReticle_Internal'])}))
    for path in [terminal, label, controller] + stock:
        m.tool(bm.SCENE, 'save_actor', actor={'refPath': path})
    m.tool('editor_toolset.toolsets.asset.AssetTools', 'save_assets', asset_paths=[bm.MODULE + '/KeystrokeTrainer'])
    print(json.dumps({'terminal': terminal, 'controller': controller,
                      'settings': m.tool(bm.DEVICE, 'GetDeviceProperties', device={'refPath': controller}, propertyNames=['Enabled', 'RunSelfTests'])}, indent=2))


if __name__ == '__main__':
    main()
