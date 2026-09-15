(() => {
  "use strict";
  const model = window.CrashlabPIDModel;
  if (!model) return;
  const { simulate, PRESETS } = model;
  const NS = "http://www.w3.org/2000/svg";
  const colors = ["#1D2475", "#AF5900", "#006874"];

  const node = (tag, attrs = {}, text) => {
    const element = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const label = (svg, x, y, text, attrs = {}) => svg.append(node("text", {
    x, y, fill: "#3F3D42", "font-size": 22,
    "dominant-baseline": "central", ...attrs,
  }, text));
  const pathData = (samples, x, y, field) => samples.map((sample, i) =>
    `${i ? "L" : "M"}${x(sample.t).toFixed(2)},${y(sample[field]).toFixed(2)}`).join(" ");

  function plot(svg, runs, options = {}) {
    const W = 1000;
    const H = options.torque ? 565 : 540;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.replaceChildren(node("title", {}, options.torque
      ? "게인에 따라 계산한 관절 각도와 입력 토크" : "같은 관절 모델로 비교한 응답"));
    const left = 85, right = 960, top = 80;
    const bottom = options.torque ? 310 : 435;
    const all = runs.flatMap((run) => run.result.samples.map((sample) => sample.angle));
    const low = Math.min(-5, Math.floor(Math.min(...all) / 10) * 10);
    const high = Math.max(40, Math.ceil(Math.max(...all) / 10) * 10);
    const x = (time) => left + time / 12 * (right - left);
    const y = (angle) => bottom - (angle - low) / (high - low) * (bottom - top);
    const plotGroup = node("g");
    svg.append(plotGroup);
    plotGroup.append(node("rect", {
      x: left, y: y(31.5), width: right - left, height: y(28.5) - y(31.5), fill: "#E6F7F8",
    }));
    const tickStep = Math.max(10, Math.ceil((high - low) / 5 / 10) * 10);
    for (let value = Math.ceil(low / tickStep) * tickStep; value <= high; value += tickStep) {
      plotGroup.append(node("line", { x1: left, y1: y(value), x2: right, y2: y(value), stroke: "#DEE3EB", "stroke-width": 2 }));
      label(svg, left - 16, y(value), value, { "text-anchor": "end" });
    }
    plotGroup.append(node("line", { x1: left, y1: y(30), x2: right, y2: y(30), stroke: "#006874", "stroke-width": 2, "stroke-dasharray": "9 7" }));
    plotGroup.append(node("path", { d: `M${left} ${top}V${bottom}H${right}`, fill: "none", stroke: "#3F3D42", "stroke-width": 2 }));
    runs.forEach((run, i) => {
      const attributes = { d: pathData(run.result.samples, x, y, "angle"), fill: "none", stroke: run.color || colors[i], "stroke-width": 5, "stroke-linejoin": "round" };
      if (run.dash) attributes["stroke-dasharray"] = run.dash;
      plotGroup.append(node("path", attributes));
    });
    for (let time = 0; time <= 12; time += 2) label(svg, x(time), bottom + 27, time, { "text-anchor": "middle" });
    label(svg, left, 28, "관절 각도 (°)", { "font-weight": 700 });
    label(svg, right, 28, "목표 30° · 허용 범위 ±5%", { "text-anchor": "end", fill: "#006874", "font-size": 21 });
    if (options.torque) {
      const tTop = 398, tBottom = 482;
      const torqueY = (torque) => tBottom - (torque + 5) / 10 * (tBottom - tTop);
      for (const torque of [-5, 0, 5]) {
        svg.append(node("line", { x1: left, y1: torqueY(torque), x2: right, y2: torqueY(torque), stroke: "#DEE3EB", "stroke-width": 2 }));
        label(svg, left - 16, torqueY(torque), torque, { "text-anchor": "end", "font-size": 20 });
      }
      svg.append(node("path", { d: pathData(runs[0].result.samples, x, torqueY, "torque"), fill: "none", stroke: "#AF5900", "stroke-width": 3 }));
      label(svg, left, 372, "입력 토크 (N·m) · 한계 ±5", { "font-size": 21, "font-weight": 700 });
      for (let time = 0; time <= 12; time += 2) label(svg, x(time), 510, time, { "text-anchor": "middle", "font-size": 20 });
      label(svg, right, 545, "시간 (s)", { "text-anchor": "end", "font-size": 19 });
    } else {
      label(svg, right, 505, "시간 (s)", { "text-anchor": "end" });
    }
  }

  document.querySelectorAll("[data-pid-comparison]").forEach((svg) => {
    const isP = svg.dataset.pidComparison === "p";
    const cases = isP
      ? [["Kp = 0.10", { kp: 0.1, ki: 0, kd: 0 }], ["Kp = 0.30", { kp: 0.3, ki: 0, kd: 0 }], ["Kp = 0.80", { kp: 0.8, ki: 0, kd: 0 }]]
      : [["P", PRESETS.P], ["PI", PRESETS.PI], ["PID", PRESETS.PID]];
    const runs = cases.map(([name, gains]) => ({ name, result: simulate(gains), dash: !isP && name === "P" ? "14 9" : null }));
    plot(svg, runs);
    if (!isP) {
      const descriptions = [];
      runs.forEach(({ name, result }) => {
        const panel = document.querySelector(`[data-pid-case='${name}']`);
        const peak = Math.max(...result.samples.map((sample) => sample.angle));
        const values = {
          angle: `${result.samples.at(-1).angle.toFixed(1)}°`,
          peak: `${peak.toFixed(1)}°`,
          error: `${result.metrics.finalError.toFixed(2)}°`,
          overshoot: `${result.metrics.overshoot.toFixed(1)}%`,
        };
        if (panel) panel.querySelectorAll("[data-case-value]").forEach((element) => {
          element.textContent = values[element.dataset.caseValue];
        });
        descriptions.push(`${name}: 12초 뒤 오차 ${values.error}, 최대 오버슈트 ${values.overshoot}`);
      });
      svg.setAttribute("aria-label", `같은 모델에서 I와 D를 추가한 응답 비교. ${descriptions.join(". ")}`);
    }
  });

  const lab = document.querySelector("[data-pid-lab]");
  if (!lab) return;
  const sliders = [...lab.querySelectorAll("input[type='range']")];
  const antiWindup = lab.querySelector("[data-pid-antiwindup]");
  const chart = lab.querySelector("[data-pid-chart]");
  let pending = 0;

  const readGains = () => Object.fromEntries(sliders.map((input) => [input.dataset.gain, Number(input.value)]));
  function render() {
    const gains = readGains();
    sliders.forEach((input) => {
      lab.querySelector(`[data-gain-value='${input.dataset.gain}']`).textContent = Number(input.value).toFixed(2);
    });
    lab.querySelectorAll("[data-pid-preset]").forEach((button) => {
      const preset = PRESETS[button.dataset.pidPreset];
      button.setAttribute("aria-pressed", String(Object.keys(preset).every((key) => Math.abs(preset[key] - gains[key]) < 1e-8)));
    });
    const result = simulate(gains, { antiWindup: antiWindup.checked });
    plot(chart, [{ result }], { torque: true });
    const metrics = result.metrics;
    const values = {
      overshoot: `${metrics.overshoot.toFixed(1)}%`,
      error: `${metrics.finalError.toFixed(2)}°`,
      settling: metrics.settlingTime === null ? "미도달" : `${metrics.settlingTime.toFixed(2)} s`,
      rise: metrics.riseTime === null ? "미도달" : `${metrics.riseTime.toFixed(2)} s`,
    };
    Object.entries(values).forEach(([key, value]) => {
      lab.querySelector(`[data-pid-metric='${key}']`).textContent = value;
    });
    const note = metrics.settlingTime === null
      ? "12초 안에 목표 ±5% 범위를 유지하지 못했습니다."
      : `${metrics.settlingTime.toFixed(2)}초부터 관측 종료까지 목표 ±5% 범위를 유지합니다.`;
    lab.querySelector("[data-pid-status]").textContent = metrics.settlingTime === null
      ? "12초 관측 · 목표 ±5% 범위 유지 실패"
      : `12초 관측 · ${metrics.settlingTime.toFixed(2)}초 이후 목표 ±5% 범위 유지`;
    lab.querySelector("[data-pid-saturation]").textContent = `${metrics.saturationPercent.toFixed(1)}%`;
    chart.setAttribute("aria-label", `Kp ${gains.kp}, Ki ${gains.ki}, Kd ${gains.kd}. 최대 오버슈트 ${values.overshoot}, 12초 뒤 오차 ${values.error}. ${note}`);
  }
  const schedule = () => {
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(render);
  };
  sliders.forEach((input) => input.addEventListener("input", schedule));
  antiWindup.addEventListener("change", schedule);
  lab.querySelectorAll("[data-pid-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      const gains = PRESETS[button.dataset.pidPreset];
      sliders.forEach((input) => { input.value = gains[input.dataset.gain]; });
      render();
    });
  });
  render();
})();
