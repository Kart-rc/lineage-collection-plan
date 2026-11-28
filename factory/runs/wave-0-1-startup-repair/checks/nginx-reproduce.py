import json, re, subprocess, time
from pathlib import Path
import yaml

root=Path('/workspace/lineage-collection-plan')
config=yaml.safe_load((root/'twin/.state/readiness-render-candidate6/compose.yaml').read_text())
packet=root/'factory/runs/wave-0-1-startup-repair/checks'
results=[]
def command(args, timeout=15):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout)

for service in ('image-provider','telemetry-docs'):
    spec=config['services'][service]
    name='lineage-nginx-diagnostic-'+service
    assert command(['docker','inspect',name]).returncode != 0, 'diagnostic name already exists'
    row={'service':service,'image':spec['image'],'network':'none','template':'generated IPv4-only sandbox template','http_proxies_disabled':True,'probes':[]}
    path=root/'twin/.state/readiness-render-candidate6/sandbox'/f'{service}.nginx.conf.template'
    args=['docker','run','--detach','--name',name,'--label','lineage.diagnostic=nginx-readiness',
          '--network','none','--add-host','otel-collector:127.0.0.1','--no-healthcheck','--log-driver','none',
          '--memory',spec['deploy']['resources']['limits']['memory'], '--pids-limit','128',
          '--security-opt','no-new-privileges:true','--cap-drop','ALL',
          '--mount',f'type=bind,src={path},dst=/nginx.conf.template,readonly']
    for key,value in spec['environment'].items(): args.extend(['--env',key+'='+value])
    for key in ('http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):
        args.extend(['--env',key+'='])
    args.extend(['--env','NO_PROXY=localhost,127.0.0.1,::1','--env','no_proxy=localhost,127.0.0.1,::1'])
    args.append(spec['image'])
    created=False
    try:
        launch=command(args);row['launch_exit_code']=launch.returncode
        if launch.returncode: raise RuntimeError('diagnostic launch failed')
        created=True
        deadline=time.monotonic()+15
        original=spec['healthcheck']['test'][1:]
        while True:
            ready=command(['docker','exec',name,*[v.replace('localhost','127.0.0.1') for v in original]],timeout=6)
            if ready.returncode==0 or time.monotonic()>=deadline:break
            time.sleep(.25)
        for endpoint in ('localhost','127.0.0.1','[::1]'):
            probe=command(['docker','exec',name,*[v.replace('localhost',endpoint) for v in original]],timeout=6)
            diagnostic='success' if probe.returncode==0 else 'connection_refused' if 'Connection refused' in probe.stderr else 'network_unreachable' if 'Network unreachable' in probe.stderr else 'other_failure'
            row['probes'].append({'host':endpoint,'exit_code':probe.returncode,'category':diagnostic})
        inspection=command(['docker','inspect',name,'--format','{{json .State}}'])
        state=json.loads(inspection.stdout)
        row['container']={key:state[key] for key in ('Status','Running','OOMKilled','ExitCode')}
        resolved=command(['docker','exec',name,'getent','hosts','localhost'])
        row['localhost_resolves_ipv6']=bool(re.search(r'(^|\s)::1(\s|$)',resolved.stdout))
    finally:
        if created:
            stopped=command(['docker','rm','--force',name]);row['exact_container_removed']=stopped.returncode==0
        results.append(row)
        (packet/'nginx-reproduction.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(row),flush=True)
