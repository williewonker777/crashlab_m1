/* 강의용 1축 관절 모델. 각도 단위는 도(°), 입력은 토크(N·m)다. */
((root) => {
  "use strict";

  const MODEL = Object.freeze({
    target: 30,
    duration: 12,
    dt: 0.002,
    inertia: 0.04,
    damping: 0.05,
    load: 0.5,
    limit: 5,
    derivativeFilter: 0.025,
  });
  const PRESETS = Object.freeze({
    P: { kp: 0.1, ki: 0, kd: 0 },
    PI: { kp: 0.1, ki: 0.02, kd: 0 },
    PD: { kp: 0.1, ki: 0, kd: 0.04 },
    PID: { kp: 0.1, ki: 0.02, kd: 0.04 },
  });
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  function simulate(gains, options = {}) {
    const m = { ...MODEL, ...options };
    const { kp, ki, kd } = gains;
    const samples = [];
    let angle = 0;
    let velocity = 0;
    let previousAngle = 0;
    let integral = 0;
    let derivative = 0;
    let peak = 0;
    let saturatedSteps = 0;
    const steps = Math.round(m.duration / m.dt);
    const sampleEvery = Math.max(1, Math.round(0.02 / m.dt));
    const alpha = m.dt / (m.derivativeFilter + m.dt);

    for (let step = 0; step <= steps; step += 1) {
      const t = step * m.dt;
      const error = m.target - angle;
      // 측정값을 미분해 목표가 계단처럼 바뀔 때 생기는 D 킥을 피한다.
      const measuredRate = (angle - previousAngle) / m.dt;
      derivative += alpha * (-measuredRate - derivative);
      const p = kp * error;
      const d = kd * derivative;
      const candidate = integral + ki * error * m.dt;
      const candidateOutput = p + candidate + d;
      const pushesIntoLimit = (candidateOutput > m.limit && error > 0)
        || (candidateOutput < -m.limit && error < 0);
      if (options.antiWindup === false || !pushesIntoLimit) integral = candidate;
      const requested = p + integral + d;
      const torque = clamp(requested, -m.limit, m.limit);
      if (step < steps && Math.abs(requested) > m.limit) saturatedSteps += 1;
      peak = Math.max(peak, angle);
      if (step % sampleEvery === 0 || step === steps) {
        samples.push({ t, angle, velocity, torque, requested, p, i: integral, d, error });
      }
      if (step === steps) break;
      const acceleration = (torque - m.load - m.damping * velocity) / m.inertia;
      previousAngle = angle;
      angle += velocity * m.dt + 0.5 * acceleration * m.dt * m.dt;
      velocity += acceleration * m.dt;
    }

    const tolerance = Math.abs(m.target) * 0.05;
    let lastOutside = -1;
    for (let i = 0; i < samples.length; i += 1) {
      if (Math.abs(samples[i].error) > tolerance) lastOutside = i;
    }
    const settlingCandidate = samples[lastOutside + 1];
    // 마지막 순간에만 허용 범위에 들어온 응답을 정착으로 표시하지 않는다.
    const settlingTime = settlingCandidate && settlingCandidate.t <= m.duration - 1
      ? settlingCandidate.t : null;
    const first10 = samples.find((s) => s.angle >= 0.1 * m.target);
    const first90 = samples.find((s) => s.angle >= 0.9 * m.target);
    return {
      samples,
      model: m,
      metrics: {
        overshoot: Math.max(0, (peak - m.target) / Math.abs(m.target) * 100),
        finalError: m.target - angle,
        settlingTime,
        riseTime: first10 && first90 ? first90.t - first10.t : null,
        saturationPercent: saturatedSteps / steps * 100,
      },
    };
  }

  const api = { MODEL, PRESETS, simulate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CrashlabPIDModel = api;
})(typeof globalThis === "undefined" ? this : globalThis);
