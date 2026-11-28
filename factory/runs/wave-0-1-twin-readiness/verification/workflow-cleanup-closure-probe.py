from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import contextlib,io,json,os,subprocess,yaml
root=Path('/workspace/lineage-collection-plan')
w=yaml.safe_load((root/'.github/workflows/full-reference-pilot.yml').read_text())
step=next(s for s in w['jobs']['pilot']['steps'] if s.get('name')=='Remove only infrastructure acquired by this pilot')
code=step['run'].split("python - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]
results={}
for case in ['old_pair','current_pair','missing_token','unowned_report']:
 with TemporaryDirectory() as td:
  r=Path(td);s=r/'twin/.state';s.mkdir(parents=True);o=r/'pilot-results';o.mkdir()
  marker_id='a'*32;current_id='b'*32 if case=='old_pair' else marker_id
  (s/'pilot-attempt.json').write_text(json.dumps({'schema_version':1,'project':'lineage-twin','fresh_project_acquired':True,'run_id':marker_id}))
  (s/'compose.yaml').write_text('services: {}\n')
  (o/'pilot.json').write_text(json.dumps({'run_id':marker_id,'ownership':{'acquired':case!='unowned_report'}}))
  calls=[]
  def run(args,**kwargs):calls.append(args);return subprocess.CompletedProcess(args,0)
  old=os.getcwd()
  try:
   os.chdir(r)
   with patch.dict(os.environ,{'LINEAGE_PILOT_INVOCATION':current_id}),patch('subprocess.run',run),contextlib.redirect_stdout(io.StringIO()):
    if case=='missing_token':os.environ.pop('LINEAGE_PILOT_INVOCATION',None)
    exec(compile(code,'cleanup-workflow','exec'),{})
  finally:os.chdir(old)
  results[case]={'cleanup_calls':len(calls),'commands':calls}
assert results['current_pair']['cleanup_calls']==1
assert all(results[c]['cleanup_calls']==0 for c in ['old_pair','missing_token','unowned_report'])
print(json.dumps(results,sort_keys=True))
