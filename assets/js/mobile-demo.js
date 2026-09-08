(() => {
  "use strict";
  const model = window.MobileRobotModel;
  if (!model) return;
  const format = (value, digits = 2) => (Math.abs(value) < 0.5 * 10 ** -digits ? 0 : value).toFixed(digits);
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const lab = document.querySelector("[data-mobile-drive]");
  if (lab) {
    const slide = lab.closest(".slide");
    const left = lab.querySelector("[data-mobile-wheel='left']");
    const right = lab.querySelector("[data-mobile-wheel='right']");
    const board = lab.querySelector("[data-mobile-board]");
    const play = lab.querySelector("[data-mobile-play]");
    const presets = { straight: [5, 5], turn: [4, 6], spin: [-4, 4] };
    const duration = 6;
    const origin = { x: 0, y: 0, theta: 0 };
    let speed, planned, projection;
    let elapsed = 0, playing = !motion.matches, request = null, previousTime = null;
    const put = (selector, value) => { lab.querySelector(selector).textContent = value; };

    function setupPath() {
      speed = model.forward(Number(left.value), Number(right.value));
      planned = Array.from({ length: 121 }, (_, i) => model.integrateExact(origin, speed.v, speed.omega, duration * i / 120));
      const xs = planned.map(p => p.x), ys = planned.map(p => p.y);
      const minX = Math.min(...xs) - 0.65, maxX = Math.max(...xs) + 0.65;
      const minY = Math.min(...ys) - 0.65, maxY = Math.max(...ys) + 0.65;
      const scale = Math.min(160, 660 / (maxX - minX), 360 / (maxY - minY));
      projection = { scale, x: 400 - (minX + maxX) * scale / 2, y: 235 + (minY + maxY) * scale / 2 };
      const worldLeft = (60 - projection.x) / scale, worldRight = (740 - projection.x) / scale;
      const worldBottom = (projection.y - 425) / scale, worldTop = (projection.y - 45) / scale;
      let grid = "";
      for (let x = Math.ceil(worldLeft); x <= worldRight; x++) {
        const sx = projection.x + x * scale;
        grid += `<path d="M${sx} 45V425" stroke="${x === 0 ? "#647080" : "#E5E9EF"}" stroke-width="${x === 0 ? 2 : 1}"/><text x="${sx}" y="454" fill="#647080" font-size="22" text-anchor="middle">${x}</text>`;
      }
      for (let y = Math.ceil(worldBottom); y <= worldTop; y++) {
        const sy = projection.y - y * scale;
        grid += `<path d="M60 ${sy}H740" stroke="${y === 0 ? "#647080" : "#E5E9EF"}" stroke-width="${y === 0 ? 2 : 1}"/><text x="45" y="${sy + 7}" fill="#647080" font-size="22" text-anchor="end">${y}</text>`;
      }
      grid += '<text x="756" y="454" fill="#647080" font-size="23">x</text><text x="25" y="28" fill="#647080" font-size="23">y</text>';
      lab.querySelector("[data-mobile-grid]").innerHTML = grid;
      lab.querySelector("[data-mobile-preview]").setAttribute("d", path(planned));
      put("[data-mobile-left]", `${format(Number(left.value), 1)} rad/s`);
      put("[data-mobile-right]", `${format(Number(right.value), 1)} rad/s`);
      put("[data-mobile-v]", `${format(speed.v)} m/s`);
      put("[data-mobile-omega]", `${format(speed.omega)} rad/s`);
      put("[data-mobile-radius]", speed.radius === null ? (Math.abs(speed.v) < 1e-10 ? "정지" : "직진 · ∞") : `${format(speed.radius)} m`);
      lab.querySelectorAll("[data-mobile-preset]").forEach(button => {
        const values = presets[button.dataset.mobilePreset];
        button.setAttribute("aria-pressed", String(Number(left.value) === values[0] && Number(right.value) === values[1]));
      });
    }

    function path(points) {
      return points.map((p, i) => `${i ? "L" : "M"}${format(projection.x + p.x * projection.scale, 3)} ${format(projection.y - p.y * projection.scale, 3)}`).join(" ");
    }

    function render() {
      const pose = model.integrateExact(origin, speed.v, speed.omega, elapsed);
      const trail = planned.filter((_, i) => duration * i / 120 < elapsed);
      trail.push(pose);
      lab.querySelector("[data-mobile-trail]").setAttribute("d", path(trail));
      const scale = projection.scale;
      const robot = lab.querySelector("[data-mobile-robot]");
      robot.setAttribute("transform", `translate(${projection.x + pose.x * scale} ${projection.y - pose.y * scale}) rotate(${-pose.theta * 180 / Math.PI})`);
      robot.innerHTML = `<rect x="${-0.27 * scale}" y="${-0.19 * scale}" width="${0.54 * scale}" height="${0.38 * scale}" rx="${0.07 * scale}" fill="#E6F7F8" stroke="#006874" stroke-width="2"/><rect x="${-0.12 * scale}" y="${-0.29 * scale}" width="${0.24 * scale}" height="${0.08 * scale}" rx="4" fill="#1D2475"/><rect x="${-0.12 * scale}" y="${0.21 * scale}" width="${0.24 * scale}" height="${0.08 * scale}" rx="4" fill="#1D2475"/><path d="M0 0H${0.42 * scale}" stroke="#006874" stroke-width="4"/><path d="M${0.42 * scale} 0L${0.3 * scale} ${-0.06 * scale}V${0.06 * scale}Z" fill="#006874"/><circle r="4" fill="#1D2475"/>`;
      put("[data-mobile-time]", `${format(elapsed, 1)} s`);
      put("[data-mobile-pose]", `x ${format(pose.x)} m · y ${format(pose.y)} m · θ ${format(pose.theta * 180 / Math.PI, 1)}°`);
      board.setAttribute("aria-label", `바퀴 각속도 왼쪽 ${left.value}, 오른쪽 ${right.value} rad/s. 전진 ${format(speed.v)} m/s, 회전 ${format(speed.omega)} rad/s. ${format(elapsed, 1)}초의 위치 x ${format(pose.x)}, y ${format(pose.y)} 미터, 방향 ${format(pose.theta * 180 / Math.PI, 1)}도.`);
      play.textContent = playing ? "일시정지" : elapsed >= duration ? "다시 재생" : "재생";
      lab.dataset.playing = String(playing);
      lab.dataset.elapsed = String(elapsed);
      lab.dataset.pose = JSON.stringify(pose);
    }

    const active = () => slide.getAttribute("aria-current") === "true" && !document.hidden && playing;
    function schedule() {
      if (!active()) {
        if (request !== null) cancelAnimationFrame(request);
        request = null;
        previousTime = null;
      } else if (request === null) request = requestAnimationFrame(tick);
    }
    function tick(time) {
      request = null;
      if (!active()) { previousTime = null; return; }
      if (previousTime !== null) elapsed = Math.min(duration, elapsed + Math.min(0.1, (time - previousTime) / 1000));
      previousTime = time;
      if (elapsed >= duration) playing = false;
      render();
      schedule();
    }
    function restart(autoplay = false) {
      elapsed = 0;
      playing = autoplay;
      previousTime = null;
      setupPath();
      render();
      schedule();
    }
    [left, right].forEach(input => input.addEventListener("input", () => restart(false)));
    lab.querySelectorAll("[data-mobile-preset]").forEach(button => button.addEventListener("click", () => {
      [left.value, right.value] = presets[button.dataset.mobilePreset];
      restart(false);
    }));
    play.addEventListener("click", () => {
      if (elapsed >= duration) elapsed = 0;
      playing = !playing;
      previousTime = null;
      render();
      schedule();
    });
    lab.querySelector("[data-mobile-reset]").addEventListener("click", () => restart(false));
    new MutationObserver(schedule).observe(slide, { attributes: true, attributeFilter: ["aria-current"] });
    document.addEventListener("visibilitychange", schedule);
    motion.addEventListener("change", event => { if (event.matches) { playing = false; render(); schedule(); } });
    setupPath(); render(); schedule();
  }

  const orientation = document.querySelector("[data-mobile-quaternion]");
  if (orientation) {
    const input = orientation.querySelector("[data-mobile-yaw]");
    function renderYaw() {
      const degrees = Number(input.value), theta = degrees * Math.PI / 180;
      const q = model.yawQuaternion(theta);
      orientation.querySelector("[data-yaw-degrees]").textContent = `${degrees}°`;
      orientation.querySelector("[data-yaw-radians]").textContent = `θ = ${format(theta, 4)} rad · |q| = ${format(Math.hypot(q.x, q.y, q.z, q.w), 4)}`;
      for (const component of ["x", "y", "z", "w"]) orientation.querySelector(`[data-q='${component}']`).textContent = format(q[component], 4);
      orientation.querySelector("[data-yaw-arrow]").setAttribute("transform", `rotate(${-degrees} 220 170)`);
      orientation.querySelector("[data-yaw-svg]").setAttribute("aria-label", `Yaw ${degrees}도. quaternion 순서 x, y, z, w는 ${[q.x, q.y, q.z, q.w].map(v => format(v, 4)).join(", ")}`);
      orientation.querySelectorAll("[data-yaw-preset]").forEach(button => button.setAttribute("aria-pressed", String(Number(button.dataset.yawPreset) === degrees)));
    }
    input.addEventListener("input", renderYaw);
    orientation.querySelectorAll("[data-yaw-preset]").forEach(button => button.addEventListener("click", () => {
      input.value = button.dataset.yawPreset;
      renderYaw();
    }));
    renderYaw();
  }
})();
