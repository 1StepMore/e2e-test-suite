"""Omni Suite operational scripts, importable as a package (issue #223 P2.1).

``scripts/`` is a regular package so every module has ONE canonical import
path (``scripts.<name>``, ``scripts.validation.<name>``). Rules of the road:

- Tests and tools import scripts through the package (``from scripts import
  format_matrix_verifier``) — the repo root is on ``sys.path`` for pytest and
  for anything that runs with the checkout as cwd.
- Entry scripts that are executed directly (``python scripts/foo.py``,
  Makefile / pre-commit / CI) place ONE documented bootstrap
  (``sys.path.insert(0, str(SUITE_ROOT))``) at the top so the package import
  inside them resolves; direct execution must keep working.
- This package is deliberately NOT added to pyproject ``packages``: installing
  a top-level package named ``scripts`` into site-packages would be a
  namespace collision waiting to happen. Importability comes from the repo
  root, not from installation.
"""
