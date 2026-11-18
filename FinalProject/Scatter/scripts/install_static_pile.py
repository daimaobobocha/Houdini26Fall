"""Install the analytic contact builder and store measured rest poses in the scene."""
import json
from pathlib import Path
import sys
import time

import hou
import numpy as np


root = Path(__file__).resolve().parents[1]
hou.hipFile.load(str(root / 'Scatter_Pile.hipnc'), suppress_save_prompt=True, ignore_load_warnings=True)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
obj = hou.node('/obj/SCATTER_PILE')
sys.path.insert(0, str(root/'scripts'))
from capture_settled_groups import capture_groups
groups = capture_groups(root, ['ce76fcf1ec63068eac14', '89095a37a3b5595fcf94', '30c45804af4fb7df1114',
                               '33118a4155196aae9136', '816f76fcab6ebc4fd319', 'c61e27866bba4dbd50eb'])
obj.setUserData('settled_groups', json.dumps(groups, separators=(',', ':')))
stash = obj.node('STATIC_CONTACT_POINTS') or obj.createNode('stash', 'STATIC_CONTACT_POINTS')
stash.setPosition(obj.node('INITIAL_SAFE_LAYOUT').position() + hou.Vector2((3, 0)))
for copy in ['INSTANCE_ASSETS', 'COPY_BULLET_COMPOUNDS']:
    obj.node(copy).setInput(1, stash)
sources = ['static_contact_pile.py', 'fast_rebuild_pile.py']
code = '\n'.join((root / 'scripts' / source).read_text(encoding='utf-8') for source in sources)
obj.setUserData('manual_build_code', code)
params = obj.parmTemplateGroup()
button = params.find('rebuild_pile')
button.setHelp('Arrange previously settled groups inside the bounds. Completed settings are cached. Esc cancels.')
params.replace('rebuild_pile', button)
obj.setParmTemplateGroup(params)
obj.setComment('Edit the bounds and density, then click Rebuild Pile for a static contact placement.')
for note in obj.stickyNotes():
    note.setText('STATIC PILE\nSelect SCATTER_PILE and adjust the bounds and density.\nClick Rebuild Pile to place the parts.\nEsc cancels. Previous settings reuse the disk cache.\n\nSTATIC_CONTACT_POINTS supplies both the visual and collision instances.\nGroups retain their simulated contact poses.\nNew placements check the space between groups.')
solver = obj.node('GRAVITY_SETTLE')
before = solver.cookCount()
start = time.perf_counter()
obj.parm('rebuild_pile').pressButton()
assert obj.evalParm('build_status').startswith('Ready:'), obj.evalParm('build_status')
assert solver.cookCount() == before
print('BUTTON', obj.evalParm('build_status'), 'seconds', time.perf_counter()-start, 'cache', obj.userData('pile_active_cache'), flush=True)
obj.setSelected(True, clear_all_selected=True)
hou.hipFile.save(str(root / 'Scatter_Pile_Static_Test.hipnc'))

