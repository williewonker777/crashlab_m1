# 크래쉬랩 M1 — 로봇 AI 강의 덱

2026 크래쉬랩 강의 ①~④를 위한 **PPT 대체형 정적 슬라이드 덱**이다.

- `index.html`: OT와 네 개 강의 덱 진입
- `orientation.html`: 한 학기 운영 · 프로젝트 · 평가 안내 (11장)
- `lecture-1.html`: ROS2 로봇 프로그래밍 이론·실습 (60장)
- `lecture-2.html`: 제어 (66장) — 이론 63 + 실습 준비 1 + 실습 2
- `lecture-3.html`: VSLAM · 내비게이션 (66장) — 이론 60 + 실습 3 + 결과 예시 3
- `lecture-4.html`: VLA 이론 (14장)
- 전체: OT 11장 + 4개 강의 206장, 총 217장

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

강의 ③의 12~15페이지는 두 눈의 관찰 위치 → 거리와 시차의 관계 → 거리 슬라이더 → 거리 지도 순서로 스테레오를 쉽게 설명한다. 46~48페이지는 격자 지도의 최단 경로 → 후보 평가값 비교 → 단계별 A* 탐색 시연이다. 본문과 시연 피드백은 대학 강의용 서술체로 통일했다. 스테레오의 가정과 참고 자료는 [STEREO_DEPTH.md](STEREO_DEPTH.md), A*의 규칙과 검증은 [PATHFINDING.md](PATHFINDING.md)에 정리했다. 시연의 계산은 `node tools/check-lecture3-basics.cjs`로 검증한다.

강의 ③의 61~66페이지는 RViz 센서 확인 → 이동 궤적과 지도 생성 → 재방문 후 지도 보정의 세 기능으로 구성한 Visual SLAM 실습이다. 각 실습에는 완료 목표와 화면 중심의 결과물만 제시한다. AI 에이전트가 구현하고 학생은 실행 화면을 확인한 뒤 다음 실습으로 진행한다. 실습 바로 다음 장에는 센서·지도·보정 전후의 RViz 결과 예시를 배치했다. 구성과 예시의 출처는 [VSLAM_LAB.md](VSLAM_LAB.md)에 정리했다.

강의 ②의 챕터 3은 차동 구동 기구학을 중심으로 오도메트리·좌표계·TF·quaternion을 연결한다. 35페이지에서는 좌우 바퀴 속도에 따른 궤적을, 42페이지에서는 yaw에 따른 quaternion을 조작할 수 있다. 구성과 참고 자료는 [MOBILE_ROBOT.md](MOBILE_ROBOT.md)에 정리했다.

챕터 4 「팔 제어」는 ALICE M1의 7자유도 팔로 물체에 접근하고 잡고 옮기는 매니퓰레이션을 다룬다. 52페이지는 7개 관절의 순기구학 시연, 54페이지는 같은 TCP pose를 유지하는 서로 다른 팔 자세의 역기구학 시연이다. 63페이지에서 관련 개념을 복습하고, 64~65페이지에서는 Pinocchio로 FK·IK를 구현해 로봇 TF와 비교하고 동작으로 연결한다. 실습의 손 기준 프레임은 시연의 교육용 TCP와 구분한다. 로봇 모델·사진·수업 구성은 [ARM_MANIPULATION.md](ARM_MANIPULATION.md)에 정리했다.
