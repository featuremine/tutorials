# Dashboard

# Tutorial 1
Guide to build a docker with our market data stack (bulldozer, extractor) and show it in a Grafana dashboard

## Steps

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-0.0.1.sh) and copy it to the root of the repo.

### Copy other requirementes (This step will not be required in the future)

Copy extractor wheel and library it to the root of the repo. Copy extractor license it to the root of the repo.

### Build our postgreSQL docker container

```bash
docker build -t tutotial1-demo -f tutorial1.docker .
```

### Run our postgreSQL docker container 

```bash
docker run -e POSTGRES_USER=myusername -e POSTGRES_PASSWORD=mypassword -p 5432:5432 tutotial1-demo
```

### Run grafana docker container

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=postgres -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testuser -p 5432:5432 postgres
```

you can test connection to the database as follow
```bash
psql --dbname=testuser --host=localhost --port=5432 --username=testuser --password
```

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=grafana -p 3000:3000 grafana/grafana
```

```bash
yamal-run -c bulldozer/installation/path/samples/coinbase_l2_ore_ytp.ini -s main
```

you can check whether data is being written by bulldozer
```bash
yamal-stats -f ore_coinbase_l2.ytp
```

to look at the actual order book updates use

```bash
python3 ytporedump.py --ytp ore_coinbase_l2.ytp --channel ore/imnts/coinbase/BTC-USD
```

```bash
python3 bulldozer2postgresql.py --database testuser --user testuser --password testuser --ytp ore_coinbase_l2.ytp --host localhost --port 5432
```

```bash
python3 bars2postgresql.py --ytp ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD" --database testuser --user testuser --password testuser --host localhost --port 5432
```



##### Configure with UI

* Open http://localhost:3000 on a browser.
* Use `admin` for username and password.
* Select `skip` if you are still seeing login message.
* Click on `Add your first data source`.
* Select `PostgreSQL` as the data source and set the following parameters.
  * `Host`: `host.docker.internal:5432`.
  * `Database`: `POSTGRES_USER` (`myusername` in the example).
  * `User`: `POSTGRES_USER` (`myusername` in the example).
  * `Password`: `POSTGRES_PASSWORD` (`mypassword` in the example).
  * `TLS/SSL Mode`: `disable`.
  * Click on `Save & test`.
* In the sidebar menu on the left, select `Dashboard/import` and upload the dashboard configuration file `dashboard_cfg.json` found in the repository.

# Tutorial 2

Guide to build 2 docker containers with our market data stack (bulldozer, extractor) connected with the syncer component and show the data in a Grafana dashboard

## Steps

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-0.0.1.sh) and copy it to the root of the repo.

### Copy syncer installer to this location

Get the syncer installer (e.g. syncer-2.1.1.sh) and copy it to the root of the repo.

### Copy other requirementes (This step will not be required in the future)

Copy extractor wheel and library it to the root of the repo. Copy extractor license it to the root of the repo.

### Build our market data generator docker container

```bash
docker build -t tutotial2_1-demo -f tutorial2_1.docker .
```

### Build our postgreSQL docker container

```bash
docker build -t tutotial2_2-demo -f tutorial2_2.docker .
```

### Run our market data generator docker container 

```bash
docker run --add-host host.docker.internal:host-gateway tutotial2_1-demo
```

### Run our postgreSQL docker container 

```bash
docker run -e POSTGRES_USER=myusername -e POSTGRES_PASSWORD=mypassword -p 5432:5432 -p 3333:3333 tutotial2_2-demo
```

### Run grafana docker container

```bash
docker run --add-host host.docker.internal:host-gateway -d --name=grafana -p 3000:3000 grafana/grafana
```

##### Configure with UI

* Open http://localhost:3000 on a browser.
* Use `admin` for username and password.
* Select `skip` if you are still seeing login message.
* Click on `Add your first data source`.
* Select `PostgreSQL` as the data source and set the following parameters.
  * `Host`: `host.docker.internal:5432`.
  * `Database`: `POSTGRES_USER` (`myusername` in the example).
  * `User`: `POSTGRES_USER` (`myusername` in the example).
  * `Password`: `POSTGRES_PASSWORD` (`mypassword` in the example).
  * `TLS/SSL Mode`: `disable`.
  * Click on `Save & test`.
* In the sidebar menu on the left, select `Dashboard/import` and upload the dashboard configuration file `dashboard_cfg.json` found in the repository.
