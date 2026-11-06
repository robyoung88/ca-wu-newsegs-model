"""
Tests of Dash callbacks, dispatched through Dash with the Flask test client (no browser).

Modules:
    dash_dispatch: Helpers which post requests to callbacks as the browser does, and parse the responses.
    base: The test case: a temporary database, a project and a minimal app.
"""
