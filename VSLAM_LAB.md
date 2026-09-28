# 강의 03 · ALICE M1 Visual SLAM 구현 실습

학생용 정본은 [vslam-lab.html](vslam-lab.html)이다. 강의 3의 **61~66페이지**에서 각 구현 단계로 연결한다.
기존의 스택 시작·TurtleBot3·slam_toolbox·Nav2 실행 실습을, 실행 중인 ALICE M1 센서를 사용하는
하나의 RGB-D Visual SLAM 개발 과제로 교체했다. 이론 1~60페이지와 전체 66장 번호는 유지한다.

| 슬라이드 | 구현 단계 | 확인할 결과 |
| --- | --- | --- |
| 61 | 영상·깊이·보정 정보 구독과 동기화 | 입력 규격, 쌍 수, 시각 차이, 유효 깊이 |
| 62 | 특징점 매칭과 깊이 역투영 | 이전 3D ↔ 현재 2D 대응과 시각화 |
| 63 | PnP·RANSAC, 자세 누적, 몸체 변환 | VO 궤적, 품질 로그, 추적 실패 처리 |
| 64 | 키프레임·지역 관측 저장과 지도 생성 | 점군과 자세 변경 후 재구성 |
| 65 | 재방문 기하 검증·포즈 그래프 최적화 | 원본 VO 보존, 보정된 궤적·지도 |
| 66 | 동일 rosbag의 VO/SLAM 비교 | 정렬된 평가, 실패율, 처리 시간, 재현 방법 |

## 실행 환경에서 확인한 내용

2026-09-28, ROS 2 Jazzy / Cyclone DDS, ROS_DOMAIN_ID=122, discovery range=LOCALHOST.
실행 중인 프로세스·ROS 그래프를 읽고 12초간 센서 메시지를 구독했다.
로봇 명령, 파라미터 변경, SLAM 시작, TF 발행은 수행하지 않았다.

- `/aeirobot/vslam_left_image`: 1280×720, rgb8, step=3840.
- `/aeirobot/vslam_depth`: 1280×720, 32FC1, step=5120, 카메라 Z 방향 깊이(m).
- `/aeirobot/vslam_left_camera_info`: fx=fy=586.666656..., cx=640, cy=360;
  K=P의 왼쪽 3×3, D=0, R=I.
- 세 입력의 frame_id는 `zed_left_camera_optical_frame`, QoS는 BEST_EFFORT / VOLATILE.
  발행자는 Isaac의 렌더 파이프라인이다. 실제 스테레오 매칭 깊이라고 표현하지 않는다.
- 관측 구간 수신량은 RGB 59장, 깊이 39장, CameraInfo 73개였다.
  수신 빈도는 각각 약 5.31 / 3.31 / 6.01 Hz. 헤더 시각 간격 중앙값은 각각 0.1초였다.
  짝이 있는 영상의 시각 차이는 0이지만 일부 입력은 누락되었다. 고정 성능 수치로 가르치지 않는다.
- `/aeirobot/odometry`: isaac_wheel_odom, BEST_EFFORT, odom → base_footprint.
- `/odometry/filtered`: ekf_filter_node, RELIABLE, odom → base_footprint.
- `/aeirobot/sim/gt_odom`: 시뮬레이터 발행, BEST_EFFORT, **odom → robot_root**.
- `/tf`: robot_state_publisher와 ekf_filter_node. `/tf_static`: robot_state_publisher,
  RELIABLE / TRANSIENT_LOCAL. 실제 영상 시각의 base_footprint ← camera 변환을 조회했다.
- `/clock`: 시뮬레이터 발행. 프로그램의 시간과 연산용 실제 경과 시간을 구분한다.
- `/rtabmap/map`, `/rtabmap/info`, `/plan`, `/global_costmap/costmap`은 당시 **발행자 0개**였다.
  `topic list`에 있다는 이유만으로 활성 데이터로 가르치지 않는다.

수신 메시지와 설정만으로 모든 픽셀의 정렬을 실증한 것은 아니다. 첫 실습에서 RGB/깊이의 물체 경계
중첩과 발행 설정을 확인하도록 명시했다. D=0·같은 크기·같은 frame_id만으로 정렬을 단정하지 않는다.

## 설계상 구분

- 학생 추정기의 입력은 RGB-D·카메라 모델과 몸체↔카메라 TF다. 바퀴·EKF·GT는 별도 평가에만 쓴다.
- 기존 로봇의 map/odom TF에 경쟁 발행하지 않는다. 학생 접두어 토픽과 프레임으로 출력한다.
- PnP의 결과 `T_cur_ref`는 이전 점을 현재 카메라 좌표로 바꾼다. 카메라 자세 누적은 역변환을 쓴다.
- 카메라에서 몸체로 변환할 때 초기·현재 영상 시각의 장착 TF를 각각 사용한다.
- 원본 VO, 고정된 상대 관측, 보정된 키프레임 자세, 지역 점군을 분리한다.
- 평면 주행 SE(2) 포즈 그래프가 기본 과제다. 6자유도 그래프와 IMU·Nav2는 확장한다.
- 그래프 첫 노드 고정, 각도 래핑, m/rad 가중치, 잘못된 루프의 기하 검증을 안내한다.
- bag은 simulation time으로 기록하고 별도 도메인에서 재생한다. Jazzy의 `--clock` 동작과 CLI 옵션을
  설치된 `ros2 bag ... --help` 및 공식 소스로 확인했다.
- GT의 child frame을 몸체 기준으로 변환한 뒤 초기 원점·축·시각을 정렬한다.
  GT 변환이 불명확하면 절대 정확도를 주장하지 않는다. 바퀴/EKF는 정답으로 사용하지 않는다.

## 자료와 검증 범위

공식 근거 링크는 [학생 가이드의 참고 자료](vslam-lab.html#references)에 있다.
새 스타일은 `assets/css/vslam-lab.css`에서 `.vslam-practice`와 `.vslam-guide`로 한정한다.
슬라이드의 도식은 HTML/CSS·SVG이며 알고리즘 성능 결과로 오해하지 않도록 개념도를 표시한다.

실습은 학생이 구현해야 할 과제다. 실행 중인 센서 입출력의 관측과 자료의 계산·화면 검증을 수행하며,
완성된 학생 SLAM이나 로봇 주행의 성능을 시험했다고 주장하지 않는다.
