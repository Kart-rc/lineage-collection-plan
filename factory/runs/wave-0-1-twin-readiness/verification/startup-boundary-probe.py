import importlib.util,contextlib,io,json,tempfile
from pathlib import Path
import pytest
repo=Path('/workspace/lineage-collection-plan')
s=importlib.util.spec_from_file_location('readiness_tests',repo/'tests/test_twin_startup.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
results={}
for case in ('over_900','missing_expected_service'):
 with tempfile.TemporaryDirectory() as td,pytest.MonkeyPatch.context() as mp:
  state,expected,calls,rows=m.configured.__wrapped__(mp,Path(td))
  if case=='over_900':
   now=[0.0];mp.setattr(m.start.time,'monotonic',lambda:now[0])
   def status(*args,**kw):now[0]=901.;return rows
   mp.setattr(m.start,'status',status)
   kw={'timeout':1800}
  else:
   m.start.prepare(None,None)['services'].pop('accounting')
   rows[:]=[r for r in rows if r['service']!='accounting'];kw={}
  with contextlib.redirect_stdout(io.StringIO()):code=m.start.startup(Path('demo'),state,**kw)
  report=m.report(state)
  results[case]={'code':code,'status':report['status'],'elapsedSeconds':report['elapsedSeconds'],'expectedServices':report['expectedServices'],'allContainersHealthy':report['allContainersHealthy']}
print(json.dumps(results,sort_keys=True))
