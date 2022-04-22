from __future__ import annotations


def fullname(o: object) -> str:
    """Introspect full name of an object"""
    name = o.__name__
    module = o.__module__
    return module + '.' + name
