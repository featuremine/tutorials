# Dashboard
Graphic visualization of market data

## Basic configuration

### Run postgreSQL docker container 

docker run --name postgresql -e POSTGRES_USER=myusername -e POSTGRES_PASSWORD=mypassword -p 5432:5432 -v /data:/var/lib/postgresql/data -d postgres

#### setup the database

psql --dbname=myusername --username=myusername --host=localhost --port=5432
myusername=# CREATE TABLE temperature(temp_id SERIAL PRIMARY KEY, timestamp TIMESTAMP DEFAULT current_timestamp, temp INT NOT NULL );

##### Insert new value

myusername=# INSERT INTO temperature(temp) VALUES (10);

##### List tables and show values

myusername=# \dt

myusername=# SELECT * from temperature;

### Run grafana docker container

docker run -d --name=grafana -p 3000:3000 grafana/grafana

##### Config with UI

Open http://localhost:3000 on a browser. Connect to the database adding it to "Data sources". Create a new dashboard with the temperature table.
