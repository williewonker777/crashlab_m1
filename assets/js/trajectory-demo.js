(() => {
  "use strict";
  const model = window.TrajectoryModel;
  const lab = document.querySelector("[data-trajectory-lab]");
  if (!model || !lab) return;
  const buttons = [...lab.querySelectorAll("[data-trajectory-duration]")];
  const chart = lab.querySelector("[data-trajectory-chart]");
  // Both choices share a 0–4 s time axis and fixed 0–60 value axes.
  const chartPath = (duration, field, bottom) => Array.from({ length: 161 }, (_, i) => {
    const time = i / 40;
    const value = model.sample(time, duration)[field];
    return `${i ? "L" : "M"}${(64 + 136 * time).toFixed(2)} ${(bottom - value * 1.6).toFixed(2)}`;
  }).join(" ");
  const paths = new Map([2, 4].map(duration => [duration, {
    position: chartPath(duration, "position", 137),
    velocity: chartPath(duration, "velocity", 294)
  }]));
  function render(duration) {
    const selected = paths.get(duration), comparison = paths.get(duration === 4 ? 2 : 4);
    for (const field of ["position", "velocity"]) {
      lab.querySelector(`[data-trajectory-${field}]`).setAttribute("d", selected[field]);
      lab.querySelector(`[data-trajectory-${field}-comparison]`).setAttribute("d", comparison[field]);
    }
    const peak = model.peaks(duration), atOneSecond = model.sample(1, duration);
    lab.querySelector("[data-trajectory-angle]").textContent = `${atOneSecond.position.toFixed(1)}°`;
    lab.querySelector("[data-trajectory-speed]").textContent = `${peak.velocity.toFixed(1)}°/s`;
    lab.querySelector("[data-trajectory-acceleration]").textContent = `${peak.acceleration.toFixed(1)}°/s²`;
    buttons.forEach(button => button.setAttribute("aria-pressed", String(Number(button.dataset.trajectoryDuration) === duration)));
    lab.querySelector("[data-trajectory-legend]").textContent = `실선 ${duration}초 · 점선 ${duration === 4 ? 2 : 4}초`;
    lab.dataset.duration = String(duration);
    chart.setAttribute("aria-label", `한 관절을 0도에서 60도로 ${duration}초 동안 움직이는 목표 궤적. 굵은 선은 ${duration}초, 점선은 ${duration === 4 ? 2 : 4}초 계획이다. 위는 각도, 아래는 속도이며, 도착 후에는 60도를 유지하고 속도는 0이다.`);
  }
  buttons.forEach(button => button.addEventListener("click", () => render(Number(button.dataset.trajectoryDuration))));
  render(4);
})();
