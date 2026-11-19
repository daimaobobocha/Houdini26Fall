from pathlib import Path
import zipfile,json
ICA=Path(__file__).resolve().parents[1]
ROOT=ICA.parent
DEST=ICA/'submission'
DEST.mkdir(exist_ok=True)
def archive(path,files,base):
    count=0
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for f in sorted(files):
            if f.is_file():
                z.write(f,f.relative_to(base).as_posix());count+=1
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
    return {'file':str(path),'files':count,'bytes':path.stat().st_size}
hipfiles=[]
for f in ICA.rglob('*'):
    rel=f.relative_to(ICA)
    if rel.parts[0] in ('tools','submission','backup','desk') or '__pycache__' in rel.parts:continue
    if f.is_file():hipfiles.append(f)
hipfiles.append(ICA/'backup/ICA10_before_stair_continuation.hipnc')
ue=ROOT/'HoudiniTesting'
uefiles=[ue/'HoudiniTesting.uproject']
for folder in ('Config','Content','Plugins'):
    for f in (ue/folder).rglob('*'):
        rel=f.relative_to(ue)
        if any(p in ('Intermediate','DerivedDataCache','__pycache__') for p in rel.parts):continue
        if f.suffix.lower() in ('.pdb','.obj','.exp','.lib'):continue
        if f.is_file():uefiles.append(f)
report=[archive(DEST/'ICA10_Houdini.zip',hipfiles,ROOT),archive(DEST/'HoudiniTesting_Unreal.zip',uefiles,ROOT)]
with open(DEST/'packages.json','w') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
