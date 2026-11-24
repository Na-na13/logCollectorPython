# Parser Service: Development Checklist

A step-by-step checklist for implementing the parser service with Flask. Work through the phases in order. Each phase ends with a *done when* criterion and a commit, so work reaches git early.

References like "PS §8" point to sections of `PARSER_SERVICE.md`. The request and response shapes are defined in `parser-openapi.json`.

---

## Design decisions (2026-11-20)

These replace the LogLead-based plan from the first version of this checklist.

- **drain3 directly, no LogLead.** LogLead's `parse_drain` uses one module-level miner for every source. You can't give it separate models per source, and its `max_clusters = 1024` LRU cache can't be changed after import, so old templates get evicted and come back with new IDs. Both conflict with PS §8. It is also slower: about 19 ms per 28-line request, against about 1 ms for drain3 directly. That matters because EvoMaster calls `/parse` after every test evaluation.
- **One `TemplateMiner` per source**, kept in a `dict` that lives as long as the service.
- **drain3's default `TemplateMinerConfig()`**: `max_clusters = None` (no eviction), `extra_delimiters = []` (`_` doesn't split tokens), `sim_th = 0.4`, `depth = 4`. Passing the config object also stops drain3 from looking for `drain3.ini`.
- **Light, shape-based masking, not position-based.** Log layouts differ between SUTs, so each regex finds its pattern anywhere in the line. Drain already turns tokens that vary but keep the same token count into `<*>`, timestamps and correlation IDs included. Masking is needed mainly for parts whose **token count varies**: JSON payloads and quoted strings.
- **No whitespace collapsing or trimming.** drain3's `str.split()` already handles repeated and trailing whitespace.
- **Timestamps** become `<NUM>:<NUM>:<NUM>.<NUM>` through the NUM rule, so no separate `<TS>` rule is needed.
- **Stack-trace frames** (lines starting with `\t`) are skipped. `Caused by:` lines are kept.
- **IDs** are drain3's integer cluster IDs as strings (`"1"`, `"2"`, ...), so there is no `e` prefix.
- **Tests check our own code, not drain3.** Drain's clustering is the library's job and its exact templates can change with settings or versions, so no test asserts exact template text or drain3's internal behaviour. Tests check properties instead: equal or different masked output, stable IDs, counts, source separation and the response shape. Each test list is split into **Required** and **Good to have**.

---

## Phase 0: Setup

