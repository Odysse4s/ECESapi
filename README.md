# ECES API — Ephemeral Code Execution Sandbox

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Docker Engine](https://img.shields.io/badge/Docker-Engine%20SDK-2496ED.svg?logo=docker&logoColor=white)](https://docker-py.readthedocs.io/)
[![Prometheus](https://img.shields.io/badge/Metrics-Prometheus-E6522C.svg?logo=prometheus&logoColor=white)](https://prometheus.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade, asynchronous code execution platform that receives untrusted arbitrary code snippets in **Python**, **C**, and **JavaScript**, executes them inside isolated ephemeral Docker containers with hardware resource ceilings, and returns runtime performance metrics.

---

## Architecture Overview

```
                                      ┌────────────────────────────────────────────────────────┐
                                      │                      ECES REST API                     │
                                      │                                                        │
┌──────────┐   POST /api/v1/execute   │  ┌───────────────────┐    ┌─────────────────────────┐  │
│  Client  │ ───────────────────────▶ │  │ RequestID / Trace │ ─▶ │ Sliding-Window Rate Lim │  │
└──────────┘                          │  └───────────────────┘    └────────────┬────────────┘  │
     │                                │                                        │               │
     │  ws://.../execute/ws           │                                        ▼               │
     └──────────────────────────────▶ │                           ┌─────────────────────────┐  │
                                      │                           │   FastAPI Router / WS   │  │
                                      │                           └────────────┬────────────┘  │
                                      │                                        │               │
                                      │                                        ▼               │
                                      │                           ┌─────────────────────────┐  │
                                      │                           │   Concurrency Limiter   │  │
                                      │                           │  (Semaphore & Capacity) │  │
                                      │                           └────────────┬────────────┘  │
                                      │                                        │               │
                                      │                                        ▼               │
                                      │                           ┌─────────────────────────┐  │
                                      │                           │   Execution History     │  │
                                      │                           │   & Prometheus Metrics  │  │
                                      │                           └────────────┬────────────┘  │
                                      └────────────────────────────────────────┼───────────────┘
                                                                               │ asyncio.to_thread
                                                                               ▼
                                                          ┌────────────────────────────────────────┐
                                                          │          Docker Engine Daemon          │
                                                          │                                        │
                                                          │   ┌────────────────────────────────┐   │
                                                          │   │  Ephemeral Runner Container    │   │
                                                          │   │  • network_mode = "none"       │   │
                                                          │   │  • user = "1000:1000"          │   │
                                                          │   │  • read_only = True            │   │
                                                          │   │  • cap_drop = ["ALL"]          │   │
                                                          │   │  • no-new-privileges: true     │   │
                                                          │   │  • mem_limit = 64MB (no swap)  │   │
                                                          │   │  • pids_limit = 64 (fork bomb) │   │
                                                          │   │  • nano_cpus = 1e9 (1 core)    │   │
                                                          │   │  • tmpfs /tmp (64MB)           │   │
                                                          │   └────────────────────────────────┘   │
                                                          │                   │                    │
                                                          │       Background Memory Monitor        │
                                                          │         (stats stream thread)          │
                                                          └────────────────────────────────────────┘
```

---

## Key Features

- **Multi-Language Runtime Support**:
  - **Python 3.12** (`python:3.12-alpine`) — unbuffered interpreter execution.
  - **C (GCC 14)** (`gcc:14-bookworm`) — 2-stage execution pipeline (strict-budget compilation → sandbox execution).
  - **JavaScript (Node.js 22)** (`node:22-alpine`) — modern V8 execution.
- **Hardware-Enforced Isolation**:
  - Memory ceiling (4MB–128MB) with swap explicitly disabled (`memswap_limit == mem_limit`).
  - CPU quota capping (1 vCPU max via `nano_cpus`).
  - Read-only root filesystem with a memory-backed volatile `/tmp` scratchpad.
  - Complete network severance (`network_mode="none"`).
  - Unprivileged user execution (`user="1000:1000"`).
  - Dropped Linux capabilities (`cap_drop=["ALL"]`) and `no-new-privileges`.
  - Process table limit (`pids_limit=64`) to neuter fork bombs.
- **WebSocket Streaming**: Persistent push connection at `/api/v1/execute/ws` for interactive code runners and IDEs.
- **Execution History & Audit Trail**: In-memory ring buffer with TTL eviction for recent execution audits (`GET /api/v1/executions`).
- **Concurrency Throttling**: Bounded `asyncio.Semaphore` pool preventing server resource exhaustion and returning HTTP 429 when saturated.
- **Sliding-Window Rate Limiting**: Per-client IP sliding window with standard `Retry-After` headers.
- **Prometheus Observability**: Pre-built metric counters and histograms exposed at `/metrics`.
- **Structured Tracing**: Request correlation IDs (`X-Request-ID`) embedded into structured JSON log outputs.
- **Robust Output Truncation**: Safeguard against stdout/stderr flood attacks by truncating at 1 MiB with explicit truncation markers.

---

## Security Model Comparison

| Threat Vector | Mitigation Strategy | Enforced By |
|---|---|---|
| **Infinite Loop / Hang** | Hard wall-clock timeout (`container.wait(timeout=...)` + `SIGKILL`) | Docker Engine SDK |
| **Out-Of-Memory (OOM) Bomb** | Hard memory ceiling via cgroups, swap disabled | Kernel cgroups |
| **Fork Bomb** | `pids_limit = 64` ceiling on process table allocations | Linux kernel PID cgroup |
| **Network Breakout / SSRF** | `network_mode = "none"` completely disables network namespace | Container runtime |
| **Filesystem Tampering** | Root filesystem marked `read_only = True`; volatile `tmpfs` on `/tmp` | Mount namespace |
| **Privilege Escalation** | `user = 1000:1000`, `no-new-privileges: true`, `cap_drop = ["ALL"]` | Linux capabilities |
| **Stdout / Memory Flooding** | Stream-level byte truncation at 1 MiB with audit marker | ECES Runner |
| **Orphaned Containers** | Guarantees container destruction inside `finally` block with fallback | Runner Lifecycle Manager |

---

## Quick Start

### Prerequisites
- Python 3.12+ (or [uv](https://github.com/astral-sh/uv))
- Docker Engine / Docker Desktop running

```bash
# 1. Clone repository
git clone https://github.com/your-username/eces-api.git
cd eces-api

# 2. Install dependencies with dev extras
uv sync

# 3. Pre-pull sandbox images (recommended for low first-run latency)
docker pull python:3.12-alpine
docker pull gcc:14-bookworm
docker pull node:22-alpine

# 4. Start the server
uv run uvicorn app.main:app --reload --port 8000
```

### Docker Compose (Production Setup with Prometheus)

Run the API service alongside a pre-configured Prometheus monitoring instance:

```bash
docker compose --profile monitoring up --build -d
```

- **API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Probe**: [http://localhost:8000/health](http://localhost:8000/health)
- **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
- **Prometheus Dashboard**: [http://localhost:9090](http://localhost:9090)

---

## API Reference

### 1. `POST /api/v1/execute`
Execute arbitrary source code inside an ephemeral sandbox.

#### Request Body
```json
{
  "language": "python",
  "code": "print('Hello from ECES!')",
  "stdin": "",
  "timeout_seconds": 3.0,
  "memory_limit_mb": 64
}
```

#### Response Body (`200 OK`)
```json
{
  "execution_id": "9d023f03-68cb-4648-9b88-1bf33cbe638e",
  "status": "success",
  "exit_code": 0,
  "stdout": "Hello from ECES!\n",
  "stderr": "",
  "stdout_truncated": false,
  "stderr_truncated": false,
  "execution_time_ms": 142.5,
  "peak_memory_mb": 14.8,
  "timed_out": false
}
```

#### Status Outcomes:
- `success` — Programme finished within limits with exit code 0.
- `timeout` — Programme exceeded `timeout_seconds` and was terminated.
- `memory_limit_exceeded` — Programme was killed by kernel OOM-killer.
- `compilation_error` — Compiler (GCC) failed during code build step.
- `runtime_error` — Programme crashed or exited with a non-zero code.

---

### 2. `WS /api/v1/execute/ws`
Persistent bidirectional WebSocket connection for instant code execution without HTTP round-trip overhead.

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/execute/ws");

ws.onopen = () => {
  ws.send(JSON.stringify({
    language: "javascript",
    code: "console.log(1 + 1);",
    timeout_seconds: 2.0,
    memory_limit_mb: 64
  }));
};

ws.onmessage = (event) => {
  const result = JSON.parse(event.data);
  console.log("Result:", result.data);
};
```

---

### 3. `GET /api/v1/languages`
Lists supported execution runtimes and metadata.

#### Response (`200 OK`)
```json
{
  "languages": [
    {
      "name": "python",
      "display_name": "Python 3.12",
      "image": "python:3.12-alpine",
      "compiled": false,
      "file_extension": ".py"
    },
    {
      "name": "c",
      "display_name": "C (GCC 14)",
      "image": "gcc:14-bookworm",
      "compiled": true,
      "file_extension": ".c"
    },
    {
      "name": "javascript",
      "display_name": "JavaScript (Node.js 22)",
      "image": "node:22-alpine",
      "compiled": false,
      "file_extension": ".js"
    }
  ]
}
```

---

### 4. `GET /api/v1/executions`
Retrieve paginated execution history and audit records.

- Query parameters: `limit` (default: 20), `offset` (default: 0).
- Individual records inspectable at `GET /api/v1/executions/{execution_id}`.
- Individual records removable at `DELETE /api/v1/executions/{execution_id}`.

---

### 5. `GET /health`
Deep readiness probe inspecting Docker Engine reachability, local image caches, and execution load.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "docker_connected": true,
  "images_available": {
    "python": true,
    "c": true,
    "javascript": true
  },
  "active_executions": 0,
  "max_concurrent": 10
}
```

---

## Configuration Reference

All application parameters can be customized via environment variables prefixed with `ECES_`:

| Environment Variable | Default | Description |
|---|---|---|
| `ECES_APP_TITLE` | `ECES API` | Title displayed in OpenAPI documentation |
| `ECES_DEBUG` | `false` | Enable verbose debug logs and plain-text logging |
| `ECES_DEFAULT_TIMEOUT_SECONDS` | `5.0` | Default timeout if unspecified in request |
| `ECES_MAX_TIMEOUT_SECONDS` | `30.0` | Absolute ceiling for execution timeout |
| `ECES_DEFAULT_MEMORY_LIMIT_MB` | `64` | Default container memory limit in MiB |
| `ECES_MAX_MEMORY_LIMIT_MB` | `128` | Maximum permissible container memory limit |
| `ECES_MAX_CODE_SIZE_BYTES` | `65536` | Maximum allowed source code size (64 KiB) |
| `ECES_MAX_OUTPUT_BYTES` | `1048576` | Truncation limit for captured stdout/stderr (1 MiB) |
| `ECES_MAX_CONCURRENT_EXECUTIONS`| `10` | Maximum simultaneous containers before queuing/429 |
| `ECES_RATE_LIMIT_ENABLED` | `true` | Enable per-IP sliding window rate limiting |
| `ECES_RATE_LIMIT_REQUESTS` | `20` | Max requests permitted within sliding window |
| `ECES_RATE_LIMIT_WINDOW_SECONDS`| `60` | Duration of rate limiting window in seconds |
| `ECES_HISTORY_ENABLED` | `true` | Retain execution logs in-memory for audits |
| `ECES_HISTORY_MAX_ENTRIES` | `1000` | Maximum history items before FIFO eviction |
| `ECES_HISTORY_TTL_SECONDS` | `3600` | Expiration time for history items |

---

## Benchmark Profile

Measurements recorded on an AMD Ryzen 7 / 32 GB RAM host with local container caches pre-warmed:

| Language | Workload | Latency (ms) | Peak Memory (MiB) | Outcome |
|---|---|---|---|---|
| **Python** | `print('Hello World')` | `~280 ms` | `11.8 MiB` | `success` |
| **Python** | `while True: pass` (timeout=2s) | `2015 ms` | `10.2 MiB` | `timeout` |
| **Python** | Allocate 500MB (limit=32MB) | `~420 ms` | `32.0 MiB` | `memory_limit_exceeded` |
| **C** | `printf("Hello World\n");` | `~690 ms` | `6.4 MiB` | `success` (compiled + run) |
| **C** | Invalid syntax | `~410 ms` | `5.1 MiB` | `compilation_error` |
| **JavaScript**| `console.log('Hello');` | `~260 ms` | `17.4 MiB` | `success` |

---

## Running Test Suites

```bash
# Run unit tests (runs in < 1s, requires no Docker daemon)
uv run pytest -m "not integration" -v

# Run full integration test suite (requires active Docker Engine)
uv run pytest -v

# Run adversary & isolation security test suite
uv run pytest tests/test_security.py -v

# Run code linter and formatter validation
uv run ruff check app tests
```

---

## License

Distributed under the [MIT License](LICENSE).
