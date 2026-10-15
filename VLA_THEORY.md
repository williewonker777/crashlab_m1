# 강의 ④ 1~51p — VLA 이론

확인일 2026-10-12, 20·21p 유도 보강 2026-10-15. 강의 ④는 총 75장이다. 이 문서는 그중 VLA 이론 51장에 쓴
구성, Action Head·Noise 학습·데이터 기록·실행 계층의 근거, 교육용 시연의 계산 가정, 수치의 출처와 보고 주체를 기록한다. 뒤의 로봇 모델
24장(52~75p)은 URDF·MJCF·USD 단원과 그리퍼 조립·M1 텔레오퍼레이션 박스 넣기 실습이며, 기존 모델 근거는 `DESIGN.md` v89에 남긴다. 기존 수치와 원문 확인일은 2026-10-11의 기록을 유지하고, Noise 보강의 원문·코드 확인일은 2026-10-12로 구분한다. 실습 자료와 검증 경계는 `DESIGN.md` v100·v102에 기록한다.

논문 성능값은 해당 논문 **저자 보고값**이다. 기업 뉴스룸·블로그·Model Card·저장소의
성능과 사양은 해당 **기업 또는 프로젝트의 공개 보고값**이다. 어느 값도 이 강의에서
독립 재현하거나 일반적인 성능 보장으로 사용하지 않는다.

## 단원 구성

| 단원 | 페이지 | 핵심 내용 |
|---|---:|---|
| 개념 | 1~9 | VLA, Policy, 모듈형 방식, Behavior Cloning과 누적 오차 |
| 구조 | 10~25 | Token, Tokenizer와 Embedding, 선형 변환, VLM Backbone, Action Head, 행동 생성 모듈의 두 구조, Action Space, Noise 학습, Token·Flow Matching·Regression, Action Chunking, Dual System |
| 데이터와 학습 | 26~35 | Episode, Frame 기록, 수집, 시간 정렬, Pretraining과 Fine-tuning |
| 실행과 평가 | 36~41 | Inference Pipeline, Inference 지연, 동기·비동기 Chunk 실행, Sim-to-Real, Wilson 신뢰구간 |
| 최신 경향 | 42~51 | 2022~2026 계보, 공개 모델, 계획, RECAP, World Action Model, 기억·경량화, 참고 링크 |

각 단원 질문 장은 2·10·26·36·42p다. 교육용 시연은 19p Action Tokenization과 38p Chunk 실행이다.
51p는 슬라이드에서 인용한 논문과 기업 발표의 원문 링크를 모은다.

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
| Diffusion | 섞은 Noise 자체를 맞히는 생성 모델 |
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

Inference는 모델을 실행해 결과를 계산하는 과정이고, 46p Reasoning은 계획을 세우는
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
Token Vector를 만드는 구성 요소는 Vision Encoder이고, 상태의 Token Vector를 만드는 구성 요소는 선형 변환이다. PaliGemma의
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
π0·SmolVLA 계열의 특정 모듈을 뜻한다. 별도 DiT까지 Action Expert라고 묶지 않는다.
두 구조를 아우르는 제목은 「행동 생성 모듈의 두 가지 구조」다.
π0는 한 Transformer 안에서 영상·문장 Token에는
VLM 가중치, 상태·행동 Token에는 별도 Action Expert 가중치를 쓴다. Action Expert는 폭 1024,
약 3억 Parameter이며 전체는 33억 Parameter로 보고됐다. π0는 영상·문장 쪽 키·값을 저장하고
작은 Action Expert만 10번 다시 계산해, RTX 4090에서 전체 73 ms 중 행동 다듬기 10번이 27 ms라고
보고했다.

