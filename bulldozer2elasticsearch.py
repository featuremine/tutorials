#!/usr/bin/env python3
"""
/******************************************************************************

        COPYRIGHT (c) 2022 by Featuremine Corporation.
        This software has been provided pursuant to a License Agreement
        containing restrictions on its use.  This software contains
        valuable trade secrets and proprietary information of
        Featuremine Corporation and is protected by law.  It may not be
        copied or distributed in any form or medium, disclosed to third
        parties, reverse engineered or used in any manner not provided
        for in said License Agreement except with the prior written
        authorization from Featuremine Corporation.

 *****************************************************************************/
"""

"""
 * @file bulldozer2elasticsearch.py
 * @date 20 Oct 2022
 * @brief Populate an elasticsearch database with bulldozer data rate
 */
"""
from elasticsearch import Elasticsearch
import argparse
import subprocess
import os
import time
from datetime import datetime
import signal

run = True

if __name__ == "__main__":
    def signal_handler(sig, frame):
        global run
        run = False
        print('Signal SIGINT received')
    signal.signal(signal.SIGINT, signal_handler)
   
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", help="Elasticsearch database host", required=False, default="127.0.0.1")
    parser.add_argument("--port", help="Elasticsearch database port", required=False, default="5432")
    parser.add_argument("--ytp", help="YTP file with market data in ORE format", required=True)
    args = parser.parse_args()
   
    # Wait until the YTP file is created by yamal-run
    while not os.path.exists(args.ytp):
        time.sleep(0.1)
   
    # Run yamal-stats to print the byte rate generated from market data
    proc_stats = subprocess.Popen(['yamal-stats', args.ytp, '-f', '-b'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Connect to Elasticsearch database
    es = Elasticsearch([f"http://{args.host}:{args.port}"])
   
    # Populate the byte rate each second into the database
    id = 1
    discard = 5
    while run:
        time.sleep(1)
        line = proc_stats.stdout.readline()
        if not line:
            break
        rate=line.decode('utf-8').rstrip()
        if rate and discard > 0:
            # discard first rates as they might be the first big numbers
            # from the beginning of the YTP file
            discard -= 1
            continue
        doc = {
            'rate': int(rate),
            'timestamp': datetime.now(),
        }
        res = es.index(index="bulldozer_rate", id=id, document=doc)
        id += 1

    proc_stats.send_signal(subprocess.signal.SIGINT)
    proc_stats.wait()
    proc_stats.stdout.close()
    proc_stats.stderr.close()
