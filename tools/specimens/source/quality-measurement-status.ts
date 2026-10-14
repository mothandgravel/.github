import type { QualityDiagnostics } from './adaptive-streaming';

// Five 3-second collection periods of scheduling slack, independent of export rate.
export const MAX_DIAGNOSTIC_AGE_MS = 15_000;

export function getQualityMeasurementStatus(
  diagnostics: QualityDiagnostics | undefined,
  now: number,
): 'current' | 'stale' | 'unavailable' {
  if (
    !diagnostics || !diagnostics.hasDelta || diagnostics.source === 'unknown' ||
    diagnostics.unavailableMetrics?.length
  ) {
    return 'unavailable';
  }
  const age = now - Date.parse(diagnostics.updatedAt);
  if (!Number.isFinite(age) || age < 0) return 'unavailable';
  return age > MAX_DIAGNOSTIC_AGE_MS ? 'stale' : 'current';
}
