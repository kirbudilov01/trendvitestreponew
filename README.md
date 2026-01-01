# Competitor Analysis YouTube Collector

This service is a background worker responsible for collecting and resolving YouTube channel information as part of a larger competitor analysis platform.

## Core Responsibilities

- **Asynchronous Job Processing:** Utilizes Celery and Redis to manage a queue of channel processing jobs.
- **YouTube Channel Resolution:** Takes a channel identifier (e.g., `@handle`, custom URL, channel ID) and resolves it to a stable YouTube Channel ID.
- **Fail-Soft Architecture:** The system is designed to be resilient. An error processing a single channel (a "Job") will not halt the entire analysis run. The failed job will be marked accordingly, but other jobs will continue.

## Architecture (Run/Job Model)

The service operates on a simple but effective two-level model:

- **Run:** A single, top-level analysis request. It represents a batch of channels to be processed.
- **Job:** The processing of a single YouTube channel within a Run. Each Job has its own status (`PENDING`, `PROCESSING`, `DONE`, `FAILED`).

A `Run` is considered complete only when all of its associated `Jobs` are in a terminal state (`DONE` or `FAILED`).

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Local Launch

1.  **Create an Environment File:**
    Copy the example environment file to create your own local configuration.
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`:**
    Open the `.env` file and replace `your_api_key_here` with your actual YouTube Data API key(s). You can list multiple keys separated by commas.

3.  **Build and Run the Services:**
    Use Docker Compose to build the images and start the containers.
    ```bash
    docker-compose up --build
    ```
    This will start the Redis instance and the Celery worker.

## Running Tests

To run the test suite, you can execute `pytest` inside the running `collector_worker` container.

1.  **Find the container ID:**
    ```bash
    docker ps
    ```
    Look for the container with a name like `..._collector_worker_1`.

2.  **Execute pytest:**
    ```bash
    docker exec -it <your_container_id> pytest
    ```

## Scaling

The collector can be scaled in two primary ways:

1.  **Increase Worker Concurrency:**
    In `docker-compose.yml`, you can increase the concurrency of a single worker by modifying the `-c` flag in the `command`:
    ```yaml
    command: celery -A collector.celery_app worker -Q collector -c 8 --loglevel=INFO # Increased from 4 to 8
    ```

2.  **Add More Worker Replicas:**
    For true horizontal scaling, you can add more worker containers.
    ```bash
    docker-compose up --build --scale collector_worker=3
    ```
    This will start three separate `collector_worker` containers, all processing jobs from the same queue.

## Scope Limitations

**This service does NOT integrate with any Large Language Models (LLMs) like GPT.**

Its sole responsibility is the collection, resolution, and status management of YouTube channel data. Analysis and interpretation of the data are handled by a separate layer in the platform.

## Integration with Main Backend

The main backend application is responsible for orchestrating analysis runs. The typical integration flow is as follows:

1.  **Backend Initiates a Run:** The backend creates a `Run` and determines the list of channels to be analyzed.
2.  **Backend Enqueues Jobs:** For each channel, the backend creates a `Job` and enqueues it into the `collector` Celery queue. This is done by calling the `process_channel_job` task.
3.  **Collector Processes Jobs:** The `collector_worker` picks up jobs from the queue, resolves the channel information, and updates the job status in a shared state manager (e.g., Redis or a database).
4.  **Backend Monitors Status:** The backend can monitor the status of Runs and Jobs to track progress and retrieve results once they are complete.
