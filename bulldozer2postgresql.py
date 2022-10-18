#!/usr/bin/python3

import psycopg2
import subprocess
import os
import time
import signal

src_dir = os.path.dirname(os.path.realpath(__file__))

conn = psycopg2.connect(database="myusername", user = "myusername", password = "mypassword", host = "127.0.0.1", port = "5432")

print("Opened database successfully")

cur = conn.cursor()
cur.execute("SELECT * from temperature")
rows = cur.fetchall()
for row in rows:
   print (f"temp_id = {row[0]}")
   print (f"timestamp = {row[1]}")
   print (f"temp = {row[2]}")

cur.execute("""
CREATE TABLE IF NOT EXISTS bulldozer_rate
(
   rate_id SERIAL PRIMARY KEY NOT NULL,
   timestamp TIMESTAMP DEFAULT current_timestamp NOT NULL,
   rate INT NOT NULL
)
""")
 
# commit the changes
conn.commit()

my_env = os.environ.copy()
my_env["PATH"] = os.path.join(src_dir, 'build', 'dependencies', 'build', 'yamal') + ":" + my_env["PATH"]
my_env["YAMALCOMPPATH"] = os.path.join(src_dir, 'build', 'dependencies', 'build', 'bulldozer', 'package', 'lib', 'yamal', 'modules')

proc_comp = subprocess.Popen(['yamal-run', '-c', os.path.join(src_dir, 'build', 'dependencies', 'src', 'bulldozer', 'samples', 'coinbase_l2_ore_ytp.ini'), '-s', 'main'],
                        env=my_env)

proc_stats = subprocess.Popen(['yamal-stats', 'ore_coinbase_l2.ytp', '-f', '-b'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=my_env)
run = True
def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    run = False

signal.signal(signal.SIGINT, signal_handler)

discard = 4
while run:
   time.sleep(1)
   line = proc_stats.stdout.readline()
   if not line:
      break
   rate=line.decode('utf-8').rstrip()
   if rate and discard > 0:
      discard -= 1
      continue
   print(rate)
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
