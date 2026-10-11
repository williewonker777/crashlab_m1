# 강의 ④ 1~45p — VLA 이론

확인일 2026-10-11. 강의 ④는 총 69장이다. 이 문서는 그중 VLA 이론 45장에 쓴
구성, 교육용 시연의 계산 가정, 수치의 출처와 보고 주체를 기록한다. 뒤의 로봇 모델
24장(46~69p)은 기존 URDF·MJCF·USD 단원이며, 그 근거는 `DESIGN.md` v89에 남긴다.

논문 성능값은 해당 논문 **저자 보고값**이다. 기업 뉴스룸·블로그·모델 카드·저장소의
성능과 사양은 해당 **기업 또는 프로젝트의 공개 보고값**이다. 어느 값도 이 강의에서
독립 재현하거나 일반적인 성능 보장으로 사용하지 않는다.

## 단원 구성

| 단원 | 페이지 | 핵심 내용 |
|---|---:|---|
| 개념 | 1~9 | VLA, 정책, 모듈형 방식, 행동 복제와 누적 오차 |
| 구조 | 10~20 | 토큰, VLM 백본, 행동 공간, 토큰·플로 매칭·회귀, 액션 청킹, 이중 시스템 |
| 데이터와 학습 | 21~29 | 에피소드, 수집, 시간 정렬, 사전학습과 미세조정 |
| 실행과 평가 | 30~35 | 추론 지연, 동기·비동기 청크 실행, Sim-to-Real, Wilson 신뢰구간 |
| 최신 경향 | 36~45 | 2022~2026 계보, 공개 모델, 계획, RECAP, 월드 액션 모델, 기억·경량화, 참고 링크 |

각 단원 질문 장은 2·10·21·30·36p다. 45p는 슬라이드에서 인용한 논문과 기업 발표의
원문 링크를 모은다.

## 시연 계산 가정

### 행동 토큰화

15p는 한 관절 목표각의 교육용 범위를 −90°~+90°로 고정하고, 같은 폭의 `N`개 구간으로
나눈다. 실제 입력 `a`는 이 범위로 자른 뒤 다음 식으로 토큰 번호와 복원값을 구한다.

```text
폭 w = 180 / N
토큰 k = min(N − 1, floor((a − (−90)) / w))
복원값 = −90 + (k + 0.5)w
최대 복원 오차 = w / 2
```

| 입력 30° | 구간 수 | 토큰 k | 복원값 | 오차 |
|---|---:|---:|---:|---:|
| 거친 구간 | 8 | 5 | 33.75° | 3.75° |
| 중간 구간 | 32 | 21 | 30.9375° | 0.9375° |
| 세밀한 구간 | 256 | 170 | 29.8828° | 0.1172° |

256구간의 폭은 0.703125°이고 최대 오차는 0.3515625°다. 경계값 +90°는 마지막
구간에 넣는다. 이 예시는 OpenVLA의 차원별 1~99 분위수 256구간 방식을 소개하기 위한
균일 구간 계산이며, ALICE M1의 관절 한계·제어 설정이 아니다.

### 추론 지연과 청크 실행

32p는 50 Hz 제어, 즉 한 제어 주기 20 ms와 청크 길이 `H=50`을 가정한다. 화면은 3초,
150제어 주기를 표시한다. 추론 지연 `L`의 주기 수는 `d = ceil(L × 50 / 1000)`이다.
실행 길이는 10·25·40 행동 중 하나로 고른다.

- 동기 실행은 `s`개 행동을 실행한 뒤 `d`주기 동안 로봇을 멈추고 다음 청크를 추론한다.
  정지 비율은 `d / (s + d)`이다.
- 비동기 실행은 청크 전환 `d`주기 전에 다음 추론을 시작한다. 전환 간격은
  `max(s, d)`이며, 새 청크의 앞 `d`개 행동은 이미 지난 시점이므로 실행하지 않는다.
- 비동기 청크가 남은 행동보다 늦게 도착하면 그 부족분만 정지한다. 예를 들어 `s=40`,
  `L=300 ms`이면 `d=15`이고 정지 비율은 `5/40`이다.

