# Creating a Local Validation App

## Requirements
1. Membership to the following ASKAP-VAST github teams
    * Validators
    * Vast Data Admin
2. Access to the data server via `ssh ubuntu@data.vast-survey.org`
3. The latest version of Docker
4. The latest version of `poetry`. You can ensure this by running `poetry self update`

&nbsp;

## Downloading Files

### 1. Structure

Create a directory for this project.

```
mkdir validation && cd validation
```

### 2. Docker & Repository
 
In your new project directory, download the compose directory.

```
scp -rp ubuntu@data.vast-survey.org:compose/validation/ .
```

This directory will include the relevant
   Docker, database, environment, Django, and repository files. You will be able
   to run the server from this stage. If you do not require the
   `ObservationDetailView` pages, skip the data portion in the next step.

### 3. Volumes

In the project directory, create a data directory in the structure of the one found on the server (and
expected by the app). 

```
mkdir volumes && cd volumes && mkdir app && cd app && mkdir data && cd data && mkdir VAST && ln -s VAST .VAST && cd VAST && mkdir vast-data && cd vast-data && mkdir TILES && cd TILES && mkdir STOKESI_CROSSMATCHES && mkdir STOKESI_IMAGES && mkdir STOKESI_SELAVY
```

The relevant data populates the `ObservationDetailView` pages representing an
observation, i.e. each entry in the list view after you select an epoch. 

As the entirety of the data is rather large (~3.0TB), you can choose which
observations to download to your local directory. Each observation is of size
~800MB. You can list the available observations from the data server by running
`ls` on the directory of
`/mnt/data/VAST/vast-data/TILES/STOKESI_IMAGES/epoch_[#]`. For the remainder of
this documentation, we will be using `VAST_1831-12` from `epoch_31` as an example observation. 

In the `STOKESI_IMAGES` directory, download the relevant image data. 

```
cd STOKESI_IMAGES && mkdir epoch_31 && cd epoch_31 && scp ubuntu@data.vast-survey.org:/mnt/data/VAST/vast-data/TILES/STOKESI_IMAGES/epoch_31/image.i.VAST_1831-12* . && cd ../..
```

In the `STOKESI_SELAVY` directory, download the relevant `selavy` data. 

```
cd STOKESI_SELAVY && mkdir epoch_31 && cd epoch_31 && scp ubuntu@data.vast-survey.org:/mnt/data/VAST/vast-data/TILES/STOKESI_SELAVY/epoch_31/selavy-image.i.VAST_1831-12* . && cd ../..
```

In the `STOKESI_CROSSMATCHES` directory, download the relevant crossmatch data. 

```
cd STOKESI_CROSSMATCHES && mkdir epoch_31 && cd epoch_31 && scp ubuntu@data.vast-survey.org:/mnt/data/VAST/vast-data/TILES/STOKESI_CROSSMATCHES/epoch_31/VAST_1831-12* . && cd ../..
```

You also need the `validation-data` and `database-data` volumes. Note this may not be
the best method of obtaining this data. Navigate to the server via 

```
ssh ubuntu@data.vast-survey.org
```

and copy the volumes from the relevant Docker containers to a temporary
directory, then exit, via 

```
mkdir temp-copy && cd temp-copy && docker cp validation_app_1:/data/app/ . && docker cp validation_database_1:/var/lib/postgresql/data/ . && exit
```

In your home environment, navigate back to the `volumes` directory, and copy the
two volumes from the server. 

```
cd ../../../.. && scp -rp ubuntu@data.vast-survey.org:temp-copy/app/ . && cd .. && scp -rp ubuntu@data.vast-survey.org:temp-copy/data/ . 
```

Then, `ssh` to the data server again.

```
ssh ubuntu@data.vast-survey.org
```

Clear the temporary directory and exit. 

```
rm temp-copy -rf && exit
```

&nbsp;

## Modifying Docker Files

### 1. Ports

In `validation/docker-compose.yml`, under `services:app:`, add an entry

```
ports:
    - 8000:8000
```

where the first 8000 can be the port of your choosing. 

### 2. Volumes 

Under `services:app:volumes:`, change the second entry
`/mnt/data:/data/vast-survey` to 

```
validation/volumes/app/data:/data/vast-survey
```

where `validation/volumes/app/data` is the data directory created in the previous section. 

Under `services:database:volumes:`, change the entry `
database-data:/var/lib/postgresql/data` to 

```
validation/volumes/data:/data/vast-survey
```

and under `services:app:volumes:`, change the entry `validation-data:/data/app` to 

```
validation/volumes/app/app:/data/vast-survey
```


### 3. Networks

Under `services:app:networks:`, comment out `public`. 

Under
`services:app:labels:`, and `services:database:labels:`, set `traefik.enable` to `false`. 

Under
`networks:`, comment out `public: external:true`. 

This ensures the server runs
locally. 

### 4. Environment

In `validation/.env`, set `DEBUG` to `True`, and `ALLOWED_HOSTS` to `localhost`. 


&nbsp;

## Running the Server

### 1. Docker

In a terminal, navigate to the project directory, then the compose directory.
Bring the relevant containers up. 

```
cd ../../validation && docker compose up -d --build
```

You can ensure the relevant containers are up by checking for `validation-app-1`
and `validation-database-1` via `docker ps`. 

### 2. Admin

Enter the validation app container via 

```
docker exec -it validation-app-1 bash
```

where the name of the container may be different depending on the name of the
compose directory. 

Then, create a new admin user. 

```
python manage.py createsuperuser
```

Django will prompt you for a username, email, and password. After you've entered
and recorded this information, exit the container.

```
exit
```

### 3. Entry

Test that the app works by opening a browser and going to 

```
localhost:8000/admin
```

If it works, it will prompt you for the username and password created in Step 2.
Once you enter these credentials, you will be navigated to the admin screen. You
can test the app by clicking on `VIEW SITE` in the top right corner.
Congratulations, you can now test new features to the app!

To restart the server to implement any changes you've made, navigate to the
compose directory, and restart the container via 

```
docker compose down && docker compose up -d --build
```