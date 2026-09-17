"use strict";
const assert = require("node:assert/strict");
const { sample, peaks } = require("../assets/js/trajectory-model.js");
const close = (a, b, tolerance = 1e-6) => assert.ok(Math.abs(a - b) < tolerance, `${a} ≠ ${b}`);

for (const duration of [2, 4]) for (const [start, end] of [[0, 60], [30, -40], [10, 10]]) {
  for (const time of [-1, 0]) assert.deepEqual(sample(time, duration, start, end), { position: start, velocity: 0, acceleration: 0 });
  for (const time of [duration, duration + 1]) assert.deepEqual(sample(time, duration, start, end), { position: end, velocity: 0, acceleration: 0 });
  close(sample(duration / 2, duration, start, end).position, (start + end) / 2);
  const step = 1e-5;
  for (let i = 1; i < 100; i++) {
    const t = i * duration / 100;
    const a = sample(t - step, duration, start, end), b = sample(t + step, duration, start, end);
    const value = sample(t, duration, start, end);
    close((b.position - a.position) / (2 * step), value.velocity);
    close((b.velocity - a.velocity) / (2 * step), value.acceleration);
  }
  // Independent numerical integration/extrema verify the plotted derivatives.
  let integral = 0, maxSpeed = 0, maxAcceleration = 0;
  const n = 10000, dt = duration / n;
  for (let i = 0; i < n; i++) {
    const value = sample((i + .5) * dt, duration, start, end);
    integral += value.velocity * dt;
    maxSpeed = Math.max(maxSpeed, Math.abs(value.velocity));
    maxAcceleration = Math.max(maxAcceleration, Math.abs(value.acceleration));
  }
  close(integral, end - start);
  close(maxSpeed, peaks(duration, start, end).velocity, 1e-5);
  close(maxAcceleration, peaks(duration, start, end).acceleration, 1e-5);
}
for (let t = 0; t <= 2; t += .02) {
  const fast = sample(t, 2), slow = sample(t * 2, 4);
  close(fast.position, slow.position);
  close(fast.velocity, slow.velocity * 2);
  close(fast.acceleration, slow.acceleration * 4);
}
close(sample(1, 4).position, 6.2109375);
close(sample(1, 2).position, 30);
close(peaks(4).velocity, 28.125);
close(peaks(2).velocity, 56.25);
assert.throws(() => sample(1, 0), RangeError);
assert.throws(() => sample(NaN, 4), RangeError);
console.log("PASS: 궤적의 시작·도착·정지, 도함수 유한차분, 속도 적분, 수치 최대값, 시간 1/2일 때 속도 2배·가속도 4배");
