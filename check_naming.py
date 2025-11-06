import bpy

if hasattr(bpy.utils, 'expose_bundled_modules'):
    bpy.utils.expose_bundled_modules()
from pathlib import Path

from pxr import Usd, UsdSkel

# Find the tree USD
tree_files = sorted(Path('data/output/test_naming').glob('**/*_tree_*.usda'))
tree_file = [f for f in tree_files if 'assembly' not in f.name][0]
print(f'Checking: {tree_file.name}\n')

stage = Usd.Stage.Open(str(tree_file))
default_prim = stage.GetDefaultPrim()
print(f'Default prim: {default_prim.GetPath()}')
skel_path = default_prim.GetPath().AppendChild('TreeSkel')
print(f'Skeleton path: {skel_path}')
skel = UsdSkel.Skeleton.Get(stage, skel_path)

if not skel:
    print('ERROR: Could not find skeleton')
    exit(1)

joints = skel.GetJointsAttr().Get()
print(f'Total joints: {len(joints)}')
print(f'\nFirst 10 joints:')
for i, joint in enumerate(joints[:10]):
    print(f'  {i}: {joint}')

# Check for tree_root
if joints[0] == 'tree_root':
    print('\n✓ First joint is tree_root (correct!)')
else:
    print(f'\n✗ First joint is {joints[0]} (expected tree_root)')

# Check for branch joints
branch_joints = [j for j in joints if 'branch_' in str(j)]
print(f'\n✓ Found {len(branch_joints)} branch_X joints')
if branch_joints:
    print(f'Sample branch joints:')
    for bj in branch_joints[:5]:
        print(f'  {bj}')

# Check twig skeleton
print('\n--- Checking Twig Skeleton ---')
twig_files = sorted(Path('data/output/test_naming').glob('**/*_twig_*.usda'))
if twig_files:
    twig_file = twig_files[0]
    print(f'Twig: {twig_file.name}')
    
    twig_stage = Usd.Stage.Open(str(twig_file))
    twig_skel = UsdSkel.Skeleton.Get(twig_stage, twig_stage.GetDefaultPrim().GetPath().AppendChild('TwigSkel'))
    
    twig_joints = twig_skel.GetJointsAttr().Get()
    print(f'Twig joints: {twig_joints}')
    
    if twig_joints[0] == 'twig_root':
        print('✓ First twig joint is twig_root (correct!)')
    else:
        print(f'✗ First twig joint is {twig_joints[0]} (expected twig_root)')

# Check assembly bindJoints
print('\n--- Checking Assembly bindJoints ---')
assembly_files = sorted(Path('data/output/test_naming').glob('**/*_assembly.usda'))
if assembly_files:
    assembly_file = assembly_files[0]
    print(f'Assembly: {assembly_file.name}')
    
    asm_stage = Usd.Stage.Open(str(assembly_file))
    instancer = asm_stage.GetPrimAtPath(asm_stage.GetDefaultPrim().GetPath().AppendChild('TwigInstances'))
    
    bind_joints_attr = instancer.GetAttribute('primvars:unreal:naniteAssembly:bindJoints')
    if bind_joints_attr:
        bind_joints = bind_joints_attr.Get()
        print(f'bindJoints count: {len(bind_joints)}')
        print(f'Sample bindJoints (first 5):')
        for bj in list(bind_joints)[:5]:
            print(f'  {bj}')
    else:
        print('✗ NO bindJoints attribute found')
    else:
        print('✗ NO bindJoints attribute found')
