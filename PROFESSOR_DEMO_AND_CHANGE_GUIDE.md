# Professor demo and change guide

## Start the local demo

Extract Cloud_Voting_App_Final.zip. Open PowerShell in the directory containing docker-compose.yml. Start Docker Desktop. Use a separate Compose project name and available ports 8080 and 8081. On the audit machine, courseaudit1126 already owns these ports. Reuse that project to show the preserved test data, or stop it before opening a fresh demo.

```powershell
# In a fresh extracted directory, create the local secret only if it is absent.
if (!(Test-Path .env)) { [IO.File]::WriteAllText((Join-Path $PWD '.env'), 'POSTGRES_PASSWORD=' + [guid]::NewGuid().ToString('N')) }
docker compose -p classroom up -d --build --wait
docker compose -p classroom ps
```

1. Open http://localhost:8081 and record the starting totals. Open http://localhost:8080 in a second tab. Click Cats, then Dogs. The confirmation means Redis accepted the request. Refresh the results and check for one additional row per choice.
2. Show the SQL counts and worker logs below. A queue length of zero after voting is normal when the worker has caught up.
3. Submit the invalid choice below. Expect HTTP 400 and identical before/after SQL totals.
4. Stop the local project after the class. Named volumes retain data. Reuse the same project name and password for the next session.

```powershell
docker compose -p classroom exec -T db psql -U voting_app -d voting -c "SELECT choice, COUNT(*) FROM votes GROUP BY choice ORDER BY choice"
docker compose -p classroom logs --tail 12 worker
docker compose -p classroom exec -T redis redis-cli LLEN votes
docker compose -p classroom exec -T redis redis-cli LLEN votes:processing
curl.exe -i -d choice=Other http://localhost:8080/vote
docker compose -p classroom stop
```

## Make the verified title change

Set POLL_TITLE in your PowerShell environment, then recreate the two web services. The title appears in each page header and browser tab. Both pages were verified locally with the example below.

```powershell
$env:POLL_TITLE='ELL8287 Campus Poll'
docker compose -p classroom up -d --wait vote result
```

To version that choice, create a topic branch from a working Git checkout. In docker-compose.yml set the fallback in both POLL_TITLE entries. For Kubernetes, add a POLL_TITLE environment variable with the same value to the vote and result containers in infra/k8s/30-vote.yaml and 50-result.yaml. Compose environment variables do not propagate to Kubernetes. Rebuild or redeploy only after reviewing the diff.

```powershell
git switch -c demo/campus-poll
git add docker-compose.yml infra/k8s/30-vote.yaml infra/k8s/50-result.yaml
git diff --cached
git commit -m "Set the classroom poll title"
# With repository write permission
git push -u origin demo/campus-poll
```

The pipeline watches matching changes on main. A topic-branch push alone does not trigger this YAML. Open a PR and obtain review before merging. After an authorized merge, verify the CI run's commit and reason. The revised job starts disposable Compose services, runs tests/acceptance.py, then builds and pushes vote, worker and result tagged with the Azure build ID. The deployment stage is included only when deployToAks is true and runs only on main after build success. For a deployment, obtain resource-owner approval and manually queue the reviewed main commit with this parameter enabled. Verify approval checks in the voting-aks-dev environment. Pipeline connections and variables are described in README.md.

## Inspect a live deployment

Open Azure DevOps → harsh-satwik-cloud-voting → Pipelines → CloudVoting-CI. Inspect the source commit, run reason, three Docker tasks and the separate Kubernetes deployment task. In ACR → Repositories inspect each image's tag and digest. Record its manifest digest and any platform-specific digest. In the correct Kubernetes context, compare each pod's requested image and resolved imageID. Check events if there is an image pull or storage error.

```powershell
kubectl config current-context
kubectl get nodes
kubectl -n voting get deploy,pods,svc,pvc -o wide
kubectl -n voting get pods -o 'custom-columns=NAME:.metadata.name,IMAGE:.spec.containers[0].image,IMAGEID:.status.containerStatuses[0].imageID'
kubectl -n voting rollout status deployment/vote
kubectl -n voting logs deploy/worker --tail=12
```

If the local demo occupies ports 8080/8081, stop it first. Keep each port-forward open in a separate terminal. The links built into the page assume these ports.

```powershell
kubectl -n voting port-forward service/vote 8080:80
kubectl -n voting port-forward service/result 8081:80
```

Open the same localhost URLs. Get permission before submitting votes to an existing database. Use Ctrl+C in each forwarding terminal when finished. The project manifests use ClusterIP. An archived temporary demo job is outside the deployment manifest set. A previously used public address should not be advertised as current.

## Reliability and scaling demonstration

Use a disposable database and namespace. The automated test below stops services, sends test votes, replays an event, and kills the test worker. Stop other apps occupying the demo ports first.

```powershell
docker compose -p courseauditdemo up -d --build --wait
python tests/acceptance.py --project courseauditdemo --output local-test-results
docker compose -p courseauditdemo stop
```

For a Kubernetes recovery experiment, record current pod names, ready endpoints and replica count. In an approved disposable namespace, run a continuous HTTP probe through the Service from another pod. Start timing, delete one named stateless vote pod and wait for a different pod UID to reach Ready. Record the gap in successful HTTP requests. A port-forward tied to a single pod can disconnect and is unsuitable as the only availability probe.

For scaling, record the original replica count, then run the following on the authorized test cluster. A persistent change belongs in the deployment manifest. Check node headroom first. Keep the database and queue at their original size.

```powershell
kubectl -n voting scale deployment/vote --replicas=3
kubectl -n voting rollout status deployment/vote
kubectl -n voting get pods -l app.kubernetes.io/name=vote -o wide
# After measuring, restore the original count (one for the supplied manifests).
kubectl -n voting scale deployment/vote --replicas=1
kubectl -n voting rollout status deployment/vote
```

## Additional change requests

| Request | Edit and verify |
|---|---|
| Add a third choice | Update vote/app.py validation and form, worker/worker.py validation, result/app.py choices and card styling. Update the CHECK constraint in both table definitions. An existing database requires an explicit schema migration and backup. Test old rows plus the new choice. |
| Change result display | Edit the cards in result/app.py or CSS in result/ui.py. Test an empty database and unequal counts. Check labels as well as percentages. |
| Adjust CPU or memory | Edit resources.requests and resources.limits under the selected container in infra/k8s. Compare actual usage and scheduling events, then use the reviewed deployment workflow. |
| Change replica count | Edit spec.replicas in infra/k8s/30-vote.yaml. Compare desired, ready and available; test through the Service. |
| Change service configuration | Set REDIS_URL or POSTGRES_HOST in Compose and the respective manifests. Validate /healthz before sending votes. |

## End the cloud demo

Stop forwards, record the final state and confirm the intended Azure subscription and resource group. If the owner approves stopping a running course AKS cluster, use the Azure Portal Stop action and verify the final power state. Record retained disks, registry and networking items for cost review. Deleting PVCs, the database or resource group is unnecessary for this demo.

