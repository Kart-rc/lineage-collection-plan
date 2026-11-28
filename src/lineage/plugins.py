"""Extractor protocol, immutable Git views, and an executable conformance gate.

Plugin code runs in disposable Linux workers. The kernel denies networking and
execution of other programs; Python socket monkeypatching is not the boundary.
"""
from __future__ import annotations

import ctypes
import errno
import fnmatch
import hashlib
import json
import multiprocessing
import os
import platform
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Protocol


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def checked_path(path: str) -> str:
    parts = PurePosixPath(path)
    if not path or parts.is_absolute() or ".." in parts.parts or "\x00" in path:
        raise ValueError("path must be relative to the repository without '..'")
    return str(parts).removeprefix("./").rstrip("/")


@dataclass(frozen=True)
class InputRef:
    path: str


@dataclass(frozen=True)
class UnitRef:
    urn: str
    path: str
    files: tuple[str, ...]
    name: str = "unit"
    kind: str = "service"
    environment: str = "fixture"
    input_refs: tuple[InputRef, ...] = ()


@dataclass(frozen=True)
class RepoView:
    """Read-only tracked regular files from one exact commit, never the worktree."""

    commit: str
    timestamp: str
    _files: dict[str, bytes] = field(repr=False)
    exclude: tuple[str, ...] = ()
    config: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_git(cls, directory: str | Path, commit: str, *, exclude=(), config=None) -> "RepoView":
        if not re.fullmatch(r"[0-9a-f]{7,40}", commit):
            raise ValueError("commit must be a hexadecimal Git commit SHA")

        def git(*args, input=None):
            result = subprocess.run(["git", "-C", str(directory), *args], input=input,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if result.returncode:
                raise ValueError("commit is unavailable in this repository")
            return result.stdout

        resolved = git("rev-parse", "--verify", commit + "^{commit}").decode().strip()
        entries = git("ls-tree", "-rz", resolved).split(b"\x00")
        objects = []
        for entry in entries:
            if not entry:
                continue
            header, name = entry.split(b"\t", 1)
            mode, kind, oid = header.split()
            # Symlinks and submodules cannot escape into a mutable checkout.
            if kind == b"blob" and mode in (b"100644", b"100755"):
                objects.append((checked_path(name.decode()), oid))
        raw = git("cat-file", "--batch", input=b"".join(oid + b"\n" for _, oid in objects)) if objects else b""
        files = {}
        offset = 0
        for path, oid in objects:
            end = raw.index(b"\n", offset)
            actual, kind, size = raw[offset:end].split()
            if actual != oid or kind != b"blob":
                raise ValueError("commit blob is unavailable")
            length = int(size)
            files[path] = raw[end + 1:end + 1 + length]
            offset = end + 2 + length
        stamp = git("show", "-s", "--format=%ct", resolved).decode().strip()
        timestamp = datetime.fromtimestamp(int(stamp), timezone.utc).isoformat().replace("+00:00", "Z")
        return cls(resolved, timestamp, files, tuple(exclude), config or {})

    def excluded(self, path: str) -> bool:
        return any(fnmatch.fnmatchcase(path, pattern) or
                   (pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:]))
                   for pattern in self.exclude)

    def files(self, path: str = ".") -> tuple[str, ...]:
        path = checked_path(path)
        return tuple(sorted(p for p in self._files if not self.excluded(p) and
                            (path == "." or p == path or p.startswith(path + "/") or
                             fnmatch.fnmatchcase(p, path))))

    def read_bytes(self, path: str) -> bytes:
        path = checked_path(path)
        if self.excluded(path):
            raise ValueError("excluded path is not readable")
        return self._files[path]

    def read_text(self, path: str) -> str:
        return self.read_bytes(path).decode()


@dataclass(frozen=True)
class ExtractContext:
    repo: RepoView
    deadline: float

    def schema_at(self, ref: InputRef, commit: str) -> bytes:
        if commit != self.repo.commit:
            raise ValueError("schema commit must equal the scanned commit")
        return self.repo.read_bytes(ref.path)


class Extractor(Protocol):
    name: str
    version: str
    technologies: frozenset[str]

    def detect(self, repo: RepoView, paths: list[str]) -> list[UnitRef]: ...
    def inputs(self, unit: UnitRef) -> list[InputRef]: ...
    def extract(self, unit: UnitRef, ctx: ExtractContext) -> Iterator[dict]: ...


