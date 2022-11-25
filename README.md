# Dashboard
This tutorial demonstrates how easy it is to deploy Featuremine market data stack to analyse and display market statistics for major cryptocurrencies across multiple exchanges. This demostration utilizes several Featuremine products. First, our feed handler, `Bulldozer`, receives raw data from the exchanges and writes normalized data into our low-latency IPC (interprocess communication) bus called `Yamal`. If needed, this market data can be distributed remotely to other machines using our `Syncer` utility. From there, Featuremine time-series analytics library, `Extractor`, picks up the normalized data and computes trading statistics, such as openning, high, low and closing trade prices for every 10s period. Here we will be utilizing `Grafana` to display this information. Grafana needs a separate database as a backend for storing data. While it supports various databases, we chose to use `PostgreSQL` because of its wide use and simplicity.

## Prerequisites
To run this tutorial, first of all, you will need to have docker installed. Please refer to [Get Docker](https://docs.docker.com/get-docker/) link for more information.

You will also need to obtain the latest version of `Bulldozer` and `Syncer` from our website [Featuremine.com](https://www.featuremine.com) or by wrting to us at <support@featuremine.com>.

## PostgreSQL setup
PostgreSQL is a free and open-source relational database management system. To set up the PostgreSQL database you can use the docker container. It is by far the simples way to get started. However, if you prefer you can install PostgreSQL locally or use an existing installation.

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=postgres -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser -p 5432:5432 postgres
```

### Useful SQL commands
To test your database connection you can run the following command:

```bash
psql --dbname=testuser --host=localhost --port=5432 --username=testuser --password
```

Then you can run the following to get a list of tables:
```bash
\dt
```
Note, the tables in the tutorial are created by the tutorial scripts, so you will not see anything there initally.

If you would like to display a specific table, run:
```bash
SELECT * FROM table_name
```

For more information visit https://www.postgresql.org

## Grafana setup
Grafana is a multi-platform open source analytics and interactive visualization web application. It provides charts, graphs, and alerts for the web when connected to supported data sources. To deploy grafana using docker, run the following:

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=grafana -p 3000:3000 grafana/grafana
```

Now you should be able to access grafana from your browser by openning [http://localhost:3000](http://localhost:3000). On the initial login use `admin` for username and password. Select `skip` if you are still seeing login message after pressing the `login` button. Then click on `Add your first data source` link. Select `PostgreSQL` as the data source and set the following parameters.
  * Enable as default
  * `Host`: `host.docker.internal:5432`.
  * `Database`: `POSTGRES_USER` (`testuser` in the example).
  * `User`: `POSTGRES_USER` (`testuser` in the example).
  * `Password`: `POSTGRES_PASSWORD` (`testuser` in the example).
  * `TLS/SSL Mode`: `disable`.
Then click on `Save & test`.

Finally, in the sidebar menu on the left, select `Dashboard/import` and upload the dashboard configuration file `dashboard_cfg.json` found in the repository.

For more information visit https://grafana.com/

## Market data stack (single docker setup)
In this section we use a single docker container to deploy the Featuremine market data stack. 

First obtain the `Bulldozer` installer (e.g. bulldozer-1.0.3-Linux-x86_64.sh ) and copy it to the root directory of the repo.

Then, build the docker container from the docker file
```bash
docker build --platform linux/amd64 -t tutotial1-demo -f tutorial1.docker .
```
Finally run the container, which will deploy the stack.
```bash
docker run --platform linux/amd64 --add-host host.docker.internal:host-gateway -d -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser tutotial1-demo
```

You should now be able to see the market data statistics and market data receive rate in the dashboard.

## Market data stack (local setup)
In this section we help you familiarize yourself with our market data stack by walking you through installation and deployment of various tools directly on your local machine.

### Installation
First install `Yamal` which is our low-latency interprocess communication bus.
```bash
pip3 install yamal==7.2.25 
```

Then install `psycopg2` that is used by the tutorial scripts.
```bash
pip3 install psycopg2
```
On Linux you might need to install `libpq` development package, which is a dependency of `psycopg2`.

Finally, install the bulldozer component with the self-extracting installer. On Linux run:
```bash
./bulldozer-1.0.3-Linux-x86_64.sh --user
```

On an M1 Mac run:
```bash
./bulldozer-1.0.3-Darwin-arm64.sh --user
```

### Market data
First run `Bulldozer` to receive market data. You can use the sample configuration provided with `Bulldozer`.
```bash
yamal-run -c ~/.local/lib/yamal/modules/bulldozer/samples/coinbase_l2_ore_ytp.ini -s main
```

You can check whether the data is being written by bulldozer by using our `yamal-stats` utility that reports statistics on the data written to yamal file.
```bash
yamal-stats -f ore_coinbase_l2.ytp
```

If you would like to look at the actual order book updates that are being written to yamal, use:
```bash
python3 ytporedump.py --ytp ore_coinbase_l2.ytp --channel ore/imnts/coinbase/BTC-USD
```

Next, run `bulldozer2postgresql.py` script which runs `yamal-stats` on the yamal file and writes data rate to the PostgreSQL database table bulldozer_rate. We can use it to monitor `Bulldozer` performance from the dashboard. Make sure to pass database credentials as command line arguments.
```bash
python3 bulldozer2postgresql.py --database testuser --user testuser --password testuser --host localhost --ytp ore_coinbase_l2.ytp
```


`bars2postgresql.py` uses the extractor, a high-performance real-time capable alpha research platform with an easy interface for financial analytics that allows you to set up a computational graph that optimizes how your computations are executed.

To install extractor and its requirements

```bash
pip3 install psycopg2 numpy==1.21.0 pytz pandas
wget https://github.com/featuremine/extractor/releases/download/v6.7.1/extractor-6.7.1-py3-none-manylinux_2_17_x86_64.whl
pip3 install extractor-6.7.1-py3-none-manylinux_2_17_x86_64.whl
```

Run `bars2postgresql.py` with the ytp file generated by the bulldozer, the market instruments and the database credentials

// had to change env variables to testuser, not sure if its worth it to use env variables for this step on the wiki
```bash
python3 bars2postgresql.py --database testuser --user testuser --password testuser --host localhost --ytp ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD"
```

NOTES ON BARS:
- ETH-BTC bars look off

# Tutorial 2

Guide to build the docker containers with our market data stack (bulldozer, extractor) connected with the syncer component and show the data in a Grafana dashboard.

## Steps

### Getting started

Run the PostgreSQL and Grafana docker containers following the first steps of the tutorial 1.

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-1.0.3-Linux-x86_64.sh ) and copy it to the root of the repo.

### Copy syncer installer to this location

Get the syncer installer (e.g. syncer-2.1.3.sh) and copy it to the root of the repo.

### Build our market data generator docker container

```bash
docker build --platform linux/amd64 -t tutotial2_1-demo -f tutorial2_1.docker .
```

### Build our docker container that populates the PostgreSQL database

```bash
docker build --platform linux/amd64 -t tutotial2_2-demo -f tutorial2_2.docker .
```

### Run our market data generator docker container 

```bash
docker run --platform linux/amd64 --add-host host.docker.internal:host-gateway -p 3333:3333 -d tutotial2_1-demo
```

### Run our docker container that populates the PostgreSQL database

```bash
docker run --platform linux/amd64 --add-host host.docker.internal:host-gateway -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser -d tutotial2_2-demo
```

#### Run the components yourself

The syncer is a component that synchronizes a YTP file in 2 different locations connected over TCP. It consists of two modes: 
* The source mode will broadcast the specified local YTP file's contents over a TCP connection.
* The sink mode will listen to a TCP Host and Port for YTP messages coming from a source and sync them to the specified local YTP file.

After you run the bulldozer component as described in the first tutorial you can synchronize the file into another location with the syncer.
Run a syncer source instance with the provided configuration file `syncer-source.ini`. You may need to change the configuration, for example the location of the file, the TCP host or port.

#Install steps were missing. Unless used with sudo, it will not unpack without user, so its either this or sudo and no --user
```bash
./syncer-2.1.3-Linux-x86_64.sh --user
```

Run a syncer sink instance on the other end where you want to duplicate the file with the provided configuration file `syncer-sink.ini`. Again the configuration may need to be changed. how can it be changed, what should i look for?

```bash
yamal-run -m syncer -o syncer --config syncer-sink.ini --section main
```

Run sink first, sink is server, source will crash if server is not ready, this is kind of confusing, source should be the server and sink should connect to it, it is currently the other way around

```bash
yamal-run -m syncer -o syncer --config syncer-source.ini --section main
```

Now you can run the bulldozer component to generate the YTP file and the scripts `bulldozer2postgresql.py` and `bars2postgresql.py` described in the first tutorial with the YTP file duplicated by the syncer. again, how can it be changed, what should i look for?