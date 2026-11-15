"""Model code and JSON configurations.

Importing this package registers an import alias for each relocated model, so
legacy names such as ``import delta`` or ``delta:make_delta`` resolve to the
single ``models.delta`` module object without shim files at the repository root.
Keep persisted factory names stable: recovery compares whole specs, and final's
rehearsal identity hashes them. New configuration files may use package names
without invalidating existing checkpoints, receipts or rehearsal records.
"""
import importlib
import importlib.abc
import importlib.util
import sys

LEGACY_MODULES = frozenset({
    'alpha', 'beta', 'gamma', 'gamma_notes', 'gamma_pairs', 'delta',
    'delta_b1', 'delta_lanes', 'delta_option_spread', 'notes', 'gemini_notes',
})


def persisted_factory_name(name):
    """Use the original spelling only for this repository's relocated models."""
    if isinstance(name, str) and ':' in name:
        module, attribute = name.split(':', 1)
        if module.startswith('models.') and module[7:] in LEGACY_MODULES:
            return f'{module[7:]}:{attribute}'
    return name


class _LegacyAlias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Make ``import delta`` return the ``models.delta`` module itself."""

    def find_spec(self, name, path=None, target=None):
        if path is None and name in LEGACY_MODULES:
            return importlib.util.spec_from_loader(name, self)
        return None

    def create_module(self, spec):
        return importlib.import_module('models.' + spec.name)

    def exec_module(self, module):
        return None


if not any(isinstance(finder, _LegacyAlias) for finder in sys.meta_path):
    sys.meta_path.append(_LegacyAlias())


def resolve_factory(name):
    """Resolve trusted module:callable specs, including legacy model aliases."""
    module, attribute = name.split(':', 1)
    if module in LEGACY_MODULES:
        module = 'models.' + module
    return getattr(importlib.import_module(module), attribute)
