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
