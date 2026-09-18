# 크래쉬랩 M1 — 로봇 AI 강의 덱

2026 크래쉬랩 강의 ①~④를 위한 **PPT 대체형 정적 슬라이드 덱**이다.

- `index.html`: OT와 네 개 강의 덱 진입
- `orientation.html`: 한 학기 운영 · 프로젝트 · 평가 안내 (11장)
- `lecture-1.html`: ROS2 로봇 프로그래밍 이론·실습 (60장)
- `lecture-2.html`: 제어 (65장) — 이론 63 + 실습 2
- `lecture-3.html`: VSLAM · 내비게이션 (63장) — 이론 57 + 실습 6
- `lecture-4.html`: VLA 이론 (14장)
- 전체: OT 11장 + 4개 강의 202장, 총 213장

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

강의 ②의 챕터 3은 차동 구동 기구학을 중심으로 오도메트리·좌표계·TF·quaternion을 연결한다. 35페이지에서는 좌우 바퀴 속도에 따른 궤적을, 42페이지에서는 yaw에 따른 quaternion을 조작할 수 있다. 구성과 참고 자료는 [MOBILE_ROBOT.md](MOBILE_ROBOT.md)에 정리했다.

챕터 4 「팔 제어」는 ALICE M1의 7자유도 팔로 물체에 접근하고 잡고 옮기는 매니퓰레이션을 다룬다. 52페이지는 7개 관절의 순기구학 시연, 54페이지는 같은 TCP pose를 유지하는 서로 다른 팔 자세의 역기구학 시연이다. 63페이지에서 관련 개념을 복습하고, 64~65페이지에서는 Pinocchio로 FK·IK를 구현해 로봇 TF와 비교하고 동작으로 연결한다. 실습의 손 기준 프레임은 시연의 교육용 TCP와 구분한다. 로봇 모델·사진·수업 구성은 [ARM_MANIPULATION.md](ARM_MANIPULATION.md)에 정리했다.
