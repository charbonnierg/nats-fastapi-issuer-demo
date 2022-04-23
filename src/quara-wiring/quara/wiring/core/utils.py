def fullname(o: object) -> str:
    """Introspect full name of an object"""
    try:
        name = o.__name__  # type: ignore[attr-defined]
    except AttributeError:
        return fullclassname(o)
    module = o.__module__
    return str(module + "." + name)


def fullclassname(o: object) -> str:
    klass = o.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__  # avoid outputs like 'builtins.str'
    return str(module + "." + klass.__qualname__)
