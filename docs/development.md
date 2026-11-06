# Development and releases

Work moves through three branches:

| Branch | Purpose | Changed by |
|---|---|---|
| `development` | Integration of feature and fix pull requests | Squash-merged pull requests |
| `canary` | Early release testing; each merge makes a prerelease `vX.Y.Z-canary.N` | Merge-commit pull requests from `development` |
| `main` | Production; each merge makes a release `vX.Y.Z` | Merge-commit pull requests from `canary` |

## Making a change

1. Branch from `development`, and open the pull request against `development`.
2. Give the pull request a [Conventional Commit](https://www.conventionalcommits.org/) title. It is checked by the
   `pull request title` workflow, and it becomes the commit message when the pull request is squash-merged, so it sets
   the next version:

    | Title | Release |
    |---|---|
    | `fix: correct the export tariff` | patch |
    | `feat: add a location to the map` | minor |
    | `feat!: change the project file format`, or a `BREAKING CHANGE: ...` footer in the description | major (minor while the version is below 1.0.0) |
    | `docs:`, `test:`, `refactor:`, `ci:`, `chore:`, ... | none |

3. The `unit tests` workflow runs on the pull request. It first regenerates the default model artifacts and compares
   them with `data/` (see the README for retrieving them if they differ), then runs the unit tests, excluding the
   Excel validation and the PSA and DSA tests. Squash-merge the pull request.

Every push to `development` builds the Docker image.

## Tests

The unit tests are in `test/unit_tests`. Run them from the repository root with `src` on the path, as the `unit tests`
workflow does:

```bash
PYTHONPATH=src python -m pytest test/unit_tests \
    --ignore=test/unit_tests/test_dsa --ignore=test/unit_tests/test_psa \
    --ignore=test/unit_tests/test_dsa_multiple.py --ignore=test/unit_tests/test_psa_multiple.py
```

The excluded PSA and DSA tests are slow; they run in the `enhanced unit tests` workflow on a release. The tests are
`unittest` test cases, so the VS Code test explorer (configured for `unittest`) runs them too.

### Callback tests

`test/unit_tests/test_app_callbacks` tests the Dash callbacks without a browser. Each test builds a minimal
`NewsegsDash` holding the input container callbacks, with a temporary database and a sprake project, and posts
requests to `/_dash-update-component` with the Flask test client. Dash itself then dispatches the request, so the
tests cover the callback's registration, pattern matching, `ctx` and grouped outputs. They don't show that a browser
emits a given event.

```bash
PYTHONPATH=src python -m pytest test/unit_tests/test_app_callbacks
```

The tests depend on the format of Dash's requests, so `requirements-test.txt` pins the Dash packages to the versions
in `conda-environment.yml`. Change them together.

- `dash_dispatch.py` holds the helpers. `dispatch_input_change` posts a change of an input to
  `react_to_input_change` and returns a `CallbackResponse`: `response.updated` is false when Dash made no update, and
  `response.get(id, prop)` gives the value returned for a component, or `NOT_UPDATED`. The callback's inputs, outputs
  and state are read from `/_dash-dependencies`. The components sent with each wildcard are those of the "page": a
  list of components, usually rendered by the app's own input container content creators with
  `render_input_containers`, so the tests follow the layout.
- `base.py` holds `InputChangeTestCase`. It sets up each test afresh, and has helpers to set up the project as the
  app does (`add_configuration`, `make_independent`, `set_focus`, `remove_configuration`) and to read what is stored:
  `stored_variable` and `loaded_variable`, `revised` (rows whose revision changed), `stale_marks` (configurations
  and processes marked stale) and `assertNothingChanged`. It reads through an uncached provider, so the assertions
  see the database rather than a cache.
- Each test case runs with the uncached project provider, and again with the cached provider the app uses, through
  `cached_variant`.
- `test_row_anchors.py` renders every registered input container for each model type, and fails if a row has an input
  of `react_to_input_change` but no component matching its first output. The Dash renderer never calls the callback
  for such a row, and a request-level test can't show that.

### Adding a test of an input handler

Add a test case to `test_registered_handlers.py`, or to a new `test_*.py` module in the package. Render the page
that holds the input, dispatch a change, and assert on both the response and the database:

```python
from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import NOT_UPDATED, variable_id

class TestMyHandler(InputChangeTestCase):
    """`my-purpose` of an `input-toggle`"""
    n_metamodels = 2  # the configurations share every variable until made independent

    def test_saved(self):
        components = self.page(('dsa', None))  # (supersection, section) of each input container
        trigger = variable_id('input-toggle', 'my-purpose', 'gen_input', 'wind_capacity', supersection = 'dsa')
        t0 = self.now()

        response = self.dispatch(trigger, True, components)

        self.assertIsNot(
            response.get(variable_id('input-group-config-update-trigger', 'trigger', 'gen_input', 'wind_capacity', supersection = 'dsa'), 'data'),
            NOT_UPDATED,
        )
        self.assertTrue(self.loaded_variable('gen_input.wind_capacity.0', 1).my_setting)
        self.assertEqual(self.stale_marks(t0), {(x, 'dsa') for x in self.metamodel_ids})

TestMyHandlerCached = cached_variant(TestMyHandler)
```

If the input isn't rendered by a content creator, add a component for it to the page, such as
`dcc.Input(id = trigger)`. Change data through the app's own paths, or through the `base.py` helpers that copy them,
so that caches see the change as they would in the app. A handler that should make no change must also leave the
database as it was: check with `database_state` and `assertNothingChanged`.

## Documentation

The documentation is built with [MkDocs](https://www.mkdocs.org) from the markdown in `docs/` and the docstrings in `src/`.

```bash
pip install -r requirements-docs.txt
mkdocs serve   # live preview at http://127.0.0.1:8000
mkdocs build   # writes static HTML to site/
```

- On pushes to `main` the `publish documentation` workflow deploys the site to the `gh-pages` branch (GitHub Pages must be set to deploy from that branch).
- The running app serves the built HTML from `site/` (or `DOCS_PATH`) at `/documentation/`; the Docker image builds it automatically.

## Releasing

- **Prerelease.** Open a pull request from `development` to `canary`, and merge it with a merge commit (not squash or
  rebase, which would separate the histories of the branches). The `release` workflow runs the unit tests, then tags
  `vX.Y.Z-canary.N` and makes a GitHub prerelease.
- **Release.** Open a pull request from `canary` to `main`, and merge it with a merge commit. The unit tests run on the
  pull request; on the merge, the `release` workflow runs the PSA and DSA tests (`enhanced unit tests`), tags `vX.Y.Z`,
  makes a GitHub Release, and then merges `main` back into `canary`, so that the next prerelease is counted from this
  release.

Versions come from [python-semantic-release](https://python-semantic-release.readthedocs.io/), configured in
`pyproject.toml`. A release is a tag and a GitHub Release only: nothing is committed back, so `project.version` in
`pyproject.toml` is not updated. A `vX.Y.Z` tag pushed by hand also gets a GitHub Release.

## Branch protection

Rulesets on the repository enforce this:

- `main`: changes only through a pull request with the `unit-tests` check passing, merged with a merge commit; no force
  pushes or deletion.
- `canary`: no force pushes or deletion. Pull requests are not required, so that the `release` workflow can merge `main`
  back into it.
- `development`: changes only through a squash-merged pull request; no force pushes or deletion.

<!-- BEGIN TEMPORARY CI SECTION: Revisit or remove during the README refactor. -->
## CI checks and generated model artifacts

Pull requests targeting `development`, `canary` or `main` run the unit-test workflow. The
workflow first regenerates the default model artifacts and checks them against
the files in `data/`; it does not modify the pull request. PSA/DSA tests run
separately on pushes to `main`. The Excel-based validation tests compare against
results extracted from the validation workbook into `data/sprake_validation/`, so
they run in CI without it. After the workbook changes, rerun
`scripts/210_extract_sprake_validation_results.py` on a computer with access to it
and commit the updated files.

If generated artifacts differ from the checked-in files, the prerequisite
check fails and uploads the generated files as the
`generated-default-model-artifacts` workflow artifact. To retrieve them, open
the failed workflow run from the pull request's **Checks** tab, then download
the artifact from the run summary's **Artifacts** section. Update the
corresponding files in `data/` and push the changes to the pull request; the
check must pass before the pull request can merge.

The artifact is available when generation reaches the comparison step. If
generation fails earlier, generated files may not be available to download.
<!-- END TEMPORARY CI SECTION -->

## Profiling

For profiling, use viztracer:

```{bash}
& C:\Users\Robert.Young\anaconda3\envs\ca-wu-newsegs-mod\python.exe -m viztracer --log_async --min_duration 500 -o trace.json c:/Users/Robert.Young/Dev/ca-wu-newsegs-model/src/app.py    
```

Results can be viewed at https://www.speedscope.app/ or https://ui.perfetto.dev/.