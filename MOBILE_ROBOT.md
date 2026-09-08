# 강의 ② 챕터 3 — 차동 구동과 로봇 상태 표현

챕터 표지는 24페이지, 본문은 25~44페이지다. 차동 구동 기구학으로 바퀴와 로봇의 움직임을 연결한 뒤, 그 결과를 odom·frame·TF·quaternion으로 표현한다. 챕터 4는 45페이지부터 이어진다.

## 강의 흐름

| 페이지 | 내용 |
| --- | --- |
| 25~27 | 차동 구동 모델과 가정, 바퀴 각속도·선속도, 직진·선회·제자리 회전 |
| 28~30 | 정기구학, 순간 회전 중심 ICC, 역기구학과 속도 명령 |
| 31~33 | 공간 좌표의 속도, 엔코더 이동량, 미드포인트 적분 |
| 34 | 좌우 바퀴 속도를 바꾸는 주행 궤적 시연 |
| 35~37 | 오도메트리와 드리프트, 프레임, map·odom·base_link |
| 38~39 | TF 트리와 시간, 센서 좌표를 odom으로 바꾸는 계산 예시 |
| 40~41 | RPY와 quaternion, yaw–quaternion 변환 시연 |
| 42~44 | Odometry 메시지, odom과 TF의 관계, 명령부터 상태 추정까지의 흐름 |

## 원자료에서 차용한 부분

로컬 원자료: `~/Downloads/2025 모바일로봇 제어.pptx` (33장). 슬라이드의 수식과 예시를 HTML·SVG로 다시 구성했으며, 원본 PPT 파일은 저장소에 복사하지 않는다.

| 원자료 페이지 | 반영 내용 |
| --- | --- |
| 21~22 | Differential Drive Kinematics: 좌우 바퀴 속도와 로봇의 전진·회전 속도, ICC, 정·역기구학 |
| 26 | 중간 방향 `θ + Δθ/2`를 이용한 위치 누적 |
| 27~28 | odom·frame·TF, 센서 전방 0.3 m 장착과 몸체 위치 `(2, 1)`, yaw 90° 예시 |
| 29~30 | Odometry에 위치와 quaternion을 담는 관계, RPY와 quaternion |

계산용 치수는 모든 본문과 시연에서 **r = 0.10 m, L = 0.50 m**로 통일했다. 실제 M1 사양을 뜻하지 않는다. `/cmd_vel`의 `geometry_msgs/msg/Twist` 표기는 원자료의 인터페이스 예시다. 실제 노드의 토픽·메시지 형식은 해당 구성에서 확인해야 한다.

## 모델과 설명의 기준

- 평면에서 바퀴가 미끄러지지 않는 이상적인 차동 구동 모델을 사용한다. `L`은 좌우 바퀴 중심 간격, `r`은 바퀴 반지름이다.
- `ωL`, `ωR`는 바퀴 각속도(rad/s), `vL = rωL`, `vR = rωR`는 바퀴 선속도(m/s)다. 로봇 중심 속도는 `v = (vR + vL)/2`, `ω = (vR − vL)/L`이다.
- 역기구학은 `ωL = (v − Lω/2)/r`, `ωR = (v + Lω/2)/r`이다. 좌우 바퀴의 양의 속도는 로봇 전방을 뜻하며, 모터·엔코더 부호와 감속비는 그 기준에 맞춰 환산한다.
- 본문의 적분은 원자료의 미드포인트 근사다. x·y를 먼저 계산할 때 갱신 전 θ를 사용한다. 주행 시연은 일정한 v·ω의 원호를 정확히 적분하며, 직진 극한에서도 안정적인 sinc 형태를 사용한다.
- 명령 속도를 적분한 예측과 센서로 실제 이동을 확인한 오도메트리를 구분한다. 궤적 시연은 잡음·미끄럼·모터 지연을 포함하지 않는다. 드리프트 그림은 개념도다.
- frame은 좌표를 읽는 기준이다. TF 트리의 `부모 → 자식` 표기는 부모 프레임에서 본 자식의 위치·방향 관계이며, 점을 다른 기준으로 표현하려면 관계를 합성하거나 역변환한다.
- TF 예시는 센서와 몸체의 축이 평행하다는 조건이다. 센서의 `(1, 0)`은 몸체에서 `(1.3, 0)`, 몸체가 odom에서 `(2, 1, 90°)`이면 odom에서 `(2, 2.3)`이다.
- 평면 주행은 roll = pitch = 0, yaw = θ로 두고 `q = (0, 0, sin(θ/2), cos(θ/2))`를 사용한다. 성분 x·y·z는 위치 좌표가 아니다. ROS 순서는 x·y·z·w이며, 다른 라이브러리는 순서가 다를 수 있다.

