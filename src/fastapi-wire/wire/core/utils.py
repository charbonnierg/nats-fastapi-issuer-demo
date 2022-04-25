import pathlib
import shutil
import tempfile
import typing as t
import weakref


def fullname(o: object) -> str:
    """Introspect full name of an object"""
    try:
        name = o.__name__  # type: ignore[attr-defined]
    except AttributeError:
        return fullclassname(o)
    try:
        module = o.__module__
    except AttributeError:
        return str(name)
    return str(module + "." + name)


def fullclassname(o: object) -> str:
    klass = o.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__  # avoid outputs like 'builtins.str'
    return str(module + "." + klass.__qualname__)


class TempDir:
    """Temporary directory that is removed once used."""

    def __init__(self, path: t.Union[pathlib.Path, str, None] = None):
        # Either accept a path as a string or Path
        if path:
            self.path = pathlib.Path(path)
            # Manually create the directory
            self.path.mkdir(parents=False, exist_ok=False)
        # Or create a new one
        else:
            # mkdtemp handles the directory creation
            self.path = pathlib.Path(tempfile.mkdtemp())
        self.name = str(self.path.resolve().absolute())
        # Register the finalizer that will remove the directory recursively
        self._finalizer = weakref.finalize(self, shutil.rmtree, self.name)

    def remove(self) -> None:
        """Remove the directory."""
        self._finalizer()

    @property
    def removed(self) -> bool:
        """Return True if the directory has been removed."""
        return not self._finalizer.alive

    def __enter__(self) -> "TempDir":
        """Allows usage with context manager:

        ```
        with TempDir() as tmpdir:
            print(tmpdir)
        ```

        Note: `tmpdir` object will still exist but directory will be removed.
        """
        return self

    def __exit__(self, *args: t.Any, **kwargs: t.Any) -> None:
        """Always remove the directory when exiting context manager."""
        self.remove()

    def __repr__(self) -> str:
        """Provide a user friendly string representation."""
        return f"TempDir(path='{self.path}', exists={not self.removed})"

    def __str__(self) -> str:
        """Provide a basic string representation."""
        return str(self.path)