- [x] Create a branch, e.g. `rest-api`.
- [x] Create and activate a virtual environment:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```
- [x] Create `requirements.txt` with `flask`, `waitress` and `drain3`.
- [ ] Pin the versions in `requirements.txt` (currently installed: `Flask==3.1.3`, `waitress==3.0.2`, `drain3==0.9.11`).
- [x] Keep `pytest` in a separate development requirements file.
- [x] Create the layout (PS §13):
  ```
  parser/__init__.py
  parser/preprocess.py
  parser/templates.py
  parser/server.py
  tests/test_preprocess.py
  tests/test_templates.py
  tests/test_server.py
  ```
- [ ] Remove the old pieces (PS §2): the stdin loop, the Docker SDK code, `COMPOSE_PROJECT` handling, and writing files. Git history keeps the old `parser.py` for reference.
- [x] Run `pytest` once, with no tests yet, to check the setup.

**Done when** `pytest` runs. **Commit.**

---

## Phase 1: Preprocessing (`parser/preprocess.py`)

- [x] Write one function, `mask(text: str) -> str` (PS §9).
- [x] Mask with shape-based regexes, from specific to general:
  - [x] JSON objects → `<JSON>`, with the flat pattern `\{[^{}]*\}`,
  - [x] UUIDs → `<UUID>`,
  - [x] colon-separated IDs → `<ID>`,
  - [x] IPs → `<IP>`,
  - [x] hex sequences → `<SEQ>`, hex numbers → `<HEX>`,
  - [x] numbers → `<NUM>`, which also covers timestamps.
- [x] **Keep the log level** (`INFO`, `WARN`, `ERROR`).

- [x] Write tests. They check properties of `mask()` (two lines are equal or different after masking), not exact output strings.
  - **Required:**
    - [x] Two lines that differ only in their timestamp give equal results (under-masking).
    - [x] Two `validate(...)` lines with different JSON payloads give equal results (under-masking).
    - [x] The `WARN` and `ERROR` versions of the same message stay different (over-masking, PS §9).
    - [x] `validate( <JSON>, requestBody.clientType)` and `... requestBody.derefClientId)` stay different (over-masking).
  - **Good to have:**
    - [x] Non-ASCII text (`ä`, emoji, CJK) survives unchanged and doesn't raise.
    - [ ] Quoted values with spaces don't change the result. Only relevant if a `<STR>` rule is added.

Lines arrive without a trailing `\r` and are never blank, because the plugin removes both before sending (PS §5).

**Done when** the required preprocessing tests pass. **Commit.**

---

## Phase 2: Drain logic without HTTP (`parser/templates.py`)

This is the most important part (PS §8). Write it as plain Python, so it can be tested quickly without a server.

- [x] Write a class `TemplateStore` with one `threading.Lock` (PS §10), one shared `TemplateMinerConfig()` and a `miners` dict (`source → TemplateMiner`).
- [x] Write a method `parse_lines(lines) -> list[dict]`. Each line is `{"source": ..., "text": ...}`.
  - [x] If `lines` is empty, return `[]`.
  - [x] Skip stack-trace frames (text starting with `\t`).
  - [x] Create a source's miner the first time that source appears.
  - [x] Create the miner only when the source is missing: `setdefault(source, TemplateMiner(...))` builds a new miner on every line and throws it away.
  - [x] Feed each line with `miner.add_log_message(mask(text))`, one line at a time (the learning call, not `match()`).
  - [x] Count lines per `(source, cluster_id)`, in order of first appearance.
  - [x] After the loop, read each template's final text from `miner.drain.id_to_cluster[cid].get_template()`, so generalisation within the batch is reported (PS §5, rule 4).
  - [x] Return `{"source": ..., "id": str(cid), "template": ..., "count": ...}` per `(source, cluster_id)`.
  - [x] Keep the whole loop and result building inside the lock.
- [ ] Optional `/reset`: with per-source miners this is just `self.miners.clear()` under the lock (PS §6).
- [ ] Write tests (PS §14, rows 1–10). Each test creates its own `TemplateStore`, so tests don't share state. They check how `TemplateStore` handles drain3's results, never the template text itself:
  - **Required:**
    - [x] The same text from two sources gives two entries, one per source (PS §8.1). Catches a shared miner or mixed-up `miners` dict.
    - [x] The same line twice in one call gives one entry with `count` 2.
    - [x] The counts add up to the number of lines sent, minus stack-trace frames.
    - [x] An empty list returns an empty list.
    - [x] Every entry has `source`, `id`, `template` and `count`, and `id` is a string (PS §5).
  - **Good to have:**
    - [ ] Two lines that Drain merges within one call (`User 42 logged in`, `User 7 logged in`) give one entry with `count` 2, and its `template` equals the miner's current template for that id (PS §5, rule 4). Checks that the text is read after the loop, without asserting what the text is.
    - [x] Run `run.py` with the sample file **twice** against one `TemplateStore`: the second call returns the same ids. A manual smoke test with real logs.
- Not tested, because they only check drain3 itself: the exact wildcard text after generalisation, and that new messages get distinct, never reused ids.

**Done when** the required tests pass. **Commit.**

---

## Phase 3: Flask layer (`parser/server.py`)

- [x] Create `app = Flask(__name__)` and one shared `TemplateStore`.
- [x] `GET /health` returns `{"status": "ok"}` with `200`.
- [ ] `POST /parse`:
  - [x] Read the body with `request.get_json(silent=True)`. If the result is `None`, return `400` with `{"error": "invalid JSON"}`.
  - [x] Validate **the whole request first**, before touching Drain (PS §7):
    - [x] `lines` exists and is a list,
    - [x] every entry has a non-empty string `source` and a string `text`.
    - [x] Error messages name the position, e.g. `lines[3]: 'source' must be a non-empty string`.
  - [ ] Only then call `store.parse_lines(body["lines"])` and return `{"templates": [...]}` with `200`.
- [ ] Optionally add `POST /reset`, calling the store's reset (see Phase 2). EvoMaster never calls it.
- [ ] Add **JSON error handlers**, because Flask's default error pages are HTML:
  - [ ] one handler for HTTP errors (`werkzeug.exceptions.HTTPException`, which covers 400, 404 and 405), returning `{"error": e.description}` with `e.code`,
  - [ ] one handler for unexpected exceptions, returning `500` with `{"error": str(e)}` and logging the stack trace.
- [ ] Make error messages self-explanatory. The error body is the only diagnostic EvoMaster users see (PS §7).
- [ ] Replace the debug `print`s with `logging` (PS §11).
- [ ] Write tests with Flask's test client (`app.test_client()`), so no server is needed (PS §14, rows 11–16):
  - **Required:**
    - [ ] `/health` and `/parse` return the status codes and JSON shapes in `parser-openapi.json`.
    - [ ] Invalid JSON, a missing `lines`, and a bad entry each return `400` with a JSON `error` naming the problem.
    - [ ] A `400` leaves the Drain state unchanged (follow it with a valid call and check the ids).
    - [ ] Unknown fields in the request are ignored (PS §5).
    - [ ] `404` and `405` return JSON, not HTML.
  - **Good to have:**
    - [ ] Non-ASCII text survives the round trip.
    - [ ] A large request (e.g. 5 000 lines) succeeds.

**Done when** the required tests pass and the endpoints behave as specified in `parser-openapi.json`. **Commit.**

---

## Phase 4: Run it for real (without Docker)

- [ ] Start the server with a single process:
  ```bash
  waitress-serve --host 0.0.0.0 --port 8080 parser.server:app
  ```
  Waitress uses several threads, which is fine because of the lock. Never run several processes: each would have its own Drain state (PS §13).
- [ ] Run the `curl` checks from PS §14:
  - [ ] `/health` returns `200`,
  - [ ] two `/parse` calls with `User 42 logged in` and `User 7 logged in` return the same id,
  - [ ] invalid JSON returns `400` with a JSON body.
- [ ] Measure request times with realistic batch sizes, to check that parsing doesn't slow EvoMaster down.
- [ ] Optionally, paste `parser-openapi.json` into editor.swagger.io and compare it with how the server behaves.

**Done when** the `curl` checks give the expected results.

---

## Phase 5: Docker image

The current `Dockerfile` is for the old stdin daemon (`parser.py`, volumes, Docker socket) and has to be rewritten. Follow the checklist in PS §12:

- [ ] Write the `Dockerfile`:
  - [x] a slim Python base image, with the version pinned (`python:3.12-slim`),
  - [ ] `pip install -r requirements.txt` (without the development requirements),
  - [ ] copy the `parser/` package, not `parser.py`,
  - [ ] remove the `VOLUME` lines and the Docker socket comment (PS §3: no mounts),
  - [ ] `ENV PYTHONUNBUFFERED=1`,
  - [ ] `EXPOSE 8080`,
  - [ ] a non-root user,
  - [ ] `CMD` running waitress on `0.0.0.0:8080` in the foreground.
- [ ] Build the image:
  ```bash
  docker build -t nanarei/evolog-parser:latest .
  ```
- [ ] Run it and repeat the `curl` checks against the container:
  ```bash
  docker run --rm -p 8080:8080 nanarei/evolog-parser:latest
  ```
- [ ] Check that it keeps running with nothing attached (`docker run -d ...`). The old image stopped when stdin closed.

**Done when** the `curl` checks pass against the container. **Commit.**

---

## Phase 6: End-to-end check with EvoMaster

- [ ] Keep the image built locally as `nanarei/evolog-parser:latest`. Testcontainers uses a local image when one exists, so nothing needs to be published yet.
- [ ] In the EvoMaster repo, update `LogCollectorDockerManualTest` to the new `LogCollector` constructor, and run it against a running Docker Compose SUT.
- [ ] Check the templates on logs from more than one SUT. Masking that works for this SUT may over-mask or under-mask others.
- [ ] Only after that works, publish to DockerHub as `:latest` plus a version tag, e.g. `:2.0.0` (PS §12).

---

## Final check

- [ ] Go through the acceptance checklist in PS §15, item by item.

---

**Tip:** in Phases 1–3, write the required tests first. Each one checks a rule from PS §5, §7 or §8 that our own code is responsible for.
