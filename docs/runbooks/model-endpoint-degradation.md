# Runbook: Model Endpoint Degradation

## Trigger
- Answer endpoint latency exceeds SLO envelope.
- Increased model timeout or model failure frequency.
- Quality checks show sharp degradation in citation/faithfulness outcomes.

## Immediate Actions
1. Confirm whether degradation affects managed endpoint, network path, or prompt orchestration.
2. Pause canary promotions and hold rollout at current stage.
3. Reduce high-cost traffic where policy allows (temporary rate reduction for answer endpoints).

## Diagnostics
- Check provider status and per-model latency/error telemetry.
- Compare current model/version configuration with previous stable release.
- Inspect timeout, retry, and concurrency settings.

## Mitigation
1. Roll back to last stable model configuration if drift introduced regression.
2. Increase timeout only within predefined budget and monitor saturation.
3. If persistent provider degradation exists, switch to approved fallback endpoint/model.

## Recovery Validation
- Orchestrated answer p95 latency returns within defined target.
- Model failure and timeout rates return to baseline.
- Post-mitigation synthetic answer checks meet quality threshold.

## Post-Incident
- Capture provider and application evidence separately.
- Update fallback policy and capacity assumptions if degradation pattern repeats.
