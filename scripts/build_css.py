"""Build the app's stylesheet, `src/assets/newsegs.css`.

Dash serves every stylesheet in `src/assets`, so the app's CSS is kept as partials in `src/styles`, one for each part of
the app, and built into the one stylesheet served: the colours of `newsegsmodelapp.components.colours`, as CSS custom
properties, then the partials in the order of their names.

Run after changing a partial or a colour:

    python scripts/build_css.py

`--check` only reports whether the stylesheet is up to date (exit status 1 if not), as the unit tests do.
"""

import argparse
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / 'src'
STYLES = SRC / 'styles'
"""The partials."""

STYLESHEET = SRC / 'assets' / 'newsegs.css'
"""The built stylesheet."""

HEADER = """\
/* The stylesheet of the NewSEGS app.
   BUILT by scripts/build_css.py from the colours of src/newsegsmodelapp/components/colours.py and the partials in
   src/styles: edit those and rebuild, not this file. */
"""

def build() -> str:
    """Build the stylesheet.

    Returns:
        The CSS.
    """
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from newsegsmodelapp.components import colours

    parts = [HEADER, colours.css_tokens()]
    for partial in sorted(STYLES.glob('*.css')):
        parts.append(f'/* --- {partial.name} --- */\n\n' + partial.read_text(encoding = 'utf-8').strip() + '\n')
    return '\n'.join(parts)

def main(argv = None) -> int:
    parser = argparse.ArgumentParser(description = __doc__.splitlines()[0])
    parser.add_argument('--check', action = 'store_true', help = 'only check that the stylesheet is up to date')
    args = parser.parse_args(argv)
    css = build()
    current = STYLESHEET.read_text(encoding = 'utf-8') if STYLESHEET.exists() else None
    if args.check:
        if css != current:
            print(f'{STYLESHEET} is out of date: run python scripts/build_css.py')
            return 1
        print(f'{STYLESHEET} is up to date')
        return 0
    if css != current:
        STYLESHEET.write_text(css, encoding = 'utf-8')
        print(f'Wrote {STYLESHEET}')
    else:
        print(f'{STYLESHEET} is already up to date')
    return 0

if __name__ == '__main__':
    sys.exit(main())
