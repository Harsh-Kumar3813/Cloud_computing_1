# Cloud Voting Application — Phase 1

A small, beginner-friendly Cloud Computing course project. It follows the five-service architecture used by Docker's sample voting application while keeping the implementation and cloud scope intentionally small.

> **Phase 1:** run locally with Docker Compose, keep source and Kubernetes manifests in GitHub, build and push three application images with Azure Pipelines to Azure Container Registry (ACR), and prepare a gated pipeline stage for AKS. The AKS stage is disabled by default and must be deliberately configured before use. No cloud resource is created by this repository.
>
> **Phase 2 (optional):** add Argo CD after Phase 1 works and the course schedule allows it. It is not needed to meet the Phase 1 goal.

## What we are making

Users choose Cats or Dogs. The vote service adds each vote to Redis, a background worker moves it into PostgreSQL, and the results service reads totals from PostgreSQL.

```text
Browser → Vote service → Redis queue → Worker → PostgreSQL → Results service → Browser
```

On a laptop, Docker Compose runs all five components. In AKS, Kubernetes manifests run the same components. Azure Pipelines builds the vote, worker, and result images and pushes them to ACR. Redis and PostgreSQL use official base images and are not custom-built application images.

## Scope boundaries

Included: the five services, local Compose workflow, three app Dockerfiles, ACR image build/push pipeline, Kubernetes manifests, and a disabled-by-default AKS deployment stage.

Excluded from Phase 1: Argo CD, self-hosted agents, Helm, Terraform, monitoring stacks, autoscaling, ingress/TLS, multi-environment promotion, custom authentication, and a production database service. The AKS example uses internal ClusterIP services; use `kubectl port-forward` for a course demo. This is a learning project, not a production voting system. It does not provide identity checks, protection against repeat voting, high availability, backups, or a public production endpoint.

## Repository layout

```text
vote/                 Flask vote page and Dockerfile
worker/               Redis-to-PostgreSQL worker and Dockerfile
result/               Results page and Dockerfile
infra/k8s/             Namespace, Redis, PostgreSQL, vote, worker, results
docker-compose.yml     Local five-service environment
azure-pipelines.yml    ACR build/push plus gated AKS deployment
.env.example          Local-only password template; never commit .env
```

## Tools and choices

| Tool | Why this project uses it | Reasonable alternative and why it is not in Phase 1 |
| --- | --- | --- |
| Docker Compose | Starts the five local services together with simple health checks. | Run each service manually: harder for beginners and less repeatable. |
| Redis | Small in-memory queue separates voting from database writes. | Direct synchronous database writes: fewer components, but loses the queue/worker architecture the project is meant to demonstrate. |
| PostgreSQL | Stores durable vote records and supports a simple totals query. | SQLite: simpler locally, but less representative of the containerized cloud architecture. |
| Azure Pipelines | Builds and pushes application images and can later apply the Kubernetes manifests. | GitHub Actions: also capable; Azure Pipelines is retained to match the agreed Azure DevOps learning goal. |
| ACR | Private registry for the three built application images. | Docker Hub: possible, but ACR keeps the learning path within Azure. |
| AKS + Kubernetes YAML | Demonstrates deployments, services, configuration, health probes, and a small persistent volume claim. | App Service/Container Apps: fewer Kubernetes concepts; they would change the agreed architecture. |
| Argo CD (Phase 2 only) | Can later demonstrate GitOps reconciliation from Git. | Not required for the first working delivery; adding it now expands the learning and setup workload. |

The source is a small original implementation of the same architecture, not a copy of the full Project 37 repository. Project 37 is used as a reference for the overall DevOps path and relevant configuration ideas. Its optional/advanced pieces are outside this scope.

### How Phase 1 differs from the Project 37 guide

The referenced folder is a deployment guide (README plus a self-hosted-agent guide) that points readers to the separate Docker sample application. This project includes its own small Python services so the course team can run and explain the full five-service flow from this repository. The guide's self-hosted Azure VM agent, Argo CD setup, image-update script, and public NodePort exposure are not included. Here, Azure Pipelines builds the three application images and the AKS stage is gated off by default; AKS services stay internal and a demo can use port forwarding. Redis and PostgreSQL remain part of the architecture, but are base images rather than custom builds.

## Stage 1 — Run the application locally

Requirements: Docker Desktop (or Docker Engine with the Compose plugin), Git, and a terminal. No Azure account is needed for this stage.

