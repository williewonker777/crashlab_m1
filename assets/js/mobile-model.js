(function (root, factory) {
  "use strict";
  const model = factory();
  if (typeof module === "object" && module.exports) module.exports = model;
  else root.MobileRobotModel = model;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function geometry(radius, track) {
    if (!Number.isFinite(radius) || !Number.isFinite(track) || radius <= 0 || track <= 0) {
      throw new RangeError("바퀴 반지름과 좌우 바퀴 간격은 양수여야 합니다.");
    }
  }

  function forward(left, right, radius = 0.1, track = 0.5) {
    geometry(radius, track);
    const vLeft = radius * left;
    const vRight = radius * right;
    const v = (vLeft + vRight) / 2;
    const omega = (vRight - vLeft) / track;
    return { vLeft, vRight, v, omega, radius: Math.abs(omega) < 1e-10 ? null : v / omega };
  }

  function inverse(v, omega, radius = 0.1, track = 0.5) {
    geometry(radius, track);
    return { left: (v - track * omega / 2) / radius, right: (v + track * omega / 2) / radius };
  }

  function wheelDelta(leftAngle, rightAngle, radius = 0.1, track = 0.5) {
    geometry(radius, track);
    const left = radius * leftAngle;
    const right = radius * rightAngle;
    return { left, right, distance: (left + right) / 2, heading: (right - left) / track };
  }

  function integrateMidpoint(pose, distance, heading) {
    const middle = pose.theta + heading / 2;
    return { x: pose.x + distance * Math.cos(middle), y: pose.y + distance * Math.sin(middle), theta: pose.theta + heading };
  }

  // 한 구간에서 일정한 v, omega에 대한 원호 적분. sinc로 직진 극한도 연속 처리한다.
  function integrateExact(pose, v, omega, dt) {
    const angle = omega * dt;
    const half = angle / 2;
    const sinc = Math.abs(half) < 1e-6 ? 1 - half * half / 6 : Math.sin(half) / half;
    const distance = v * dt * sinc;
    return { x: pose.x + distance * Math.cos(pose.theta + half), y: pose.y + distance * Math.sin(pose.theta + half), theta: pose.theta + angle };
  }

  // 부모 프레임으로 표현한 자식의 pose를 이용해 자식 프레임의 점을 변환한다.
  function transformPoint(pose, point) {
    const c = Math.cos(pose.theta), s = Math.sin(pose.theta);
    return { x: pose.x + c * point.x - s * point.y, y: pose.y + s * point.x + c * point.y };
  }

  function yawQuaternion(theta) {
    return { x: 0, y: 0, z: Math.sin(theta / 2), w: Math.cos(theta / 2) };
  }

  function quaternionYaw(q) {
    const norm = Math.hypot(q.x, q.y, q.z, q.w);
    if (!Number.isFinite(norm) || norm === 0) throw new RangeError("유효한 회전 쿼터니언이 필요합니다.");
    const x = q.x / norm, y = q.y / norm, z = q.z / norm, w = q.w / norm;
    return Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z));
  }

  return Object.freeze({ forward, inverse, wheelDelta, integrateMidpoint, integrateExact, transformPoint, yawQuaternion, quaternionYaw });
});
