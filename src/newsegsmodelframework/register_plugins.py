"""Import this module to ensure that the plugin registries are prepared.

Kept for compatibility: the project plugins are now imported by `newsegsmodelframework.plugins`
itself, so importing `newsegsmodelframework.plugins.registers` is sufficient.
"""

def load_project_factories():
    """Load the project plugins, which register their factories in `PROJECT_FACTORIES`.

    Returns:
        Dictionary of the project plugin modules by name.
    """
    from newsegsmodelframework.plugins import PROJECT_PLUGINS
    return dict(PROJECT_PLUGINS)

load_project_factories()
