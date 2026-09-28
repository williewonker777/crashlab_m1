(() => {
  "use strict";

  // Four-neighbour, unit-cost grid. Manhattan distance is a consistent lower bound.
  const map = {
    width: 7, height: 5, start: [0, 3], goal: [6, 1],
    walls: [[2, 1], [2, 2], [2, 3], [3, 1], [4, 1]],
  };
  const key = ([x, y]) => `${x},${y}`;
  const point = (id) => id.split(",").map(Number);
  const remaining = (id, goal) => {
    const [x, y] = point(id);
    return Math.abs(x - goal[0]) + Math.abs(y - goal[1]);
  };
  const createSearch = (grid = map) => ({
    grid, walls: new Set(grid.walls.map(key)),
    open: new Set([key(grid.start)]), closed: new Set(),
    costs: new Map([[key(grid.start), 0]]), parents: new Map(),
    current: null, path: [], done: false, steps: 0,
  });
  const candidates = (state) => [...state.open].sort((a, b) => {
    const ha = remaining(a, state.grid.goal), hb = remaining(b, state.grid.goal);
    return state.costs.get(a) + ha - state.costs.get(b) - hb || ha - hb;
  });
  const stepSearch = (state) => {
    if (state.done) return state;
    const current = candidates(state)[0];
    if (!current) { state.done = true; return state; }
    state.current = current;
    state.open.delete(current);
    state.closed.add(current);
    state.steps += 1;
    // Stop when the goal is selected from the entire frontier, not when first seen.
    if (current === key(state.grid.goal)) {
      for (let id = current; id !== undefined; id = state.parents.get(id)) state.path.unshift(id);
      state.done = true;
      return state;
    }
    const [x, y] = point(current);
    for (const [dx, dy] of [[1, 0], [0, -1], [0, 1], [-1, 0]]) {
      const nx = x + dx, ny = y + dy, id = key([nx, ny]);
      if (nx < 0 || ny < 0 || nx >= state.grid.width || ny >= state.grid.height
        || state.walls.has(id) || state.closed.has(id)) continue;
      const cost = state.costs.get(current) + 1;
      if (cost < (state.costs.get(id) ?? Infinity)) {
        state.costs.set(id, cost);
        state.parents.set(id, current);
        state.open.add(id);
      }
    }
    if (!state.open.size) state.done = true;
    return state;
  };
  const stereoAt = (distance) => ({
    distance, disparity: 72 / distance,
    left: 370 + 108 / distance, right: 370 - 108 / distance,
  });

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { map, createSearch, candidates, stepSearch, remaining, stereoAt };
  }
  if (typeof document === "undefined") return;

  const eyeDemo = document.querySelector("[data-eye-demo]");
  if (eyeDemo) {
    const thumb = eyeDemo.querySelector("[data-eye-thumb]");
    const status = eyeDemo.querySelector("[data-eye-status]");
    const buttons = [...eyeDemo.querySelectorAll("[data-eye]")];
    buttons.forEach((button) => button.addEventListener("click", () => {
      const left = button.dataset.eye === "left";
      thumb.setAttribute("transform", `translate(${left ? 370 : 230} 0)`);
      status.textContent = left ? "왼쪽 눈으로 본 모습" : "오른쪽 눈으로 본 모습";
      buttons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
    }));
  }

  const stereoDemo = document.querySelector("[data-simple-stereo]");
  if (stereoDemo) {
    const slider = stereoDemo.querySelector("input[type=range]");
    const presets = [...stereoDemo.querySelectorAll("[data-distance]")];
    const update = () => {
      const { distance, disparity, left, right } = stereoAt(Number(slider.value));
      stereoDemo.querySelectorAll("[data-distance-output]").forEach((node) => { node.textContent = distance.toFixed(1); });
      stereoDemo.querySelector("[data-disparity-output]").textContent = disparity.toFixed(1).replace(/\.0$/, "");
      stereoDemo.querySelector("[data-ball-left]").setAttribute("cx", left);
      stereoDemo.querySelector("[data-ball-right]").setAttribute("cx", right);
      stereoDemo.querySelector("[data-left-guide]").setAttribute("d", `M${left} 86V289`);
      stereoDemo.querySelector("[data-right-guide]").setAttribute("d", `M${right} 210V289`);
      const measure = stereoDemo.querySelector("[data-disparity-line]");
      measure.setAttribute("x1", right);
      measure.setAttribute("x2", left);
      slider.setAttribute("aria-valuetext", `${distance.toFixed(1)}미터`);
      presets.forEach((button) => button.setAttribute("aria-pressed", String(Number(button.dataset.distance) === distance)));
    };
    slider.addEventListener("input", update);
    presets.forEach((button) => button.addEventListener("click", () => {
      slider.value = button.dataset.distance;
      update();
    }));
    update();
  }

  const quiz = document.querySelector("[data-astar-quiz]");
  if (quiz) {
    const choices = [...quiz.querySelectorAll("[data-choice]")];
    const feedback = quiz.querySelector("[data-quiz-feedback]");
    choices.forEach((button) => button.addEventListener("click", () => {
      const correct = button.dataset.choice === "B";
      choices.forEach((choice) => {
        choice.setAttribute("aria-pressed", String(choice === button));
        choice.classList.toggle("is-correct", choice === button && correct);
      });
      feedback.textContent = correct
        ? "맞아요! B는 4 + 4 = 8점. 가장 작은 점수라 먼저 살펴봐요."
        : `${button.dataset.choice}는 10점이에요. 온 길과 남은 길을 더해, 더 작은 점수를 찾아보세요.`;
    }));
  }

  const demo = document.querySelector("[data-astar-demo]");
  if (demo) {
    let state = createSearch();
    const cells = [...demo.querySelectorAll("[data-cell]")];
    const status = demo.querySelector("[data-search-status]");
    const next = demo.querySelector("[data-search-next]");
    const finish = demo.querySelector("[data-search-finish]");
    const render = () => {
      const path = new Set(state.path);
      cells.forEach((cell) => {
        const id = cell.dataset.cell;
        const isStart = id === key(map.start), isGoal = id === key(map.goal);
        cell.classList.toggle("is-candidate", state.open.has(id));
        cell.classList.toggle("is-checked", state.closed.has(id));
        cell.classList.toggle("is-current", id === state.current && !state.done);
        cell.classList.toggle("is-path", path.has(id));
        const f = state.costs.has(id) ? state.costs.get(id) + remaining(id, map.goal) : null;
        cell.querySelector("text").textContent = isStart ? "출발" : isGoal ? "학교"
          : state.walls.has(id) ? "벽" : path.has(id) ? "●" : state.open.has(id) ? f
            : state.closed.has(id) ? "·" : "";
        const [x, y] = point(id);
        cell.querySelector("title").textContent = `${x + 1}열 ${y + 1}행: ` + (isStart ? "출발" : isGoal ? "학교"
          : state.walls.has(id) ? "벽" : path.has(id) ? "찾은 길" : state.open.has(id) ? `후보, 점수 ${f}`
            : state.closed.has(id) ? "살펴본 칸" : "빈 칸");
      });
      const cost = state.current ? state.costs.get(state.current) : 0;
      const h = state.current ? remaining(state.current, map.goal) : remaining(key(map.start), map.goal);
      demo.querySelector("[data-search-g]").textContent = cost;
      demo.querySelector("[data-search-h]").textContent = h;
      demo.querySelector("[data-search-f]").textContent = cost + h;
      demo.querySelector("[data-search-count]").textContent = state.steps;
      if (state.done) {
        status.textContent = state.path.length
          ? `도착! 기록한 길을 거꾸로 이었어요. 가장 짧은 길은 ${state.path.length - 1}칸이에요.`
          : "후보를 모두 살펴봤지만 갈 수 있는 길이 없어요.";
      } else if (!state.steps) {
        status.textContent = "출발 칸부터 시작해요. ‘한 단계 보기’를 눌러 보세요.";
      } else {
        const best = candidates(state)[0];
        const score = state.costs.get(best) + remaining(best, map.goal);
        status.textContent = `이 칸의 이웃을 살펴봤어요. 남은 후보 ${state.open.size}개 중 다음은 ${score}점인 칸이에요.`;
      }
      next.disabled = state.done;
      finish.disabled = state.done;
    };
    next.addEventListener("click", () => { stepSearch(state); render(); });
    finish.addEventListener("click", () => { while (!state.done) stepSearch(state); render(); });
    demo.querySelector("[data-search-reset]").addEventListener("click", () => { state = createSearch(); render(); });
    render();
  }
})();
