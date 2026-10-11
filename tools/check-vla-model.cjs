"use strict";
const assert = require("node:assert/strict");
const { quantize, delaySteps, schedule, pausedSteps } = require("../assets/js/vla-model.js");
const close = (a, b, tolerance = 1e-9) => assert.ok(Math.abs(a - b) <= tolerance, `${a} ≠ ${b}`);

// Uniform binning: every value maps to one bin, the bin contains the value,
// and the reconstruction error never exceeds half a bin width.
for (const bins of [2, 8, 32, 256]) {
  const width = 180 / bins;
  let previous = -1;
  for (let i = 0; i <= 18000; i++) {
    const value = -90 + i / 100;
    const q = quantize(value, bins);
    assert.ok(Number.isInteger(q.index) && q.index >= 0 && q.index < bins);
    assert.ok(q.index >= previous, "bin index must not decrease");
    previous = q.index;
    const low = -90 + q.index * width, high = low + width;
    assert.ok(value >= low - 1e-9 && value <= high + 1e-9, `${value} outside bin ${q.index}`);
    assert.ok(q.error <= width / 2 + 1e-9);
    close(q.maxError, width / 2);
  }
  assert.equal(quantize(-90, bins).index, 0);
  assert.equal(quantize(90, bins).index, bins - 1);
  assert.equal(quantize(-500, bins).index, 0);
  assert.equal(quantize(500, bins).index, bins - 1);
}
// Values printed on the slide and in VLA_THEORY.md.
const q8 = quantize(30, 8), q32 = quantize(30, 32), q256 = quantize(30, 256);
assert.equal(q8.index, 5); close(q8.center, 33.75); close(q8.error, 3.75); close(q8.width, 22.5);
assert.equal(q32.index, 21); close(q32.center, 30.9375); close(q32.error, 0.9375);
assert.equal(q256.index, 170); close(q256.center, 29.8828125); close(q256.error, 0.1171875);
close(quantize(0, 256).maxError, 0.3515625);
assert.throws(() => quantize(0, 1), RangeError);
assert.throws(() => quantize(NaN, 8), RangeError);
assert.throws(() => quantize(0, 8.5), RangeError);

// Latency in control periods at 50 Hz (20 ms).
assert.equal(delaySteps(0), 0);
assert.equal(delaySteps(20), 1);
assert.equal(delaySteps(21), 2);
assert.equal(delaySteps(60), 3);
assert.equal(delaySteps(200), 10);
assert.equal(delaySteps(480), 24);
assert.throws(() => delaySteps(-1), RangeError);

const covered = (segments, duration) => {
  const marks = new Array(duration).fill(0);
  for (const { start, end } of segments) for (let t = start; t < end; t++) marks[t] += 1;
  return marks;
};
for (const execute of [10, 25, 40]) {
  for (let latency = 0; latency <= 480; latency += 20) {
    const d = latency / 20;
    for (const mode of ["sync", "async"]) {
      const plan = schedule({ mode, latencyMs: latency, execute });
      assert.equal(plan.delaySteps, d);
      // The robot lane is a partition of the displayed 150 steps: each step is
      // either executing one action or paused, never both and never missing.
      assert.ok(covered(plan.robot, 150).every(count => count === 1), `${mode} s=${execute} d=${d} robot lane`);
      // At most one inference runs at a time.
      assert.ok(covered(plan.inference, 150).every(count => count <= 1), `${mode} inference overlap`);
      for (const segment of plan.robot) assert.ok(segment.start < segment.end);
      if (mode === "sync") {
        close(plan.pauseRatio, d / (execute + d));
        assert.equal(plan.discardedPerChunk, 0);
        // Pauses coincide exactly with inference in synchronous execution.
        assert.deepEqual(covered(plan.robot.filter(s => s.kind === "pause"), 150), covered(plan.inference, 150));
      } else {
        const interval = Math.max(execute, d);
        assert.equal(plan.interval, interval);
        close(plan.pauseRatio, Math.max(0, interval + d - 50) / interval);
        assert.equal(plan.discardedPerChunk, d);
        // Every executed action after a switch exists in its chunk: run length ≤ 50 - d.
        for (const segment of plan.robot.filter(s => s.kind === "run" && s.chunk > 0)) {
          assert.ok(segment.end - segment.start <= 50 - d);
        }
        // A new chunk arrives exactly when its inference finishes.
        for (const job of plan.inference) {
          const next = plan.robot.find(s => s.kind === "run" && s.chunk === job.chunk);
          if (next && job.end < 150) assert.equal(next.start, job.end);
        }
      }
    }
  }
}
// Cases discussed on the slide: s = 25, latency 200 ms.
const sync = schedule({ mode: "sync", latencyMs: 200, execute: 25 });
const asyncPlan = schedule({ mode: "async", latencyMs: 200, execute: 25 });
close(sync.pauseRatio, 10 / 35);
assert.equal(asyncPlan.pauseRatio, 0);
assert.equal(pausedSteps(asyncPlan.robot), 0);
assert.ok(pausedSteps(sync.robot) > 0);
// s = 40 with 300 ms: 40 + 15 > 50, so the asynchronous chunk runs out for 5 steps per switch.
close(schedule({ mode: "async", latencyMs: 300, execute: 40 }).pauseRatio, 5 / 40);
assert.throws(() => schedule({ mode: "fast", latencyMs: 0, execute: 10 }), RangeError);
assert.throws(() => schedule({ mode: "sync", latencyMs: 0, execute: 60 }), RangeError);
console.log("PASS: 균일 구간 토큰화 18,001×4 값의 구간 포함·오차 한계·경계, 슬라이드 예시 값, 동기·비동기 청크 일정 150단계 분할·추론 비중첩·정지 비율·도착 시점");