def opaque_event(unit: UnitRef, repo: RepoView, reason: str, producer: str) -> dict:
    """An unresolved unit boundary; this asserts no invented downstream consumer."""
    return {
        "schemaVersion": "2", "eventType": "EVIDENCE", "eventTime": repo.timestamp,
        "producer": producer,
        "edge": {"type": "DERIVES", "from": {"namespace": "unit://git", "name": unit.urn.split("unit://git/", 1)[-1]},
                 "to": {"namespace": "svc://" + unit.environment, "name": unit.name},
                 "opaque": [{"reason": reason}]},
        "evidence": {"source": "ci_static", "runtime": False, "observedAt": repo.timestamp,
                     "rawRef": "git://" + repo.commit + "/" + unit.path},
    }


class StubExtractor:
    """Explicit fixture mode: one opaque, metadata-only unit per configured path."""

    name = "stub"
    version = "0.1.0"
    technologies = frozenset({"fixture"})

    def detect(self, repo: RepoView, paths: list[str]) -> list[UnitRef]:
        descriptors = {item["path"]: (kind, item) for kind in ("services", "schemas", "projects")
                       for item in repo.config.get(kind, [])}
        result = []
        for path in sorted(set(paths)):
            kind, item = descriptors.get(path, ("services", {"name": path.split("/")[-1]}))
            result.append(UnitRef("unit://git/" + repo.config.get("repository", "fixture") + "/" + path,
                                  path, repo.files(path), item.get("name", path), kind,
                                  repo.config.get("environment", "fixture")))
        return result

    def inputs(self, unit: UnitRef) -> list[InputRef]:
        return list(unit.input_refs)

    def extract(self, unit: UnitRef, ctx: ExtractContext) -> Iterator[dict]:
        reason = "OTHER" if unit.files else "EXTRACTOR_ERROR"
        yield opaque_event(unit, ctx.repo, reason, "lineage-extractors/stub@" + self.version)


class WorkerFailure(RuntimeError):
    pass


class WorkerTimeout(WorkerFailure):
    pass


def _deny_network_and_exec() -> None:
    """Fail closed unless Linux seccomp can block network/exec syscalls."""
    architectures = {
        "x86_64": (0xC000003E, [41, 42, 43, 44, 45, 46, 47, 49, 50, 53, 288, 299, 307, 59, 322, 101, 308, 272, 298, 321, 425, 426, 427, 56, 57, 58, 435]),
        "aarch64": (0xC00000B7, list(range(198, 213)) + [242, 243, 221, 281, 117, 268, 97, 241, 280, 425, 426, 427, 220, 435]),
    }
    if platform.system() != "Linux" or platform.machine() not in architectures:
        raise WorkerFailure("isolation: Linux seccomp architecture unavailable")
    arch, blocked = architectures[platform.machine()]

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]

    instructions = [Filter(0x20, 0, 0, 4), Filter(0x15, 1, 0, arch), Filter(0x06, 0, 0, 0x80000000), Filter(0x20, 0, 0, 0)]
    # Also deny the x32 ABI: otherwise x86 callers could bypass native numbers.
    if platform.machine() == "x86_64":
        instructions += [Filter(0x45, 0, 1, 0x40000000), Filter(0x06, 0, 0, 0x80000000)]
    for number in blocked:
        instructions += [Filter(0x15, 0, 1, number), Filter(0x06, 0, 0, 0x00050000 | errno.EPERM)]
    instructions.append(Filter(0x06, 0, 0, 0x7FFF0000))
    array = (Filter * len(instructions))(*instructions)
    program = Program(len(instructions), array)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise WorkerFailure("isolation: seccomp unavailable")


