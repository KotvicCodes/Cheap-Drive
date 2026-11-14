"""Model code and JSON configurations.

The one-line root modules alias these modules for standalone legacy imports.
Keep persisted factory names stable: recovery compares whole specs, and final's
rehearsal identity hashes them. New configuration files may use package names
without invalidating existing checkpoints, receipts or rehearsal records.
"""
import importlib

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


def resolve_factory(name):
    """Resolve trusted module:callable specs, including legacy model aliases."""
    module, attribute = name.split(':', 1)
    return getattr(importlib.import_module(module), attribute)
