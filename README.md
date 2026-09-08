# 크래쉬랩 M1 — 로봇 AI 강의 덱

2026 크래쉬랩 강의 ①~④를 위한 **PPT 대체형 정적 슬라이드 덱**이다.

- `index.html`: OT와 네 개 강의 덱 진입
- `orientation.html`: 한 학기 운영 · 프로젝트 · 평가 안내 (12장)
- `lecture-1.html`: 로보틱스 기초 · ROS2 · 개발환경 (21장)
- `lecture-2.html`: 제어 (63장)
- `lecture-3.html`: VSLAM · 내비게이션 (47장)
- `lecture-4.html`: VLA 이론 (14장)
- 전체: OT 12장 + 4개 강의 145장, 총 157장

## 조작

- 다음: `→`, `↓`, `Space`, `PageDown`
- 이전: `←`, `↑`, `PageUp`
- 처음/마지막: `Home`, `End`
- 전체화면: `F`
- 도움말: `?`

빌드 도구 없이 GitHub Pages 루트에서 동작한다. 모든 교육 다이어그램은 인라인 SVG다.

강의 ②의 챕터 3은 차동 구동 기구학을 중심으로 오도메트리·좌표계·TF·quaternion을 연결한다. 34페이지에서는 좌우 바퀴 속도에 따른 궤적을, 41페이지에서는 yaw에 따른 quaternion을 조작할 수 있다. 구성과 참고 자료는 [MOBILE_ROBOT.md](MOBILE_ROBOT.md)에 정리했다.

챕터 4 「팔 제어」는 ALICE M1의 7자유도 팔로 물체에 접근하고 잡고 옮기는 매니퓰레이션을 다룬다. 52페이지는 7개 관절의 순기구학 시연, 54페이지는 같은 TCP pose를 유지하는 서로 다른 팔 자세의 역기구학 시연이다. 로봇 모델·사진·수업 구성은 [ARM_MANIPULATION.md](ARM_MANIPULATION.md)에 정리했다.
