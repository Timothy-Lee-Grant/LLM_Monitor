# Targeted Implementation: Container & Orchestration Skills for a Microsoft Backend Role

| | |
|---|---|
| **Date** | 29-06-2026 (02:27) |
| **For** | Timothy Grant |
| **Purpose (per `CLAUDE.md`)** | Research-based learning targets — what container/orchestration skills to build, why Microsoft values them, and how to grow each *through this project* |
| **Trigger** | You identified Docker as a major weakness; this maps that weakness onto a concrete, Microsoft-aligned skill ladder |

---

## 1. Why this is a high-leverage area for *your* goal

You're targeting a cloud/backend role at Microsoft, and Microsoft's cloud platform is built on containers and Kubernetes. Azure's own training paths list, as core skills, *"deploying, configuring, and scaling an AKS cluster, deploying an Azure Container Registry instance, and deploying applications into an AKS cluster"* — and explicitly state these require *"a basic understanding of core Docker concepts such as containers, container images, and docker commands."* In other words: **Docker fluency is the prerequisite that everything Microsoft-cloud sits on top of.** The weakness you just identified is squarely on the critical path, which makes it a high-return thing to fix now.

The good news from your project: you're already operating a multi-container system with volumes, networks, and service discovery. You're not starting at zero — you're starting at "uses Docker, doesn't yet have the mental model," which the concepts lecture addresses. This document is the *ladder above* that: where to go next.

---

## 2. The skill ladder (each rung builds on the last)

### Rung 1 — Docker fundamentals (you're here; solidify it)
The non-negotiable base Microsoft assumes you already have:
- The four nouns (image, container, volume, network) and their lifecycles.
- Dockerfiles: layers, build cache, multi-stage builds (you already use multi-stage on the .NET side — good).
- `docker`/`docker compose` CLI fluency and **log-based troubleshooting**.
- Image hygiene: `.dockerignore`, small/supported base images, pinned dependencies, non-root users.

*Grow it in this project:* implement the AI_Suggestions fixes; add `.dockerignore` and a non-root user to your Dockerfiles; practice reading `docker stats`/`logs`/`inspect` until troubleshooting is reflexive.

### Rung 2 — Multi-container orchestration with Compose (you're mid-climb)
- `depends_on` with **healthchecks** and conditions (`service_healthy`, `service_completed_successfully`).
- Volumes for stateful services; named networks; environment/secret injection.
- Readiness vs. liveness; one-shot init jobs (you have one — the model puller).

*Grow it in this project:* the healthcheck work in AI_Suggestions *is* this rung. Next, add Postgres/pgvector with a healthcheck and a seed job — a textbook stateful-dependency exercise.

### Rung 3 — Container registries & image distribution
Microsoft's container skills lists call out **Azure Container Registry (ACR)**, *"container image management,"* and pushing/pulling images as core. Concepts: tagging strategy, image versioning, registries as the hand-off between build and deploy.

*Grow it in this project:* tag your `llm_monitor-langchain_service` images with versions; practice `docker push`/`pull` against a free registry (Docker Hub now, ACR later).

### Rung 4 — Kubernetes fundamentals (the big Microsoft target)
This is where Microsoft-cloud roles concentrate. The Azure training path lists the infrastructure you must understand: *"the control plane, node pools, pods, deployments, namespaces, services, ingress, and load balancing."* Translate your Compose mental model upward:

| Compose concept (you know) | Kubernetes equivalent (the target) |
|----------------------------|-------------------------------------|
| a service | a **Deployment** + **Pod** |
| `ports:` published | a **Service** (ClusterIP/NodePort/LoadBalancer) |
| reaching by service name | Kubernetes DNS + Services |
| `depends_on` + healthcheck | **readiness/liveness probes** |
| a volume | **PersistentVolume / PVC** |
| `.env` / `environment` | **ConfigMaps** and **Secrets** |
| `docker compose up` | `kubectl apply -f` / Helm |

