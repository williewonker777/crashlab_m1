(() => {
  "use strict";

  const header = document.querySelector(".site-header");
  const segmentButtons = document.querySelectorAll(".time-segment");
  const timeBars = document.querySelectorAll("[data-total-minutes]");

  const updateHeader = () => {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 8);
  };

  const closeTooltips = (except) => {
    document.querySelectorAll(".time-segment-wrap.is-open").forEach((segment) => {
      if (segment !== except) segment.classList.remove("is-open");
    });
  };

  segmentButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const segment = button.closest(".time-segment-wrap");
      const shouldOpen = !segment.classList.contains("is-open");
      closeTooltips(segment);
      segment.classList.toggle("is-open", shouldOpen);
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".time-segment-wrap")) closeTooltips();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeTooltips();
      document.activeElement?.blur();
    }
  });

  timeBars.forEach((bar) => {
    const expected = Number(bar.dataset.totalMinutes);
    const actual = [...bar.querySelectorAll("[data-minutes]")]
      .reduce((sum, segment) => sum + Number(segment.dataset.minutes), 0);

    if (actual !== expected) {
      console.error(`시간 배분 오류: ${actual}분 / ${expected}분`);
    }
  });

  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });
})();
