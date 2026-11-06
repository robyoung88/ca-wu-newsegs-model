"""Tests of the app's stylesheet: built from its partials and colours (`scripts/build_css.py`), and the only one served."""

import importlib.util
import re
import unittest
from pathlib import Path

from newsegsmodelapp.components import colours, icons, stats

ROOT = Path(__file__).resolve().parents[2]

def _build_css_module():
    spec = importlib.util.spec_from_file_location('build_css', ROOT / 'scripts' / 'build_css.py')
    module = importlib.util.module_from_spec(spec) # pyright: ignore[reportArgumentType]
    spec.loader.exec_module(module) # pyright: ignore[reportOptionalMemberAccess]
    return module

class TestCssBuild(unittest.TestCase):

    def setUp(self):
        self.build_css = _build_css_module()

    def test_stylesheet_is_up_to_date(self):
        self.assertEqual(
            self.build_css.build(), self.build_css.STYLESHEET.read_text(encoding = 'utf-8'),
            'src/assets/newsegs.css is out of date: run python scripts/build_css.py',
        )

    def test_one_stylesheet_is_served(self):
        # Dash serves every stylesheet in assets, in its subfolders too
        served = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'src' / 'assets').rglob('*.css'))
        self.assertEqual(served, ['src/assets/newsegs.css'])

    def test_partials_take_colours_from_the_scheme(self):
        # Colours are in components/colours.py, so that the scheme is changed in one place
        for partial in sorted(self.build_css.STYLES.glob('*.css')):
            css = re.sub(r'/\*.*?\*/', '', partial.read_text(encoding = 'utf-8'), flags = re.S)
            with self.subTest(partial = partial.name):
                self.assertEqual(re.findall(r'#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d', css), [])

    def test_configuration_colour_classes(self):
        css = self.build_css.build()
        self.assertEqual(len(colours.CONFIG_COLOUR_CLASSES), len(colours.CONFIG_COLOURS))
        for i, cls in enumerate(colours.CONFIG_COLOUR_CLASSES):
            self.assertIn(f'.{cls} {{ color: var(--ns-config-{i + 1}) !important; }}', css)
            self.assertIn(f'--ns-config-{i + 1}: {colours.CONFIG_COLOURS[i]};', css)

    def test_configurations_have_the_same_colours_in_the_ui_and_plots(self):
        self.assertEqual(icons.ICON_COLOUR_CLASSES, colours.CONFIG_COLOUR_CLASSES)
        self.assertEqual(stats.COMPARATOR_COLORS, colours.CONFIG_COLOURS)
        self.assertEqual(colours.config_colour(len(colours.CONFIG_COLOURS)), colours.CONFIG_COLOURS[0])
        self.assertEqual(colours.config_colour_class(1), 'config-colour-2')

    def test_rgba(self):
        self.assertEqual(colours.rgba('#432461', 0.25), 'rgba(67, 36, 97, 0.25)')

if __name__ == '__main__':
    unittest.main()
