# Changes from the supplied source

- vote/app.py adds a per-submission UUID, a Redis socket timeout and process liveness.
- worker/worker.py atomically reserves one queued vote. It preserves a legacy message's assigned ID across retries, adds a nullable unique event_id column to existing rows, commits before acknowledging, and suppresses duplicate inserts.
- result/app.py exposes independent process liveness. vote/ui.py and result/ui.py read the escaped POLL_TITLE setting.
- docker-compose.yml publishes web ports on loopback, persists Redis append-only files in a named volume and supplies POLL_TITLE.
- The Vote and Result Kubernetes liveness checks use /livez; readiness remains dependency-aware.
- tests/acceptance.py exercises a disposable Compose project. The Azure pipeline runs it before image publication and watches test/Compose changes on main.
- The professor runbook covers demonstration, change control, verification and lifecycle.
- When adopting the new Redis volume on an existing installation, stop submissions, drain or back up the old queue and verify the data before switching volumes. The test project was isolated. No deployment of these fixes to Azure is evidenced.

