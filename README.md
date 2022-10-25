# Dashboard

# Tutorial 1
Guide to build a docker with our market data stack (bulldozer, extractor) and show it in a Grafana dashboard

## Steps

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-0.0.1.sh) and copy it to the root of the repo.

### Copy other requirementes (This step will not be required in the future)

Copy extractor wheel and library it to this location. Copy extractor license to this location.

### Build our postgreSQL docker container

```bash
docker build -t tutotial1-demo -f tutorial1.docker .
```

### Run our postgreSQL docker container 

```bash
docker run -e POSTGRES_USER=myusername -e POSTGRES_PASSWORD=mypassword -p 5432:5432 tutotial1-demo
```

### Run grafana docker container

docker run -d --name=grafana -p 3000:3000 grafana/grafana

##### Config with UI

Open http://localhost:3000 on a browser. Use `admin` for username and password. Then select skip if you are still seeing login message. Click on `Add your first data source`. Select `PostgreSQL` as the data source. Set `Host` to your host machine's ip and port `5432`. Set `Database` field to the same name as the `POSTGRES_USER` (`myusername` in the example) and use username and password as you did when running the tutorial1 image (`myusername` and `mypassword` in the example). Set `TLS/SSL Mode` to disable. In the sidebar menu on the left, select `Dashboard/import` and upload a dashboard configuration file `dashboard_cfg.json` found in the repo.

# Tutorial 2

Guide to build 2 docker containers with our market data stack (bulldozer, extractor) connected with the syncer component and show the data in a Grafana dashboard

## Steps

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-0.0.1.sh) and copy it to this location.

### Copy syncer installer to this location

Get the bulldozer installer (e.g. bulldozer-2.1.1.sh) and copy it to this location.

### Copy other requirementes (This step will not be required in the future)

Copy extractor wheel and library it to this location. Copy extractor license to this location.

### Build our market data generator docker container

docker build -t *docker-image-tag-21* -f tutorial2_1.docker .

### Build our postgreSQL docker container

docker build -t *docker-image-tag-22* -f tutorial2_2.docker .

### Run our market data generator docker container 

docker run --add-host host.docker.internal:host-gateway *docker-image-tag-21*

### Run our postgreSQL docker container 

docker run -e POSTGRES_USER=myusername -e POSTGRES_PASSWORD=mypassword -p 5432:5432 -p 3333:3333 *docker-image-tag-22*

### Run grafana docker container

docker run -d --name=grafana -p 3000:3000 grafana/grafana

##### Config with UI

Open http://localhost:3000 on a browser. Connect to the database adding it to "Data sources". Create a new dashboard importing the configuration dashboard_cfg.json.
