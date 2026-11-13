"""Tests of the NewSEGS model.

Importing this package, which pytest and unittest do before importing any test module, selects
the `testing` environment (see `config.environment`), so that the tests use the `[testing]`
section of `settings.toml`. `spraketest`, a variant of `testing`, is left in place if selected.
"""
import os

if os.environ.get('NEWSEGS_ENV', '').strip().lower() not in ('testing', 'spraketest'):
    os.environ['NEWSEGS_ENV'] = 'testing'
