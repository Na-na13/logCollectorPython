# Log Parser Service: Specification and Implementation Guide

This document specifies the HTTP service inside the `evolog-parser` Docker image, which EvoMaster's log collector talks to. It is meant as a working reference for implementing the service in the parser repository. The overall design and the reasons behind it are in [DESIGN.md](DESIGN.md); this document covers only the parser side.

> The terms **MUST**, **SHOULD** and **MAY** mark what EvoMaster relies on (MUST), what is strongly recommended (SHOULD), and what is optional (MAY).

## Contents

1. [Role of the service](#1-role-of-the-service)
2. [What changes compared to the current parser](#2-what-changes-compared-to-the-current-parser)
3. [Container contract](#3-container-contract)
4. [Endpoint: `GET /health`](#4-endpoint-get-health)
5. [Endpoint: `POST /parse`](#5-endpoint-post-parse)
6. [Endpoint: `POST /reset` (optional)](#6-endpoint-post-reset-optional)
7. [Errors](#7-errors)
8. [Drain state and template IDs](#8-drain-state-and-template-ids)
9. [Preprocessing log lines](#9-preprocessing-log-lines)
10. [Concurrency and performance](#10-concurrency-and-performance)
11. [Logging inside the service](#11-logging-inside-the-service)
12. [Docker image](#12-docker-image)
13. [Implementation choices](#13-implementation-choices)
14. [Testing the service](#14-testing-the-service)
15. [Acceptance checklist](#15-acceptance-checklist)

---

## 1. Role of the service

The service turns log lines into Drain log templates. That is its only job.

```
EvoMaster (LogCollector)                       parser service
        │                                            │
        │  GET /health  (until 200)                  │
        │ ──────────────────────────────────────────►│
        │                                            │
        │  for every test evaluation:                │
        │  POST /parse {lines: [...]}                │
        │ ──────────────────────────────────────────►│  feed each line into the
        │                                            │  Drain model of its source
        │  200 {templates: [...]}                    │
        │ ◄──────────────────────────────────────────│
```

The service does **not**:

- talk to Docker or read container logs (EvoMaster does that),
- know anything about tests, time windows or the SUT,
- read or write files for exchanging data,
- read configuration from environment variables set by EvoMaster.

One container instance serves one EvoMaster run. It is started by Testcontainers at the beginning of the run and removed at the end. The Drain state lives in memory for that time.

---

## 2. What changes compared to the current parser

| Current `parser.py` | New service |
|---|---|
| Reads `"<startMs> <endMs>"` requests from stdin, replies `OK` / `ERROR` on stdout | HTTP server with `GET /health` and `POST /parse` |
| Fetches container logs through the Docker SDK and the mounted `/var/run/docker.sock` | Receives the lines in the request body. **Remove** the Docker SDK dependency and all log-fetching code. |
| Filters containers with the `COMPOSE_PROJECT` environment variable | **Remove.** EvoMaster selects the containers. |
| Writes `templates/unique-templates.txt` and log copies under `logs/` | **Remove.** Results go in the HTTP response; nothing is written to disk. |
| Reports unique/new templates | Reports **every** template matched by the request's lines |
| Runs Drain on the time window's logs | Keeps one long-lived, incremental Drain model per source |

Keep the Drain configuration and any preprocessing that worked well for template quality (see [§9](#9-preprocessing-log-lines)).

---

## 3. Container contract

| Item | Requirement |
|---|---|
| Port | The HTTP server **MUST** listen on port **8080** inside the container. EvoMaster exposes this port; Testcontainers maps it to a random free host port. |
| Bind address | The server **MUST** bind to `0.0.0.0`, not `127.0.0.1`. A server bound to localhost inside a container cannot be reached from outside it, and `/health` will time out. |
| Startup | The server **SHOULD** start within a few seconds. Testcontainers waits for `/health` with a default timeout of 60 seconds. |
| Mounts | The container **MUST NOT** require any volume or Docker socket mount. |
| Environment | The container **MUST NOT** require any environment variable to be set. Defaults must work out of the box. |
| Image name | Published as `nanarei/evolog-parser:latest`, which is the default of the `logCollectorParserImage` option. |
| Lifetime | Runs until the container is stopped. It must not exit on its own, e.g. on EOF of stdin, which Testcontainers does not keep open. |

---

## 4. Endpoint: `GET /health`

Readiness check used by Testcontainers (`Wait.forHttp("/health")`).

| | |
|---|---|
| Request | No body |
| Response | `200 OK` once the service can accept `/parse` requests |
| Body | Not inspected by EvoMaster. A small JSON body is recommended: `{"status": "ok"}` |

- It **MUST** return `200` only when the service is really ready: the Drain library is imported, the configuration is loaded, and the server is accepting connections.
- It **SHOULD** be cheap. It is polled repeatedly during startup.

---

## 5. Endpoint: `POST /parse`

Feeds a batch of log lines into Drain and returns the templates they matched. EvoMaster calls this once after each test evaluation, so it is called thousands of times per run.

### Request

`Content-Type: application/json`, UTF-8.

```json
{
  "lines": [
    { "source": "oauth2-client", "text": "2026-11-16 10:00:01.123 INFO  [main] User 42 logged in" },
    { "source": "oauth2-client", "text": "2026-11-16 10:00:01.130 INFO  [main] User 7 logged in" },
    { "source": "oauth2-token",  "text": "2026-11-16 10:00:01.140 WARN  [io-1] Token expired for client abc" }
  ]
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `lines` | array | yes | Lines in the order they were logged. May be empty. |
| `lines[].source` | string, non-empty | yes | The component that logged the line: the Docker Compose service name, or the container name. |
| `lines[].text` | string | yes | One raw log line, without the trailing newline. May contain any Unicode. Never blank, and never ends in `\r`: the plugin drops blank lines and strips `\r\n` line endings before sending. |

Notes:

- Docker does **not** add its own timestamps: EvoMaster reads the streams without Docker's `timestamps` flag. Timestamps in `text` come from the application's own log format.
- Multi-line messages such as stack traces arrive as **separate lines**, e.g. one per `at ...` frame. Treat every line on its own.
- Unknown fields in the request **MUST** be ignored, so EvoMaster can add fields later without breaking the service.

### Response

`200 OK`, `Content-Type: application/json`.

```json
{
  "templates": [
    { "source": "oauth2-client", "id": "1", "template": "<TS> INFO [main] User <*> logged in", "count": 2 },
    { "source": "oauth2-token",  "id": "1", "template": "<TS> WARN [io-1] Token expired for client <*>", "count": 1 }
  ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `templates` | array | One entry per distinct `(source, id)` matched by this request's lines |
| `templates[].source` | string | The source, copied from the request |
| `templates[].id` | **string** | Drain cluster ID within that source. Send it as a string, even if Drain uses integers internally. |
| `templates[].template` | string | The template's **current** text, after this request was processed |
| `templates[].count` | integer ≥ 1 | Number of lines **in this request** that matched this template |

### Rules

1. **Every line goes into Drain.** Each line updates the Drain model of its source, so a line may create a new template or generalise an existing one.
2. **Return every matched template, not only new ones.** If a line matches a template that already existed before this request, that template **MUST** be in the response. EvoMaster's archive decides what is new.
3. **One entry per `(source, id)`.** If several lines in the request match the same template, return it once with the summed `count`.
4. **Report the final text.** If a template's text changes while the request is processed (e.g. the first line creates `User 42 logged in`, the second generalises it to `User <*> logged in`), report the text **after** the last line.
5. **Order.** It **SHOULD** follow the order in which each template was first matched in the request. EvoMaster does not depend on the order, but a fixed order makes tests and traces easier to read.
6. **Empty request.** `{"lines": []}` returns `{"templates": []}` with `200`.
7. **Unknown fields in the response are allowed.** EvoMaster ignores them. You **MAY** add extra fields for debugging, e.g. `"change": "created" | "updated" | "none"`.

### Worked example

Starting from a fresh service:

**Call 1**, test A:

```json
{"lines": [{"source": "svc", "text": "User 42 logged in"}]}
```
→
```json
{"templates": [{"source": "svc", "id": "1", "template": "User 42 logged in", "count": 1}]}
```

**Call 2**, test B:

```json
{"lines": [{"source": "svc", "text": "User 7 logged in"},
           {"source": "svc", "text": "Disk almost full"}]}
```
→
```json
{"templates": [{"source": "svc", "id": "1", "template": "User <*> logged in", "count": 1},
               {"source": "svc", "id": "2", "template": "Disk almost full",   "count": 1}]}
```

Cluster `1` generalised but kept its ID. `2` is new.

**Call 3**, test C:

```json
{"lines": [{"source": "svc",   "text": "User 99 logged in"},
           {"source": "other", "text": "User 99 logged in"}]}
```
→
```json
{"templates": [{"source": "svc",   "id": "1", "template": "User <*> logged in", "count": 1},
               {"source": "other", "id": "1", "template": "User 99 logged in",  "count": 1}]}
```

- `svc:1` is returned even though it already existed (rule 2).
- `other` has its own Drain model, so it starts again at ID `1`. EvoMaster tells them apart as `log:svc:1` and `log:other:1`.

---

## 6. Endpoint: `POST /reset` (optional)

| | |
|---|---|
| Request | No body |
| Response | `200 OK`, e.g. `{"status": "ok"}` |
| Effect | Drops all Drain models. The next `/parse` starts from scratch, and IDs restart. |

EvoMaster does **not** call this. It is a convenience for testing the service, so tests don't need a new container each time. You may leave it out.

---

## 7. Errors

EvoMaster treats **any status other than `200`** from `/parse` as a failed request. It logs a warning, reports no log targets for that test, and continues the search. So errors don't need to be machine-readable, but they should be useful in EvoMaster's log.

**The error body is the only diagnostic a user sees.** The plugin's warning includes the full response body, e.g. `Log parser request failed, no log targets for this test: HTTP 400: {"error": "lines[3]: 'source' must be a non-empty string"}`. The service's own stdout and stderr are hidden at EvoMaster's default log level (see [§11](#11-logging-inside-the-service)), so a stack trace printed by the service is not visible there. Put the essential information into the `error` message.

| Situation | Status | Body |
|---|---|---|
| Body is not valid JSON | `400` | `{"error": "invalid JSON: <detail>"}` |
| `lines` missing or not an array | `400` | `{"error": "'lines' must be an array"}` |
| An entry lacks `source`/`text`, or they are not strings | `400` | `{"error": "lines[3]: 'source' must be a non-empty string"}` |
| Unknown path | `404` | `{"error": "not found"}` |
| Wrong method (e.g. `GET /parse`) | `405` | `{"error": "method not allowed"}` |
| Unexpected exception while parsing | `500` | `{"error": "<exception message>"}` |

Guidelines:

- **Validate the whole request before touching Drain.** A request rejected with `400` must not leave half of its lines in the model.
- The service **MUST** keep running after an error. One bad request must not crash the process or corrupt the Drain state.
- Log the error with its stack trace to stderr (see [§11](#11-logging-inside-the-service)).

---

## 8. Drain state and template IDs

This is the part that matters most for EvoMaster, because a template's ID is what becomes the fitness target `log:<source>:<id>`.

### Requirements

1. **One model per source.** Keep a map `source → Drain model`. Create a model the first time a source appears.
2. **Incremental.** Lines are added one by one to a long-lived model. Do not rebuild or re-cluster from scratch per request. That would renumber the clusters and break ID stability.
3. **Stable IDs.** Once a cluster ID is assigned, the same kind of line **MUST** keep mapping to that ID for the rest of the container's lifetime, even when its template text generalises.
4. **IDs are never reused.** A new cluster gets a new ID.
5. **In memory only.** No persistence is needed. The state lives as long as the container does. A new EvoMaster run gets a new container and starts fresh.

### Things to watch

- **Batch-oriented Drain implementations.** If the library clusters a whole dataframe at once and numbers the clusters in that run, IDs are not stable across requests. Such a library can't be used as-is for this service. Check that the library you choose supports adding single messages to an existing model.
- **Cluster merging or eviction.** Some implementations can cap the number of clusters and evict old ones (e.g. an LRU limit). Disable eviction, or set a limit high enough never to be reached in a run; otherwise an evicted template could come back with a new ID.
- **Matching without learning.** Some libraries offer a "match only" call that does not update the model. Use the learning call (add/train); otherwise new templates are never created.

### Size

A typical run produces a few hundred to a few thousand templates per source. Memory is not a concern.

---

## 9. Preprocessing log lines

Lines arrive exactly as the SUT logged them. Without preprocessing, varying parts such as timestamps, thread names or request IDs can stop Drain from grouping similar lines, which produces many near-duplicate templates and many useless fitness targets.

Do preprocessing **in the service**, so EvoMaster stays generic. Recommended:

| Step | Why | Example |
|---|---|---|
| Strip or mask a leading timestamp | Every line has a different one | `2026-11-16 10:00:01.123 INFO ...` → `<TS> INFO ...` |
| Mask numbers, UUIDs, IPs, hex IDs | High-variance tokens | `user 42` → `user <NUM>` |
| Collapse repeated whitespace | Log layouts pad columns with spaces | `INFO  [main]` → `INFO [main]` |
| Optionally trim trailing whitespace | Spaces at the end (`\r` is already removed by the plugin) | |

Notes:

- Apply exactly the same preprocessing to every line of a source, always. Changing it mid-run changes the templates.
- Keep the **log level** (`INFO`, `WARN`, `ERROR`) in the line. A `WARN` and an `ERROR` version of the same message are different behaviour and should stay different targets.
- Masking is a trade-off. Too much masking merges different messages, too little splits one message into many templates. Reuse what worked in the current parser and tune it with real SUT logs.
- If the library has a built-in masking feature (regex masking rules), it is fine to use it instead of preprocessing yourself.

---

## 10. Concurrency and performance

- EvoMaster sends **one request at a time** and waits for the response. There is no parallel load in normal use.
- Still, protect the Drain models with a lock if the HTTP server may handle requests on several threads. Otherwise two overlapping requests (e.g. a retry after a timeout) could corrupt the model.
- **Latency matters.** `/parse` runs after every test evaluation, so its time directly adds to EvoMaster's search time. Aim for well under 100 ms for a typical request of a few dozen lines. Avoid per-request setup (re-reading configuration, creating models, importing heavy libraries).
- **Request size.** A single test may produce hundreds or thousands of lines (e.g. stack traces). Do not set a small body size limit; a few MB per request should be accepted.
- EvoMaster uses a 60-second timeout for `/parse`. If a request takes longer, EvoMaster gives up on it, but the service may still finish processing it. Another reason for the lock.

---

## 11. Logging inside the service

The plugin forwards the container's stdout and stderr to its own SLF4J logger, with the prefix `parser` (Testcontainers `Slf4jLogConsumer`). This replaces the old `logs/processbuilder-log` file.

**This output is hidden by default.** `Slf4jLogConsumer` logs both streams at INFO level, while EvoMaster's console shows only WARN and above (`core/src/main/resources/logback.xml`). The service's output is therefore for debugging only. To see it:

- run `docker logs <container>` on the parser container while EvoMaster runs, or
- lower the log level of `org.evomaster.core.extra.logcollector.LogCollector` to INFO in EvoMaster's logging configuration.

What a user does see when something goes wrong is the plugin's warning with the error response body ([§7](#7-errors)).

Guidelines:

- Write diagnostics to stderr or stdout, **unbuffered**. Both streams are treated the same, so the choice between them does not matter for EvoMaster. In Python, set `PYTHONUNBUFFERED=1` in the image or flush explicitly; otherwise messages show up late or not at all.
- Log once at startup: version, Drain settings, listening port.
- Per request, log at most one short line, e.g. number of lines, number of templates, time taken. Don't log full log lines by default; EvoMaster already writes them to its trace file when asked.
- Turn off or quiet the HTTP framework's per-request access log if it is noisy. It would add one line to EvoMaster's log per test evaluation.

---

## 12. Docker image

Checklist for the `Dockerfile`:

- [ ] Small Python base image (e.g. a `slim` variant), with the Python version pinned.
- [ ] Dependencies installed from a pinned requirements file. Remove the Docker SDK and anything that was only used for fetching logs or writing files.
- [ ] `EXPOSE 8080`.
- [ ] `ENV PYTHONUNBUFFERED=1`.
- [ ] Runs as a non-root user (recommended).
- [ ] `CMD` starts the HTTP server bound to `0.0.0.0:8080` in the foreground.
- [ ] No `VOLUME` declarations are needed.
- [ ] Builds and runs on `linux/amd64`; also consider `linux/arm64` for Apple Silicon users (`docker buildx build --platform linux/amd64,linux/arm64`).

Publishing:

- Push as `nanarei/evolog-parser:latest`, which is EvoMaster's default.
- Also pushing an explicit version tag (e.g. `:2.0.0`) is recommended. Users can then pin it through `logCollectorParserImage`, and the image can later move to an EvoMaster organisation account under the same tag.
- Until the REST version is pushed to `:latest`, EvoMaster's new code will time out on `/health`, because the old image does not serve HTTP. For local development, build the image locally under that name; Testcontainers uses a local image when one exists. Otherwise pass a different tag through `logCollectorParserImage`.

---

## 13. Implementation choices

These are left to you; the contract above is what matters.

**HTTP framework**

| Option | Notes |
|---|---|
| Python standard library (`http.server`) | No dependencies; you write routing, JSON parsing and status codes yourself. Use `ThreadingHTTPServer` plus a lock, or the plain single-threaded `HTTPServer`. |
| Flask | Small and simple, but needs a production WSGI server (e.g. `gunicorn` or `waitress`) rather than the development server. Use **one worker process**: several processes would each have their own Drain state. |
| FastAPI + uvicorn | Request validation and an automatic OpenAPI page at `/docs`. Again **one worker process**. |

Whichever you pick: **exactly one process holding the Drain state**. Multi-process servers break the shared-state requirement in a non-obvious way, because different requests would hit different Drain models.

**Drain library**

| Option | Notes |
|---|---|
| `drain3` (logpai/IBM) | Designed for streaming: adds one message at a time to a persistent model and returns the cluster ID, the current template and whether the cluster changed. Has built-in regex masking. A natural fit for [§8](#8-drain-state-and-template-ids). Check its cluster-limit setting. |
| `loglead` (used by the current parser) | Check whether its Drain can add messages incrementally to an existing model with stable IDs. If it only clusters whole batches, see the warning in [§8](#8-drain-state-and-template-ids). |
| Own implementation | Possible, but Drain has several details (similarity threshold, tree depth, parameter tokens) that are easy to get subtly wrong. |

**Suggested module layout**

```
parser/
  server.py         HTTP routing, JSON (de)serialisation, validation, error responses
  templates.py      source → Drain model map, lock, parse(lines) → template hits
  preprocess.py     line normalisation / masking
tests/
  test_templates.py   rules of §5 and §8, without HTTP
  test_server.py      status codes and JSON shapes, through HTTP
Dockerfile
requirements.txt
```

Keeping the Drain logic (`templates.py`) independent of HTTP lets you test the important rules quickly, without starting a server.

---

## 14. Testing the service

### Manual checks with `curl`

```bash
docker build -t nanarei/evolog-parser:latest .
docker run --rm -p 8080:8080 nanarei/evolog-parser:latest

curl -i http://localhost:8080/health

curl -s -X POST http://localhost:8080/parse \
     -H 'Content-Type: application/json' \
     -d '{"lines":[{"source":"svc","text":"User 42 logged in"}]}'

curl -s -X POST http://localhost:8080/parse \
     -H 'Content-Type: application/json' \
     -d '{"lines":[{"source":"svc","text":"User 7 logged in"}]}'
# expect the same id as the first call, with a generalised template

curl -i -X POST http://localhost:8080/parse -H 'Content-Type: application/json' -d 'not json'
# expect 400
```

### Automated tests to write

| # | Test | Expected |
|---|---|---|
| 1 | Empty `lines` | `200`, empty `templates` |
| 2 | One line | One template, `count` 1 |
| 3 | Same line twice in one request | One entry, `count` 2 |
| 4 | Same message twice in **separate** requests | Same `id` both times; the second response still contains it (rule 2) |
| 5 | Two variants that generalise (`User 42 …`, `User 7 …`) | Same `id`; template text contains a wildcard after the second |
| 6 | Generalisation within one request | Reported text is the final, generalised one (rule 4) |
| 7 | Same text from two sources | Two entries with different `source`; IDs are independent |
| 8 | Many different messages | All IDs distinct; none reused |
| 9 | Leading timestamps differ, message same | Same template (preprocessing works) |
| 10 | `WARN` vs `ERROR` with the same message | Different templates |
| 11 | Non-ASCII text (`ä`, emoji, CJK) | `200`; text survives the round trip |
| 12 | Invalid JSON / missing `lines` / missing `source` | `400`; Drain state unchanged (follow up with a valid call and check IDs) |
| 13 | Unknown fields in the request | Ignored, `200` |
| 14 | Large request (e.g. 5 000 lines) | `200` within a reasonable time |
| 15 | `/health` | `200` |
| 16 | `/reset` (if implemented) | After reset, a known message gets a fresh ID sequence |

### End-to-end with EvoMaster

Once the Java side is implemented, `LogCollectorDockerManualTest` in this module starts the image through Testcontainers against a running Compose project. That is the final check that the contract (port, bind address, `/health`, JSON shapes) is met.

---

## 15. Acceptance checklist

- [ ] Listens on `0.0.0.0:8080` inside the container
- [ ] `GET /health` returns `200` only when ready
- [ ] `POST /parse` accepts `{"lines":[{"source","text"}]}` and returns `{"templates":[{"source","id","template","count"}]}`
- [ ] `id` is sent as a string
- [ ] All matched templates are returned, not only new ones
- [ ] One entry per `(source, id)` with summed `count`; final template text
- [ ] One incremental Drain model per source; IDs stable and never reused for the container's lifetime
- [ ] Cluster eviction disabled or unreachable
- [ ] Invalid requests return `400` and leave Drain state unchanged
- [ ] The service keeps running after errors
- [ ] Drain access is protected by a lock; exactly one server process
- [ ] No Docker SDK, no socket or volume mounts, no required environment variables, no files written
- [ ] Unbuffered stdout/stderr; quiet per-request logging
- [ ] Image published as `nanarei/evolog-parser:latest` (plus a version tag)
