(() => {
  "use strict";
  const model = window.VlaModel;
  if (!model) return;
  const SVG = "http://www.w3.org/2000/svg";
  const make = (name, attributes = {}, text) => {
    const node = document.createElementNS(SVG, name);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const format = (value, digits) => (Object.is(Number(value.toFixed(digits)), -0) ? 0 : value).toFixed(digits);

  // Demo 1 · uniform action binning of one joint target in [-90°, 90°].
  const token = document.querySelector("[data-token-demo]");
  if (token) {
    const range = token.querySelector("[data-token-range]");
    const binsLayer = token.querySelector("[data-token-bins]");
    const zoomLayer = token.querySelector("[data-token-zoom]");
    const figure = token.querySelector("[data-token-figure]");
    const buttons = [...token.querySelectorAll("[data-token-bins-choice]")];
    const min = -90, max = 90, left = 40, right = 680;
    const x = value => left + (value - min) / (max - min) * (right - left);
    let bins = 256;
    const write = (name, value) => token.querySelectorAll(`[data-token-${name}]`).forEach(node => { node.textContent = value; });
    const update = () => {
      const value = Number(range.value);
      const q = model.quantize(value, bins, min, max);
      binsLayer.replaceChildren();
      const step = (right - left) / bins;
      for (let i = 0; i < bins; i++) {
        const active = i === q.index;
        binsLayer.append(make("rect", {
          x: (left + i * step).toFixed(3), y: 30, width: step.toFixed(3), height: 40,
          fill: active ? "#7B5EA7" : (i % 2 ? "#E3E7F1" : "#FFFFFF"),
          stroke: bins <= 32 ? "#C9D0E2" : "none", "stroke-width": 1
        }));
      }
      token.querySelector("[data-token-marker]").setAttribute("transform", `translate(${x(q.clipped).toFixed(2)} 0)`);
      // Zoom on seven neighbouring bins so the active one stays visible at 256 bins.
      zoomLayer.replaceChildren();
      const first = Math.min(Math.max(q.index - 3, 0), bins - 7);
      const zLeft = 80, zWidth = 80;
      for (let j = 0; j < 7; j++) {
        const index = first + j;
        const active = index === q.index;
        zoomLayer.append(make("rect", {
          x: zLeft + j * zWidth, y: 140, width: zWidth, height: 50, rx: 4,
          class: active ? "vla-bin is-active" : "vla-bin"
        }));
        zoomLayer.append(make("text", {
          x: zLeft + j * zWidth + zWidth / 2, y: 214, "text-anchor": "middle", class: "small"
        }, String(index)));
      }
      const zoomX = value => zLeft + ((value - min) / q.width - first) * zWidth;
      zoomLayer.append(make("line", {
        x1: zoomX(q.clipped).toFixed(2), y1: 130, x2: zoomX(q.clipped).toFixed(2), y2: 200,
        stroke: "#1D2475", "stroke-width": 5, "stroke-linecap": "round"
      }));
      zoomLayer.append(make("line", {
        x1: zoomX(q.center).toFixed(2), y1: 136, x2: zoomX(q.center).toFixed(2), y2: 196,
        stroke: "#416A22", "stroke-width": 4, "stroke-dasharray": "8 6"
      }));
      const activeLeft = left + q.index * step;
      token.querySelector("[data-token-link-left]").setAttribute("d", `M${activeLeft.toFixed(2)} 72 L${zLeft + (q.index - first) * zWidth} 138`);
      token.querySelector("[data-token-link-right]").setAttribute("d", `M${(activeLeft + step).toFixed(2)} 72 L${zLeft + (q.index - first + 1) * zWidth} 138`);
      write("value", format(q.clipped, 1));
      write("index", String(q.index));
      write("center", format(q.center, 2));
      write("error", format(q.error, 2));
      write("width", format(q.width, 3).replace(/0+$/, "").replace(/\.$/, ""));
      buttons.forEach(button => button.setAttribute("aria-pressed", String(Number(button.dataset.tokenBinsChoice) === bins)));
      range.setAttribute("aria-valuetext", `${format(q.clipped, 1)}도`);
      figure.setAttribute("aria-label", `${format(q.clipped, 1)}도를 ${bins}개 구간으로 나누면 ${q.index}번 구간이 되고, 구간 중앙값 ${format(q.center, 2)}도로 복원된다. 오차는 ${format(q.error, 2)}도이며 최대 오차는 구간 폭의 절반인 ${format(q.maxError, 3)}도다.`);
    };
    range.addEventListener("input", update);
    buttons.forEach(button => button.addEventListener("click", () => { bins = Number(button.dataset.tokenBinsChoice); update(); }));
    update();
  }

  // Demo 2 · synchronous versus asynchronous chunk execution at 50 Hz, H = 50.
  const chunk = document.querySelector("[data-chunk-demo]");
  if (chunk) {
    const range = chunk.querySelector("[data-chunk-range]");
    const robotLayer = chunk.querySelector("[data-chunk-robot]");
    const inferLayer = chunk.querySelector("[data-chunk-infer]");
    const figure = chunk.querySelector("[data-chunk-figure]");
    const modeButtons = [...chunk.querySelectorAll("[data-chunk-mode]")];
    const executeButtons = [...chunk.querySelectorAll("[data-chunk-execute]")];
    const left = 150, right = 700, steps = 150;
    const x = step => left + step / steps * (right - left);
    let mode = "async", execute = 25;
    const write = (name, value) => chunk.querySelectorAll(`[data-chunk-${name}]`).forEach(node => { node.textContent = value; });
    const bar = (layer, segment, y, height, fill) => {
      const width = x(segment.end) - x(segment.start);
      layer.append(make("rect", { x: x(segment.start).toFixed(2), y, width: Math.max(0, width - 1.5).toFixed(2), height, rx: 5, fill }));
      return width;
    };
    const label = (layer, segment, width, y, size, text) => {
      const node = make("text", {
        x: (x(segment.start) + width / 2).toFixed(2), y,
        "text-anchor": "middle", class: "white", "font-size": size
      }, text);
      layer.append(node);
      // Clip-free labels, including the shorter final segment and double-digit chunks.
      if (node.getComputedTextLength() > width - 13.5) node.remove();
    };
    const update = () => {
      const latency = Number(range.value);
      const plan = model.schedule({ mode, latencyMs: latency, execute });
      robotLayer.replaceChildren();
      inferLayer.replaceChildren();
      for (const segment of plan.robot) {
        const fill = segment.kind === "pause" ? "#F7931E" : (segment.chunk % 2 ? "#5B63B5" : "#1D2475");
        const width = bar(robotLayer, segment, 52, 56, fill);
        if (segment.kind === "run") label(robotLayer, segment, width, 80, 20, `C${segment.chunk}`);
      }
      for (const segment of plan.inference) {
        const width = bar(inferLayer, segment, 152, 44, "#7B5EA7");
        label(inferLayer, segment, width, 174, 18, `→C${segment.chunk}`);
      }
      const pausePercent = Math.round(plan.pauseRatio * 100);
      write("latency", String(latency));
      write("delay", String(plan.delaySteps));
      write("pause", String(pausePercent));
      write("discard", String(plan.discardedPerChunk));
      modeButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.chunkMode === mode)));
      executeButtons.forEach(button => button.setAttribute("aria-pressed", String(Number(button.dataset.chunkExecute) === execute)));
      range.setAttribute("aria-valuetext", `${latency}밀리초`);
      const modeName = mode === "sync" ? "동기" : "비동기";
      figure.setAttribute("aria-label", `${modeName} 실행, 인퍼런스 지연 ${latency}밀리초는 ${plan.delaySteps}개 제어 주기다. 청크마다 ${execute}개 행동을 실행할 때 로봇이 멈춰 있는 시간은 ${pausePercent}%이고, 새 청크에서 이미 지나간 행동 ${plan.discardedPerChunk}개는 실행하지 않는다.`);
    };
    range.addEventListener("input", update);
    modeButtons.forEach(button => button.addEventListener("click", () => { mode = button.dataset.chunkMode; update(); }));
    executeButtons.forEach(button => button.addEventListener("click", () => { execute = Number(button.dataset.chunkExecute); update(); }));
    update();
  }
})();
