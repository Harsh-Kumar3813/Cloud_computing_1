# Cloud-native voting application

This teaching poll has three Python services. Vote and result use Flask. Vote accepts Cats or Dogs and enqueues a list entry in Redis. Worker atomically claims an entry, commits it to PostgreSQL using a unique event ID, then acknowledges it. Results reads grouped SQL counts on page refresh. A repeated user submission is a separate ballot.

## Local demonstration

Install Docker Compose v2. In a new terminal in this directory copy .env.example to .env and replace the sample password with a local-only random value. Keep .env private. Run `docker compose up -d --build --wait`. Open http://localhost:8080 to vote and http://localhost:8081 for results. Use `docker compose ps` to see health. Use `docker compose stop` to pause without removing volumes. PostgreSQL and Redis use named volumes. Redis uses append-only persistence with a one-second fsync interval. This leaves a durability window during abrupt host failure.

## Repeatable tests

Use a fresh project prefix to avoid touching an existing database. From PowerShell set `$env:COMPOSE_PROJECT_NAME='votingauditclass'`, choose unused ports as described in PROFESSOR_CHANGE_GUIDE.md, start the stack and run `python tests/smoke.py`. For non-default ports set TEST_VOTE_URL and TEST_RESULT_URL first. Run `python tests/experiment.py --project votingauditclass --out local-results` only on that disposable project. It intentionally stops the project's DB/Redis/worker and replays a committed vote. Use a distinct project name for each independent clean run.

## Azure

The pipeline first starts the five-service Compose stack, tests the full path and recovery, publishes its measurements, then builds and pushes three BuildId tags. AKS deployment requires main and an explicitly enabled deployToAks parameter. Set environment approval checks separately in Azure DevOps. The cluster manifests use internal services in namespace voting and a PostgreSQL managed-csi PVC. The Redis AKS manifest still has ephemeral storage. Schedule a quiesced migration to durable storage before relying on the cloud queue during pod replacement. Keep the database Secret and Azure credentials outside Git.

Use separate terminals for `kubectl -n voting port-forward svc/vote 8080:80` and `kubectl -n voting port-forward svc/result 8081:80`. Verify the intended kube context first. Worker readiness indicates recent successful dependency checks. Web liveness and readiness have separate endpoints. The vote and result containers still run Flask's development server for this course demo.

See PROFESSOR_CHANGE_GUIDE.md for the title demonstration, promotion, and rollback. VALIDATION.md and docs/ORIGINAL_README.md describe the earlier version. Its tests and deployment records refer to an earlier revision. The submission's evidence folder identifies measurements for this audit. Argo CD, election identity, automated backups and public ingress are outside this implementation.
