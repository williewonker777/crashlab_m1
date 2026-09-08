"use strict";
const assert = require("node:assert/strict");
const m = require("../assets/js/mobile-model.js");
const close = (actual, expected, tolerance = 1e-10) => assert.ok(Math.abs(actual - expected) < tolerance, `${actual} ≠ ${expected}`);
const origin = { x: 0, y: 0, theta: 0 };

for (const radius of [0.065, 0.1, 0.2]) for (const track of [0.4465, 0.5, 0.8]) {
  for (const left of [-8, -1, 0, 4, 8]) for (const right of [-8, -1, 0, 6, 8]) {
    const f = m.forward(left, right, radius, track);
    const wheels = m.inverse(f.v, f.omega, radius, track);
    close(wheels.left, left); close(wheels.right, right);
  }
}
const f = m.forward(4, 6);
close(f.v, 0.5); close(f.omega, 0.4); close(f.radius, 1.25);
assert.equal(m.forward(4, 4).radius, null);
close(m.forward(-4, 4).v, 0);
assert.throws(() => m.forward(4, 6, 0, 0.5), RangeError);

const straight = m.integrateExact(origin, 0.5, 0, 2);
close(straight.x, 1); close(straight.y, 0); close(straight.theta, 0);
const spin = m.integrateExact(origin, 0, 1, Math.PI / 2);
close(spin.x, 0); close(spin.y, 0); close(spin.theta, Math.PI / 2);
const circle = m.integrateExact(origin, 0.5, 0.4, 2 * Math.PI / 0.4);
close(circle.x, 0); close(circle.y, 0); close(circle.theta, 2 * Math.PI);
for (const omega of [-1.6, -0.4, 1e-12, 0, 0.4, 1.6]) {
  let accumulated = { x: 1, y: -2, theta: 0.7 };
  for (let i = 0; i < 600; i++) accumulated = m.integrateExact(accumulated, 0.5, omega, 0.01);
  const direct = m.integrateExact({ x: 1, y: -2, theta: 0.7 }, 0.5, omega, 6);
  close(accumulated.x, direct.x); close(accumulated.y, direct.y); close(accumulated.theta, direct.theta);
}
const delta = m.wheelDelta(0.4, 0.6);
close(delta.distance, 0.05); close(delta.heading, 0.04);
const mid = m.integrateMidpoint(origin, delta.distance, delta.heading);
close(mid.x, 0.04999000033332889); close(mid.y, 0.0009999333346666541);
const exact = m.integrateExact(origin, f.v, f.omega, 0.1);
assert.ok(Math.hypot(mid.x - exact.x, mid.y - exact.y) < 0.000004);

const pBase = m.transformPoint({ x: 0.3, y: 0, theta: 0 }, { x: 1, y: 0 });
const pOdom = m.transformPoint({ x: 2, y: 1, theta: Math.PI / 2 }, pBase);
close(pBase.x, 1.3); close(pOdom.x, 2); close(pOdom.y, 2.3);
for (let degrees = -180; degrees <= 180; degrees += 5) {
  const theta = degrees * Math.PI / 180, q = m.yawQuaternion(theta);
  close(Math.hypot(q.x, q.y, q.z, q.w), 1);
  close(Math.cos(m.quaternionYaw(q)), Math.cos(theta));
  close(Math.sin(m.quaternionYaw(q)), Math.sin(theta));
  const opposite = Object.fromEntries(Object.entries(q).map(([k, v]) => [k, -v]));
  close(Math.cos(m.quaternionYaw(opposite)), Math.cos(theta));
  close(Math.sin(m.quaternionYaw(opposite)), Math.sin(theta));
}
assert.throws(() => m.quaternionYaw({ x: 0, y: 0, z: 0, w: 0 }), RangeError);
console.log("PASS: 정·역기구학 225 조합, 직진·회전·원호 적분, 엔코더 누적, 좌표변환, quaternion 정규화·동치성");
