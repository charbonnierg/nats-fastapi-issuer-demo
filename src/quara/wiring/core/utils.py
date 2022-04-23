from __future__ import annotations


def fullname(o: object) -> str:
    """Introspect full name of an object"""
    try:
        name = o.__name__
    except AttributeError:
        return fullclassname(o)
    module = o.__module__
    return module + "." + name


def fullclassname(o: object) -> str:
    klass = o.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__  # avoid outputs like 'builtins.str'
    return module + "." + klass.__qualname__