GR00T N1의 Diffusion Transformer는 DiT 변형이다. VLM Token을 Cross Attention으로 참고하고 Flow Matching으로 학습하며, Noise 섞인 행동을 4번 다듬는다. DiT는 2022년 이미지 생성에서
U-Net 대신 Transformer를 쓴 구조로 제안됐다. Diffusion이라는 이름은 비평형 통계물리의 확산 과정에서 왔다.
Diffusion 모델은 섞은 Noise 자체를 맞히고, Flow Matching은 섞은 점에서 행동 쪽 방향을 맞힌다. 두 방식 모두 학습에서는 행동에 Noise를 섞고, 실행에서는 Noise에서 출발해 여러 번 다듬는다.

### Noise를 섞어 배우는 방법

20p는 정답이 두 갈래일 때 제곱 오차의 최솟값이 평균이라는 점을 유도하고, 21p는 같은 두 정답으로 Diffusion·Flow Matching의 학습과 실행을 **교육용 예시**로 설명한다. 아래 원문·코드 위치와 commit은 Claude가 2026-10-12에 확인했다고 TASK-352에 기록한 자료이다. 이 문서를 고칠 때 원문과 코드를 독립적으로 다시 읽거나 실행하지 않았으며, 수치와 흐름을 모든 로봇의 성능이나 동작 보장으로 사용하지 않는다.

