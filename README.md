

<a href="https://softserve.academy/"><img src="https://s.057.ua/section/newsInternalIcon/upload/images/news/icon/000/050/792/vnutr_5ce4f980ef15f.jpg" title="SoftServe IT Academy" alt="SoftServe IT Academy"></a>

***INSERT GRAPHIC HERE (include hyperlink in image)***

# PyDataCenter5000
> PyDataCenter: Smart Monitoring and Remote Ops


**Badges will go here**

- build status
- coverage
- issues (waffle.io maybe)
- devDependencies
- npm package
- slack
- downloads
- gitter chat
- license
- etc.

[![Coverage Status](https://img.shields.io/gitlab/coverage/ita-social-projects/Forum/master?style=flat-square)](https://coveralls.io)
[![Github Issues](https://img.shields.io/github/issues/ita-social-projects/Forum?style=flat-square)](https://github.com/ita-social-projects/Forum/issues)
[![Pending Pull-Requests](https://img.shields.io/github/issues-pr/ita-social-projects/Forum?style=flat-square)](https://github.com/ita-social-projects/Forum/pulls)
[![License](http://img.shields.io/:license-mit-blue.svg?style=flat-square)](http://badges.mit-license.org)

---

## Table of Contents (Optional)

> If your `README` has a lot of info, section headers might be nice.

- [Installation](#installation)
  - [Required to install](#Required-to-install)
  - [Environment](#Environment)
  - [Clone](#Clone)
  - [Setup](#Setup)
  - [How to run local](#How-to-run-local)
  - [How to run Docker](#How-to-run-Docker)
- [Usage](#Usage)
  - [How to work with swagger UI](#How-to-work-with-swagger-UI)
  - [How to run tests](#How-to-run-tests)
  - [How to Checkstyle](#How-to-Checkstyle)
- [Documentation](#Documentation))
- [Contributing](#contributing)
  - [git flow](#git-flow)
  - [issue flow](#git-flow)
- [FAQ](#faq)
- [Support](#support)
- [License](#license)

---

## Installation

- All the `code` required to get started
- Images of what it should look like

### Required to install
* Python 3.8
* PostgreSQL 14

```shell
$ pip install -r requirements.txt
```

### Environment

Global variables backend and sample filling
Django

```properties
DEBUG=True or False #Django backend debug mode

db details
SECRET_KEY= key ... # Use rules for hashed data
PG_DB= Database name
PG_USER= Database user
PG_PASSWORD= Database user password
DB_HOST=sample filling => localhost or '127.0.0.1' # Database host
DB_PORT=sample filling => 5432 # Database port

Used by Docker
PGADMIN_DEFAULT_PASSWORD= key ... #Use rules for hashed data. Used by Docker
PGADMIN_DEFAULT_EMAIL= "user login" sample filling admin@admin.com . Used by Docker
POSTGRES_DB= database name
ENGINE= #docker-compose.dev.yml
```
Global variables frontend and sample filling

```properties
REACT_APP_BASE_API_URL= sample filling => http://localhost:8000 #Path to the backend API server
REACT_APP_PUBLIC_URL= sample filling => http://localhost:8080 #Path to the frontend visualization
```

### Clone

- Clone this repo to your local machine using `____`

### Setup

- If you want more syntax highlighting, format your code like this:
- Localhost

> update and install this package first

```shell
$ pip install -r requirements.txt
```

> now install npm and bower packages

```shell
$ sudo apt update
$ sudo apt install nodejs
$ sudo apt install npm

```

### How to run local
### Django backend server
- Setup  .env
> Setup .env
``` shell
#db details
SECRET_KEY= 'key ...'
PG_DB= sample filling => forum
PG_USER= sample filling => postgres
PG_PASSWORD= sample filling => postgres
DB_HOST=  sample filling => localhost
DB_PORT=  sample filling => 5432

PGADMIN_DEFAULT_PASSWORD= 'key ...'
PGADMIN_DEFAULT_EMAIL=  sample filling => admin@admin.com

DEBUG=True or False  
ENGINE= # docker-compose.dev.yml
POSTGRES_DB= sample filling =>  forum  # docker-compose
ALLOWED_ENV_HOST=sample filling => "http://localhost:8080" # docker-compose and settings.py
REDIS_URL= sample filling =>  redis://localhost:6379/0 #local
```
- User, run the local server on port localhost:8000
``` shell
$ python manage.py makemigrations
$ python manage.py migrate
$ python manage.py runserver
```
### Celery and Redis
Correct application operation (in terms of moderation autoapprove functionality, to be precise) requires a running Celery worker and a Redis server. The simplest way to start Redis is:

`docker run --rm -p 6379:6379 redis:7`

Docker will automatically download the image and run the Redis server with the ports exposed. Redis will be available at 127.0.0.1:6379. You should place this host and port in the environment variable REDIS_URL, which Celery uses through Django's settings.py.

Don't forget to install Celery via pip.  
```instal
pip install -r requirements.txt
```
Add in BackEnd .env
```.env 
REDIS_URL= redis://localhost:6379/0
```

The Celery worker itself needs to be started in a separate terminal (in the directory where manage.py is located) with the command:

`celery -A forum worker --loglevel=info`

On some Windows machines, there might be issues, in that case try:

`celery -A forum worker --loglevel=info -P eventlet`

### Node JS  frontend server
- Setup frontend .env
> Setup frontend .env

``` shell
REACT_APP_BASE_API_URL= sample filling => http://localhost:8000 # Path to the backend API server
REACT_APP_PUBLIC_URL= sample filling => http://localhost:8080 # Path to the frontend visualization
```

- User, run the local server on port localhost:8080 
``` shell
PORT=8080 npm start
or
PORT=8080 npm restart
```

### How to run Docker

- Setup Docker  
> Setup .env
``` shell

```
> Run Docker comands
```shell
$ docker compose build
$ docker compose up
$ docker exec -i contener-name-exemple python manage.py makemigrations
$ docker exec -i contener-name-exemple python manage.py migrate
```

> Stop Docker comands
```shell
ctrl + c
$ docker stop $(docker ps -q)
```
---

## Usage
### How to work with swagger UI
### How to run tests
- User, run test:
```shell
$ python manage.py test --settings=forum.test_setting
```
- Running tests from Docker container:
```
$ docker compose -f docker-compose.dev.yml exec api-dev python manage.py test --settings=forum.test_setting
```
- Check Test Coverage and make report (from Backend directory):
```shell
$ coverage run manage.py test --settings=forum.test_setting
$ coverage report
```
- Check Test Coverage and make report from Docker container:
```shell
$ docker compose -f docker-compose.dev.yml exec api-dev coverage run manage.py test --settings=forum.test_setting
$ docker compose -f docker-compose.dev.yml exec api-dev coverage report
```
### How to Checkstyle

---

## Documentation
- 🔃 Documentation <a href="https://github.com/ita-social-projects/____/wiki" target="_blank">PyDataCenter5000/wiki</a>.

---

## Team

> Or Contributors/People


- You can just grab their GitHub profile image URL
- You should probably resize their picture using `?s=200` at the end of the image URL.

---


## Support

Reach out to me at one of the following places!

- Website at <a href="#" target="_blank">`#`</a>
- Facebook at <a href="#" target="_blank">`#`</a>
- Insert more social links here.

---

## License

[![License](http://img.shields.io/:license-mit-blue.svg?style=flat-square)](http://badges.mit-license.org)

- **[MIT license](http://opensource.org/licenses/mit-license.php)**
- Copyright 2020 © <a href="https://softserve.academy/" target="_blank"> SoftServe IT Academy</a>.



