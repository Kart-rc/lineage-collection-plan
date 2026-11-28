#!/usr/bin/env python3
"""Measure the unchanged collector on transient, independently synthetic OTLP.

Only aggregate metadata leaves the temporary directory. No captured reference
records, holdout cases, Kafka records, containers or infrastructure are touched.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import tempfile
import time

MIB = 1024 * 1024
ROOT = Path(__file__).resolve().parents[4]
PROFILE = dict(max_input_bytes=64*MIB, max_line_bytes=MIB, max_events=4096,
               max_metadata_bytes=8*MIB, max_memory_bytes=1536*MIB,
               max_sends_per_cycle=128, max_acknowledged=100000,
               parse_timeout=30.0, send_timeout=5.0)
BASE_NS = 1795867200000000000


def attr(key, value):
    if isinstance(value, int):
        return {'key': key, 'value': {'intValue': str(value)}}
    return {'key': key, 'value': {'stringValue': value}}


def spans_document(first, count, minutes):
    resources = {}
    for identity in range(first, first+count):
        mode = identity % 8
        service, kind, extra = (
            ('checkout', 3, [attr('server.address', 'payment'), attr('server.port', 50051), attr('rpc.service', 'oteldemo.PaymentService')]),
            ('payment', 2, [attr('rpc.service', 'oteldemo.PaymentService')]),
            ('checkout', 4, [attr('messaging.system', 'kafka'), attr('messaging.destination.name', 'orders')]),
            ('accounting', 5, [attr('messaging.system', 'kafka'), attr('messaging.destination.name', 'orders')]),
            ('fraud-detection', 5, [attr('messaging.system', 'kafka'), attr('messaging.destination.name', 'orders')]),
            ('frontend', 3, [attr('server.address', 'recommendation'), attr('server.port', 9001)]),
            ('accounting', 3, [attr('db.system', 'postgresql'), attr('db.statement', 'SELECT order_id, zip_code FROM accounting.shipping')]),
            ('cart', 3, [attr('db.system', 'redis'), attr('db.statement', 'GET'), attr('server.address', 'valkey-cart')]),
        )[mode]
        common = [attr('http.request.method', 'GET'), attr('http.route', '/capacity/check'),
                  attr('http.response.status_code', 200), attr('network.transport', 'tcp'),
                  attr('network.protocol.name', 'http'), attr('network.protocol.version', '1.1'),
                  attr('server.name', service), attr('deployment.environment.name', 'synthetic-capacity'),
                  attr('telemetry.sdk.name', 'opentelemetry'), attr('telemetry.sdk.language', 'python'),
                  attr('telemetry.sdk.version', '1.0.0'), attr('service.version', '3.1.0')]
        minute = (identity // 8) % minutes
        span = {'traceId': f'{identity//2+1:032x}', 'spanId': f'{identity+1:016x}',
                'name': 'capacity-readiness', 'kind': kind,
                'startTimeUnixNano': str(BASE_NS + minute*60_000_000_000),
                'endTimeUnixNano': str(BASE_NS + minute*60_000_000_000 + 1_000_000),
                'attributes': common + extra, 'status': {'code': 1}}
        if mode == 1:
            span['parentSpanId'] = f'{identity:016x}'
        resources.setdefault(service, []).append(span)
    return {'resourceSpans': [{'resource': {'attributes': [attr('service.name', service)]},
                              'scopeSpans': [{'scope': {'name': 'synthetic-capacity'}, 'spans': spans}]}
                             for service, spans in sorted(resources.items())]}


def logs_document(first, count, minutes):
    records = []
    for identity in range(first, first+count):
        cluster = 'frontend' if identity % 2 else 'image-provider'
        records.append({'timeUnixNano': str(BASE_NS+(identity//2 % minutes)*60_000_000_000),
                        'observedTimeUnixNano': str(BASE_NS+(identity//2 % minutes)*60_000_000_000),
                        'severityNumber': 9, 'severityText': 'INFO',
                        'body': {'stringValue': 'synthetic-capacity-request-completed'},
                        'attributes': [attr('event.name', 'proxy.access'), attr('upstream.cluster', cluster),
                                       attr('http.request.method', 'GET'), attr('http.route', '/capacity/check'),
                                       attr('http.response.status_code', 200), attr('network.protocol.name', 'http'),
                                       attr('network.protocol.version', '1.1'), attr('network.transport', 'tcp'),
                                       attr('deployment.environment.name', 'synthetic-capacity')]})
    return {'resourceLogs': [{'resource': {'attributes': [attr('service.name', 'frontend-proxy')]},
                             'scopeLogs': [{'scope': {'name': 'synthetic-capacity'}, 'logRecords': records}]}]}


def generate(path, target_bytes, builder, minutes):
    size = count = lines = longest = 0
    digest = hashlib.sha256()
    with path.open('wb') as stream:
        while True:
            document = builder(count, 64, minutes)
            encoded = json.dumps(document, separators=(',', ':'), sort_keys=True).encode() + b'\n'
            if size + len(encoded) > target_bytes:
                break
            stream.write(encoded)
            digest.update(encoded)
            size += len(encoded)
            count += 64
            lines += 1
            longest = max(longest, len(encoded))
    return {'bytes': size, 'records': count, 'lines': lines, 'max_line_bytes': longest, 'sha256': digest.hexdigest()}


def parser(capture, values, output, stats):
    from lineage.collector import _parse_worker
    _parse_worker(capture, None, {}, values, output)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    Path(stats).write_text(json.dumps({'peak_rss_bytes': usage.ru_maxrss*1024,
                                      'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime}))


def memory(pid):
    try:
        values = {}
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            name, _, text = line.partition(':')
            if name in {'VmRSS', 'VmHWM', 'VmSize', 'VmPeak'}:
                values[name] = int(text.split()[0])*1024
        return values
    except (FileNotFoundError, ProcessLookupError):
        return {}


def measure(name, target_mib, minutes, limits, expected):
    result = {'case': name, 'target_input_bytes': int(target_mib*MIB), 'synthetic_window_minutes': minutes,
              'limits': limits, 'expected': expected, 'raw_data_retained': False}
    with tempfile.TemporaryDirectory(prefix='lineage-capacity-') as folder:
        os.chmod(folder, 0o700)
        capture = Path(folder)
        traces = generate(capture/'traces.jsonl', int(target_mib*MIB*2/3), spans_document, minutes)
        logs = generate(capture/'logs.jsonl', int(target_mib*MIB/3), logs_document, minutes)
        result['inputs'] = {'traces': traces, 'logs': logs}
        result['input_bytes'] = traces['bytes']+logs['bytes']
        result['log_trace_byte_ratio'] = logs['bytes']/traces['bytes']
        if name == 'line-bound':
            oversized = {'resourceSpans': [{'resource': {'attributes': [attr('synthetic.capacity.note', 'x'*MIB)]}, 'scopeSpans': []}]}
            (capture/'traces.jsonl').write_text(json.dumps(oversized)+'\n')
            encoded = (capture/'traces.jsonl').read_bytes()
            result['inputs']['traces'] = {'bytes': len(encoded), 'records': 0, 'lines': 1,
                                         'max_line_bytes': len(encoded), 'sha256': hashlib.sha256(encoded).hexdigest()}
            result['input_bytes'] = len(encoded) + logs['bytes']
            result['line_boundary_fixture_bytes'] = len(encoded)
        output, stats = capture/'metadata.json', capture/'resource-stats.json'
        worker = multiprocessing.get_context('spawn').Process(target=parser, args=(str(capture), limits, str(output), str(stats)))
        started = time.monotonic()
        worker.start()
        peaks = {}
        timed_out = False
        while worker.is_alive():
            for key, value in memory(worker.pid).items():
                peaks[key] = max(peaks.get(key, 0), value)
            if time.monotonic()-started > limits['parse_timeout']:
                timed_out = True
                worker.terminate()
                break
            worker.join(0.01)
        worker.join(1)
        if worker.is_alive():
            worker.kill()
            worker.join(1)
        result.update(elapsed_seconds=round(time.monotonic()-started, 6), process_exit_code=worker.exitcode,
                      sampled_process_memory_bytes=peaks)
        worker.close()
        if timed_out:
            result['status'], result['category'] = 'error', 'parse_timeout'
        elif output.exists():
            raw_metadata = output.read_bytes()
            parsed = json.loads(raw_metadata)
            result.update(status=parsed['status'], category=parsed.get('category'),
                          metadata_bytes=len(raw_metadata), event_count=len(parsed.get('events', [])),
                          diagnostics=parsed.get('diagnostics', {}))
        else:
            result['status'], result['category'] = 'error', 'parse_unavailable'
        if stats.exists():
            result['process_resource_usage'] = json.loads(stats.read_text())
        result['matches_expected'] = (result['status'] == 'ok') if expected == 'ok' else (result['category'] == expected)
    return result


def main():
    options = argparse.ArgumentParser(description=__doc__)
    options.add_argument('--output', type=Path, required=True)
    options.add_argument('--cases', nargs='*')
    args = options.parse_args()
    cases = [
        ('default-observed-size', 18, 12, {**PROFILE, 'max_input_bytes': 16*MIB, 'max_memory_bytes': 512*MIB, 'parse_timeout': 10.0}, 'input_limit'),
        ('observed-size-margin', 18, 12, PROFILE, 'ok'),
        ('three-times-observed', 54, 36, PROFILE, 'ok'),
        ('near-profile-ceiling', 64, 40, PROFILE, 'ok'),
        ('over-input-bound', 65, 40, PROFILE, 'input_limit'),
        ('line-bound', 1, 1, PROFILE, 'line_limit'),
        ('event-bound', 18, 12, {**PROFILE, 'max_events': 1}, 'event_limit'),
        ('metadata-bound', 18, 12, {**PROFILE, 'max_metadata_bytes': 1024}, 'metadata_limit'),
    ]
    report = {'kind': 'synthetic-capacity-calibration', 'source_scope': 'valid synthetic OTLP; no reference capture or holdout',
              'profile_proposal': PROFILE, 'container_memory_proposal_bytes': 2048*MIB,
              'observed_candidate_7_input_bytes': 17731133, 'raw_fixture_retention': 'temporary files removed after each case',
              'collector_source_sha256': hashlib.sha256((ROOT/'src/lineage/collector.py').read_bytes()).hexdigest(),
              'service_edges_source_sha256': hashlib.sha256((ROOT/'src/lineage/service_edges.py').read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'cases': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if args.cases and case[0] not in args.cases:
            continue
        result = measure(*case)
        report['cases'].append(result)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
        print(json.dumps({key: result.get(key) for key in ('case', 'input_bytes', 'status', 'category', 'elapsed_seconds', 'event_count', 'matches_expected')}), flush=True)
    return 0 if all(case['matches_expected'] for case in report['cases']) else 1

if __name__ == '__main__':
    raise SystemExit(main())
