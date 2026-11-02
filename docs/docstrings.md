# Docstring conventions

The API reference pages are generated from docstrings (Google style), so each level of
the code documents a different thing:

| Where | Documents | Example |
|---|---|---|
| Package `__init__.py` | What the package is for, and a guide to its modules. Does not repeat module or class documentation. | `newsegsmetamodel/__init__.py` |
| Module (`.py` file) | The role of the module and anything that is not a class or function it defines, e.g. helpers it also contains. | `newsegsmetamodel.py` |
| Class | What an instance represents, what it holds, its states and how to use it. Details of use belong here, not in the module. | `NewsegsMetaModel` |
| Function or method | What it does, `Args`, `Returns` and `Raises`. | |

Rules of thumb:

* Public classes, functions and methods (names not starting `_`) should have a docstring.
  Methods that override a documented method with `@override` inherit its documentation.
* A first line that stands alone as a summary, then a blank line.
* Docstrings that still contain `TODO` were generated as templates and need writing. Search for
  `TODO: Add` to find them.
* Cross-reference with the full path, e.g. ``[`find_constructor`][newsegsmodelframework.core.find_constructor]``.
