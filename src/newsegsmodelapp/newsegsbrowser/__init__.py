from pathlib import Path
import os
PACKAGEDIR = Path(__file__).parent.absolute()
ROOTDIR = Path(__file__).parent.parent.absolute()
STATICDATA = os.path.join(Path(__file__).parent.parent.parent.parent.absolute(), 'data')
