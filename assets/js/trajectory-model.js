(function (root, factory) {
  "use strict";
  const model = factory();
  if (typeof module === "object" && module.exports) module.exports = model;
  else root.TrajectoryModel = model;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  // One joint, in degrees. A fifth-order time scaling starts/ends at rest
  // with zero acceleration. This is an educational reference, not M1 limits.
  function validate(duration, start, end) {
    if (![duration, start, end].every(Number.isFinite) || duration <= 0) {
      throw new RangeError("유한한 시작·목표각과 양수인 이동 시간이 필요합니다.");
    }
  }
  function sample(time, duration, start = 0, end = 60) {
    validate(duration, start, end);
    if (!Number.isFinite(time)) throw new RangeError("시간은 유한한 수여야 합니다.");
    if (time <= 0) return { position: start, velocity: 0, acceleration: 0 };
    if (time >= duration) return { position: end, velocity: 0, acceleration: 0 };
    const u = time / duration, distance = end - start;
    return {
      position: start + distance * (10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5),
      velocity: distance / duration * 30 * u ** 2 * (1 - u) ** 2,
      acceleration: distance / duration ** 2 * 60 * u * (1 - u) * (1 - 2 * u)
    };
  }
  function peaks(duration, start = 0, end = 60) {
    validate(duration, start, end);
    const distance = Math.abs(end - start);
    return {
      velocity: 15 / 8 * distance / duration,
      acceleration: 10 / Math.sqrt(3) * distance / duration ** 2
    };
  }
  return { sample, peaks };
});
