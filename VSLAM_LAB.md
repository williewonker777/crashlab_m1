# 강의 03 · Visual SLAM 실습과 구현 결과

사용자가 제공한 `/home/wonker/crashlab_vslam`을 참고 구현으로 사용한다.
별도의 구현 가이드 페이지와 링크는 제거하고 **실습 → 해당 결과**를 한 쌍으로 배치했다.
이론 1~60p는 본문을 유지하며, 강의 3은 총 72장이다.

| 실습 | 결과 | 내용 | 결과 근거 |
| --- | --- | --- | --- |
| 61 | 62 | RGB-D 입력과 동기화 | 현재 토픽의 영상·깊이 캡처, node.py의 디코딩 |
| 63 | 64 | 특징점과 3D–2D 대응 | 현재 입력에 frontend.py 실행 |
| 65 | 66 | VO 추적과 실패 개선 | docs/vo-before-after.png, README |
| 67 | 68 | 키프레임과 점유 지도 | docs/live-map.png, slam.py·slam_node.py |
| 69 | 70 | 루프 제약과 지도 보정 | docs/slam-result.png, slam.py·posegraph.py |
| 71 | 72 | 동일 입력의 VO/SLAM 평가 | README의 3.52 m bag 비교표, replay.py·evaluate.py |

## 현재 입력으로 생성한 결과

`tools/capture-vslam-lab.py`는 이미 설정된 ROS 환경에서 두 RGB-D 쌍을 구독한다.
운동 명령·TF 발행·파라미터 변경 없이 센서를 읽으며, 제공된 코드 파일을 변경하지 않는다.
`node.py`의 SENSOR_QOS와 디코딩 함수, `PinholeCamera.from_camera_info`,
`RGBDFrontend.make_frame`, `match`, `estimate_motion`을 사용한다.

```bash
python3 tools/capture-vslam-lab.py --source /home/wonker/crashlab_vslam
```

그림과 메타데이터는 `assets/img/vslam-results/`에 있다.
`live-capture.json`에는 캡처 시각, 참조 소스 SHA-256, 입력 규격과 측정값을 기록한다.
이 명령은 센서 발행이 존재하는 ROS 2 환경에서 실행하는 자료 생성 도구이며, 웹사이트 동작에는 필요하지 않다.

2026-09-28 19:44 KST에 읽은 결과:

- 입력 토픽은 `/aeirobot/vslam_left_image`, `/aeirobot/vslam_depth`,
  `/aeirobot/vslam_left_camera_info`다.
- 1280×720, rgb8 / 32FC1, `zed_left_camera_optical_frame`.
  BEST_EFFORT / VOLATILE, 동기화 큐 10, 허용 시각 차이 0.02초.
- CameraInfo: fx=fy=586.666656..., cx=640, cy=360.
- 영상 시각은 7220.93 s와 7221.43 s, 각 RGB–깊이 쌍의 시각 차이는 0 ms.
- 첫 깊이 영상에서 유한한 양수 픽셀 비율은 75.3509%.
- 기준 영상 특징점 1,810개, 깊이 조건을 통과한 특징점 1,608개.
- 3D–2D 대응 1,390쌍, PnP inlier 1,368개, 추정 성공.
- `live-input.png`는 RGB와 깊이 시각화다. 표시 범위는 0~8 m이고, 범위를 넘는 유효 깊이는
  최댓값 색으로 표시한다. 무효 깊이는 회색이다. 이 표시 범위가 추적기의 깊이 제한은 아니다.
- `live-matches.png`는 정제된 자세의 재투영 오차가 3 px 이하인 대응 중 32쌍만 표시한다.
  두 프레임의 입력·프론트엔드 확인 결과이며 전체 주행 정확도 측정은 아니다.

## 기존 실행 결과의 출처와 조건

제공된 프로젝트의 다음 그림은 수정하지 않고 그대로 복사했다. 복사본과 원본의 SHA-256이 같다.

- `docs/vo-before-after.png`: 별도의 VO 비교 bag. 고정 4.2 m 깊이 제한에서 적응형 제한과
  이동량 검사를 적용한 전후 결과다. 그림과 README의 기록은 추적 실패 81→0회,
  ATE RMSE 40.2→2.8 cm, 종점 위치 오차 85.2→4.4 cm다.
  이는 아래 사각 경로 SLAM 비교와 다른 기록이다.
