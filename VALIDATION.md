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

Next stage: create/select the GitHub repository and publish only after explicit user approval. Azure DevOps, ACR and AKS setup remain pending. Argo CD remains optional Phase 2.

Follow-up: set the worker Redis socket read timeout to 10 seconds, longer than its 5-second blocking queue wait. Rebuilt the worker and submitted a third test vote (Cats). The final local dataset contains three test votes: two Cats and one Dogs.
