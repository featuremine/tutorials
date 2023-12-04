"""
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.
        
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import argparse
import extractor

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp", help="YTP file name", required=True)
    parser.add_argument("--channel", help="YTP channel", required=True)
    parser.add_argument("--live", help="Run in live mode", action="store_true")
    parser.add_argument('--graphviz', help="Visualize graph of instantiated nodes", action='store_true')

    args = parser.parse_args()

    graph = extractor.system.comp_graph()
    op = graph.features

    if args.live:
        upds = op.seq_ore_live_split(args.ytp, (args.channel,))
    else:
        upds = op.seq_ore_sim_split(args.ytp, (args.channel,))

    levels = [op.book_build(upd, 1) for upd in upds]

    if args.graphviz:
        from extractor.tools.visualization import graph_viz
        g = graph_viz(graph)
        g.render(view=True)
    else:
        for level in levels:
            graph.callback(level, lambda frame: print(frame))
        if args.live:
            graph.stream_ctx().run_live()
        else:
            graph.stream_ctx().run()