def isolated(call: Callable[[], object], timeout: float) -> object:
    """Bound crashes, hangs, network and process execution for every plugin phase."""
    if timeout <= 0:
        raise WorkerTimeout("deadline exceeded")
    context = multiprocessing.get_context("fork")
    receive, send = context.Pipe(duplex=False)

    def worker():
        receive.close()
        try:
            os.setsid()
            # Never expose exception text or plugin prints (which may contain input).
            null = os.open(os.devnull, os.O_RDWR)
            os.dup2(null, 0)
            os.dup2(null, 1)
            os.dup2(null, 2)
            os.close(null)
            keep = {0, 1, 2, send.fileno()}
            for descriptor in os.listdir("/proc/self/fd"):
                if int(descriptor) not in keep:
                    try:
                        os.close(int(descriptor))
                    except OSError:
                        pass
            _deny_network_and_exec()
            result = call()
            # JSON avoids running untrusted pickle reducers in the parent.
            send.send_bytes(json.dumps([True, result], default=_encode).encode())
        except BaseException as error:
            send.send_bytes(json.dumps([False, type(error).__name__]).encode())
        finally:
            send.close()

    process = context.Process(target=worker, daemon=True)
    process.start()
    send.close()
    try:
        if not receive.poll(timeout):
            raise WorkerTimeout("deadline exceeded")
        try:
            ok, result = json.loads(receive.recv_bytes(maxlength=16 * 1024 * 1024), object_hook=_decode)
        except (EOFError, OSError, ValueError) as error:
            raise WorkerFailure("extractor worker crashed") from error
        if not ok:
            raise WorkerFailure("extractor failed: " + result)
        return result
    finally:
        if process.is_alive():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        receive.close()


@dataclass(frozen=True)
class ConformanceFixture:
    repo: RepoView
    unit: UnitRef
    expected_edges: tuple[dict, ...]
    reformatted: RepoView
    renamed: RepoView
    unreadable: UnitRef
    minimum_precision: float = 1.0
    minimum_recall: float = 1.0
    deadline_seconds: float = 2.0


def _encode(value):
    if isinstance(value, bytes):
        return {"__lineage_type__": "bytes", "hex": value.hex()}
    if isinstance(value, (InputRef, UnitRef, RepoView, ConformanceFixture)):
        return {"__lineage_type__": type(value).__name__,
                "fields": {key: getattr(value, key) for key in value.__dataclass_fields__}}
    if isinstance(value, frozenset):
        return sorted(value)
    raise TypeError("worker returned unsupported data")


def _decode(value):
    kind = value.get("__lineage_type__")
    if kind == "bytes":
        return bytes.fromhex(value["hex"])
    classes = {cls.__name__: cls for cls in (InputRef, UnitRef, RepoView, ConformanceFixture)}
    if kind in classes:
        fields = value["fields"]
        for name in ("files", "input_refs", "exclude", "expected_edges"):
            if name in fields:
                fields[name] = tuple(fields[name])
        return classes[kind](**fields)
    return value


@dataclass(frozen=True)
class EntryPointExtractor:
    """Metadata-only parent handle; imports and package methods stay in workers."""
    name: str
    version: str
    technologies: frozenset[str]
    entry: metadata.EntryPoint

    def detect(self, repo, paths):
        return self.entry.load().detect(repo, paths)

    def inputs(self, unit):
        return self.entry.load().inputs(unit)

    def extract(self, unit, ctx):
        return self.entry.load().extract(unit, ctx)


def stub_fixture() -> ConformanceFixture:
    files = {"src/example/main.go": b"package main\n"}
    repo = RepoView("a" * 40, "2026-11-28T00:00:00Z", files)
    unit = UnitRef("unit://git/fixture/src/example", "src/example", tuple(files), "example")
    expected = opaque_event(unit, repo, "OTHER", "lineage-extractors/stub@0.1.0")["edge"]
    return ConformanceFixture(repo, unit, (expected,),
                              RepoView(repo.commit, repo.timestamp, {"src/example/main.go": b"package   main\n"}),
                              RepoView(repo.commit, repo.timestamp, {"src/example/main.go": b"package renamed\n"}),
                              UnitRef(unit.urn, unit.path, (), unit.name))


def _accuracy_floor(extractor_name: str) -> dict[str, float]:
    """Resolve the approved floor, independently of plugin-supplied thresholds."""
    from .config import parameters, repository_root

    accuracy = parameters()["baseline_accuracy"]
    if extractor_name in {"protobuf", "ef-core-orm"}:
        # parameters.yaml explicitly identifies descriptor/ORM deterministic
        # hops; WP-24 applies that precision and recall floor to ORM edges.
        return accuracy["deterministic_hops"]
    if extractor_name == "model-assisted":
        # WP-29 overrides the ordinary per-hop precision floor and specifies
        # no recall floor. Read its approved number rather than copying a
        # separately tunable threshold into implementation or plugin metadata.
        work_package = repository_root() / "factory/work-packages/WP-29-model-assisted-extractor-for-opaque-units-with-a.md"
        matches = re.findall(r"(?m)^- Precision >= ([0-9]+(?:\.[0-9]+)?) on accepted edges against the golden graph\s*$",
                             work_package.read_text())
        if len(matches) != 1 or not 0 <= float(matches[0]) <= 1:
            raise ValueError("WP-29 approved precision floor is unavailable")
        return {"precision": float(matches[0]), "recall": 0.0}
    return accuracy["per_hop_default"]


