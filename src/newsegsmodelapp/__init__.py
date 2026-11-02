"""The NewSEGS web application: a multi-page Dash app, its backend and its plugins.

Attributes:
    APP_ROOT: The `src` directory.
    STATICDATA: The `data` directory.

Modules:
    registers: Registries that plugins add to; the extension points of the app.
    register_plugins: Imports the plugins; imported by the app, dispatcher and workers.
    dash_extension: `NewsegsDash`, the app class.
    types: `Page` and `LayoutConfiguration`.

Subpackages:
    backend: Database layer, dispatcher, workers and maintenance.
    components: Reusable Dash components, layouts and callbacks.
    plugins: Pages, and the model-specific contents and processing.

"""
from pathlib import Path
APP_ROOT = Path(__file__).parent.parent.resolve()
STATICDATA = APP_ROOT.parent / 'data'
