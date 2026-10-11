# 강의 ④ 1~48p — VLA 이론

확인일 2026-10-11. 강의 ④는 총 72장이다. 이 문서는 그중 VLA 이론 48장에 쓴
구성, 교육용 시연의 계산 가정, 수치의 출처와 보고 주체를 기록한다. 뒤의 로봇 모델
24장(49~72p)은 기존 URDF·MJCF·USD 단원이며, 그 근거는 `DESIGN.md` v89에 남긴다.

논문 성능값은 해당 논문 **저자 보고값**이다. 기업 뉴스룸·블로그·Model Card·저장소의
성능과 사양은 해당 **기업 또는 프로젝트의 공개 보고값**이다. 어느 값도 이 강의에서
독립 재현하거나 일반적인 성능 보장으로 사용하지 않는다.

## 단원 구성

| 단원 | 페이지 | 핵심 내용 |
|---|---:|---|
| 개념 | 1~9 | VLA, Policy, 모듈형 방식, Behavior Cloning과 누적 오차 |
| 구조 | 10~23 | Token, Tokenizer와 Embedding, 선형 변환, VLM Backbone, 행동 생성 모듈의 두 구조, Action Space, Token·Flow Matching·Regression, Action Chunking, Dual System |
| 데이터와 학습 | 24~32 | Episode, 수집, 시간 정렬, Pretraining과 Fine-tuning |
| 실행과 평가 | 33~38 | Inference 지연, 동기·비동기 Chunk 실행, Sim-to-Real, Wilson 신뢰구간 |
| 최신 경향 | 39~48 | 2022~2026 계보, 공개 모델, 계획, RECAP, World Action Model, 기억·경량화, 참고 링크 |

각 단원 질문 장은 2·10·24·33·39p다. 교육용 시연은 18p Action Tokenization과 35p Chunk 실행이다.
48p는 슬라이드에서 인용한 논문과 기업 발표의 원문 링크를 모은다.

## 용어와 근거

### 강의용 용어와 짧은 풀이

애매한 한글 음역 대신 Policy·Noise·Action Expert처럼 실제 영문 원어로 표기한다. 어려운 용어는 첫 설명에서
**단어(짧은 한국어 뜻)** 형식으로 쓴다. 카드·소제목에 이미 있는 이름을 본문 첫머리에
되풀이하지 않고 설명 문장으로 풀어 쓴다. 괄호와 바로 뒤 설명의 뜻이 같으면 괄호를 뺀다.
그림의 좁은 칸과 반복 목차에는 용어만 남기고 인접 본문이나 용어 표에서 뜻을 확인한다.
MoE·LoRA·RTC 등은 정식 영문 이름을 괄호에 쓰고, 같은 문장에서 역할을 설명한다.

| 영문 표기 | 짧은 뜻 |
|---|---|
| Policy | 행동을 선택하는 규칙 |
| Pretraining | 미리 넓게 배우는 학습 |
| Fine-tuning | 우리 데이터로 추가 학습 |
| Post-training | 기본 학습 뒤의 추가 개선 |
| Behavior Cloning | 시연을 따라 행동 배우기 |
| Distribution Shift | 학습 때와 다른 상황 |
| Action Expert | π0의 상태·행동 Token만 맡는 작은 가중치 묶음 |
| Noise | 데이터에 섞는 무작위 값 |
| Diffusion Transformer | 무작위 값 다듬기를 Transformer로 계산하는 구조 |
| Action Space | 행동값의 형식과 범위 |
| Discrete Token | 행동값을 구간 번호로 바꾼 조각 |
| Regression | 연속값을 바로 예측하는 방식 |
| Multimodal Distribution | 올바른 행동이 여러 갈래인 분포 |
| Percentile | 분포에서의 상대적 위치 |
| Flow Matching | 무작위 값에서 정답으로 가는 방향을 배우는 방법 |
| Action Chunking | 행동 묶음 예측 |
| Inference | 모델의 결과 계산 |
| Latent Representation | 상황을 요약한 모델 내부 숫자 목록 |
| Dual System | 느린 판단과 빠른 실행의 분업 |
| Reasoning | 단계적으로 생각하기 |