- `docs/live-map.png`: 별도 라이브 저장 지도. 341×272칸, 0.05 m/칸,
  키프레임 59개와 루프 제약 20개가 반영되어 있다. 남색=점유, 흰색=자유, 회색=미탐색.
- `docs/slam-result.png`: 3.52 m 사각 경로, 입력 703프레임, 키프레임 65개, 루프 제약 32개.
  주황 점선은 VO, 빨강은 보정 궤적, 녹색은 루프 제약이다.
- 결과 6의 표는 README의 위 3.52 m 기록을 옮긴다. ATE RMSE 7.00→3.60 cm,
  종점 위치 6.56→0.43 cm, 거리 대비 종점 오차 1.87→0.12%, 종점 yaw 3.17→0.05°.
  `replay.run_slam()`은 키프레임 시각의 GT와 보정 전후 자세를 평가한다.

기존 그림·표를 이번 작업에서 전체 bag으로 재생해 얻었다고 표현하지 않는다.
README의 후속 11 m / 1,934프레임 실험은 조건이 달라 위 표와 섞지 않는다.
현재 소스의 기본 파라미터로 과거 결과가 완전히 재현된다고도 단정하지 않는다.

`evaluate.py`의 `ate()`는 각 궤적의 첫 자세로 정렬한 뒤 3차원 위치 오차의 RMSE를 계산한다.
일반적인 새 평가에서는 시각과 로봇 기준점을 먼저 일치시켜야 한다. 현재 GT 토픽의 child는
`robot_root`이고 몸체 출력은 `base_footprint`에 해당하므로, 기존 기록을 프레임 보정까지 검증한
절대 정확도 보증처럼 사용하지 않는다. 표는 제공된 코드·문서의 평가 규칙에 따른 사례다.

## 실습과 실제 코드의 연결

- `node.py`: RGB-D 구독·동기화와 CameraInfo 캐시. `odom`·`path`는 `/crashlab_vslam/` 아래에 발행한다.
  TF 기본 발행은 꺼져 있다. 헤더 시각 TF가 늦으면 최신 장착 변환을 사용하는 구현이므로,
  기본 사례는 머리 자세가 고정된 조건으로 이해한다.
- `frontend.py`: ORB → 깊이 역투영 → 매칭 → PnP·RANSAC·정제 → 이동량 검사.
  PnP 결과를 역변환한 `T_ref_cur`를 `Motion`에 담는다.
- `vo.py`: 키프레임에 대한 자세를 추적하고 직전 프레임 매칭을 보조로 사용한다.
  `tracked`, `reason`을 통해 실패를 구분한다. `node.py`는 실패 시 큰 공분산을 발행한다.
- `slam.py`: 원본 VO와 보정 자세를 분리하고 지역 점군을 저장한다. `map_scans()`와
  `occupancy_grid()`로 공간을 구성한다. 이 코드의 ROS 지도 출력은 **OccupancyGrid**다.
  따라서 실습 4의 결과 규약도 점군 확인과 OccupancyGrid 출력으로 맞췄다.
- `posegraph.py`: SE(2) 그래프를 Gauss–Newton으로 최적화하고 첫 노드를 고정한다.
  `slam_node.py`는 `/crashlab_vslam/map`, `/graph_path`, `/loops`, `/map_pose`를 발행한다.
- `replay.py`·`evaluate.py`: 고정 입력을 재생하고 같은 평가 규칙으로 비교한다.

## 검증

- 제공된 코드의 기존 테스트를 `./run_tests.sh -q`로 실행해 통과했다.
  실제 수집 항목은 182개다. 코드 변경이나 주행 노드 실행은 하지 않았다.
- 현재 토픽의 두 프레임을 원본 프론트엔드로 처리해 입력·특징점 결과 그림을 생성했다.
- 홈페이지와 덱의 슬라이드 수, 61~72p 순서, ID·ARIA·링크·이미지를 확인한다.
- 강의 이론 1~60p는 전체 장수 ARIA 변경을 제외하고 본문이 같다.
- 별도 구현 가이드 HTML·링크·전용 CSS를 제거한다. 과거 변경 기록은 DESIGN.md에 남긴다.