| 구분 | 강의에 반영한 내용 | 출처·보고 구분 |
|---|---|---|
| π0 학습 | 시연 행동 묶음과 같은 크기의 정규분포 Noise 및 시간 하나를 뽑고, 섞은 점에서 방향 하나를 예측해 제곱 오차를 계산한다. 코드의 `t`는 Beta(1.5, 1)로 Noise 쪽을 더 자주 뽑는다. | [π0 §IV](https://arxiv.org/abs/2410.24164)는 저자 보고, [openpi `compute_loss`](https://github.com/Physical-Intelligence/openpi/blob/215abfb/src/openpi/models/pi0.py)는 `215abfb` 코드 확인 기록이다. |
| π0·GR00T N1 실행 | π0는 Noise에서 출발해 10번, GR00T N1은 4번 반복해 행동을 다듬는다. | [π0](https://arxiv.org/abs/2410.24164)·[GR00T N1 §2](https://arxiv.org/abs/2503.14734)는 저자 보고, [openpi `sample_actions`](https://github.com/Physical-Intelligence/openpi/blob/215abfb/src/openpi/models/pi0.py)는 `num_steps=10` 코드 확인 기록이다. |
| Flow Matching | 섞은 점에서 정답 쪽 방향을 맞히며, 이 강의는 Noise와 행동 사이의 직선 경로를 쓴다. | [Flow Matching](https://arxiv.org/abs/2210.02747), [Rectified Flow](https://arxiv.org/abs/2209.03003), 논문 저자 보고. |
| Diffusion | 섞은 Noise `ε` 자체를 맞히는 ε 예측을 쓴다. | [DDPM](https://arxiv.org/abs/2006.11239), 논문 저자 보고. |

#### 기호와 코드의 방향

강의의 기호는 `τ=0`을 Noise, `τ=1`을 정답 행동으로 두고 `x=(1−τ)ε+τa`, 정답 방향을 `a−ε`로 둔다. openpi 코드는 반대로 `t=1`을 Noise, `t=0`을 정답으로 두며 목표 방향도 `ε−a`이다. `τ=1−t`로 바꾸면 같은 경로이다. 코드의 `dt=−0.1`도 `x + (−0.1)(ε−a) = x + 0.1(a−ε)`이므로 강의에서 행동 쪽으로 0.1씩 가는 계산과 같다.

#### 평균 행동의 함정(20p)

20p는 같은 관측·명령에서 시연 절반은 왼쪽 `a=−1`, 절반은 오른쪽 `a=+1`인 **교육용 예시**다. `a`는 출발할 때 옆으로 트는 정도를 −1~+1로 정규화한 값이다. Regression은 이 관측에 출력 `â` 하나만 내므로 손실은 `L(â)=½(â+1)²+½(â−1)²=â²+1`이다. `dL/dâ=2â=0`에서 `â=0`이 최솟값이고, `L(0)=1`이 정답의 `L(±1)=2`보다 작다. 즉 학습이 잘 될수록 둘 다 아닌 장애물 정면으로 간다. 일반형은 `E[(â−a)²]=(â−E[a])²+Var(a)`이므로 제곱 오차를 가장 작게 하는 출력은 `â=E[a]`이다. 그림의 손실 곡선은 같은 식으로 계산한 좌표이며 장면의 좌우 위치와 같은 가로축을 쓴다. Regression을 쓰는 OpenVLA-OFT의 높은 성공률 보고는 그대로 둔다. 이 예시는 정답이 여러 갈래일 때의 한계를 보이는 개념도이며 모든 작업의 성능 비교가 아니다.

#### 교육용 계산과 평균(21p)

21p의 값은 실제 장비 측정값이 아닌 **교육용 예시**다. 20p와 같은 두 정답(−1, +1)을 쓴다. 학습 한 번은 오른쪽 시연 `a=+1`, Noise `ε=−0.6`, 섞는 비율 `τ=0.25`로 놓는다. 그러면 `x=0.75×(−0.6)+0.25×1=−0.20`이다. `x=(1−τ)ε+τa`는 τ에 대한 직선이므로 `dx/dτ=a−ε=1.6`이고, τ가 0에서 1로 갈 때 x가 `a−ε`만큼 변한다는 뜻이다. 모델은 `a`·`ε`를 모른 채 x·τ와 관측·명령만 보고 이 기울기를 맞힌다. 예측이 `1.2`이면 손실은 `(1.2−1.6)²=0.16`이다. 학습에서는 시연·Noise·`τ`를 새로 뽑아 이 계산을 한 번 수행한다.

제곱 오차에서 최적 예측은 조건부 기댓값이다. 같은 `(x, τ)`를 지나는 직선이 여럿이면 모델은 그 기울기들의 평균 `v*(x,τ)=E[a−ε | x_τ=x]`를 배운다. `ε=(x−τa)/(1−τ)`를 넣으면 `a−ε=(a−x)/(1−τ)`이므로 `v*=(E[a|x]−x)/(1−τ)`이다. Noise가 표준정규분포이고 두 정답이 반반이면 `x_τ | a ~ N(τa, (1−τ)²)`이고, 사후 평균은 `E[a|x]=tanh(xτ/(1−τ)²)`이다. 출발점 `τ=0`에서는 `x=ε`가 `a`와 독립이라 기울기 `−1−x`와 `1−x`의 평균 `−x`가 평균 정답 0을 가리킨다. 한 번에 `δ=1`만큼 가면 `x+(−x)=0`이 되어 20p의 Regression 답과 같다.

실행 판의 보라 궤적은 이 `v*`를 `δ=0.1`로 10번 Euler 적분한 값이다. Noise `0.5`에서는 `0.5000→0.4500→0.4062→0.3712→0.3501→0.3535→0.4045→0.5304→0.6868→0.8434→1.0000`이고, `−0.5`는 부호만 반대다. 처음에는 평균 0 쪽으로 가다가 τ가 커질수록 x가 치우친 쪽 정답의 직선만 남아 +1 또는 −1로 꺾인다. 점선은 한 번에 이동한 결과로 두 Noise 모두 0에 멈춘다. 검산용으로 표준정규 Noise 20,000개(seed 0)를 같은 방식으로 옮기면 끝점의 약 50%가 양수(+1 쪽), 50%가 음수(−1 쪽)였다. 다만 출발값이 0에 매우 가까우면 10번 안에 ±1까지 가지 못한 끝점도 있었다(최소 |끝점| 약 0.37). 이 판은 학습이 이상적으로 됐다고 둔 교육용 가정이다. 실제 모델의 예측 오차, 행동 묶음 차원, π0의 Beta 분포 `t` 표본은 반영하지 않는다. 유한 반복이 모든 문제에서 올바른 정답을 보장한다는 뜻이 아니다.

### Action Head·데이터 기록·실행 계층

#### Action Head의 위치

14p의 행동 출력은 모터 전류나 토크 자체가 아니라, VLA 신경망 끝의 **Action Head**이다. Backbone이
영상·문장·관절 상태를 읽어 만든 Vector를 받아 앞으로 보낼 행동 숫자를 계산한다. 실행에서는 센서
관측 → Backbone → Action Head → 로봇 쪽 출력 처리 → 관절 제어기 → 드라이버·모터 순서다.
Action Head가 내보내는 것은 제어기가 따라갈 목표값이며, 모터 전류는 제어기와 드라이버가 만든다.

수집 때는 사람이 리더 팔로 정한 관절 목표가 행동으로 기록된다. 같은 시각의 로봇 관절 상태와 영상은
관측으로 기록된다. 학습 때 Action Head는 그 관측에서 기록된 행동을 맞히도록 가중치를 고친다. 실행 때는
사람 대신 Action Head가 같은 형식의 목표를 같은 제어기로 보낸다. 따라서 행동의 의미·단위·주기는 수집과
실행에서 같아야 한다.

16p는 이 관계를 수집·학습·실행 세 행으로 나눠 보인다. 수집과 실행 행은 관측 → 행동을 정하는 쪽 →
행동 → 제어기·모터의 같은 형식을 쓴다. 수집에서는 사람이 리더 팔로 행동을 정하고, 실행에서는 VLA가
그 자리를 대신한다. 학습 행은 로봇 없이 저장된 관측과 기록된 행동을 비교한다.

#### Frame 기록과 행동의 의미

31p는 Episode를 제어 주기마다 남긴 Frame의 연속으로 설명한다. 교육용 예시의 `frame_index` 62와
`timestamp` 1.24 s는 50 Hz 기록에서 62 × 0.02 s로 계산한 값이다. 한 팔 7관절과 그리퍼의 숫자 8개도
교육용 예시이며, 실제 로봇의 관절 순서와 단위는 사용한 설정을 따른다.

| 항목 | Frame에 저장하는 값 | LeRobot 형식 |
|---|---|---|
| 시각 | 몇 번째 기록인지와 시각 | `frame_index`, `timestamp` |
| 영상 | 같은 시각의 카메라 이미지 | `observation.images.*` |
| 관절 상태 | 그 시각에 측정한 관절각과 그리퍼 | `observation.state` |
| 행동 | 그 시각에 제어기로 보낸 목표 | `action` |
| 명령 | 작업 문장 | `task` |

관절 상태는 로봇이 지금 있는 곳이고, 행동은 가라고 보낸 곳이다. 원격 조작에서는 리더 팔의 관절각이
행동이고, 따라 움직인 로봇 팔의 관절각이 상태가 된다. 저수준 제어기는 이 차이를 이용해 힘을 낸다.
학습은 한 시점의 영상·관절 상태·명령을 입력으로, 그 시점부터 이어지는 행동 묶음을 정답으로 사용한다.

#### Inference Pipeline과 제어기

37p의 Inference Pipeline은 VLA가 목표를 만들고 로봇 쪽 프로그램이 그 목표를 실행 가능한 명령으로
바꾸는 경계를 보여 준다. 모델 쪽에서는 입력을 정리하고 VLA가 정규화된 행동 Chunk를 계산한다. 로봇 쪽에서는
저장한 통계로 원래 단위로 되돌리고, 관절 한계와 이동량을 확인한 뒤 제어 주기마다 하나씩 제어기로 보낸다.
관절 변화량으로 학습한 경우에는 현재 관절각을 더해 목표각을 만든다.

Action Head의 결과는 관절 목표이고, 제어기는 목표와 현재 각도의 차이로 토크를 정한다. 드라이버가 그
토크에 맞게 전류를 조절한다. 모델을 GPU 컴퓨터에서 실행하는 경우 로봇 프로그램은 관측을 보내고 행동 Chunk를
받으므로, 네트워크 통신 시간도 Inference 지연에 더해진다. 37p의 `50×8`과 0.5 s는 화면에서 `예` 또는
교육용 예시로 표시한다. 20 ms와 50 Hz는 ALOHA 예제의 `max_hz=50`과 그에 대응하는 제어 주기다.

### Action Head·기록·실행의 원문과 코드 근거

이번 보강의 원문·코드 확인일은 2026-10-12이다. 논문 인용은 저자 보고값이고, 저장소 코드는 해당 commit에서
확인한 구현이다. 아래 내용은 독립 재현이나 모든 로봇에 대한 동작 보장이 아니다.

| 주제 | 슬라이드에 반영한 내용 | 원문·코드 commit |
|---|---|---|
| 원격 조작의 행동·관측·제어 | 리더 로봇 관절 위치를 행동으로 기록하고, 팔로워 관절 위치와 4대 카메라 영상을 관측으로 기록한다. 목표와 현재 상태의 차이는 저수준 PID가 힘으로 만든다. 원격 조작과 기록은 50 Hz이다. | [ACT §III·IV](https://arxiv.org/abs/2304.13705), 논문 저자 보고 |
| Frame 기록 | 매 주기에 관측을 읽고 리더 팔 행동을 `robot.send_action`으로 보낸 뒤 관측·행동·`task`를 한 Frame으로 저장한다. 데이터셋 fps는 기록 fps이다. | [LeRobot `record_loop`](https://github.com/huggingface/lerobot/blob/b9cb121/src/lerobot/scripts/lerobot_record.py), [상수·형식](https://github.com/huggingface/lerobot/blob/b9cb121/src/lerobot/datasets/feature_utils.py), `b9cb121` |
| 로봇 전송 | `send_action`은 `Goal_Position`을 쓰고, 현재 위치에서 지나치게 먼 목표는 `max_relative_target`으로 자른다. 서보는 POSITION 모드와 P·I·D 계수로 설정한다. | [LeRobot SO-101 follower](https://github.com/huggingface/lerobot/blob/b9cb121/src/lerobot/robots/so_follower/so_follower.py), `b9cb121` |
| 실행 처리 | 실행은 전처리 → `policy.select_action` → 후처리·역정규화 → 행동 큐·보간 → `robot_action_processor` → `send_action` 순서다. MEAN_STD 역변환은 `tensor * std + mean`이다. | [LeRobot 동기 실행](https://github.com/huggingface/lerobot/blob/b9cb121/src/lerobot/rollout/inference/sync.py), [전략](https://github.com/huggingface/lerobot/blob/b9cb121/src/lerobot/rollout/strategies/core.py), [정규화](https://github.com/huggingface/lerobot/blob/b9cb121/src/lerobot/processor/normalize_processor.py), `b9cb121` |
| SmolVLA·π0 | SmolVLA 설정은 `chunk_size`·`n_action_steps` 50과 STATE·ACTION MEAN_STD를 둔다. π0는 Action Expert 폭 1024와 `Linear(width → action_dim)` 출력층을 쓴다. | [SmolVLA](https://arxiv.org/abs/2506.01844), [LeRobot SmolVLA 설정](https://github.com/huggingface/lerobot/blob/b9cb121/src/lerobot/policies/smolvla/configuration_smolvla.py), [π0](https://arxiv.org/abs/2410.24164), [openpi π0](https://github.com/Physical-Intelligence/openpi/blob/215abfb/src/openpi/models/pi0.py), 논문 저자 보고·`b9cb121`·`215abfb` |
| 학습 범위 | OpenVLA는 Vision Encoder까지 포함한 전체 가중치 학습을 기본으로 보고한다. SmolVLA는 VLM을 고정하고 Action Expert만 학습한다. OpenVLA의 행동은 기존 언어 어휘 256개를 구간 번호에 사용한다. | [OpenVLA §3.2·3.4·5.2](https://arxiv.org/abs/2406.09246), [SmolVLA §4.3](https://arxiv.org/abs/2506.01844), 논문 저자 보고 |
| Training Pipeline | openpi 기본 설정은 `batch_size` 32와 `num_train_steps` 30,000이다. 학습 전에 정규화 통계를 계산하고 Checkpoint의 assets에 복제한다. 35p의 「한 번에 32개씩 3만 번」은 이 코드 설정을 풀어 쓴 말이다. | [openpi 학습 설정](https://github.com/Physical-Intelligence/openpi/blob/215abfb/src/openpi/training/config.py), [README](https://github.com/Physical-Intelligence/openpi/blob/215abfb/README.md), `215abfb` |
| 원격 Inference·출력 처리 | openpi는 GPU 서버에서 모델을 돌리고 로봇 클라이언트가 관측을 보내 `(action_horizon, action_dim)` Chunk를 받는다. 출력은 원래 단위로 되돌린 뒤 현재 상태와 합쳐 목표로 바꾼다. ALOHA 예제는 `ActionChunkBroker(action_horizon=25)`와 `max_hz=50`을 쓴다. | [openpi 원격 Inference](https://github.com/Physical-Intelligence/openpi/blob/215abfb/docs/remote_inference.md), [ALOHA 실행](https://github.com/Physical-Intelligence/openpi/blob/215abfb/examples/aloha_real/main.py), [변환](https://github.com/Physical-Intelligence/openpi/blob/215abfb/src/openpi/transforms.py), [출력 처리 설정](https://github.com/Physical-Intelligence/openpi/blob/215abfb/src/openpi/policies/policy_config.py), `215abfb` |
| 모터·물리 주기 | MuJoCo `motor`는 direct-drive이고, position actuator는 목표와 현재 상태의 차이로 힘을 낸다. 기본 timestep은 0.002 s이다. Isaac Lab의 decimation은 Policy 한 번당 물리 step 수다. | [MuJoCo XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html), [Isaac Lab Actuators](https://isaac-sim.github.io/IsaacLab/main/source/how-to/write_articulation_cfg.html), [Isaac Lab 환경 설정](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.envs.html) |

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

19p는 한 관절 목표각의 교육용 범위를 −90°~+90°로 고정하고, 같은 폭의 `N`개 구간으로
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

38p는 50 Hz 제어, 즉 한 제어 주기 20 ms와 Chunk 길이 `H=50`을 가정한다. 화면은 3초,
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
| π0 | PaliGemma 3B + Action Expert 약 300M, H=50, 최대 50 Hz, 다듬기 10번, 약 1만 시간·7구성·68작업 | [π0](https://arxiv.org/abs/2410.24164), 논문 저자 보고 |
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
20p는 Multimodal의 뜻이 여러 입력이 아니라 여러 정답 갈래임을 명시한다. 25p는 System 2가
내부 숫자 목록으로 System 1에 정보를 넘기는 방향, 39p는 실물 센서의 Noise가 만드는 차이를
분명히 한다. LoRA·MoE·DiT·RTC의 영문 확장과 설명을 구분한다. 수치·출처·도식의 연결 구조와
두 시연의 계산 가정은 바꾸지 않는다. 원문 확인일은 계속 2026-10-11이다.

## 검증 범위

`node tools/check-vla-model.cjs`는 균일 구간의 포함·경계·오차 한계, 슬라이드의 30° 예시,
150단계 동기·비동기 Chunk 분할과 Inference 비중첩을 검사한다. `tools/check-lecture4-content.py`는
20p 손실 곡선·표시점과 21p 학습 산술·실행 궤적·한 번 이동 점선을 위 식으로 다시 계산해 대조한다. 브라우저 검증은 Token 시연의
슬라이더·구간 버튼과 Chunk 시연의 슬라이더·방식·실행 길이 버튼, 그리고 입력 초점 중 방향키
슬라이드 이동 억제를 대상으로 한다. 화면·오버랩·가림 검증 결과는 작업 기록에서 확인한다.
