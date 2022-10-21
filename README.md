# Dashboard

# Tutorial 1
Guide to build a docker with our market data stack (bulldozer, extractor) and show it in a Grafana dashboard

## Steps

### Copy bulldozer installer to this location

Get the bulldozer installer (e.g. bulldozer-0.0.1.sh) and copy it to this location.

### Build our postgreSQL docker container

docker build -t *docker-image-tag* -f tutorial1.docker .

### Run our postgreSQL docker container 

docker run -e POSTGRES_USER=myusername -e POSTGRES_PASSWORD=mypassword -p 5432:5432 *docker-image-tag*

### Run grafana docker container

docker run -d --name=grafana -p 3000:3000 grafana/grafana

##### Config with UI

Open http://localhost:3000 on a browser. Connect to the database adding it to "Data sources". Create a new dashboard importing the configuration dashboard_cfg.json.

# Tutorial 2

Guide to build 2 docker containers with our market data stack (bulldozer, extractor) connected with the syncer component and show the data in a Grafana dashboard
