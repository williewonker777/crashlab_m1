/* Copy one lab assignment together with the student's verification criteria. */
(() => {
  const timers = new WeakMap();
  const clean = (text) => text.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();

  function assignment(slide) {
    const checks = [...slide.querySelectorAll(".agent-review li")].map((item, i) =>
      `${i + 1}. ${clean(item.innerText)}`
    );
    return [
      slide.querySelector("h2").textContent.trim(),
      "",
      "에이전트 작업",
      clean(slide.querySelector(".agent-prompt").innerText),
      "",
      "학생이 직접 검증할 항목 — 최종 판정은 학생이 작성한다.",
      ...checks,
      "",
      clean(slide.querySelector(".lab-check").innerText),
    ].join("\n");
  }

  function legacyCopy(text) {
    const field = document.createElement("textarea");
    field.value = text;
    field.readOnly = true;
    field.setAttribute("aria-label", "복사할 실습 지시문");
    Object.assign(field.style, { position: "fixed", left: "-9999px", top: "0" });
    document.body.append(field);
    try {
      field.select();
      return document.execCommand("copy");
    } finally {
      field.remove();
    }
  }

  document.querySelectorAll("[data-copy-lab]").forEach((button) => {
    button.addEventListener("click", async () => {
      const slide = button.closest(".agent-lab");
      const status = slide.querySelector(".lab-copy-status");
      const text = assignment(slide);
      clearTimeout(timers.get(button));
      button.disabled = true;
      let copied = false;
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
          copied = true;
        }
      } catch (_) { /* Try the browser's local copy operation next. */ }
      if (!copied) {
        try { copied = legacyCopy(text); } catch (_) { /* Offer manual selection. */ }
      }
      button.disabled = false;
      button.focus({ preventScroll: true });
      if (copied) {
        button.textContent = "복사 완료";
        status.textContent = "에이전트 작업과 학생 검증 항목을 복사했다.";
      } else {
        const range = document.createRange();
        range.selectNodeContents(slide.querySelector(".lab-body"));
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = "Ctrl/Cmd+C";
        status.textContent = "자동 복사를 사용할 수 없어 본문을 선택했다. Ctrl+C 또는 Command+C로 복사한다.";
      }
      timers.set(button, setTimeout(() => { button.textContent = "지시문 복사"; }, 3000));
    });
  });
})();
