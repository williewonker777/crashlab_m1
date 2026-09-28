# 강의 03 · Visual SLAM 실습

강의 3의 61~72p는 실습과 결과 예시를 한 쌍으로 배치한다.
최종 제출에는 각 결과 파일과 함께 학생이 작성한 전체 실습 코드·실행 명령을 포함한다.
학생은 ALICE M1의 RGB-D 입력으로 특징점 대응, 이동 추정, 점군 지도,
재방문 검증과 자세 보정을 연결한다. 각 단계에서 파일을 저장해 다음 단계의 입력으로 사용한다.

| 실습 / 결과 | 작업 범위 | 제출 파일 | 확인 항목 |
| --- | --- | --- | --- |
| 61 / 62 | 동기화된 입력 30쌍 | input.png, input.csv | 영상·깊이 정렬, 시각 차이, 유효 깊이 비율 |
| 63 / 64 | 두 영상의 특징점 대응 | matches.png, pairs.csv | 이전 3D 점과 현재 2D 픽셀의 행 순서 |
| 65 / 66 | 짧은 복귀 주행의 VO | trajectory.png, poses.csv | 원점·단위, 지지점, OK/LOST 기록 |
| 67 / 68 | 키프레임 5개의 점군 지도 | map.png, keyframes.npz | 지역 점과 자세의 분리 저장, 지도 재생성 |
| 69 / 70 | 재방문 후보 한 쌍의 검증 | loop.png, loop.csv | 기하 검증, 채택/기각 사유, 상대 자세 |
| 71 / 72 | 5개 자세와 루프 제약 1개 | comparison.png, comparison.csv | 같은 관측·가중치의 잔차, 지도 변화 |

제목은 「실습 N · 주제」와 「실습 N 결과 · 같은 주제」로 대응시킨다.
본문은 기존 강의의 「~한다/~이다」 서술체를 사용한다.
점유 지도, 자동 장소 검색, GT 기반 정확도 평가는 추가 확장으로 둔다.
첫 실습부터 전체 시스템의 모든 기능을 요구하지 않는다.
별도 구현 가이드 페이지는 없다.

## 실제 토픽의 입력 예시

62·64p는 2026-09-28 19:44 KST의 읽기 전용 입력 캡처다.

- 영상: `/aeirobot/vslam_left_image`, rgb8, 1280×720.
- 깊이: `/aeirobot/vslam_depth`, 32FC1, m 단위, 1280×720.
- 내부 파라미터: `/aeirobot/vslam_left_camera_info`.
- CameraInfo: fx=fy=586.666656…, cx=640, cy=360.
- 관측한 optical frame: `zed_left_camera_optical_frame`.
- BEST_EFFORT / VOLATILE. 동기화 허용 차이는 20 ms다.
- 캡처한 두 쌍은 RGB–깊이 시각 차이가 각각 0 ms다.
- 첫 깊이 영상의 유한한 양수 픽셀은 75.3509%다.
- 첫 영상 특징점 1,810개, 깊이 조건을 통과한 특징점 1,608개,
  3D–2D 대응 1,390쌍, PnP 지지점 1,368개다.

`live-input.png`의 깊이 색상 범위는 0~8 m이고 무효 깊이는 회색이다.
`live-matches.png`는 정제된 자세의 재투영 오차가 3 px 이하인 대응 중 32쌍만 표시한다.
이 값들은 입력 확인 사례이며 학생의 필수 점수나 주행 정확도 측정값이 아니다.
기록은 `assets/img/vslam-results/live-capture.json`에 있다.

## 알고리즘 점검용 입력과 결과

66·68·70·72p는 **학습용 합성 RGB-D 입력**을 처리한 결과다.
ALICE M1의 실제 주행 측정과 구분한다. 수업에서 저장한 ALICE M1 입력을 기본으로 사용하고,
움직임이 있는 입력이 필요할 때 이 데이터로 단계별 계산을 점검할 수 있다.
예시 수치와 같아지는 것이 제출 기준은 아니다.

- [입력 NPZ](assets/data/vslam-lab/sample-input.npz): 텍스처가 있는 방의 49프레임, 640×360.
- [배열 규격 JSON](assets/data/vslam-lab/sample-info.json): 키·크기·단위와 예시 측정값.
- [결과 파일 ZIP](assets/data/vslam-lab/sample-results.zip): 궤적, 점군, 루프 검증,
  보정 비교의 PNG·CSV·NPZ와 데이터 설명. 구현 파일은 포함하지 않는다.

NPZ는 NumPy의 `load()`로 읽는 배열 묶음이다. 입력 키는 다음과 같다.

