(() => {
  "use strict";

  const demo = document.querySelector(".motor-encoder");
  if (!demo) return;

  const buttons = [...demo.querySelectorAll("[data-encoder-lead]")];
  const waveform = demo.querySelector(".motor-encoder-quadrature");
  const status = demo.querySelector("[data-encoder-status]");
  const playButton = demo.querySelector("[data-encoder-play]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const optical = Object.fromEntries([
    "rotor", "sensor-a", "sensor-b", "transmitted", "shutter", "receiver", "light-dot",
    "light-status", "photon-in", "photon-out", "cursor-line", "cursor-a", "cursor-b",
  ].map((name) => [name, demo.querySelector(`[data-encoder-${name}]`)]));
  let playing = !reducedMotion.matches;
  let elapsed = 0;
  let frame = null;
  let previousTime = null;
  let previousLight = null;

  const modulo = (value, period) => ((value % period) + period) % period;
  const renderOptics = () => {
    const forward = demo.dataset.encoderDirection === "A";
    // Eight slit periods per turn; sixteen seconds per turn, slowed for teaching.
    // The initial angles align the fixed A/B pickups with the waveform's first edges.
    const angle = (forward ? -8.4375 : 42.1875) + (forward ? 1 : -1) * elapsed * 22.5;
    const openAt = (sensorAngle) => modulo(sensorAngle - angle, 45) >= 22.5;
    const a = openAt(0);
    const b = openAt(11.25);
    optical.rotor.setAttribute("transform", `rotate(${angle.toFixed(4)} 78 80)`);
    optical["sensor-a"].setAttribute("fill", a ? "#F0B323" : "#1D2475");
    optical["sensor-b"].setAttribute("fill", b ? "#F0B323" : "#1D2475");
    demo.dataset.encoderLightA = String(Number(a));
    demo.dataset.encoderLightB = String(Number(b));

    if (a !== previousLight) {
      optical.transmitted.setAttribute("opacity", a ? "1" : "0");
      optical.shutter.setAttribute("opacity", a ? "0" : "1");
      optical.receiver.setAttribute("fill", a ? "#E6F7F8" : "#D8DEE9");
      optical["light-dot"].setAttribute("fill", a ? "#C38B00" : "#647080");
      optical["photon-out"].setAttribute("opacity", a ? "1" : "0");
      optical["light-status"].textContent = a ? "빛 통과 → 수광 신호 1" : "빛 차단 → 수광 신호 0";
      previousLight = a;
    }
    const travel = modulo(elapsed, 1);
    optical["photon-in"].setAttribute("cx", 317 + travel * 121);
    optical["photon-out"].setAttribute("cx", 472 + travel * 129);

    // One pulse period is 160px and lasts two seconds. Rewind after three periods.
    const x = 70 + modulo(elapsed, 6) * 80;
    optical["cursor-line"].setAttribute("d", `M${x} 16 V145`);
    optical["cursor-a"].setAttribute("cx", x);
    optical["cursor-a"].setAttribute("cy", a ? 25 : 65);
    optical["cursor-b"].setAttribute("cx", x);
    optical["cursor-b"].setAttribute("cy", b ? 97 : 137);
  };

  const canAnimate = () => playing && !document.hidden && demo.getAttribute("aria-current") === "true";
  const tick = (time) => {
    frame = null;
    if (!canAnimate()) { previousTime = null; return; }
    if (previousTime !== null) elapsed += Math.min((time - previousTime) / 1000, 0.1);
    previousTime = time;
    renderOptics();
    frame = requestAnimationFrame(tick);
  };
  const syncAnimation = () => {
    if (canAnimate() && frame === null) {
      previousTime = null;
      frame = requestAnimationFrame(tick);
    } else if (!canAnimate()) {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      previousTime = null;
    }
  };
  const setPlaying = (value) => {
    playing = value;
    demo.dataset.encoderPlaying = String(playing);
    playButton.textContent = playing ? "일시정지" : "재생";
    syncAnimation();
  };

  // 160px is one period; 40px is the quarter-period phase difference.
  const signalPath = (high, low, firstRise) => {
    let path = `M70 ${low}`;
    for (let rise = firstRise; rise < 625; rise += 160) {
      const fall = Math.min(rise + 80, 625);
      path += ` H${rise} V${high} H${fall}`;
      if (fall < 625) path += ` V${low}`;
    }
    return `${path} H625`;
  };

  const setText = (name, value) => {
    demo.querySelector(`[data-encoder-${name}]`).textContent = value;
  };

  const selectLead = (lead) => {
    const forward = lead === "A";
    const following = forward ? "B" : "A";
    const start = forward ? 10 : 12;
    const end = forward ? 12 : 10;

    demo.dataset.encoderDirection = lead;
    buttons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.encoderLead === lead));
    });
    demo.querySelector("[data-encoder-wave-a]").setAttribute("d", signalPath(25, 65, forward ? 100 : 140));
    demo.querySelector("[data-encoder-wave-b]").setAttribute("d", signalPath(97, 137, forward ? 140 : 100));
    waveform.setAttribute("aria-label", `${lead} 신호가 ${following} 신호보다 4분의 1주기 앞선다. 이 예시에서는 카운트가 ${forward ? "증가" : "감소"}하는 방향이다. 파형은 선후 관계를 보여주는 개념도이다.`);
    status.textContent = `${lead}가 ${following}보다 먼저 상승 → 카운트 ${forward ? "증가" : "감소"}`;

    setText("angle-start", `${start}°`);
    setText("angle-end", `${end}°`);
    setText("count-start", `${start * 10}카운트 × 0.1°`);
    setText("count-end", `${end * 10}카운트 × 0.1°`);
    setText("rate-formula", `(${end}° − ${start}°) ÷ 0.1 s`);
    setText("rate-result", `= ${forward ? "+" : "−"}20°/s`);
    elapsed = 0;
    previousTime = null;
    renderOptics();
    syncAnimation();
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => selectLead(button.dataset.encoderLead));
  });
  playButton.addEventListener("click", () => setPlaying(!playing));
  new MutationObserver(syncAnimation).observe(demo, { attributes: true, attributeFilter: ["aria-current"] });
  document.addEventListener("visibilitychange", syncAnimation);
  reducedMotion.addEventListener("change", (event) => { if (event.matches) setPlaying(false); });
  selectLead("A");
  setPlaying(playing);
})();
