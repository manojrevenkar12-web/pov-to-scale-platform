alerts: SLOLatencyBurn1h SLOLatencyBurn6h SLOLatencyBurn3d
owner: ai-lab-platform
---
# Engagement service is slow

Fewer than 95% of requests finish in 4 seconds.

1. Compare p95 by model in the gateway dashboard: a slow model deployment points to Azure-side load.
2. Check whether answers got longer (output tokens per request); a prompt change can double latency.
3. Check the retrieval step (vector search) latency in the service's traces.
4. If one model is slow, route to the fallback deployment for that engagement and open an Azure support case.
5. If a release caused it, roll back with Argo CD; the promotion gate should have caught it, so add the case to the eval set.
