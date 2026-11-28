from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util,json,pytest
s=importlib.util.spec_from_file_location('pilot_tests','/workspace/lineage-collection-plan/tests/test_twin_pilot.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
with TemporaryDirectory() as td,pytest.MonkeyPatch.context() as mp:
 kwargs,commands,clock,*_=m.trial.__wrapped__(Path(td),mp)
 report=m.pilot.run_pilot(**kwargs)
 locust=[args for args,_ in commands.calls if 'exec' in args and 'load-generator' in args]
 print(json.dumps({'pilot_status':report['status'],'measured_wait_seconds':report['run_window']['duration_seconds'],'load_activity_queries':len(locust),'load_stats_measured':bool(report['load'].get('activity'))}))