## 공식 자료와 정합성

- [REP-103: 단위와 좌표축](https://github.com/ros-infrastructure/rep/blob/master/rep-0103.rst): SI 단위, 몸체 x 전방·y 왼쪽·z 위쪽, 오른손 좌표계와 양의 yaw 방향을 따른다.
- [REP-105: 이동 로봇의 프레임](https://github.com/ros-infrastructure/rep/blob/master/rep-0105.rst): odom의 연속성과 누적 오차, map 기준 추정의 보정 가능성, base_link의 몸체 고정 관계를 구분한다. base_link 원점은 플랫폼의 설계 기준이며 반드시 기하학적 중심일 필요는 없다.
- [ROS 2 Jazzy tf2 개념](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Concepts/Intermediate/About-Tf2.rst): TF는 시간에 따른 프레임 관계를 관리한다. 위치를 측정하는 센서가 아니며, 측정 시각에 맞는 변환이 필요하다.
- [ROS 2 Jazzy 정적 TF](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Static-Broadcaster-Py.rst): 고정 장착 센서는 정적 변환으로 설명한다. 움직이는 관절에 붙은 센서는 별도 동적 관계가 필요하다.
- [ROS 2 Jazzy quaternion 기초](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Intermediate/Tf2/Quaternion-Fundamentals.rst): ROS 성분 순서, 단위 길이, 항등 회전 `(0, 0, 0, 1)`, RPY 변환을 따른다.
- [nav_msgs/msg/Odometry 정의](https://github.com/ros2/common_interfaces/blob/jazzy/nav_msgs/msg/Odometry.msg): pose는 `header.frame_id`, twist는 `child_frame_id` 기준이다. 본문의 odom·base_link는 해당 필드에 넣는 예시 이름이며 메시지 형식 자체가 강제하는 이름은 아니다.

Odometry와 `odom → base_link` TF를 함께 발행할 때 같은 추정 상태·시각·프레임 이름을 사용한다. 같은 TF 연결은 하나의 발행 주체가 담당하며, Odometry 메시지만으로 TF가 자동 생성되지는 않는다.

## 조작과 검증

34페이지의 두 슬라이더는 바퀴 각속도를 조절한다. 값을 바꾸면 시작 위치로 돌아가 새 예상 경로를 표시하고 일시정지한다. 재생 버튼으로 6초의 이동을 볼 수 있다. 직진·왼쪽 선회·제자리 회전 프리셋도 제공한다. 현재 슬라이드에서만 애니메이션을 실행하며, 동작 줄이기 설정에서는 자동 재생을 시작하지 않는다.

41페이지에서는 yaw를 −180°~180°로 바꾸며 방향 화살표와 quaternion 네 성분을 확인한다. 두 시연 모두 키보드로 조작할 수 있다.

계산 검증: `node tools/check-mobile-model.cjs`. 225개 정·역기구학 왕복 조합, 직진·제자리 회전·원운동, 작은 각속도에서의 적분, 미드포인트 예제, TF 점 변환, quaternion 단위 길이와 yaw 왕복을 확인한다.
