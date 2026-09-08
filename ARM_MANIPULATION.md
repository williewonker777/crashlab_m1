# 강의 ② 챕터 4 — 팔 제어

챕터 표지는 45페이지, 본문은 46~63페이지의 18장이다. 권장 진행은 설명 25~30분, 두 시연과 토의 10~15분이다. 물체에 접근하고 잡고 옮기는 작업을 중심으로 순기구학(FK, 정기구학이라고도 함)·역기구학(IK)을 연결한다.

## 구성

| 페이지 | 핵심 내용 |
| --- | --- |
| 46~49 | 매니퓰레이션의 목표, M1의 어깨 3·팔꿈치 1·손목 3축, 관절 공간과 작업 공간, TCP |
| 50~52 | 사진으로 보는 FK, 변환의 연결, 7개 관절각을 직접 조절하는 시연 |
| 53~55 | 목표 pose의 IK, 같은 손끝과 다른 팔 자세, Jacobian을 이용한 수치 IK |
| 56~58 | 작업공간·방향 제약, 특이점, 관절 한계·충돌·경로 연속성 |
| 59~61 | 접근·파지·들어 올리기, 자유 이동과 직선 접근, 궤적·관절 제어·피드백 |
| 62~63 | 카메라의 물체 pose에서 파지 목표까지의 변환, 시연을 이용한 확인 문제 |

사진은 장식보다 설명에 사용한다. 관절 그룹 표시에는 `m1-arm-ext.png`, TCP와 작업 목표에는 `m1-gripper.png`, FK 비교에는 접은·중간·뻗은 팔 사진, 집기 단계에는 `m1-grasp-*`, 관측 좌표 설명에는 `m1-sensor.png`를 사용한다. 흰 본체가 보이도록 틴트 패널을 깐다. 사진의 관절각·TCP·작업공간을 실측값으로 취급하지 않는다.

## M1 모델의 근거와 범위

주 자료는 `~/Downloads/alice_m1_urdf/alice_m1.urdf`다. 같은 팔 연결을 `~/robot_ws/src/aeirobot_framework/simulation/kamino/alice_m1_left_arm.urdf`와 `alice_m1_gripper.urdf`에서도 확인했다. 다른 ALICE 기종의 팔 파라미터는 사용하지 않는다.

원본 URDF SHA-256: `4ee25ca91d171dfe7204024065bbec69619bc9d437753435af43b53a84ee2412`

시연의 기준 프레임은 `torso_link`이고, 왼팔을 사용한다. 아래 xyz와 회전축은 각 관절의 로컬 기준이다. 앞 관절이 회전하면 뒤 관절의 축도 함께 움직인다. 원본의 이 7개 관절은 모두 origin rpy = 0이다.

| q | 관절 이름 | origin xyz [m] | 로컬 회전축 |
| --- | --- | --- | --- |
| 1 | l_sh_p | (0, 0.24, 0) | y |
| 2 | l_sh_r | (0, 0, 0) | x |
| 3 | l_sh_y | (0, 0, 0) | z |
| 4 | l_el_p | (0, 0, −0.26) | y |
| 5 | l_wr_y | (0, 0, −0.255) | z |
| 6 | l_wr_p | (0, 0, 0) | y |
| 7 | l_wr_r | (0, 0, 0) | x |

손의 장착 방식과 TCP는 구분한다. 브라우저 시연은 `left_arm_link_7`에서 **로컬 −z 방향 0.10 m, 회전 오프셋 0인 교육용 TCP**를 가정한다. 실제 손의 장착 변환·파지 중심을 재현한 값이 아니다. 원본의 `l_hand` 고정 변환도 이 교육용 TCP와 별개의 항목이다. 슬라이더 ±120°는 조작 범위일 뿐, 실기 허용 범위가 아니다. 원본 URDF의 넓은 joint limit을 실기 가동 한계로 안내하지 않는다.

계산은 7개의 회전과 연결 위치를 합성한다. 시연은 관절 축·링크 연결을 보여주는 투영 도식이며, 실물의 외형·충돌 형상·관절 토크·손가락은 포함하지 않는다. 원본 로봇이나 ROS 노드로 명령을 보내지 않는다.

## 시연과 수학적 조건

52페이지에서는 q₁~q₇, 위치, quaternion을 연결해서 본다. 입력은 도 단위로 표시하고 내부에서 rad로 바꾼다. 입체·정면·측면 보기와 세 가지 관절 자세 프리셋을 제공한다. 손목 회전도 TCP 오프셋과 회전축에 따라 위치와 방향에 영향을 줄 수 있다.

