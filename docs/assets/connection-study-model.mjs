import { getQualityMeasurementStatus } from './specimens/measurement-status.mjs';

// Authored fixtures, deliberately fixed in time. These are not captured telemetry.
const sampleTime = Date.parse('2026-01-01T12:00:00Z');
const diagnostics = Object.freeze({
  bitrate: 500000, rtt: 40, jitter: 3, packetLoss: 0, healthScore: 90,
  frameRate: 24, frameWidth: 640, frameHeight: 360,
  hasDelta: true, source: 'inbound', updatedAt: new Date(sampleTime).toISOString(),
});

export function inspectReading(kind = 'measured', age = 2) {
  if (!['measured', 'missing'].includes(kind)) throw new Error('Unknown specimen fixture');
  if (!Number.isInteger(age) || age < 0 || age > 30) throw new Error('Inspection age must be 0–30 seconds');
  const reading = kind === 'measured' ? diagnostics : undefined;
  return Object.freeze({
    connection: 'connected', kind, age: reading ? age : null,
    frameRate: reading?.frameRate ?? null,
    measurement: getQualityMeasurementStatus(reading, sampleTime + age * 1000),
  });
}
