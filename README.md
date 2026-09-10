# 크래쉬랩 M1 — 로봇 AI 강의 덱

2026 크래쉬랩 강의 ①~④를 위한 **PPT 대체형 정적 슬라이드 덱**이다.

- `index.html`: OT와 네 개 강의 덱 진입
- `orientation.html`: 한 학기 운영 · 프로젝트 · 평가 안내 (12장)
- `lecture-1.html`: ROS2 로봇 프로그래밍 이론·실습 (59장)
- `lecture-2.html`: 조작 — 주행 · 모터 제어 (16장)
- `lecture-3.html`: VSLAM · 내비게이션 (47장)
- `lecture-4.html`: VLA 이론 (14장)
- 전체: OT 12장 + 4개 강의 136장, 총 148장

강의 1은 PowerPoint 원본의 텍스트·도형·이미지를 네이티브 HTML/CSS로 변환한 덱이다.
다른 강의와 같은 헤더·서체·색상 토큰을 사용하며, 본문 그리드는 글자 크기에 맞춰 높이가 늘어난다.
좁은 화면에서는 도식 영역을 가로로 스크롤할 수 있다.
다시 생성하려면 다음 명령을 사용한다.

```bash
python3 tools/pptx_to_native_html.py "/path/to/theory.pptx" . --append "/path/to/practice.pptx"
```

변환기는 `tools/style_lecture1.py`로 공통 템플릿을 적용한다.
기존 변환 HTML에도 `python3 tools/style_lecture1.py lecture-1.html`로 적용할 수 있다.

## 조작

- 다음: `→`, `↓`, `Space`, `PageDown`
- 이전: `←`, `↑`, `PageUp`
- 처음/마지막: `Home`, `End`
- 전체화면: `F`
- 도움말: `?`

빌드 도구 없이 GitHub Pages 루트에서 동작한다. 모든 교육 다이어그램은 인라인 SVG다.