| 키 | 크기·형식 | 뜻 |
| --- | --- | --- |
| gray | uint8 [49, 360, 640] | 특징점 처리용 명암 영상 |
| depth | float32 [49, 360, 640] | optical Z, m 단위; NaN은 무효 |
| K | float64 [3, 3] | 이 영상 크기에 맞는 내부 파라미터; 왜곡 없음 |
| stamp | float64 [49] | 시각, 초 |
| T_base_camera | float64 [4, 4] | 고정된 카메라→몸체 변환 |

예시 장면은 평면 이동 후 시작 위치·방향으로 돌아온다.
49프레임 중 첫 프레임은 원점 설정에 사용하며, 실패 2프레임을 LOST로 기록한다.
두 실패는 이동량 검사에서 발생한다. 지지점이 많아도 비현실적인 이동은 기각할 수 있다.
실패 프레임에서 마지막 자세를 유지하되, 그 좌표를 새로운 성공 관측으로 간주하지 않는다.

지도에는 대표 키프레임 5개와 지역 점 11,045개를 사용한다.
키프레임 0과 4의 재방문 대응 458쌍이 PnP의 지지점으로 남아, 루프 제약 1개를 추가한다.
`sample-loop.png`에는 24쌍만 표시한다. 이동 제약 4개와 재방문 제약 1개를 사용해
첫 자세를 고정하고 평면 자세 5개를 보정한다.

| 비교 항목 | 보정 전 | 보정 후 |
| --- | ---: | ---: |
| 전체 잔차 J | 84.89 | 9.70 |
| 루프 위치 잔차 | 35.98 cm | 3.59 cm |
| 추적 실패 | 2회 | 2회 |

J는 위치 잔차를 0.05 m로, 각도 잔차를 5°에 해당하는 rad 값으로 나눈 뒤 제곱해 합한다.
보정 전후 모두 **같은 이동·루프 제약과 같은 가중치**를 사용한다.
루프 위치 잔차는 두 자세가 예측하는 상대 이동과 PnP가 관측한 상대 이동의 차이다.
시작점과 종점의 거리나 GT에 대한 위치 오차와 구분한다.
작은 잔차는 관측 사이의 일관성을 뜻하며, 그 자체가 절대 정확도를 보증하지는 않는다.

## 제출 파일 규약

- `input.csv`: `t_rgb_s, t_depth_s, dt_ms, valid_ratio`. 비율은 0~1이다.
- `pairs.csv`: `X, Y, Z, u, v`. XYZ는 이전 카메라 좌표(m), uv는 현재 영상 좌표(px)다.
- `poses.csv`: `t_s, x_m, y_m, yaw_rad, matches, inliers, status, reason`.
  첫 행은 INIT, 이후는 OK 또는 LOST다. 좌표는 첫 몸체 자세를 기준으로 한다.
- `keyframes.npz`: 키프레임 번호·시각·원래 카메라 자세·지역 점군을 저장한다.
  예시에서는 `points[offsets[k]:offsets[k+1]]`가 k번째 키프레임의 카메라 좌표 점군이다.
  `T_world_camera`는 카메라에서 첫 카메라 좌표로의 변환이다.
- `loop.csv`: `i, j, dx_m, dy_m, dyaw_rad, matches, inliers, accepted, reason`.
  상대 자세는 j의 몸체 좌표를 i의 몸체 좌표로 바꾼다. 기각 시 상대 자세를 제약으로 쓰지 않는다.
- `comparison.csv`: `metric, before, after`. `graph_cost`, `loop_translation_m`,
  `lost_frames`를 기록한다. 화면에는 cm로 표시할 수 있지만 CSV의 길이 단위는 m다.

TF의 고정 카메라→몸체 변환을 M이라 하면, 머리 자세가 고정된 실습에서
몸체 상대 자세는 `M @ T_W_camera @ inv(M)`으로 계산한다.
보정 후의 점은 `T_body0_body_optimized @ M @ p_camera`로 다시 배치한다.
ROS 토픽으로 내보내는 기능은 파일로 계산과 결과를 확인한 뒤 연결할 수 있다.

PnP의 변환 방향은 [OpenCV 공식 문서](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html),
잔차를 받아 최적화하는 인터페이스는 [SciPy 공식 문서](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html)를 따른다.

## 검증

- 실습·결과 12장을 여섯 가지 화면 크기에서 확인했다. 텍스트 겹침·잘림, 페이지 가로 넘침과 JavaScript 예외가 없다.
- 72장 번호·ARIA·제목 쌍·이미지·내부 링크, 키보드 이동과 모바일 그림 스크롤을 확인했다.
- 배포 NPZ의 배열 크기와 단위, ZIP 내부 파일·열, 49행 로그, 5개 키프레임과 루프 한 개를 확인했다.
- CSV의 자세와 관측만으로 전체 잔차와 루프 위치 잔차를 독립적으로 계산해 표·JSON과 일치함을 확인했다.
- 이론 1~60p는 기존 HTML과 같다. 실제 로봇을 움직이거나 주행 정확도를 새로 측정하지 않았다.
