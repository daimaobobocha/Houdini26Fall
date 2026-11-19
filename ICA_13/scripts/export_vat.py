import hou,os,traceback,json
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/ICA_13.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
result={}
for name in ['VAT_GHOST','VAT_RBD']:
    vat=hou.node('/obj/VAT_EXPORTS/'+name)
    print('EXPORT_START',name,flush=True)
    try:
        vat.parm('renderall').pressButton()
        result[name]={'errors':list(vat.errors()),'warnings':list(vat.warnings())}
        print('EXPORT_FINISHED',name,result[name],flush=True)
    except Exception as e:
        result[name]={'exception':str(e)}
        traceback.print_exc()
with open(ROOT+'/vat_validation.json','w') as f:json.dump(result,f,indent=2)
hou.setFrame(48)
hou.hipFile.save()