*Grow it in this project:* once Compose is solid, port one service to Kubernetes locally (kind/minikube or Docker Desktop's K8s). Writing the Deployment/Service/Probe YAML for your *own* app is the fastest way to internalize K8s.

### Rung 5 — Azure-native: AKS & Container Apps
The 2026 Microsoft-specific layer. Skills called out: **AKS** (clusters, node pools, ingress), **Azure Container Apps**, **KEDA** (event-driven autoscaling), **HorizontalPodAutoscaler** and cluster autoscaler, secrets/env management, and *"monitoring container workloads."* Also: integrating **Microsoft Entra ID** for cluster access and planning hub-spoke networking.

*Grow it (beyond this project):* a free-tier Azure account; deploy your container image to **Azure Container Apps** first (the gentler on-ramp), then an **AKS** cluster. This is also résumé gold — "deployed a multi-service AI app to AKS" is a concrete, interview-ready story.

---

## 3. Recommended sequence (don't skip rungs)

```
Now ──▶ Rung 1 solidify (this week, via AI_Suggestions fixes)
     ──▶ Rung 2 (healthchecks + add pgvector with a seed job)
     ──▶ Rung 3 (tag + push images to a registry)
     ──▶ Rung 4 (port ONE service to local Kubernetes)
     ──▶ Rung 5 (deploy to Azure Container Apps, then AKS)
```
Each rung is a *project milestone*, not a course to binge. The principle: learn each layer by applying it to LLM_Monitor, so you finish with both the skill and a portfolio artifact that demonstrates it.

---

## 4. Certification & structured-learning anchors (optional but signal-rich)

- **Microsoft Learn — "Deploy containers by using Azure Kubernetes Service (AKS)"** training path (AZ-1001) covers Rungs 3–5 hands-on.
- The **Azure AI / cloud developer** associate certifications (e.g., AI-200 era) bundle containerized-AI deployment, which aligns this Docker work with your AI-engineering track.
- These aren't required to get hired, but a cert + a deployed project is a strong, verifiable pairing for a career-changer story.

---

## 5. How this ties back to your other documents

- The **Docker concepts lecture** (companion) builds Rung 1's mental model.
- The **AI_Suggestions** doc is your Rung 1→2 hands-on worklist.
- Your **skill-gap analysis** can now track "Infrastructure/Docker" as a first-class competency with this ladder as the mitigation path.
- This connects to your AI-engineering research too: production AI systems *are* containerized, scaled, and observed — so climbing this ladder directly serves the "ship a reliable, observable AI system" bar Microsoft screens for.

---

## 6. The one-sentence takeaway

Docker fluency isn't a side-quest — it's the foundation of the entire Microsoft cloud stack you're aiming at, and you're already standing on the first rung; climb it deliberately (Docker → Compose → registries → Kubernetes → AKS), using LLM_Monitor as the thing you containerize, orchestrate, and eventually deploy to Azure, and you turn a current weakness into one of your most marketable strengths.

---

## Sources

- [Deploy containers by using Azure Kubernetes Service (AKS) — Microsoft Learn](https://learn.microsoft.com/en-us/training/paths/deploy-manage-containers-azure-kubernetes-service/)
- [Azure Kubernetes Service (AKS) — Microsoft Azure](https://azure.microsoft.com/en-us/products/kubernetes-service/)
- [Azure Kubernetes Service (AKS) documentation — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/)
- [Kubernetes on Azure tutorial: Prepare an application for AKS — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/tutorial-kubernetes-prepare-app)
- [AI-200: Azure AI Cloud Developer Associate Certification Guide for 2026 — K21 Academy](https://k21academy.com/azure-aiml/ai-200-certification-guide-2026)
- [Docker Compose Health Checks: An Easy-to-follow Guide — Last9](https://last9.io/blog/docker-compose-health-checks/)
- [Docker Compose Service Dependencies: Solving Startup Sequence with Healthchecks — BetterLink](https://eastondev.com/blog/en/posts/dev/20251217-docker-compose-healthcheck/)
- [Ollama Production Deployment: Docker-Compose Setup Guide — SitePoint](https://www.sitepoint.com/ollama-local-llm-production-deployment-docker/)
- [`curl` missing from Ollama Docker image, causing healthcheck failures — ollama/ollama Issue #9781](https://github.com/ollama/ollama/issues/9781)

*No source files were modified. Only this research document was added to `Documentation/targeted_implementations/`.*
