# Dashboard
This tutorial demonstrates how easy it is to deploy the Featuremine market data stack to analyze and display market statistics for major cryptocurrencies across multiple exchanges. This demonstration utilizes several Featuremine products. First, our feed handler, `Bulldozer`, receives raw data from the exchanges and writes normalized data into our low-latency IPC (interprocess communication) bus called `Yamal`. If needed, this market data can be distributed remotely to other machines using our `Syncer` utility. From there, Featuremine's high-performance event processing library, `Extractor`, picks up the normalized data and computes trading statistics, such as opening, high, low and closing trade prices for every 10s period. Here we will be utilizing `Grafana` to display this information. Grafana needs a separate database as a backend for storing data. While it supports various databases, we chose to use `PostgreSQL` because of its wide use and simplicity.

## Prerequisites
To run this tutorial, first of all, you will need to have docker installed. Please refer to [Get Docker](https://docs.docker.com/get-docker/) link for more information.

You will also need to obtain the latest version of `Bulldozer` and `Syncer` from our website [Featuremine.com](https://www.featuremine.com) or by writing to us at <support@featuremine.com>.

## PostgreSQL setup
PostgreSQL is a free and open-source relational database management system. To set up the PostgreSQL database you can use the docker container. It is by far the simplest way to get started. However, if you prefer you can install PostgreSQL locally or use an existing installation.

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
Note, the tables in the tutorial are created by the tutorial scripts, so you will not see anything there initially.

If you would like to display a specific table, run:
```sql
SELECT * FROM table_name
```

For more information visit https://www.postgresql.org

## Grafana setup
Grafana is a multi-platform open source analytics and interactive visualization web application. It provides charts, graphs, and alerts for the web when connected to supported data sources. To deploy grafana using docker, run the following:

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=grafana -p 3000:3000 grafana/grafana
```

Now you should be able to access grafana from your browser by opening [http://localhost:3000](http://localhost:3000). On the initial login use `admin` for username and password. Select `skip` if you are still seeing login message after pressing the `login` button. Then click on `Add your first data source` link. Select `PostgreSQL` as the data source and set the following parameters.
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

First, obtain the `Bulldozer` installer (e.g. bulldozer-1.0.3-Linux-x86_64.sh ) and copy it to the root directory of the repo.

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
First, install `Yamal` which is our low-latency interprocess communication bus. On Linux you can do this by running the following:
```bash
wget https://github.com/featuremine/yamal/releases/download/v7.2.25/yamal-7.2.25-Linux-x86_64.tar.gz
tar xvzfk yamal-7.2.25-Linux-x86_64.tar.gz -C $HOME/.local/
export PATH=$PATH:$HOME/.local/bin
pip3 install yamal==7.2.25
```

On an M1 Mac run:
```bash
wget https://github.com/featuremine/yamal/releases/download/v7.2.25/yamal-7.2.25-Darwin-arm64.tar.gz
tar xvzfk yamal-7.2.25-Darwin-arm64.tar.gz -C $HOME/.local/
export PATH=$PATH:$HOME/.local/bin
pip3 install yamal==7.2.25
```

Second, install `psycopg2` that is used by the tutorial scripts.
```bash
pip3 install psycopg2
```
On Linux you might need to install the `libpq` development package, which is a dependency of `psycopg2`.

Then, install the `Bulldozer` feed handler with the self-extracting installer. On Linux run:
```bash
./bulldozer-1.0.3-Linux-x86_64.sh --user
```

On an M1 Mac run:
```bash
./bulldozer-1.0.3-Darwin-arm64.sh --user
```

Finally install `Extractor`, which is our event processing library.
```bash
pip3 install psycopg2 numpy==1.21.0 pytz pandas
wget https://github.com/featuremine/extractor/releases/download/v6.7.2/extractor-6.7.2-py3-none-manylinux_2_17_x86_64.whl
pip3 install extractor-6.7.2-py3-none-manylinux_2_17_x86_64.whl
```

### Deployment
First, run `Bulldozer` to receive market data. You can use the sample configuration provided with `Bulldozer`.
```bash
yamal-run -c ~/.local/lib/yamal/modules/bulldozer/samples/coinbase_l2_ore_ytp.ini -s main
```

You can check whether the data is being written by bulldozer by using our `yamal-stats` utility that reports statistics on the data written to yamal files.
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

Finally, we need to compute opening, high, low and closing trade prices. In this tutorial `bars2postgresql.py` script uses `Extractor` to do that. Run `bars2postgresql.py` by passing the securities and the database credentials as arguments.
```bash
python3 bars2postgresql.py --database testuser --user testuser --password testuser --host localhost --ytp ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD"
```

You should now be able to see the market data statistics and market data receive rate in the dashboard.

## Market data stack (distributed docker setup)
In this section we use two docker containers to illustrate a distributed setup. This might be useful if you have multiple consumers of the market data. To accomplish this we use `Syncer`, which synchronizes data between yamal files on different machines.

First, obtain the `Bulldozer` and `Syncer` installers and copy them to the root directory of the repo.

Then build one docker container with the feed handler and the syncer:
```bash
docker build --platform linux/amd64 -t tutotial2_1-demo -f tutorial2_1.docker .
```
and another with the the syncer and the market data statistics scripts.
```bash
docker build --platform linux/amd64 -t tutotial2_2-demo -f tutorial2_2.docker .
```

Finally, run the two docker containers:

```bash
docker run --platform linux/amd64 --add-host host.docker.internal:host-gateway -p 3333:3333 -d tutotial2_1-demo
```

```bash
docker run --platform linux/amd64 --add-host host.docker.internal:host-gateway -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser -d tutotial2_2-demo
```

At this point you should see the dashboard updating with the latest statistics.
