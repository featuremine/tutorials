"""
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.
        
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import argparse
import msgpack
from yamal import yamal, data, streams, stream
from io import BytesIO

import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp-file", help="ytp file name", required=True)
    parser.add_argument("--follow", help="ytp file name", type=bool, default=False, required=False)
    args = parser.parse_args()

    y = yamal(args.ytp_file)
    dat = y.data()

    it = iter(dat)
    while(True):
        for seq, ts, strm, msg in it:
            unpacker = msgpack.Unpacker(BytesIO(msg), raw=False)
            for unpacked in unpacker:
                print(strm.channel, unpacked)
        if not args.follow:
            break