Inference는 모델을 실행해 결과를 계산하는 과정이고, 43p Reasoning은 계획을 세우는
단계적 사고다. Multimodal Distribution은 행동 정답의 여러 갈래이며 영상·문장 입력을 함께
쓰는 Multimodal과 구분한다. 1~99 Percentile은 원래 1~99 분위수의 같은 구간 표기다.
Token·Vector·Tokenizer·Embedding·Vision Encoder·Transformer는 12p 표에서 한국어 역할을
별도 설명 칸에서 풀어 쓴다. 이미 영문인 이름에 같은 영문을 괄호로 반복하지 않는다.
LoRA의 정식 이름은 Low-Rank Adaptation, RTC는 Real-Time Chunking, VLM은 Vision-Language Model,
MoE는 Mixture of Experts, WAM은 World Action Model이다. RECAP의 원문 이름은
RL with Experience and Corrections via Advantage-conditioned Policies이다.

### Token 생성의 역할 구분

11p는 문장 처리의 두 단계를 나눈다. **Tokenizer**는 문장을 사전에 있는 조각으로
나누고 번호를 붙인다. **Embedding**은 그 번호를 숫자 목록인 Vector로 바꾼다. 따라서
Tokenizer를 “단어 조각 → Vector”라고 쓰지 않는다. PaliGemma는 Gemma의 SentencePiece
Tokenizer와 어휘 Embedding 층을 별도로 사용한다고 설명한다.

영상과 로봇 상태도 한 줄에서 모델이 읽는 Vector가 되므로 Token이라 부른다. 다만 영상의
Token Vector를 만드는 부품은 Vision Encoder이고, 상태의 Token Vector를 만드는 부품은 선형 변환이다. PaliGemma의
224×224 영상은 14×14 조각 256개가 되고, Vision Encoder의 폭 1152는 선형 연결 층 하나로
Gemma-2B가 쓰는 길이 2048에 맞춘다. π0와 SmolVLA는 상태를 선형 변환으로 Token 하나에
투영한다.

`빨간 컵을 집어`의 7조각 `빨·간·▁·컵·을·▁집·어`와 번호
`242656·238264·235248·243111·236392·113832·236770`은 Claude가 big_vision의
`paligemma_tokenizer.model`(sha256 `8986bb4f…`, 어휘 257,152)로 실행해 기록한 자료다.
`▁`는 띄어쓰기이다. 이 문서 작성에서는 그 Tokenizer를 다시 실행하지 않았다.

### 선형 변환의 교육용 예시

13p는 입력 관절값 세 개 `0.5 · −0.2 · 1.0`을 출력 두 개 `0.48 · −0.10`으로 바꾸는
교육용 예시를 쓴다. 첫 출력의 가중치는 `0.4 · 0.1 · 0.3`이며 계산은 다음과 같다.

```text
0.4×0.5 + 0.1×(−0.2) + 0.3×1.0 = 0.48
```

둘째 출력의 가중치는 `−0.2 · 0.5 · 0.1`이고, 계산 결과는 `−0.10`이다. 관절값 8개를
숫자 1024개로 바꾸면 가중치는 8×1024=8192개다. 이 교육용 예시에는 편향을 넣지 않았다.
실제 선형 변환은 설정에 따라 편향을 더할 수 있다.

### 행동 모듈의 근거

15p는 **Action Expert**를 π0의 상태·행동 Token만 맡는 작은 가중치 묶음으로 설명한다.
π0·SmolVLA 계열의 특정 부품을 뜻한다. 별도 DiT까지 Action Expert라고 묶지 않는다.
두 구조를 아우르는 제목은 「행동 생성 모듈의 두 가지 구조」다.
π0는 한 Transformer 안에서 영상·문장 Token에는
VLM 가중치, 상태·행동 Token에는 별도 Action Expert 가중치를 쓴다. Action Expert는 폭 1024,
약 3억 Parameter이며 전체는 33억 Parameter로 보고됐다. π0는 영상·문장 쪽 키·값을 저장하고
작은 Action Expert만 10단계 다시 계산해, RTX 4090에서 전체 73 ms 중 행동 10단계가 27 ms라고
보고했다.

GR00T N1의 Diffusion Transformer는 DiT 변형이다. VLM Token을 Cross Attention으로 참고하고 Flow Matching으로 학습하며, Noise 섞인 행동을 4단계로 다듬는다. DiT는 2022년 이미지 생성에서
U-Net 대신 Transformer를 쓴 구조로 제안됐다. Diffusion이라는 이름은 비평형 통계물리의 확산 과정에서 왔다.
Diffusion 모델은 Noise를 섞는 과정을 거꾸로 배워 데이터를 만든다.

