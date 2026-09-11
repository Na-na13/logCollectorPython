# EvoLog Parser Daemon

Python daemon that collects Docker container logs and extracts unique log templates using [LogLead](https://github.com/EvoTestOps/LogLead) Drain parsing. Used as a subprocess by the EvoMaster LogCollector plugin, which starts and manages the container automatically.

Communicates over stdin/stdout: receives `startMs endMs` per test, writes templates to `/app/templates/unique-templates.txt`, responds `OK` or `ERROR: <message>`.

## Build

```bash
docker build -t evolog/parser:latest .
```

## Usage

Set `LOG_COLLECTOR_PROJECT` to the name of the Docker Compose project whose logs you want to collect, then start EvoMaster normally:

```bash
export LOG_COLLECTOR_PROJECT=my-compose-project
java -cp evomaster.jar:logCollector-*.jar org.evomaster.core.Main ...
```

LogCollector starts the container, passes the project name through, and shuts it down when EvoMaster exits. If `LOG_COLLECTOR_PROJECT` is not set, logs are collected from all running containers.

The Docker Compose project name is usually the directory name of the `docker-compose.yml` file. It matches the `com.docker.compose.project` label applied automatically by `docker compose up`.

