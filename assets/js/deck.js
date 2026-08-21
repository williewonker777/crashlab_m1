(() => {
  "use strict";

  const deck = document.querySelector("[data-deck]");
  if (!deck) return;

  const slides = [...deck.querySelectorAll(".slide")];
  const progress = document.querySelector("[data-progress]");
  const counter = document.querySelector("[data-counter]");
  const help = document.querySelector("#shortcut-help");
  const helpOpen = document.querySelector("[data-help-open]");
  const helpClose = document.querySelector("[data-help-close]");
  const fullscreenButton = document.querySelector("[data-fullscreen]");
  const previousDeck = deck.dataset.prevDeck;
  const nextDeck = deck.dataset.nextDeck;
  let currentIndex = 0;
  let scrollFrame = 0;

  const clamp = (value) => Math.max(0, Math.min(slides.length - 1, value));

  const updateChrome = (index) => {
    currentIndex = clamp(index);
    const current = currentIndex + 1;
    progress.style.transform = `scaleX(${current / slides.length})`;
    counter.textContent = `${current} / ${slides.length}`;
    slides.forEach((slide, slideIndex) => {
      if (slideIndex === currentIndex) slide.setAttribute("aria-current", "true");
      else slide.removeAttribute("aria-current");
    });
  };

  const activeIndexFromScroll = () => {
    const center = deck.scrollTop + deck.clientHeight / 2;
    let closest = 0;
    let distance = Infinity;
    slides.forEach((slide, index) => {
      const slideCenter = slide.offsetTop + slide.offsetHeight / 2;
      const nextDistance = Math.abs(center - slideCenter);
      if (nextDistance < distance) {
        distance = nextDistance;
        closest = index;
      }
    });
    return closest;
  };

  const goTo = (index, updateHash = true) => {
    const target = clamp(index);
    slides[target].scrollIntoView({ block: "start", behavior: "auto" });
    updateChrome(target);
    if (updateHash) history.replaceState(null, "", `#slide-${target + 1}`);
  };

  const goRelative = (offset) => {
    const target = currentIndex + offset;
    if (target < 0 && previousDeck) {
      location.href = previousDeck;
      return;
    }
    if (target >= slides.length && nextDeck) {
      location.href = nextDeck;
      return;
    }
    goTo(target);
  };

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
      else await document.exitFullscreen();
    } catch (error) {
      console.warn("전체화면을 사용할 수 없습니다.", error);
    }
  };

  const openHelp = () => {
    if (!help.open) help.showModal();
  };

  const closeHelp = () => {
    if (help.open) help.close();
  };

  document.addEventListener("keydown", (event) => {
    if (help.open) {
      if (event.key === "?") {
        event.preventDefault();
        closeHelp();
      }
      return;
    }

    if (event.target instanceof Element
      && event.target.closest("button")
      && [" ", "Enter"].includes(event.key)) {
      return;
    }

    const nextKeys = ["ArrowRight", "ArrowDown", " ", "PageDown"];
    const previousKeys = ["ArrowLeft", "ArrowUp", "PageUp"];

    if (nextKeys.includes(event.key)) {
      event.preventDefault();
      goRelative(1);
    } else if (previousKeys.includes(event.key)) {
      event.preventDefault();
      goRelative(-1);
    } else if (event.key === "Home") {
      event.preventDefault();
      goTo(0);
    } else if (event.key === "End") {
      event.preventDefault();
      goTo(slides.length - 1);
    } else if (event.key.toLowerCase() === "f") {
      event.preventDefault();
      toggleFullscreen();
    } else if (event.key === "?") {
      event.preventDefault();
      openHelp();
    }
  });

  deck.addEventListener("scroll", () => {
    cancelAnimationFrame(scrollFrame);
    scrollFrame = requestAnimationFrame(() => updateChrome(activeIndexFromScroll()));
  }, { passive: true });

  helpOpen.addEventListener("click", openHelp);
  helpClose.addEventListener("click", closeHelp);
  fullscreenButton.addEventListener("click", toggleFullscreen);

  document.addEventListener("fullscreenchange", () => {
    fullscreenButton.setAttribute("aria-pressed", String(Boolean(document.fullscreenElement)));
  });

  const hashMatch = location.hash.match(/^#slide-(\d+)$/);
  const initial = hashMatch ? clamp(Number(hashMatch[1]) - 1) : 0;
  requestAnimationFrame(() => goTo(initial, false));
})();
