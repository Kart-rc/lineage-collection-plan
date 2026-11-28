from pathlib import Path
from tempfile import TemporaryDirectory
import json,sys
from unittest.mock import patch
sys.path.insert(0,'/workspace/lineage-collection-plan')
from twin import pilot
with TemporaryDirectory() as td:
 root=Path(td);state=root/'.state';output=root/'results';state.mkdir();output.mkdir()
 old='a'*32
 (state/'pilot-attempt.json').write_text(json.dumps({'schema_version':1,'project':'lineage-twin','fresh_project_acquired':True,'run_id':old}))
 (output/'pilot.json').write_text(json.dumps({'run_id':old,'ownership':{'acquired':True}}))
 commands=[]
 def run(*a,**kw):commands.append(a);raise AssertionError('must not run')
 def readonly(*a,**kw):raise PermissionError('simulated report filesystem failure')
 with patch.object(pilot,'TWIN',root),patch.object(pilot,'write_json',readonly):
  result=pilot.run_pilot(root/'demo',state,output,run=run,stats=lambda *a,**kw:{'raw_files':{},'failure_categories':[]})
 marker=json.loads((state/'pilot-attempt.json').read_text());report=json.loads((output/'pilot.json').read_text())
 acquired=(marker.get('schema_version')==1 and marker.get('project')=='lineage-twin' and marker.get('fresh_project_acquired') is True and report.get('ownership',{}).get('acquired') is True and marker.get('run_id')==report.get('run_id'))
 print(json.dumps({'new_attempt_owned':result['ownership']['acquired'],'new_attempt_status':result['status'],'commands_before_failure':len(commands),'new_attempt_run_id_differs':result['run_id']!=old,'workflow_cleanup_would_accept_stale_pair':acquired}))
