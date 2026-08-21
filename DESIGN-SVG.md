# 다이어그램 컴포넌트 규격 (v4)
2026-08-21. **모든 SVG는 이 규격의 컴포넌트만 조합해서 만든다. 즉흥적으로 그리지 않는다.**

## 0. 왜 이 문서가 필요한가

지금 SVG들은 매번 손으로 그려져서 화살표 하나하나가 다르다. 실제 렌더에서 확인한 문제:

- 화살촉이 선 굵기에 비해 크고 연결부가 어색하다
- 같은 그림 안에서 화살표 길이가 제각각이라 리듬이 없다
- 라벨("SLAM")이 아무것과도 연결되지 않은 채 허공에 떠 있다
- 흰 노드를 흰 카드 위에 올려 경계가 사라졌다
- 카드 폭 1680px 중 내용이 900px만 쓰고 좌우 400px씩 비었다
- 순환 구조인데 화살표가 끊겨 순환으로 안 읽힌다

규칙을 더 쓰는 대신 **쓸 부품을 정해준다.**

## 1. 공통 defs — 모든 SVG 최상단에 넣는다

```svg
<defs>
  <!-- 화살촉: 선 굵기 5 기준. refX=9 로 촉 끝이 목표 지점에 정확히 닿는다 -->
  <marker id="ah-blue" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M0,1 L10,5 L0,9 L2.5,5 Z" fill="#1D2475"/>
  </marker>
  <marker id="ah-accent" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M0,1 L10,5 L0,9 L2.5,5 Z" fill="#75B446"/>
  </marker>
  <marker id="ah-gray" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M0,1 L10,5 L0,9 L2.5,5 Z" fill="#3F3D42"/>
  </marker>
</defs>
```

화살촉 뒷면을 `L2.5,5` 로 오목하게 판다. 직선 삼각형보다 선과의 접합이 자연스럽다.
**화살표는 반드시 marker 로만 그린다.** polygon 을 따로 그려 붙이지 않는다.

## 2. 노드

```svg
<!-- 주 노드: 남색 채움 + 흰 글자 -->
<g class="node-primary">
  <rect x="0" y="0" width="260" height="110" rx="16" fill="#1D2475"/>
  <text x="130" y="55" text-anchor="middle" dominant-baseline="central"
        font-size="30" font-weight="700" fill="#FFFFFF">추정</text>
</g>

<!-- 보조 노드: 연그린 채움 + 남색 글자 -->
<rect ... rx="16" fill="#EDF6E3"/>  <text ... fill="#1D2475">

<!-- 3차 노드: 흰 채움 + 2px 테두리 (배경이 흰색이 아닐 때만 사용) -->
<rect ... rx="16" fill="#FFFFFF" stroke="#D8DEE9" stroke-width="2"/>
```

**규격 통일**: 노드 크기는 `260×110` 또는 `200×90` 둘 중 하나만 쓴다. 제각각 금지.
`dominant-baseline="central"` 을 반드시 넣어라. 없으면 글자가 세로 중앙에서 어긋난다.

## 3. 연결선

```svg
<!-- 직선 연결 -->
<line x1="260" y1="55" x2="460" y2="55"
      stroke="#1D2475" stroke-width="5" stroke-linecap="round"
      marker-end="url(#ah-blue)"/>

<!-- 꺾인 연결: 모서리를 둥글게 -->
<path d="M 260 55 H 380 Q 400 55 400 75 V 200"
      fill="none" stroke="#1D2475" stroke-width="5"
      stroke-linecap="round" stroke-linejoin="round"
      marker-end="url(#ah-blue)"/>
```

- 연결선은 **노드 경계에서 시작하고 노드 경계에서 끝난다.** 노드 안쪽에서 시작하지 않는다
- 길이가 다른 화살표를 같은 그림에 섞지 마라. **같은 층위의 연결은 같은 길이**로 맞춘다
- 꺾을 때는 반드시 `Q` 로 반경 20 둥글리기. 직각 꺾임 금지

## 4. 순환 구조

4개 노드를 사각으로 배치하고 화살표 4개를 따로 그리면 순환으로 안 읽힌다.
**하나의 닫힌 path** 로 그리고 중간에 marker 를 붙인다.

```svg
<!-- 네 노드를 감싸는 둥근 사각 궤도. 중앙 라벨 자리를 비워둔다 -->
<path d="M 330 110 H 690 Q 730 110 730 150 V 330 Q 730 370 690 370
         H 330 Q 290 370 290 330 V 150 Q 290 110 330 110 Z"
      fill="none" stroke="#1D2475" stroke-width="5" stroke-dasharray="0"/>
<!-- 진행 방향 표시는 궤도 위 4곳에 작은 삼각형으로 -->
```

중앙에 라벨을 둘 거면 **연한 원판을 깔고 그 위에** 올린다. 허공에 띄우지 않는다.

## 5. 주석 (리더선)

```svg
<g class="annot">
  <circle cx="520" cy="240" r="5" fill="#75B446"/>
  <line x1="520" y1="240" x2="620" y2="180"
        stroke="#75B446" stroke-width="2"/>
  <text x="632" y="180" dominant-baseline="central"
        font-size="22" fill="#3F3D42">여기서 오차가 생긴다</text>
</g>
```

- 점(r=5) → 2px 리더선 → 라벨. 라벨은 리더선 끝에서 **12px 띄운다**
- 라벨은 절대 도형 위에 직접 올리지 않는다

## 6. 캔버스와 여백

- `viewBox="0 0 1600 620"` 를 기본으로 한다. 카드 폭을 실제로 채운다
- 내용은 `x: 40 ~ 1560` 을 쓴다. 좌우 400px씩 비우지 마라
- 모든 좌표는 **20의 배수**에 맞춘다. 정렬이 정돈감을 만든다

## 7. 텍스트

| 용도 | 크기 | 굵기 | 색 |
|---|---|---|---|
| 노드 라벨 | 30 | 700 | 흰색(주) / #1D2475(보조) |
| 주석 | 22 | 400 | #3F3D42 |
| 수치 | 28 | 700 | #1D2475 |
| 축 라벨 | 22 | 500 | #3F3D42 |

`text` 에는 항상 `dominant-baseline` 을 명시한다.

## 8. 금지

- polygon 으로 그린 수제 화살촉
- 노드 크기가 그림마다 다른 것
- 흰 배경 카드 위의 테두리 없는 흰 노드
- 연결선 없이 떠 있는 라벨
- 20의 배수가 아닌 좌표
- 같은 그림 안에서 화살표 길이가 제각각인 것
