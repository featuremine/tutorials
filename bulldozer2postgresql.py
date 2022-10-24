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
 * @file bulldozer2postgresql.py
 * @date 20 Oct 2022
 * @brief Populate a PostgreSQL database with bulldozer data rate
 */
"""
import psycopg2
import argparse
import subprocess
import os
import time
import signal

run = True

if __name__ == "__main__":
    def signal_handler(sig, frame):
        global run
        run = False
        print('Signal SIGINT received')
    signal.signal(signal.SIGINT, signal_handler)
   
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", help="postgreSQL database name", required=True)
    parser.add_argument("--user", help="postgreSQL user name", required=True)
    parser.add_argument("--password", help="postgreSQL database password", required=False, default="")
    args = parser.parse_args()

    # Run the bulldozer component to get crypto market data into YTP file
    cfg_file = os.path.join(os.sep, 'usr', 'local', 'lib', 'yamal', 'modules', 'bulldozer', 'samples', 'coinbase_l2_ore_ytp.ini')
    proc_comp = subprocess.Popen(['yamal-run', '-c', cfg_file, '-s', 'main'])
   
    # Wait until the YTP file is created by yamal-run
    while not os.path.exists('ore_coinbase_l2.ytp'):
        time.sleep(0.1)
   
    # Run yamal-stats to print the byte rate generated from market data
    proc_stats = subprocess.Popen(['yamal-stats', 'ore_coinbase_l2.ytp', '-f', '-b'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Connect to PostgreSQL database
    tries = 10
    while True:
        try:
            conn = psycopg2.connect(database = args.database, user = args.user, password = args.password, host = "127.0.0.1", port = "5432")
            break
        except psycopg2.OperationalError as e:
            if tries > 0:
                tries -= 1
            else:
                proc_comp.send_signal(subprocess.signal.SIGINT)
                proc_comp.wait()
                proc_stats.send_signal(subprocess.signal.SIGINT)
                proc_stats.wait()
                proc_stats.stdout.close()
                proc_stats.stderr.close()
                raise
        time.sleep(1)
    cur = conn.cursor()
   
    # Create database table to store the byte rate generated from market data
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bulldozer_rate
    (
        rate_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        rate INT NOT NULL
    )
    """)
    conn.commit()
   
    # Populate the byte rate each second into the database
    discard = 4
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
        cur.execute(f"""
        INSERT INTO bulldozer_rate (rate) VALUES
        ({rate})
        """)
        conn.commit()

    conn.close()
    proc_comp.send_signal(subprocess.signal.SIGINT)
    proc_comp.wait()
    proc_stats.send_signal(subprocess.signal.SIGINT)
    proc_stats.wait()
    proc_stats.stdout.close()
    proc_stats.stderr.close()
