"""
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.
        
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import argparse
import extractor
from functools import partial

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp", help="YTP file name", required=True)
    parser.add_argument("--prefix", help="Prefix for market data channels", required=True)
    parser.add_argument("--securities", help="List of securities", required=True, nargs='*', default=[], type=str)
    parser.add_argument('--graphviz', help="Visualize graph of instantiated nodes", action='store_true')

    args = parser.parse_args()

    graph = extractor.system.comp_graph()
    op = graph.features

    upds = op.seq_ore_live_split(args.ytp, tuple([args.prefix + sec for sec in args.securities]))
    levels = [op.book_build(upd, 1) for upd in upds]

    if args.graphviz:
        from extractor.tools.visualization import graph_viz
        g = graph_viz(graph)
        g.render(view=True)
    else:
        for sec, level in zip(args.securities, levels):
            graph.callback(level, partial(lambda frame, security: print(security + '\n', frame), security=sec))
        graph.stream_ctx().run_live()