def check_conformance(plugin: Extractor, fixture: ConformanceFixture, deadline: float | None = None) -> dict[str, bool]:
    """Exercise the published checks; no self-declared boolean attestation is trusted."""
    from .evidence import prepare_event

    results = {name: False for name in ("golden", "determinism", "metamorphic", "opaque", "schema", "budget", "isolation")}
    if not re.fullmatch(r"[a-z][a-z0-9-]*", plugin.name) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][\w.-]+)?", plugin.version):
        return results
    try:
        floor = _accuracy_floor(plugin.name)
    except (OSError, KeyError, TypeError, ValueError):
        return results
    if (not 0 < fixture.deadline_seconds <= 5
            or not floor["precision"] <= fixture.minimum_precision <= 1
            or not floor["recall"] <= fixture.minimum_recall <= 1):
        return results
    try:
        def extract(repo, unit):
            allowance = min(fixture.deadline_seconds, deadline - time.monotonic()) if deadline else fixture.deadline_seconds
            return isolated(lambda: list(plugin.extract(unit, ExtractContext(repo, time.monotonic() + allowance))), allowance)

        runs = [extract(fixture.repo, fixture.unit) for _ in range(3)]
        variants = [extract(repo, fixture.unit) for repo in (fixture.reformatted, fixture.renamed)]
        unreadable = extract(fixture.repo, fixture.unreadable)
        for events in runs + variants + [unreadable]:
            for event in events:
                if "weight" in event.get("evidence", {}):
                    raise ValueError("extractor must not assign a weight")
                prepare_event(event)
        results["schema"] = True
        results["determinism"] = len({canonical(events) for events in runs}) == 1
        edges = {canonical(event["edge"]) for event in runs[0]}
        golden = {canonical(edge) for edge in fixture.expected_edges}
        precision = len(edges & golden) / len(edges) if edges else float(not golden)
        recall = len(edges & golden) / len(golden) if golden else float(not edges)
        results["golden"] = precision >= fixture.minimum_precision and recall >= fixture.minimum_recall
        results["metamorphic"] = all({canonical(event["edge"]) for event in events} == edges for events in variants)
        results["opaque"] = bool(unreadable) and all(event.get("edge", {}).get("opaque") for event in unreadable)
        results["budget"] = True
        results["isolation"] = True
    except WorkerTimeout:
        pass
    except (ValueError, KeyError, TypeError, WorkerFailure):
        pass
    return results


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, Extractor] = {}
        self.rejected: dict[str, list[str]] = {}

    def register(self, plugin: Extractor, fixture: ConformanceFixture, deadline: float | None = None) -> bool:
        checks = check_conformance(plugin, fixture, deadline)
        failed = [name for name, passed in checks.items() if not passed]
        if plugin.name in self._plugins:
            failed.append("unique_name")
        if failed:
            self.rejected[plugin.name] = failed
            return False
        self._plugins[plugin.name] = plugin
        return True

    def discover(self, deadline: float | None = None) -> None:
        """Load only extractors with matching executable conformance fixtures.

        The companion entry point does not alter detect/inputs/extract.
        Package import is isolated too.
        """
        fixtures = {ep.name: ep for ep in metadata.entry_points(group="lineage_ci.conformance")}
        for entry in metadata.entry_points(group="lineage_ci.extractors"):
            if entry.name not in fixtures:
                self.rejected[entry.name] = ["missing_conformance_fixture"]
                continue
            try:
                def load_metadata():
                    plugin = entry.load()
                    return [plugin.name, plugin.version, sorted(plugin.technologies), fixtures[entry.name].load()()]
                name, version, technologies, fixture = isolated(load_metadata, min(5, deadline - time.monotonic()) if deadline else 5)
                if name != entry.name:
                    raise ValueError("entry point name mismatch")
                plugin = EntryPointExtractor(name, version, frozenset(technologies), entry)
                self.register(plugin, fixture, deadline)
            except Exception:
                self.rejected[entry.name] = ["isolation_or_load"]

    def values(self) -> tuple[Extractor, ...]:
        return tuple(self._plugins[name] for name in sorted(self._plugins))

    def get(self, name: str) -> Extractor | None:
        return self._plugins.get(name)
