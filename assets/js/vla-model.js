(function (root, factory) {
  "use strict";
  const model = factory();
  if (typeof module === "object" && module.exports) module.exports = model;
  else root.VlaModel = model;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  // Educational models for lecture 4. They explain the arithmetic of uniform
  // action binning and of chunk execution timing; they are not M1 settings.

  function quantize(value, bins, min = -90, max = 90) {
    if (![value, bins, min, max].every(Number.isFinite) || !Number.isInteger(bins) || bins < 2 || max <= min) {
      throw new RangeError("유한한 값, 2 이상의 정수 구간 수, min < max가 필요합니다.");
    }
    const width = (max - min) / bins;
    const clipped = Math.min(max, Math.max(min, value));
    // The upper edge belongs to the last bin so every value in [min, max] has a token.
    const index = Math.min(bins - 1, Math.floor((clipped - min) / width));
    const center = min + (index + 0.5) * width;
    return { index, center, width, error: Math.abs(clipped - center), maxError: width / 2, clipped };
  }

  function delaySteps(latencyMs, hz = 50) {
    if (!Number.isFinite(latencyMs) || latencyMs < 0 || !Number.isFinite(hz) || hz <= 0) {
      throw new RangeError("0 이상의 지연과 양수인 제어 주파수가 필요합니다.");
    }
    // Round before ceil so values such as 0.1 * 3 do not add a spurious step.
    return Math.ceil(Number((latencyMs * hz / 1000).toFixed(9)));
  }

  // Steps are control periods. Chunk 0 is ready at t = 0 in both modes.
  // sync: execute s actions, stop for the d-step inference, repeat.
  // async: start the next inference d steps before the switch so it arrives on
  // time; one inference runs at a time, so the switch interval is u = max(s, d).
  // After a switch the first d actions of the new chunk are already in the past.
  function schedule({ mode, latencyMs, execute, horizon = 50, hz = 50, durationSteps = 150 }) {
    if (mode !== "sync" && mode !== "async") throw new RangeError("mode는 sync 또는 async입니다.");
    if (![execute, horizon, durationSteps].every(Number.isInteger) || execute < 1 || horizon < execute || durationSteps < 1) {
      throw new RangeError("1 ≤ 실행 길이 ≤ 청크 길이인 정수와 양수인 표시 길이가 필요합니다.");
    }
    const d = delaySteps(latencyMs, hz);
    const robot = [], inference = [];
    const push = (lane, kind, start, end, chunk) => {
      const s = Math.max(0, start), e = Math.min(durationSteps, end);
      if (e > s) lane.push({ kind, start: s, end: e, chunk });
    };
    let paused = 0, discardedPerChunk = 0, interval;
    if (mode === "sync") {
      interval = execute + d;
      for (let t = 0, k = 0; t < durationSteps; k++) {
        push(robot, "run", t, t + execute, k);
        t += execute;
        if (d > 0) {
          push(inference, "infer", t, t + d, k + 1);
          push(robot, "pause", t, t + d, k + 1);
        }
        t += d;
      }
      paused = d / interval;
    } else {
      interval = Math.max(execute, d);
      if (interval > horizon) throw new RangeError("추론 간격이 청크 길이보다 길면 행동이 모자랍니다.");
      discardedPerChunk = d;
      for (let k = 0; k * interval < durationSteps; k++) {
        const start = k * interval, next = start + interval;
        const firstIndex = k === 0 ? 0 : d;
        const available = horizon - firstIndex;
        const runEnd = Math.min(next, start + available);
        push(robot, "run", start, runEnd, k);
        if (runEnd < next) push(robot, "pause", runEnd, next, k + 1);
        if (d > 0) push(inference, "infer", next - d, next, k + 1);
      }
      paused = Math.max(0, interval + d - horizon) / interval;
    }
    return { delaySteps: d, interval, pauseRatio: paused, discardedPerChunk, robot, inference };
  }

  function pausedSteps(segments) {
    return segments.filter(segment => segment.kind === "pause").reduce((sum, segment) => sum + segment.end - segment.start, 0);
  }

  return { quantize, delaySteps, schedule, pausedSteps };
});
