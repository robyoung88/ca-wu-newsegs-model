from pathlib import Path

PACKAGEDIR = Path(__file__).parent.absolute()
ROOTDIR = PACKAGEDIR.parent.absolute()
STATICDATA = ROOTDIR.parent.absolute() / 'data'
STATICDOCS = ROOTDIR.parent.absolute() / 'docs'
