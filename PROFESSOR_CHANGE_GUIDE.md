# Changing the voting application

Use a fresh Compose project and database for demonstrations. Run these commands in PowerShell from the repository root after setting a local POSTGRES_PASSWORD. On this Windows machine the executable is under $env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin. Add that directory at the front of PATH for this terminal. If the empty system32 docker file masks it, call docker.exe explicitly.

## A small, reversible change

Set $env:POLL_TITLE = 'Campus companion poll' and run docker.exe compose -p votingauditclass up -d --build --wait. Visit localhost:8080 and localhost:8081. Both browser titles and header labels change. Submit each choice and refresh results. Run python tests/smoke.py only on an isolated data set. Restore the original title by removing the environment variable and running the same up command. For a change that ships with the images, edit the default title in vote/ui.py and result/ui.py. To use another browser port, set VOTE_PORT and RESULT_PORT plus the corresponding browser-facing VOTE_URL and RESULT_URL.

## From an edit to an image

Create a branch with git switch -c class/title-demo. Commit the two UI files and push the branch when authorized. The pipeline includes main and the named November audit branch. Other branches require manual CI or a reviewed branch-filter change. A README-only change does not match the path filter. The Compose test must pass before three Docker@2 tasks push vote, worker and result tagged with the Azure build ID. Record the source SHA, reason, timestamps and digests.

## From an image to the cluster

For an approved release, review the diff and merge to main. Queue that exact revision with deployToAks enabled, an authorized ARM connection and the voting-aks-dev environment checks. The branch guard excludes audit branches. The pipeline renders the registry/tag placeholders and waits up to 300 seconds for rollout. Get deployment images and Pod imageIDs, compare with ACR (multi-platform index and platform-specific digests can differ), then port-forward vote and result. Preserve database rows. Before replacing a Redis Pod, pause submissions and drain the queue, or migrate it to persistent storage in a separately approved window. An earlier worker cannot safely handle an in-flight claim left by the new version. Drain both keys before rollback. The updated database column is nullable for existing rows.

## Other requests a professor might make

| Request | Exact place to edit | Verification |
|---|---|---|
| Three vote replicas | Set spec.replicas to 3 in infra/k8s/30-vote.yaml. For a temporary approved drill use kubectl -n voting scale deployment/vote --replicas=3. | Wait for three Ready Pods, then restore the previous count. A service port-forward selects one Pod. |
| Adjust resources | Change containers[0].resources.requests and limits in the corresponding manifest. | Check rollout, scheduling events and kubectl top pods. |
| Show one decimal percentage | In result/app.py change the displayed percentage from .0f to .1f. | Use one Cats and two Dogs in a fresh database and check 33.3% and 66.7%. |
| Add a third option | Add it to the form/allowlist in vote/app.py, worker validation, result choices, styling and tests. Create a reviewed SQL migration replacing the old choice CHECK on existing databases in addition to updating both CREATE TABLE definitions. | Back up first. Test old rows, three choices, invalid input, percentages and rollout compatibility. |
| Change browser routes | Set VOTE_URL and RESULT_URL for the two browser links. For a proxy-mounted results route also test its refresh link. | Follow both links from a real browser using the intended public or forwarded addresses. |

The production poll still uses Cats and Dogs. A third option needs a data migration. Changing the title is the safer live demonstration.

