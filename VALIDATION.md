# Local validation — 1 November 2026

- Docker Desktop engine: 29.7.2.
- Three application images built successfully.
- Redis initially failed with an exec-format error. Removing this project's failed Redis container and cached Redis image, then downloading it again, resolved the error.
- Vote and results health endpoints: HTTP 200.
- Submitted one Cats and one Dogs vote through HTTP POST.
- Results returned two processed votes and 50% per choice.
- Containers left running for the student demo.
- Browser visual inspection and Azure deployment have not been performed in this validation.

Open http://localhost:8080 to vote and http://localhost:8081 for results. The two test votes remain in the local database.

On this Windows machine, an empty C:\Windows\System32\docker file masks the actual Docker executable. Use the following PowerShell command from the project folder when needed:

```powershell
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" compose ps
```

To stop the project while preserving votes, replace `ps` with `down`. Do not use `down -v` unless you intend to delete the sample database volume.

At the time of this local check, GitHub publishing and Azure setup were pending. Later cloud validation is recorded below. Argo CD remains optional Phase 2.

Follow-up: set the worker Redis socket read timeout to 10 seconds, longer than its 5-second blocking queue wait. Rebuilt the worker and submitted a third test vote (Cats). The final local dataset contains three test votes: two Cats and one Dogs.

## AKS application validation — 1 November 2026

- A successful Azure Pipelines build pushed all three application images to ACR using passwordless authentication.
- Applied the Kubernetes manifests to the approved course cluster using those images while another pipeline run was waiting for a hosted agent. This manual application check alone does not prove pipeline deployment works.
- All five deployments became available; all five pods were Running and Ready with zero restarts at inspection.
- PostgreSQL's 1 GiB PVC was Bound using AKS managed-csi storage. PGDATA uses a subdirectory of the disk mount.
- Both application health endpoints returned HTTP 200 through localhost-only Kubernetes port forwarding.
- Submitted one Cats and one Dogs vote; results displayed two votes and 50% for each choice. A direct SQL count independently confirmed one vote per choice.
- Invalid choice submission returned HTTP 400. The worker logs confirmed both valid votes were stored, and the Redis queue was empty after processing.
- These were functional HTTP/SQL checks, not a new browser visual review, load test, backup test, or stop/start recovery test.
- Account-specific evidence and the restart/demo runbook are retained locally outside the public repository. Billing totals and student credit coverage were not verified by these tests.

### Automated deployment follow-up

The retried Azure Pipelines run subsequently succeeded: all three image build/push tasks and the AKS deployment stage passed using passwordless service connections. The cluster ran the new build's three application images. Both HTTP health checks still returned 200, and the two database votes remained visible after the rollout. The earlier queued run was canceled because its assigned hosted agent remained offline; no paid agent capacity was purchased.
