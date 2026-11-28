from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util,json,pytest
s=importlib.util.spec_from_file_location('pilot_tests','/workspace/lineage-collection-plan/tests/test_twin_pilot.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
results={}
for mode in ['idle','flat_counter','active']:
 with TemporaryDirectory() as td,pytest.MonkeyPatch.context() as mp:
  kwargs,commands,clock,*_=m.trial.__wrapped__(Path(td),mp)
  def mutation(v,n):
   if mode=='idle':v.update(state='stopped',user_count=0,num_requests=100)
   elif mode=='flat_counter':v.update(state='running',user_count=5,num_requests=100)
  commands.locust_mutation=mutation
  report=m.pilot.run_pilot(**kwargs,invocation_id='d'*32)
  queries=[args for args,_ in commands.calls if 'exec' in args and 'load-generator' in args]
  results[mode]={'status':report['status'],'duration_seconds':report['run_window']['duration_seconds'],'all_containers_healthy':report['load']['all_healthy'],'traffic_holds':report['load']['traffic']['holds'],'queries':len(queries),'failure_categories':report['failure_categories'],'invocation_bound':report['run_id']=='d'*32}
assert results['idle']['status']==results['flat_counter']['status']=='blocked'
assert results['active']['status']=='passed'
assert all(r['duration_seconds']>=600 and r['queries']>0 for r in results.values())
print(json.dumps(results,sort_keys=True))
