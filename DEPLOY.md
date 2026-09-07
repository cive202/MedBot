# Deploying MedAssist to RunPod

**Use a GPU *Pod*, not Serverless.** Chat streams over SSE (`app/routers/chat.py`),
the model is kept resident in VRAM (`keep_alive=30m`), and SQLite + Chroma are
stateful. Serverless workers are stateless with cold starts of 30–60 s, and the
FastAPI app has to be always-on regardless — so serverless would mean paying for
a host *and* GPU workers while making the UX worse.

Everything runs in **one container**: Ollama on loopback, FastAPI on `:8000`
serving both the API and the built React app. One origin means no CORS and no
`SameSite=None` cookie problems.

---

## 1. Build the image

Push to `main`. `.github/workflows/build-image.yml` builds and pushes to
`ghcr.io/safal999sapkota-collab/medbot:latest`. First build takes ~15–20 min;
later ones hit the layer cache.

Then make the package pullable by RunPod — either:

* **GitHub → your profile → Packages → medbot → Package settings → Change
  visibility → Public** (simplest), or
* keep it private and add registry credentials in RunPod
  (Settings → Container Registry Auth) using a GitHub PAT with `read:packages`.

## 2. Create a Network Volume

RunPod → Storage → Network Volume.

| Setting | Value |
|---|---|
| Size | **30 GB** |
| Region | one that actually has your GPU in stock |

Holds MedGemma (~5 GB), the HF embedding cache, `rf_model.joblib` (162 MB),
Chroma, and the SQLite DB. Without it, every restart re-downloads ~6 GB.

## 3. Deploy the Pod

RunPod → Pods → Deploy, attach the network volume from step 2.

| Setting | Value |
|---|---|
| GPU | 16 GB class — RTX A4000 / 4000 Ada / L4 |
| Template | Custom → `ghcr.io/safal999sapkota-collab/medbot:latest` |
| Container disk | 20 GB |
| Volume mount path | `/workspace` |
| Expose HTTP ports | **8000** |
| Expose TCP ports | *(none)* |
| Docker command | *(leave empty — the image's CMD runs `start.sh`)* |

> **Never expose 11434.** An open Ollama port is an unauthenticated public LLM.

`medgemma:4b` at Q4 is ~3.5 GB of weights plus the vision tower and KV cache —
about 8 GB in use. A 24 GB card buys headroom you will not use.

## 4. Environment variables

Set these on the pod (Edit Pod → Environment Variables):

| Variable | Value | Notes |
|---|---|---|
| `SECRET_KEY` | `openssl rand -hex 32` | signs JWTs |
| `FERNET_KEY` | see below | encrypts saved profiles |
| `ENVIRONMENT` | `production` | |
| `COOKIE_SECURE` | `true` | the RunPod proxy is HTTPS |
| `FRONTEND_ORIGINS` | `https://<pod-id>-8000.proxy.runpod.net` | only matters if you later split the frontend off |
| `MEDGEMMA_MODEL` | whatever `ollama list` shows locally | tags differ by publisher — copy yours exactly |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | optional | also add the proxy URL as an authorized redirect URI |

Generate the Fernet key once, locally:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Set it once and never change it.** `models/user.py` stores profile data through
`EncryptedJSON`; a new key makes every previously saved profile permanently
undecryptable. Keep it out of git.

## 5. Upload the trained artifacts

`backend/data/` is gitignored, so the RF model is **not** in the image. Yours is
already trained at
`C:\Users\Safal\Downloads\ARTEMIS-dev\ARTEMIS-dev\backend\data\` — no need to
retrain on the pod or ship the 182 MB Kaggle CSV.

From your PC (install `runpodctl` first):

```bash
cd "C:\Users\Safal\Downloads\ARTEMIS-dev\ARTEMIS-dev\backend\data"
runpodctl send rf_model.joblib specialist_knn.joblib
```

On the pod (web terminal), receive them into the volume:

```bash
cd /workspace/data && runpodctl receive <code-from-your-machine>
```

Restart the pod so the RF warm-load picks them up. `specialist_knn.joblib`
rebuilds itself from the versioned `.xlsx` if you skip it; `rf_model.joblib`
does not — without it disease prediction silently returns `[]`.

Chroma is seeded automatically at boot by `start.sh` (idempotent).

## 6. Verify

```bash
curl https://<pod-id>-8000.proxy.runpod.net/health
```

Expect `medgemma.ollama_running: true`, `model_ready: true`, `rf.ready: true`.
`rf.loading: true` for the first ~30 s is normal — the classifier warms in the
background (`main.py` lifespan) so the app serves immediately.

**Test SSE streaming before building anything on top of it:**

```bash
curl -N -X POST https://<pod-id>-8000.proxy.runpod.net/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"I have a fever and a cough"}'
```

Tokens must arrive progressively. If the response instead lands in one lump
after a long pause, the proxy is buffering — fall back to an exposed TCP port or
put a Cloudflare tunnel in front.

Then open `https://<pod-id>-8000.proxy.runpod.net/` — the React app is served
from the same origin, so login sets a first-party cookie and refreshing on
`/chat` works (the SPA fallback in `main.py` handles it).

## 7. Costs

* GPU bills only while the pod is **running** — stop it when idle.
* The network volume bills continuously (~$0.07/GB/month, so ~$2/month for
  30 GB). That is the price of not re-downloading 6 GB on every boot.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| App won't import, `ModuleNotFoundError: magic` | `libmagic1` missing — the Dockerfile installs it; check you built from this Dockerfile |
| `/health` shows `model_ready: false` | wrong `MEDGEMMA_MODEL` tag; check `ollama list` on the pod |
| Predictions always empty | `rf_model.joblib` not on the volume (step 5) |
| Login works, next request is 401 | `COOKIE_SECURE` false over HTTPS, or you split the frontend to another origin |
| Everything re-downloads on restart | volume not mounted at `/workspace` |
| Saved profiles unreadable after redeploy | `FERNET_KEY` changed |
