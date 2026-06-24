"""Heavy-import blocker for MCP cold-start subprocess tests.

The ``test_mcp_smoke.py::TestMCPStartupLatency::test_cold_start_under_budget``
test spawns a **fresh** Python interpreter to measure cold-start import time.
The parent process's blocker (in ``tests/conftest.py``) is in-memory
``sys.meta_path`` state and does not propagate to the subprocess — so the
subprocess would re-import the real ``litellm`` chain (30-90s+) and exceed
the 30s pytest-timeout.

The subprocess calls ``install()`` from this module BEFORE importing any
OL/OPP/ORF code, which pre-stubs the same heavy top-level packages
(litellm, torch, transformers, sentence_transformers, keybert, yake,
span_aligner, typer) and installs a ``_HeavyImportBlocker`` at
``sys.meta_path[0]``.

Mirrors the blocker in ``tests/conftest.py`` and in
``Omni_Localizer/tests/conftest.py`` (E2E-74 litellm stub fix, OL 0.4.6).
Keep all three copies in sync.
"""
import sys
import types
from importlib.machinery import ModuleSpec


_BLOCKED = frozenset({
    "litellm", "torch", "transformers",
    "sentence_transformers", "keybert", "yake",
    "span_aligner", "typer",
})


class _Stub(types.ModuleType):
    """Lightweight stub module — see tests/conftest.py for full docstring."""

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        cls = type(name, (), {})
        try:
            object.__setattr__(self, name, cls)
        except (AttributeError, TypeError):
            pass
        return cls


class _Blocker:
    """Block heavy imports (litellm, torch, ...) by returning stub specs."""

    def find_spec(self, name, path, target=None):
        top = name.split(".")[0]
        if name in _BLOCKED or top in _BLOCKED:
            return ModuleSpec(name, self)
        return None

    def create_module(self, spec):
        return _Stub(spec.name)

    def exec_module(self, module):
        # Submodule stubs of a blocked top-level package must look like
        # packages (``__path__``) so ``from litellm.X import Y`` walks
        # into them.
        if "." in module.__name__ and not hasattr(module, "__path__"):
            module.__path__ = []


def install() -> None:
    """Pre-stub ``litellm`` and install the meta-path blocker.

    Idempotent: safe to call multiple times. If ``litellm`` is already
    in ``sys.modules`` (e.g. by a parent process preloading it), the
    pre-stub is skipped.
    """
    if "litellm" not in sys.modules:
        _litellm_stub = types.ModuleType("litellm")
        _litellm_stub.Router = type("Router", (), {})
        _litellm_stub.__path__ = []
        sys.modules["litellm"] = _litellm_stub
    # Only install the blocker if it isn't already there (idempotent).
    if not any(isinstance(f, _Blocker) for f in sys.meta_path):
        sys.meta_path.insert(0, _Blocker())
