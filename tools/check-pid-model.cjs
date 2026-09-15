// 실행: node tools/check-pid-model.cjs
const assert = require("node:assert/strict");
const { MODEL, PRESETS, simulate } = require("../assets/js/pid-model.js");

// P/PD의 평형 오차는 일정 부하를 지탱하는 P 토크에서 구할 수 있다.
for (const name of ["P", "PD"]) {
  const result = simulate(PRESETS[name], { duration: 60 });
  assert.ok(Math.abs(result.metrics.finalError - MODEL.load / PRESETS[name].kp) < 0.002, name);
}
// I를 더한 안정한 루프는 같은 부하에서도 목표로 수렴한다.
for (const name of ["PI", "PID"]) {
  assert.ok(Math.abs(simulate(PRESETS[name], { duration: 60 }).metrics.finalError) < 0.002, name);
}
assert.equal(simulate(PRESETS.P).metrics.settlingTime, null);
assert.ok(simulate(PRESETS.PID).metrics.overshoot < simulate(PRESETS.PI).metrics.overshoot);

// 강의 비교 예시에서 I의 오차 보정과 D의 감쇠 효과가 뚜렷해야 한다.
const comparison = Object.fromEntries(["P", "PI", "PID"].map((name) => [name, simulate(PRESETS[name])]));
assert.ok(comparison.P.metrics.finalError > 4.5);
assert.ok(Math.abs(comparison.PI.metrics.finalError) < 0.5);
assert.ok(comparison.PI.metrics.overshoot - comparison.P.metrics.overshoot > 15);
assert.ok(comparison.PID.metrics.overshoot < comparison.PI.metrics.overshoot / 2);
assert.ok(comparison.PID.metrics.settlingTime < comparison.PI.metrics.settlingTime);

// 목표가 계단처럼 변해도 측정값 미분에는 D 킥이 없다.
assert.equal(simulate({ kp: 0, ki: 0, kd: 0.5 }).samples[0].d, 0);
assert.ok(simulate({ kp: 0, ki: 0, kd: 0 }, { load: 0 }).samples.every((s) => s.angle === 0));

// 전체 슬라이더 범위에서 값이 유한하고 실제 토크는 항상 한계 안에 있다.
for (const kp of [0, 0.3, 1.2]) for (const ki of [0, 0.04, 0.4]) for (const kd of [0, 0.12, 0.5]) {
  const result = simulate({ kp, ki, kd });
  assert.equal(result.samples.at(-1).t, MODEL.duration);
  assert.ok(result.samples.every((s) => Number.isFinite(s.angle) && Math.abs(s.torque) <= MODEL.limit));
}

// 포화가 있는 예시에서 조건부 적분이 과도한 누적을 줄이는지 확인한다.
const gains = { kp: 0.3, ki: 0.3, kd: 0.12 };
const guarded = simulate(gains);
const unguarded = simulate(gains, { antiWindup: false });
assert.ok(guarded.metrics.overshoot < unguarded.metrics.overshoot);
assert.ok(unguarded.samples.every((s) => Math.abs(s.torque) <= MODEL.limit));

// 시간 간격을 절반으로 줄여도 표시 결과가 크게 바뀌지 않아야 한다.
const normal = simulate(PRESETS.PID);
const finer = simulate(PRESETS.PID, { dt: MODEL.dt / 2 });
assert.equal(normal.samples.length, finer.samples.length);
assert.ok(Math.max(...normal.samples.map((s, i) => Math.abs(s.angle - finer.samples[i].angle))) < 0.1);
assert.ok(Math.abs(normal.metrics.overshoot - finer.metrics.overshoot) < 0.2);
console.log("PID model checks passed: equilibrium, saturation, anti-windup, D input, and time-step convergence.");
