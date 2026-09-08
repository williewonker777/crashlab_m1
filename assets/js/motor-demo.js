(() => {
  "use strict";

  const demo = document.querySelector(".motor-modes");
  if (!demo) return;

  const toggle = demo.querySelector("[data-motor-demo-toggle]");
  const restart = demo.querySelector("[data-motor-demo-restart]");

  const setPlaying = (playing) => {
    demo.dataset.demoPlaying = String(playing);
    toggle.setAttribute("aria-pressed", String(playing));
    toggle.textContent = playing ? "일시정지" : "계속 재생";
  };

  toggle.addEventListener("click", () => {
    demo.dataset.demoStarted = "true";
    restart.disabled = false;
    setPlaying(demo.dataset.demoPlaying !== "true");
  });

  restart.addEventListener("click", () => {
    demo.getAnimations({ subtree: true }).forEach((animation) => {
      animation.currentTime = 0;
    });
    setPlaying(true);
  });
})();