54페이지에서는 기준 관절각 `[-30, 25, 10, -70, 15, 25, 0]°`의 전체 TCP pose를 목표로 고정한다. q₃를 −40°~60°로 정한 뒤 나머지 6개 관절을 수치 IK로 계산한다. 이 범위의 예제에서는 팔꿈치 위치가 달라져도 TCP 위치와 방향을 유지한다. 이는 모든 목표나 모든 관절 제한에서 가능한 동작이라는 뜻은 아니다.

IK는 기하 Jacobian과 감쇠 최소제곱으로 작은 수정을 반복한다. 위치 오차 1 µm, 방향 오차 10 µrad 미만을 내부 수렴 기준으로 사용한다. 화면의 작은 수치 오차는 교육용 계산의 오차이며, 실물 M1의 정밀도 사양이 아니다. 회전 오차는 상대 회전행렬의 회전벡터로 구하며 quaternion 네 성분을 단순히 빼지 않는다. 관절 한계와 충돌 검사는 이 시연에 포함하지 않는다.

관절 속도 순서에 대응하는 Jacobian은 `[선속도; 각속도]` 순서의 6×7 행렬이다. 원본 기하와 교육용 TCP에서 모든 관절각이 0이면 rank 5, 굽힌 팔 기준 자세에서는 rank 6임을 수치 확인했다. 특이점은 일부 방향의 순간 운동 능력이 줄어드는 조건이다. 특정 방향의 운동 요구가 큰 관절 속도로 이어질 수 있으며, 모든 운동에서 항상 큰 속도가 발생한다는 뜻은 아니다.

## 매니퓰레이션 설명의 기준

- 팔의 7자유도와 손가락의 자유도·개폐 제어를 분리한다. 손끝 위치만 맞추는 작업과 방향까지 맞추는 파지 작업도 구분한다.
- 전체 pose의 독립 조건이 6개이고 Jacobian이 full rank인 일반 자세에서는 여유자유도가 1개다. 사진의 어깨·팔꿈치·손목 그룹을 손끝 pose의 위치·방향에 일대일로 나누지 않는다.
- IK는 목표 자세의 후보, 경로 계획은 현재 상태부터 그 후보까지의 경로, 시간 부여는 속도·가속도 제한을 고려한 궤적, 관절 제어는 실제 추종을 담당한다.
- 접근·파지·들어 올리기·운반·놓기·후퇴를 분리한다. 접촉과 파지 유지는 장착한 손이 지원하는 위치·힘·전류 등과 영상 피드백을 이용해 확인한다. 개폐 명령을 보냈다는 사실만으로 성공을 단정하지 않는다.
- 물체를 잡은 뒤에는 물체도 손과 함께 움직이는 형상으로 고려한다. 시작과 끝만 확인하지 않고 중간 경로의 관절 한계·충돌·연속성을 검사한다.
- 카메라 기준의 물체 pose를 측정 시각의 TF로 팔 기준에 변환하고, 물체 기준의 파지 변환을 더해 목표 TCP pose를 만든다. 물체 중심과 파지점은 다를 수 있다.

## 참고 자료

- [Modern Robotics — Forward Kinematics](https://modernrobotics.northwestern.edu/nu-gm-book-resource/4-1-2-product-of-exponentials-formula-in-the-end-effector-frame/): 관절각에서 말단의 위치·방향을 구하는 FK의 의미. 본문은 입문 수준의 연속 좌표변환으로 설명한다.
- [Modern Robotics — Inverse Kinematics](https://modernrobotics.northwestern.edu/chapters/chapter6/): 목표 말단 pose의 해와 수치 반복 방식.
- [Modern Robotics — Singularities](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-3-singularities/): Jacobian의 크기·rank, 여유자유도, 손끝을 유지하는 내부 운동.
- [MoveIt — Pick and Place with Task Constructor](https://moveit.picknik.ai/main/doc/tutorials/pick_and_place_with_moveit_task_constructor/pick_and_place_with_moveit_task_constructor.html): 접근·파지·물체 부착·들어 올리기·놓기의 작업 분해.
- [MoveIt — Planning Scene](https://moveit.picknik.ai/main/api/html/planning_scene_overview.html): 로봇·물체·환경 상태와 제약·충돌 검사의 관계.
- [MoveIt — Concepts](https://moveit.ai/documentation/concepts/): 경로에 시간을 부여하고 관절 속도·가속도 한계를 반영하는 역할.

자료의 개념을 강의에 적용했으며, 특정 MoveIt 구성이나 예제를 M1에 설치·실행했다고 주장하지 않는다.

## 검증

`node tools/check-arm-model.cjs`로 기준 자세의 FK, 140개 Jacobian 열의 유한차분, 회전행렬·quaternion 정규성, 51개 여유자유도 해의 위치·방향 유지, 도달 불가능 목표의 실패를 검증한다. 원본 URDF를 별도로 읽어 NumPy의 4×4 변환으로 계산한 40개 자세와도 비교했다. 최대 수치 차이는 약 3.4×10⁻¹⁶이다.
