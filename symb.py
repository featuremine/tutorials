import conveyor.test.testtools as testtools
import json
import os
import unittest
import datetime
from conveyor.utils import schemas


strgspec = schemas.strategy
sessspec = schemas.session


dir = os.path.join(os.getenv('TEST_OUTPUT_DIR', os.getcwd()), 'test-output', 'logs_test')
os.makedirs(dir, exist_ok=True)


if __name__ == '__main__':
    y = testtools.YTPSetup(subdir=dir)

    comps = {}

    m = testtools.MngrLoader(
        ytp=y,
        computations=comps,
        validation=[]
    )
    m.start()
    b = testtools.OrdBuilder(
        ytp=y,
        comps=comps,
    )
    b.init_currencies()
    b.init_futures()
    b.init_account()
    b.init_venues()
    b.init_risk()
    b.mrkt_update(b.mrkt_rnd_step())
    b.wait()
    m.stop()