### 원문 근거

- [PaliGemma](https://arxiv.org/abs/2407.07726): SentencePiece Tokenizer·Embedding 층, 영상 Token과 선형 연결 층.
- [Getting ViT in Shape](https://arxiv.org/abs/2305.13035): SigLIP-So400m/14의 14×14 조각과 폭 1152.
- [Gemma](https://arxiv.org/abs/2403.08295): Gemma-2B의 폭 2048, SentencePiece와 어휘 256k.
- [π0](https://arxiv.org/abs/2410.24164): 상태·행동 Token의 별도 가중치와 Inference 보고값.
- [SmolVLA](https://arxiv.org/abs/2506.01844): 상태를 선형 층으로 Token 하나에 투영하는 구조.
- [GR00T N1](https://arxiv.org/abs/2503.14734): DiT 변형·Cross Attention·Flow Matching·4단계 Inference.
- [DiT](https://arxiv.org/abs/2212.09748): 이미지 생성용 Transformer Diffusion 모델.
- [Deep Unsupervised Learning using Nonequilibrium Thermodynamics](https://arxiv.org/abs/1503.03585): Diffusion 모델의 역과정 학습.

## 시연 계산 가정

### Action Tokenization

18p는 한 관절 목표각의 교육용 범위를 −90°~+90°로 고정하고, 같은 폭의 `N`개 구간으로
나눈다. 실제 입력 `a`는 이 범위로 자른 뒤 다음 식으로 Token 번호와 복원값을 구한다.

```text
폭 w = 180 / N
Token k = min(N − 1, floor((a − (−90)) / w))
복원값 = −90 + (k + 0.5)w
최대 복원 오차 = w / 2
```

| 입력 30° | 구간 수 | Token k | 복원값 | 오차 |
|---|---:|---:|---:|---:|
| 거친 구간 | 8 | 5 | 33.75° | 3.75° |
| 중간 구간 | 32 | 21 | 30.9375° | 0.9375° |
| 세밀한 구간 | 256 | 170 | 29.8828° | 0.1172° |

256구간의 폭은 0.703125°이고 최대 오차는 0.3515625°다. 경계값 +90°는 마지막
구간에 넣는다. 이 예시는 OpenVLA의 차원별 1~99 Percentile 256구간 방식을 소개하기 위한
균일 구간 계산이며, ALICE M1의 관절 한계·제어 설정이 아니다.

### Inference 지연과 Chunk 실행

35p는 50 Hz 제어, 즉 한 제어 주기 20 ms와 Chunk 길이 `H=50`을 가정한다. 화면은 3초,
150제어 주기를 표시한다. Inference 지연 `L`의 주기 수는 `d = ceil(L × 50 / 1000)`이다.
실행 길이는 10·25·40 행동 중 하나로 고른다.

- 동기 실행은 `s`개 행동을 실행한 뒤 `d`주기 동안 로봇을 멈추고 다음 Chunk를 계산한다.
  정지 비율은 `d / (s + d)`이다.
- 비동기 실행은 Chunk 전환 `d`주기 전에 다음 Inference를 시작한다. 전환 간격은
  `max(s, d)`이며, 새 Chunk의 앞 `d`개 행동은 이미 지난 시점이므로 실행하지 않는다.
- 비동기 Chunk가 남은 행동보다 늦게 도착하면 그 부족분만 정지한다. 예를 들어 `s=40`,
  `L=300 ms`이면 `d=15`이고 정지 비율은 `5/40`이다.

기본 표시값 `s=25`, `L=200 ms`에서 `d=10`이다. 동기 방식의 정지 비율은 `10/35`이고,
비동기 방식은 정지하지 않으며 새 Chunk마다 10개 행동을 버린다. 이 일정은
`assets/js/vla-model.js`의 순수 계산 모델로 검증한다. 실제 로봇의 지연·Chunk 길이·안전
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
| π0 | PaliGemma 3B + Action Expert 약 300M, H=50, 최대 50 Hz, 10단계, 약 1만 시간·7구성·68작업 | [π0](https://arxiv.org/abs/2410.24164), 논문 저자 보고 |
| FAST | 학습 시간 최대 5배 단축 | [FAST](https://arxiv.org/abs/2501.09747), 논문 저자 보고 |
| OpenVLA-OFT | LIBERO 76.5%→97.1%, 행동 생성 처리량 26배 | [OpenVLA-OFT](https://arxiv.org/abs/2502.19645), 논문 저자 보고 |
| Helix | 7B VLM 7~9 Hz, 80M Policy 200 Hz, 상체 35자유도 | [Figure Helix 발표](https://www.figure.ai/news/helix), Figure 보고 |
| GR00T N1 | 10 Hz/120 Hz, H=16, 전체 2.2B | [GR00T N1](https://arxiv.org/abs/2503.14734), 논문 저자 보고 |
| π0.5 | 하위 작업 예측 뒤 행동, 1단계 학습 예시의 97.6%가 가정용 Mobile Manipulator 이외 데이터 | [π0.5](https://arxiv.org/abs/2504.16054), 논문 저자 보고 |
| SmolVLA | 450M, 비동기 작업 시간 13.75 s→9.7 s | [SmolVLA](https://arxiv.org/abs/2506.01844), 논문 저자 보고 |
| ECoT | OpenVLA 대비 일반화 과제 성공률 +28%p | [ECoT](https://arxiv.org/abs/2407.08693), 논문 저자 보고 |
| DROID | 7.6만 궤적, 장면 564개 | [DROID](https://arxiv.org/abs/2403.12945), 논문 저자 보고 |
| π*0.6 RECAP | 어려운 작업 처리량 2배 이상, 실패율 약 절반 | [π*0.6](https://arxiv.org/abs/2511.14759), 논문 저자 보고 |
| DreamZero | 14B, VLA 대비 일반화 2배 이상, 7 Hz | [DreamZero](https://arxiv.org/abs/2602.15922), 논문 저자 보고 |
| MEM | 최대 15분 작업 | [MEM](https://arxiv.org/abs/2603.03596), 논문 저자 보고 |
| π0.7 | 2026-04-16 공개 | [π0.7](https://arxiv.org/abs/2604.15483), 논문 저자 보고 |
| WAM 비교 | Chunk당 590~800 ms, π0.5 약 190 ms | [NVIDIA WAM 블로그](https://developer.nvidia.com/blog/pretrained-to-imagine-fine-tuned-to-act-the-rise-of-world-action-models/), NVIDIA 보고 |
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
- [GR00T N1.6 Model Card](https://huggingface.co/nvidia/GR00T-N1.6-3B): 공개 모델의 크기·배포 정보.
- [openpi](https://github.com/Physical-Intelligence/openpi): π0 계열 실행·LoRA 메모리 안내값. Inference 8 GB, LoRA 22.5 GB, 전체 Fine-tuning 70 GB 이상은 프로젝트 문서의 안내값이다.
- [LeRobotDataset v3](https://huggingface.co/docs/lerobot/lerobot-dataset-v3): 데이터셋 형식 참고자료.
- [PaliGemma 구조](https://developers.googleblog.com/gemma-explained-paligemma-architecture/): 224 px 입력에서 패치 Token 256개의 설명.

## 문맥 보정 · Claude 추가 지시 반영

2026-10-12 사용자 후속 지시에 따라 영어 이름을 유지하면서 반복 풀이와 빠진 주어·목적어를
보정한다. 7p의 1~3 Hz는 같은 빈도를 「1초에 1~3번」으로 풀어 쓴 것이며 새 성능값이 아니다.
19p는 Multimodal의 뜻이 여러 입력이 아니라 여러 정답 갈래임을 명시한다. 23p는 System 2가
내부 숫자 목록으로 System 1에 정보를 넘기는 방향, 36p는 실물 센서의 Noise가 만드는 차이를
분명히 한다. LoRA·MoE·DiT·RTC의 영문 확장과 설명을 구분한다. 수치·출처·도식의 연결 구조와
두 시연의 계산 가정은 바꾸지 않는다. 원문 확인일은 계속 2026-10-11이다.

## 검증 범위

`node tools/check-vla-model.cjs`는 균일 구간의 포함·경계·오차 한계, 슬라이드의 30° 예시,
150단계 동기·비동기 Chunk 분할과 Inference 비중첩을 검사한다. 브라우저 검증은 Token 시연의
슬라이더·구간 버튼과 Chunk 시연의 슬라이더·방식·실행 길이 버튼, 그리고 입력 초점 중 방향키
슬라이드 이동 억제를 대상으로 한다. 화면·오버랩·가림 검증 결과는 작업 기록에서 확인한다.