1. Copy `.env.example` to `.env` and replace its sample password with a new local-only password. Keep `.env` out of Git; `.gitignore` excludes it.
2. From this folder, run `docker compose up --build`.
3. Open [http://localhost:8080](http://localhost:8080), submit a vote, then open [http://localhost:8081](http://localhost:8081) to see totals. A first result may take a moment while the worker processes the queue.
4. Inspect service output with `docker compose logs -f`.
5. Stop with `Ctrl+C`, then run `docker compose down`. This preserves the local PostgreSQL volume. To reset only this sample's local vote data, run `docker compose down -v` (this deletes the Compose-managed database volume).

Expected observation: the vote page accepts only Cats or Dogs; the worker logs stored votes; the results totals change. Try multiple votes and record what happens if Redis or PostgreSQL is unavailable.

## Stage 2 — Put source and manifests in GitHub

1. Create a private or course-approved GitHub repository for this project and add the contents of this folder.
2. Check `git status` and confirm `.env` is not staged. Do not commit passwords, tokens, subscription IDs, or personal account details.
3. Push the `main` branch. Keep code, Dockerfiles, pipeline YAML, and Kubernetes manifests together so the course team can review each change.

## Stage 3 — Prepare Azure DevOps and ACR (manual account setup)

These are setup instructions only. This project has not signed in, created resources, or verified student-credit eligibility or prices.

1. In Azure, confirm with the course/team owner which subscription and region to use, whether the account can create ACR/AKS resources, and what credit and expiry rules apply. Check current pricing and student-offer terms yourself before creating anything; neither credit eligibility nor zero cost is guaranteed.
2. Create or select an Azure DevOps project and connect its pipeline to the GitHub repository. Select `azure-pipelines.yml` when asked for a pipeline YAML file.
3. Configure an Azure DevOps **Docker Registry** service connection for the intended ACR using workload identity federation (passwordless). The YAML expects the connection name `sc-acr-cloud-voting`; change `ACR_SERVICE_CONNECTION` in YAML if using another name. Limit the identity to `AcrPush` on the registry and authorize only this project's pipeline. Do not put a registry password in YAML.
4. Create a pipeline and first run the **BuildAndPush** stage only after the service connection is ready. It builds `vote`, `worker`, and `result` with the Azure Pipelines build ID as the tag and pushes them to ACR.
5. Confirm each image/tag in the ACR portal. That is the evidence that the build/push stage succeeded; no such result is claimed here.

## Stage 4 — Prepare AKS deployment (gated and opt-in)

The `DeployToAKS` stage is designed for `main` only and has the boolean `deployToAks` run parameter set to `false` by default. It will remain skipped until the team deliberately sets that run parameter to `true` and supplies the values below. Do not enable it until the course owner approves the target cluster and the team is ready to deploy.

Required Azure DevOps setup, to be supplied by the account owner:

Create the Azure DevOps environment named `voting-aks-dev` referenced by the deployment job. Add course-approved approval/check policies to that environment before enabling the deployment stage.

| Pipeline value | What to enter |
| --- | --- |
| `AZURE_SERVICE_CONNECTION` | Name of an Azure Resource Manager service connection authorized for the selected AKS resource. Use least privilege permitted by the course setup. |
| `AKS_RESOURCE_GROUP` | Resource group containing the approved AKS cluster. |
| `AKS_CLUSTER_NAME` | Approved AKS cluster name. |
| `ACR_LOGIN_SERVER` | Registry hostname such as `example.azurecr.io` (hostname only, no image path). |
| `ACR_SERVICE_CONNECTION` | Docker Registry service connection used by the image build stage. |
| `deployToAks` (run parameter) | Keep `false` during setup; select `true` only when an approved deployment is intended. |

Before an actual deployment, the cluster administrator must ensure the AKS kubelet identity can pull from ACR (or provide an approved image-pull credential method), and that the Kubernetes service connection has the required permissions. Create the namespace first through the pipeline manifests. Create the database password Secret in the `voting` namespace using a secure secret mechanism approved by the course owner; never store its value in Git or pipeline YAML. Example for a local `kubectl` session after connecting to an approved cluster:

```powershell
$dbPassword = Read-Host "Choose a strong database password" -AsSecureString
$plainForKubectl = [System.Net.NetworkCredential]::new("", $dbPassword).Password
kubectl create namespace voting --dry-run=client -o yaml | kubectl apply -f -
kubectl -n voting create secret generic voting-db --from-literal=POSTGRES_PASSWORD=$plainForKubectl
Remove-Variable plainForKubectl, dbPassword
```

This example sends the value to the local `kubectl` process; use the course's approved secret handling approach. Kubernetes Secret values are encoded, not encrypted by that fact alone. Enable the cluster's recommended secret-at-rest controls and restrict access. The pipeline applies the YAML and waits for rollouts, but this blueprint implementation has not been executed against AKS.

For the course demo, forward the internal services from a terminal:

```text
kubectl -n voting port-forward service/vote 8080:80
kubectl -n voting port-forward service/result 8081:80
```

Keep each command in its own terminal, then visit the same localhost URLs as in the local stage.

## Cost and credit controls

- Cloud work is a manual course-team step. This repository does not sign in, provision, or deploy.
- Before provisioning, check the current Azure pricing calculator, the subscription's student credit/offer terms, region, resource quotas, and course deadlines. Values and eligibility can change and are not guaranteed by this plan.
- Use one small development environment, one region, and only the resources required by the course rubric. ACR storage, AKS nodes, disks, public IPs, and related services may incur charges even when the sample app is idle.
- Agree who owns cleanup and the deadline for deleting resources. After a demo, stop/delete the AKS cluster and any unused registry, disks, public IPs, and resource group as approved by the owner. Verify deletion in Azure Cost Management later; estimates and budgets are not hard spending caps.
- Do not create resources until the account owner confirms permission, available credit, and cleanup responsibility.

## Validation and evidence to collect

Run these checks in order and save screenshots or short notes for the report:

1. Local Compose starts all five services; capture the vote page and results page.
2. Submit Cats and Dogs votes; capture the results and worker logs.
3. Check service health and inspect logs after a deliberate local restart or dependency outage; note recovery behavior.
4. Check Python syntax with `python -m compileall vote worker result` and Compose configuration with `docker compose config`.
5. After Azure DevOps is configured, record the pipeline run, image tags in ACR, and (only if approved/enabled) AKS pod/service status and browser results.

Local Docker builds and the vote-to-results flow were validated on 1 November 2026; see VALIDATION.md for the recorded checks and limitations. Azure checks still require the separate manual setup above.

## Two-student work split

| Student | Primary tasks | Shared work |
| --- | --- | --- |
| Student A | Vote/results user flow, Compose, local validation notes, screenshots. | Review each other's changes; explain the vote data path. |
| Student B | Worker/database flow, Dockerfiles, Kubernetes YAML, Azure pipeline configuration notes. | Review each other's changes; explain image build and deployment flow. |

Both students should be able to explain every component. Pair on GitHub/ADO setup and any cloud action; do not let one person provision resources without the course team's agreement.

## Suggested course timeline

Treat these as flexible work blocks, not deadline guarantees. Keep quiz/assignment weeks and the end-semester rush free of cloud setup.

| Block | Work and checkpoint |
| --- | --- |
| 1 | Confirm rubric and scope; review architecture; submit proposal. |
| 2 | Build/run the local app; record a successful vote-to-results flow. |
| 3 | Review Dockerfiles and Compose; commit to GitHub; capture local evidence. |
| 4 | Prepare Kubernetes manifests and Azure pipeline YAML; explain choices in README/report. |
| 5 | If course approval, access, and time allow, manually configure ACR/ADO and validate image push. Otherwise present the deployment plan without claiming it ran. |
| 6 | Optional, only after Phase 1 and course workload allow: Argo CD exploration. Finalize report and rehearse demo before end-semester workload peaks. |

## Proposal, report, and demo

**Proposal:** state the problem and goal; include the architecture diagram; explain Redis, worker, PostgreSQL, Docker, GitHub, Azure Pipelines, ACR, and AKS; list the Phase 1 boundary, two-person split, timeline, validation plan, and cost/permission assumptions.

**Report:** document the data flow; choices and alternatives; local setup; Git/CI flow; Kubernetes resources; what was actually validated; screenshots/logs; known limitations; risks and cost controls. Clearly distinguish planned Azure work from completed work.

**Demo (about 5–8 minutes):** show a vote locally, follow it through Redis/worker/PostgreSQL to results, explain the Docker Compose and pipeline files, show the Kubernetes manifests, and show ACR/AKS only if those stages were truly configured and run. Close with the optional Phase 2 Argo CD idea.

## Risks and limits

- Cloud access, course policies, service connection permissions, regional quotas, student credits, and live prices depend on the account and can change.
- PostgreSQL in this sample is a single pod with a small persistent volume claim. It is suitable for a classroom demonstration, not production resilience or backup.
- The vote form has no login or anti-repeat-vote mechanism; totals are illustrative, not election-grade.
- The default pipeline deploy stage is gated but not an authorization system. Protect the Azure DevOps environment with course-approved approvals/checks and restrict service connection permissions before enabling it.
- The Kubernetes services are internal. Public ingress, TLS, and hardening are deliberately outside Phase 1.

## Optional Phase 2 — Argo CD

After Phase 1 is complete, explore Argo CD as a separate extension: point it at the Git repository's Kubernetes manifests, observe reconciliation, then change a manifest and capture how the cluster follows Git. Agree on a course-approved cluster and cleanup plan first. Do not add Argo CD to Phase 1 acceptance criteria.

## Reference

- [Lloyd Theophilus DevOps Project 37](https://github.com/lloyd-theophilus/DevOps-Projects/tree/master/DevOps-Project-37) — reference for the general project flow and selected configuration concepts; not a request to reproduce the full repository.
- [Docker sample voting application](https://github.com/dockersamples/example-voting-app) — reference for the vote/Redis/worker/PostgreSQL/results architecture.
- [Docker@2 task reference](https://learn.microsoft.com/azure/devops/pipelines/tasks/reference/docker-v2?view=azure-pipelines) and [KubernetesManifest@1 task reference](https://learn.microsoft.com/azure/devops/pipelines/tasks/reference/kubernetes-manifest-v1?view=azure-pipelines) — Azure Pipelines task documentation.