기본 표시값 `s=25`, `L=200 ms`에서 `d=10`이다. 동기 방식의 정지 비율은 `10/35`이고,
비동기 방식은 정지하지 않으며 새 청크마다 10개 행동을 버린다. 이 일정은
`assets/js/vla-model.js`의 순수 계산 모델로 검증한다. 실제 로봇의 지연·청크 길이·안전
설정이 아니다.

## 수치와 보고 범위

| 주제 | 슬라이드 수치·주장 | 출처와 보고 주체 |
|---|---|---|
| RT-1 | 시연 13만 개, 700개 이상 명령, 256구간, 3 Hz | [RT-1](https://arxiv.org/abs/2212.06817), 논문 저자 보고 |
| RT-2 | 256구간, 최대 55B, 1~3 Hz; 새 동작은 로봇 데이터 분포에 한정 | [RT-2](https://arxiv.org/abs/2307.15818), 논문 저자 보고 |
| Open X-Embodiment | 로봇 22종, 기관 21곳 | [Open X-Embodiment](https://arxiv.org/abs/2310.08864), 논문 저자 보고 |
| ACT | 10분 시연에서 80~90% 성공 | [ACT](https://arxiv.org/abs/2304.13705), 논문 저자 보고 |
| Diffusion Policy | 12개 작업 평균 46.9% 향상 | [Diffusion Policy](https://arxiv.org/abs/2303.04137), 논문 저자 보고 |
| Octo | 80만 궤적 | [Octo](https://arxiv.org/abs/2405.12213), 논문 저자 보고 |
| OpenVLA | 7B, 97만 시연, RT-2-X 대비 +16.5%p, 약 6 Hz | [OpenVLA](https://arxiv.org/abs/2406.09246), 논문 저자 보고 |
| π0 | PaliGemma 3B + 행동 전문가 약 300M, H=50, 최대 50 Hz, 10단계, 약 1만 시간·7구성·68작업 | [π0](https://arxiv.org/abs/2410.24164), 논문 저자 보고 |
| FAST | 학습 시간 최대 5배 단축 | [FAST](https://arxiv.org/abs/2501.09747), 논문 저자 보고 |
| OpenVLA-OFT | LIBERO 76.5%→97.1%, 행동 생성 처리량 26배 | [OpenVLA-OFT](https://arxiv.org/abs/2502.19645), 논문 저자 보고 |
| Helix | 7B VLM 7~9 Hz, 80M 정책 200 Hz, 상체 35자유도 | [Figure Helix 발표](https://www.figure.ai/news/helix), Figure 보고 |
| GR00T N1 | 10 Hz/120 Hz, H=16, 전체 2.2B | [GR00T N1](https://arxiv.org/abs/2503.14734), 논문 저자 보고 |
| π0.5 | 하위 작업 예측 뒤 행동, 1단계 학습 예시의 97.6%가 가정용 모바일 매니퓰레이터 이외 데이터 | [π0.5](https://arxiv.org/abs/2504.16054), 논문 저자 보고 |
| SmolVLA | 450M, 비동기 작업 시간 13.75 s→9.7 s | [SmolVLA](https://arxiv.org/abs/2506.01844), 논문 저자 보고 |
| ECoT | OpenVLA 대비 일반화 과제 성공률 +28%p | [ECoT](https://arxiv.org/abs/2407.08693), 논문 저자 보고 |
| DROID | 7.6만 궤적, 장면 564개 | [DROID](https://arxiv.org/abs/2403.12945), 논문 저자 보고 |
| π*0.6 RECAP | 어려운 작업 처리량 2배 이상, 실패율 약 절반 | [π*0.6](https://arxiv.org/abs/2511.14759), 논문 저자 보고 |
| DreamZero | 14B, VLA 대비 일반화 2배 이상, 7 Hz | [DreamZero](https://arxiv.org/abs/2602.15922), 논문 저자 보고 |
| MEM | 최대 15분 작업 | [MEM](https://arxiv.org/abs/2603.03596), 논문 저자 보고 |
| π0.7 | 2026-04-16 공개 | [π0.7](https://arxiv.org/abs/2604.15483), 논문 저자 보고 |
| WAM 비교 | 청크당 590~800 ms, π0.5 약 190 ms | [NVIDIA WAM 블로그](https://developer.nvidia.com/blog/pretrained-to-imagine-fine-tuned-to-act-the-rise-of-world-action-models/), NVIDIA 보고 |
| Wilson 구간 | 8/10은 49.0~94.3%, 80/100은 71.1~86.7% (95%, z=1.959964) | 교육용 계산; 특정 모델 성능이 아님 |

## 원문과 공식 자료

### 논문

- [RT-1](https://arxiv.org/abs/2212.06817), [RT-2](https://arxiv.org/abs/2307.15818), [Open X-Embodiment](https://arxiv.org/abs/2310.08864), [ACT](https://arxiv.org/abs/2304.13705), [Diffusion Policy](https://arxiv.org/abs/2303.04137)
- [Octo](https://arxiv.org/abs/2405.12213), [OpenVLA](https://arxiv.org/abs/2406.09246), [π0](https://arxiv.org/abs/2410.24164), [FAST](https://arxiv.org/abs/2501.09747), [OpenVLA-OFT](https://arxiv.org/abs/2502.19645)
- [GR00T N1](https://arxiv.org/abs/2503.14734), [π0.5](https://arxiv.org/abs/2504.16054), [Knowledge Insulation](https://arxiv.org/abs/2505.23705), [SmolVLA](https://arxiv.org/abs/2506.01844), [RTC](https://arxiv.org/abs/2506.07339)
- [RoboArena](https://arxiv.org/abs/2506.18123), [ECoT](https://arxiv.org/abs/2407.08693), [DROID](https://arxiv.org/abs/2403.12945), [Gemini Robotics 1.5](https://arxiv.org/abs/2510.03342), [π*0.6](https://arxiv.org/abs/2511.14759)
- [DreamZero](https://arxiv.org/abs/2602.15922), [MEM](https://arxiv.org/abs/2603.03596), [π0.7](https://arxiv.org/abs/2604.15483)

### 기업 발표와 기술 문서

- [Figure Helix](https://www.figure.ai/news/helix): Helix 구조·속도 공개값.
- [Gemini Robotics ER 2](https://blog.google/innovation-and-ai/models-and-research/google-deepmind/gemini-robotics-er-2/): 계획·진행 판단과 하위 VLA 실행의 Google DeepMind 설명.
- [Gemini Robotics 2](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/): 2026-07-30 Google DeepMind 발표. 휴머노이드 전신 동작·여러 엔드 이펙터의 손 조작·다중 로봇 협업과, 계획을 맡는 ER 2와 동작을 실행하는 VLA의 역할 구분.
- [NVIDIA GTC 2026 보도자료](https://nvidianews.nvidia.com/news/nvidia-expands-open-model-families-to-power-the-next-wave-of-agentic-physical-and-healthcare-ai): 2026-03-16 GR00T N2 예고.
- [NVIDIA WAM 기술 블로그](https://developer.nvidia.com/blog/pretrained-to-imagine-fine-tuned-to-act-the-rise-of-world-action-models/): WAM 지연 비교와 2026-06-15 게시일.
- [GR00T N1.6 모델 카드](https://huggingface.co/nvidia/GR00T-N1.6-3B): 공개 모델의 크기·배포 정보.
- [openpi](https://github.com/Physical-Intelligence/openpi): π0 계열 실행·LoRA 메모리 안내값. 추론 8 GB, LoRA 22.5 GB, 전체 미세조정 70 GB 이상은 프로젝트 문서의 안내값이다.
- [LeRobotDataset v3](https://huggingface.co/docs/lerobot/lerobot-dataset-v3): 데이터셋 형식 참고자료.
- [PaliGemma 구조](https://developers.googleblog.com/gemma-explained-paligemma-architecture/): 224 px 입력에서 패치 토큰 256개의 설명.

## 검증 범위

`node tools/check-vla-model.cjs`는 균일 구간의 포함·경계·오차 한계, 슬라이드의 30° 예시,
150단계 동기·비동기 청크 분할과 추론 비중첩을 검사한다. 브라우저 검증은 토큰 시연의
슬라이더·구간 버튼과 청크 시연의 슬라이더·방식·실행 길이 버튼, 그리고 입력 초점 중 방향키
슬라이드 이동 억제를 대상으로 한다. 화면·오버랩·가림 검증 결과는 작업 기록에서 확인한다.
