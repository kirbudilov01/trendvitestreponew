# YouTube Competitor Analysis Collector

This repository contains a standalone Celery-based worker service responsible for resolving and collecting YouTube channel data.

## What it does

The collector is designed to be a robust, fault-tolerant background worker. Its primary responsibilities are:
- **Resolving Channels:** Takes various inputs (channel URLs, handles like `@MrBeast`, raw channel IDs) and resolves them to a canonical YouTube Channel ID (`UC...`).
- **YouTube API Interaction:** Manages a pool of YouTube Data API keys, handles key rotation on quota errors, and implements retry/backoff logic for transient API failures.
- **State Management:** Tracks the state of each analysis run and individual channel jobs in memory (for simplicity in this version).
- **Task Queueing:** Uses Celery and Redis to process channels asynchronously, ensuring that a failure in one channel does not affect others.

## How to run it

### With Docker (Recommended)

1.  **Environment Variables:** Create a `.env` file in the project root and add your YouTube API keys:
    ```
    YT_API_KEYS=your_api_key_1,your_api_key_2,your_api_key_3
    ```

2.  **Build and Run:**
    ```bash
    docker-compose up --build
    ```
    This will start a Redis container and the `collector_worker` container. The worker will connect to Redis and wait for tasks.

### Local Development

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run Redis:** Make sure you have a Redis instance running on `localhost:6379`.

3.  **Set Environment Variables:**
    ```bash
    export REDIS_URL=redis://localhost:6379/0
    export YT_API_KEYS="your_api_key_1,your_api_key_2"
    ```

4.  **Run the Worker:**
    ```bash
    celery -A collector.celery_app worker -l info
    ```

## Integration with the Main Backend

The collector is designed to be called by a main backend service. The backend is responsible for initiating analysis runs and querying their status.

**Workflow:**

1.  **Backend starts a run:** The backend calls the `Orchestrator`'s `start_run` method, providing an `analysis_id`, `owner_id`, and a list of channel inputs.
    ```python
    from collector.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    channel_inputs = ["@MrBeast", "https://youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw"]

    result = orchestrator.start_run(
        analysis_id=123,
        owner_id=456,
        channel_inputs=channel_inputs
    )
    run_id = result["run_id"]
    ```
    This creates a `Run` and enqueues one `Job` for each unique channel input.

2.  **Backend polls for status:** The backend can periodically call `get_run_status` to check the progress of the run.
    ```python
    status = orchestrator.get_run_status(run_id)
    # { 'run_status': 'RUNNING', 'progress': 0.5, 'status_counts': {...}, ... }
    ```

3.  **Collector finalizes the run:** Once all jobs for a run are completed (with `DONE`, `FAILED`, or `NEEDS_SEARCH` status), the `Orchestrator`'s `finalize_run` method is triggered by the last job, which marks the run as `FINISHED` and calculates a final summary.
