"""Canonical metadata identifiers, including nested and repeated element paths (BL-1)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*$")
_AUTHORITY = re.compile(r"^[A-Za-z0-9._-]+$")
_PERCENT = re.compile(r"%([0-9a-fA-F]{2})")
_IDENTIFIER = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"')
_FIELD = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*|\*)(?:\[\])?(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|\*)(?:\[\])?)*$")
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _component(value: str) -> str:
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        raise ValueError("Malformed percent escape in URN")
    value = _PERCENT.sub(lambda m: chr(int(m[1], 16)) if chr(int(m[1], 16)) in _UNRESERVED else "%" + m[1].upper(), value)
    value = _IDENTIFIER.sub(r"\1", value)
    if '"' in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("URN identifiers must be unambiguous and contain no controls")
    return quote(value, safe="/._-~!$&'()+,;=:@[]*%")


@dataclass(frozen=True)
class URN:
    scheme: str
    authority: str
    path: str = ""
    field: str | None = None

    @property
    def namespace(self) -> str:
        return f"{self.scheme}://{self.authority}"

    @property
    def name(self) -> str:
        return self.path

    @property
    def dataset(self) -> str:
        return self.namespace + ("/" + self.path if self.path else "")

    def __str__(self) -> str:
        return self.dataset + ("#" + self.field if self.field is not None else "")


def parse(value: str) -> URN:
    """Parse and canonicalize; case is retained for names and attributes.

    Wildcards are accepted as identifiers because the pinned graph also contains
    must-not-flow scope URNs. Evidence validation separately restricts fields.
    """
    if not isinstance(value, str) or value.count("://") != 1 or value.count("#") > 1:
        raise ValueError("Expected a scheme://authority/name[#field] URN")
    scheme, rest = value.split("://", 1)
    if not _SCHEME.fullmatch(scheme):
        raise ValueError("Invalid URN scheme")
    body, marker, field = rest.partition("#")
    authority, slash, path = body.partition("/")
    if not _AUTHORITY.fullmatch(authority) or (slash and not path):
        raise ValueError("Invalid URN authority or empty path")
    path = _component(path)
    if marker:
        field = _component(field)
        if not path or not _FIELD.fullmatch(field):
            raise ValueError("Invalid nested field path")
    return URN(scheme, authority, path, field if marker else None)


def normalize(value: str) -> str:
    return str(parse(value))


def format(value: URN) -> str:
    """Format a parsed URN, validating explicitly constructed instances too."""
    return normalize(str(value))
