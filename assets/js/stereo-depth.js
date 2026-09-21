(() => {
  "use strict";
  const slide = document.querySelector("[data-stereo-demo]");
  if (!slide) return;
  const range = slide.querySelector("[data-stereo-range]");
  // 교육용 이상 카메라의 값이며 실기기의 보정값이 아니다.
  // 정류 후 좌우 fₓ=600 px, cₓ=640 px. 점 P의 X=0.10 m를 고정한다.
  const focalPx = 600, baselineM = 0.12, principalPx = 640, pointXM = 0.10;
  const write = (name, value) => {
    slide.querySelectorAll(`[data-stereo-value="${name}"]`).forEach(node => { node.textContent = value; });
  };
  const position = u => 80 + (u - 600) * 5;
  const update = () => {
    const depthM = Number(range.value);
    // 화면에 보이는 좌표를 먼저 반올림하여, 표시한 뺄셈과 결과도 일치시킨다.
    const leftU = Number((principalPx + focalPx * pointXM / depthM).toFixed(2));
    const rightU = Number((principalPx + focalPx * (pointXM - baselineM) / depthM).toFixed(2));
    const disparityPx = Number((leftU - rightU).toFixed(2));
    write("depth", depthM.toFixed(2));
    write("left", leftU.toFixed(2));
    write("right", rightU.toFixed(2));
    write("disparity", disparityPx.toFixed(2));
    write("recovered", (focalPx * baselineM / disparityPx).toFixed(2));
    range.setAttribute("aria-valuetext", `${depthM.toFixed(2)} 미터`);
    const xLeft = position(leftU), xRight = position(rightU);
    slide.querySelector("[data-stereo-left]").setAttribute("cx", xLeft);
    slide.querySelector("[data-stereo-right]").setAttribute("cx", xRight);
    for (const [key, x] of [["left", xLeft], ["right", xRight]]) {
      const line = slide.querySelector(`[data-stereo-guide="${key}"]`);
      line.setAttribute("x1", x);
      line.setAttribute("x2", x);
    }
    const dim = slide.querySelector("[data-stereo-disparity]");
    dim.setAttribute("x1", xRight);
    dim.setAttribute("x2", xLeft);
    slide.querySelectorAll("[data-stereo-preset]").forEach(button => {
      button.setAttribute("aria-pressed", String(Number(button.dataset.stereoPreset) === depthM));
    });
    const description = slide.querySelector("[data-stereo-description]");
    description.textContent = `같은 점의 왼쪽 영상 좌표 ${leftU.toFixed(2)} 픽셀, 오른쪽 영상 좌표 ${rightU.toFixed(2)} 픽셀. 시차 ${disparityPx.toFixed(2)} 픽셀로 계산한 깊이는 ${(focalPx * baselineM / disparityPx).toFixed(2)} 미터다.`;
  };
  range.addEventListener("input", update);
  slide.querySelectorAll("[data-stereo-preset]").forEach(button => {
    button.addEventListener("click", () => { range.value = button.dataset.stereoPreset; update(); });
  });
  update();
})();
