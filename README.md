# Wirepas Provisioning Server

## Introduction

This is the reference implemantation of the Wirepas provisioning server. It provides an example of the server side of Wirepas
Provisioning Protocol. It must be used with the _provisioning_joining_node_ application of the SDK. Please refer to the
provisioning reference manual for further information.

## Installation

### Host dependencies

The main requirements of Provisioning Server are:

-   Python 3.7
-   Pip3 (we recommend the latest available)

### Installing from PyPi

The Provisioning Server is available from [PyPi](https://pypi.org/project/wirepas-provisioning/) and you can install the
latest stable version with:

```shell
    pip3 install wirepas-provisioning
```

If you wish to install a particular version please see the release history from PyPi.

### Installing from Github

First of all, make sure to clone the repository using the https address.

Checkout the [git tag that corresponds to the release version](https://github.com/wirepas/wm-provisioning/releases) you want
to install and install the package with:

```shell
    pip3 install .
```

If you want to develop or patch a bug under your local environment, you can install the package in development mode through:

```shell
    pip3 install -e .
```

When installed in development mode, changes to the source files will be immediately visible.

## Usage

Once installed, the Provisioning Server will be accessible through wm-prov-srv.
It requires few parameters to run:
 - The Mqtt broker credentials the server will connect to.
 - A configuration file containing a list of nodes authorized to provision and their associated data. An example is available
[here](examples/provisioning_config.yml)

```shell
wm-prov-srv --host my_server.com \
            --port 8883 \
            --username my_username \
            --password my_password \
            --config examples/provisioning_config.yml
```

## Building and running over Docker

Docker allows application to run on a sandbox containing all the dependencies needed to run and execute them.
If you are not familiar with Docker, please refer to the official documentation at [docker.com](https://www.docker.com).

### Dockerhub

Provisioning server builds are available from dockerhub under the
[Provisioning server registry](https://hub.docker.com/r/wirepas/provisioning-server).

The latest tag points to the current stable release, whereas the edge tag points to the top of master. The latest tag is built
automatically at dockerhub whenever this repository is tagged. The edge tag is built after each single merge into master.

To pull the Provisioning server image from dockerhub use:

```shell
    docker pull wirepas/provisioning-server:latest
    docker pull wirepas/provisioning-server:<tag>
```

### Running with docker

As the container will have no access to your local environment, you will have o propagate the input parameters through env
variables and by mounting the _provisioning_config.yml_ file inside the container.

To run it with docker type:

```shell
    docker run -v $(pwd)/examples/provisioning_config.yml:/home/wirepas/wm-provisioning/vars/settings.yml \
               -e WM_SERVICES_MQTT_HOSTNAME=my_server.com  \
               -e WM_SERVICES_MQTT_PORT=8883 \
               -e WM_SERVICES_MQTT_USERNAME=username \
               -e WM_SERVICES_MQTT_PASSWORD=password \
               wirepas/provisioning-server
```

### Running with compose

To run the Provisioning Server using docker compose, you will have to modify the [template](docker/docker-compose.yml) file to fit your environment.
Environment must be customized to fit your mqtt broker parameters:

```yml
environment:
  WM_SERVICES_MQTT_HOSTNAME: "my_server.com"
  WM_SERVICES_MQTT_PORT: "8883"
  WM_SERVICES_MQTT_USERNAME: "username"
  WM_SERVICES_MQTT_PASSWORD: "password"
```

And the path of the configuration file path must be specified. Example if your config is located in /home/user/provisioning_config.yml

```yml
volumes:
    - /home/user/provisioning_config.yml:/home/wirepas/wm-provisioning/vars/settings.yml
```


In the folder where you stored the customized file, please run:

```bash
docker-compose up -d
```
You can see the logs with:

```bash
docker-compose logs
```
And stop the gateway with:

```bash
docker-compose down
```

The tag to use for the provisioning server images can be chosen when invoking the docker-compose (by default it is latest tag).

```bash
PROV_SRV_TAG=edge docker-compose up -d
```

### Building the image locally

To build the image locally in the root of the repo type:

```shell
    docker build -f docker/Dockerfile -t provisioning-server .
```

Alternatively you can also build using the docker-compose.yml present in
the root of the directory:

```shell
    docker-compose -f docker/docker-compose.yml  build
```

## License

Licensed under the Apache License, Version 2.0.