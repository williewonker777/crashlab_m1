# 크래쉬랩 M1 — 로봇 AI 강의 덱

2026 크래쉬랩 강의 ①~④를 위한 **PPT 대체형 정적 슬라이드 덱**이다.

- `index.html`: OT와 네 개 강의 덱 진입
- `orientation.html`: 한 학기 운영 · 프로젝트 · 평가 안내 (12장)
- `lecture-1.html`: ROS2 로봇 프로그래밍 이론·실습 (60장)
- `lecture-2.html`: 조작 — 주행 · 모터 제어 (16장)
- `lecture-3.html`: VSLAM · 내비게이션 (47장)
- `lecture-4.html`: VLA 이론 (14장)
- 전체: OT 12장 + 4개 강의 137장, 총 149장

강의 1은 PowerPoint 원본의 텍스트·도형·이미지를 네이티브 HTML/CSS로 변환한 덱이다.
다시 생성하려면 다음 명령을 사용한다.

```bash
python3 tools/pptx_to_native_html.py "/path/to/theory.pptx" . --append "/path/to/practice.pptx"
```

## 조작

- 다음: `→`, `↓`, `Space`, `PageDown`
- 이전: `←`, `↑`, `PageUp`
- 처음/마지막: `Home`, `End`
- 전체화면: `F`
- 도움말: `?`

빌드 도구 없이 GitHub Pages 루트에서 동작한다. 모든 교육 다이어그램은 인라인 SVG다.
