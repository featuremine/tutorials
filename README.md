# Dashboard

# Tutorial 1

Guide to build the docker container with our market data stack (bulldozer, extractor) and show it in a Grafana dashboard.

## Steps

### Run postgreSQL docker container 

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=postgres -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser -p 5432:5432 postgres
```

#### PostgreSQL

PostgreSQL is a database that Grafana uses as a data source for the dashboards.
If you want you can test or make some changes on the database following the next PostgreSQL steps.

#### Get PostgreSQL

```bash
sudo apt-get install postgresql
```

#### Connect to the database

```bash
psql --dbname=testuser --host=localhost --port=5432 --username=testuser --password
```

#### Useful commands

Get a list of tables:
```bash
\dt
```

Show a specific table:
```bash
SELECT * FROM table_name
```

For more information visit https://www.postgresql.org

### Run Grafana docker container

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=grafana -p 3000:3000 grafana/grafana
```

### Configure Grafana with UI

* Open http://localhost:3000 on a browser.
* Use `admin` for username and password.
* Select `skip` if you are still seeing login message.
* Click on `Add your first data source`.
* Select `PostgreSQL` as the data source and set the following parameters.
  * `Host`: `host.docker.internal:5432`.
  * `Database`: `POSTGRES_USER` (`testuser` in the example).
  * `User`: `POSTGRES_USER` (`testuser` in the example).
  * `Password`: `POSTGRES_PASSWORD` (`testuser` in the example).
  * `TLS/SSL Mode`: `disable`.
  * Click on `Save & test`.
* In the sidebar menu on the left, select `Dashboard/import` and upload the dashboard configuration file `dashboard_cfg.json` found in the repository.

#### Grafana

Grafana is a multi-platform open source analytics and interactive visualization web application. It provides charts, graphs, and alerts for the web when connected to supported data sources.

You will be able to see the graphs if you open http://localhost:3000 on a browser and open the uploaded `market-data` dashboard.

For more information visit https://grafana.com/

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-1.0.3-Linux-x86_64.sh ) and copy it to the root of the repo.

### Copy other requirementes (This step will not be required in the future)

Copy extractor wheel (e.g. extractor-6.7.1-py3-none-manylinux_2_17_x86_64.whl) to the root of the repo.

### Build the tutorial 1 docker container

```bash
docker build -t tutotial1-demo -f tutorial1.docker .
```

### Run the tutorial 1 docker container 

```bash
docker run --add-host host.docker.internal:host-gateway -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser tutotial1-demo
```

#### Run the components yourself

If you want to run each program yourself instead of just running the docker containers you can follow these next steps.

Yamal is our core library that handles YTP files and all of the components.
To install Yamal

```bash
wget https://github.com/featuremine/yamal/releases/download/v7.2.24/yamal-7.2.24-Linux-x86_64.tar.gz
tar xvzfk yamal-7.2.24-Linux-x86_64.tar.gz -C /
wget https://github.com/featuremine/yamal/releases/download/v7.2.24/yamal-7.2.24-py3-none-manylinux_2_17_x86_64.whl 
pip3 install yamal-7.2.24-py3-none-manylinux_2_17_x86_64.whl 
```

Bulldozer is a cryptocurrency feed handler that outputs the exchange feed data into a YTP file.
Install the bulldozer component with the self-extracting installer

```bash
./bulldozer-1.0.3-Linux-x86_64.sh
```

Get coinbase data into a YTP file with the sample configuration

```bash
yamal-run -c bulldozer/installation/path/samples/coinbase_l2_ore_ytp.ini -s main
```

You can check whether the data is being written by bulldozer

```bash
yamal-stats -f ore_coinbase_l2.ytp
```

To look at the actual order book updates use:

```bash
python3 ytporedump.py --ytp ore_coinbase_l2.ytp --channel ore/imnts/coinbase/BTC-USD
```

`bulldozer2postgresql.py` runs `yamal-stats` on the YTP file and populates the postgreSQL database table bulldozer_rate with the data rate.

To run `bulldozer2postgresql.py` first install psycopg2(PostgreSQL database adapter)

```bash
sudo apt-get install libpq-dev
pip3 install psycopg2
```

Run `bulldozer2postgresql.py` with the generated YTP file and the database credentials

```bash
python3 bulldozer2postgresql.py --database ${POSTGRES_USER} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host localhost --ytp ore_coinbase_l2.ytp
```

`bars2postgresql.py` populates the postgreSQL database with the market data.

`bars2postgresql.py` uses the extractor, a high-performance real-time capable alpha research platform with an easy interface for financial analytics that allows you to set up a computational graph that optimizes how your computations are executed.

To install extractor and its requirements

```bash
pip3 install psycopg2 numpy==1.21.0 pytz pandas
wget https://github.com/featuremine/yamal/releases/download/v6.7.1/extractor-6.7.1-py3-none-manylinux_2_17_x86_64.whl
pip3 install extractor-6.7.1-py3-none-manylinux_2_17_x86_64.whl
```

Run `bars2postgresql.py` with the ytp file generated by the bulldozer, the market instruments and the database credentials

```bash
python3 bars2postgresql.py --database ${POSTGRES_USER} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host localhost --ytp ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD"
```

# Tutorial 2

Guide to build the docker containers with our market data stack (bulldozer, extractor) connected with the syncer component and show the data in a Grafana dashboard.

## Steps

### Getting started

Run the PostgreSQL and Grafana docker containers following the first steps of the tutorial 1.

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-1.0.3-Linux-x86_64.sh ) and copy it to the root of the repo.

### Copy other requirementes (This step will not be required in the future)

Copy extractor wheel (e.g. extractor-6.7.1-py3-none-manylinux_2_17_x86_64.whl) to the root of the repo.

### Copy syncer installer to this location

Get the syncer installer (e.g. syncer-2.1.1.sh) and copy it to the root of the repo.

### Build our market data generator docker container

```bash
docker build -t tutotial2_1-demo -f tutorial2_1.docker .
```

### Build our docker container that populates the PostgreSQL database

```bash
docker build -t tutotial2_2-demo -f tutorial2_2.docker .
```

### Run our market data generator docker container 

```bash
docker run --add-host host.docker.internal:host-gateway tutotial2_1-demo
```

### Run our docker container that populates the PostgreSQL database

```bash
docker run --add-host host.docker.internal:host-gateway -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser -p 3333:3333 tutotial2_2-demo
```
