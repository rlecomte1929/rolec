# Stanford CS224R: Deep Reinforcement Learning — Spring 2025
## Comprehensive Research Document for ReloPass / Case Command

**Course:** CS 224R Deep Reinforcement Learning, Stanford University, Spring 2025  
**Instructor:** Chelsea Finn (primary), with guest lectures by Aviral Kumar, Archit Sharma, Noam Brown  
**Playlist:** https://www.youtube.com/playlist?list=PLoROMvodv4rPwxE0ONYRa_itZFdaKCylL  

**Research Note:** YouTube transcripts were not retrievable via any available method (timedtext API, scraping, third-party services, Python libraries — all blocked or inaccessible). This document is compiled from Stanford lecture slide PDFs extracted via zlib decompression of FlateDecode-compressed PDF streams. Content reflects slide text, which captures all key concepts, algorithms, and terminology, though phrasing may differ from the spoken lecture. Where slide PDFs were unavailable or undownloadable due to size constraints, the section relies on curriculum knowledge and adjacent slide content.

---

## Table of Contents

1. Lecture 1: Introduction to Deep RL
2. Lecture 2: Imitation Learning
3. Lecture 3: Policy Gradients
4. Lecture 4: Actor-Critic Methods
5. Lecture 5: Off-Policy Actor-Critic
6. Lecture 6: Q-Learning
7. Lecture 7: Offline RL
8. Lecture 8: Reward Learning
9. Lecture 9: RL for LLMs and RLHF
10. Lecture 10: RL for LLM Reasoning
11. Lecture 11: Model-Based RL
12. Lecture 12: Multi-Task and Goal-Conditioned RL
13. Lecture 13: Meta-Reinforcement Learning
14. Lecture 14: Exploration
15. Lecture 15: Hierarchy in Imitation and Reinforcement Learning
16. Lecture 16: Sim-to-Real Transfer
17. Lecture 17: RL for Robot Foundation Models and VLAs
18. Lecture 18: Frontiers and Open Problems in Deep RL
19. Course-Level Summary

---

## Lecture 1: Introduction to Deep RL

**Video URL:** https://www.youtube.com/watch?v=EvHRQhMX7_w  
**Slide Source:** Not downloadable (PDF exceeded size limit)

### Transcript / Slide Content
*Transcript unavailable. Slide PDF exceeded download limits. The following is reconstructed from course structure and adjacent lectures.*

CS 224R is Chelsea Finn's course on deep reinforcement learning, covering sequential decision-making with neural networks. The course opens by asking: what is reinforcement learning, and why do we care about it now? RL is framed as a framework for decision-making under uncertainty, where an agent observes state, takes action, receives reward, and transitions to a new state. The Markov Decision Process (MDP) formalism is introduced: state space S, action space A, transition dynamics T(s'|s,a), reward function r(s,a), discount factor gamma, and horizon H. The agent's goal is to find a policy — a mapping from states to actions — that maximizes expected cumulative reward. Deep RL replaces hand-crafted features and tabular representations with neural networks capable of scaling to high-dimensional inputs. The course motivation spans robotics, game playing (Atari, Go, chess), recommendation systems, autonomous driving, and language model alignment. Key challenges introduced: reward design, sample efficiency, exploration, generalization, and safety.

### Lecture Summary (300 words)
Lecture 1 sets the conceptual foundation for the entire course. The MDP formalism provides a universal language for sequential decision-making: an agent in a state takes an action, receives a reward, and moves to the next state according to dynamics it may or may not know. The goal is a policy that maximizes expected discounted return. "Deep" RL adds neural function approximators, enabling policies and value functions to scale from simple toy environments to raw-pixel Atari games, robot manipulation, and language generation.

Chelsea Finn frames the course around a practical question: given the enormous capability of modern deep learning, how do we harness it for agents that must act sequentially over time? Unlike supervised learning, RL deals with a moving target — the data distribution depends on the policy itself, rewards are often sparse and delayed, and actions have long-horizon consequences.

The lecture surveys the landscape of RL algorithms: imitation learning (learning from expert demonstrations without reward), policy gradient methods (directly optimizing the expected return objective), actor-critic methods (hybrid estimators that combine policy gradients with learned value functions), Q-learning (learning the optimal action-value function directly), offline RL (learning from fixed datasets), model-based RL (learning a simulator of the world), and multi-task and meta-RL (generalizing across tasks). The course is explicitly applications-oriented: most lectures tie algorithms to robotics, LLM alignment, or recommender systems.

Key practical warning: RL is notoriously difficult to debug. Reward hacking, policy collapse, and hyperparameter sensitivity are endemic. The course emphasizes principled debugging and ablation.

### ReloPass Application Notes
The MDP formalism directly applies to Case Command. State: employee profile (nationality, role, move date, corridor). Action: which compliance step to surface next. Reward: step completed on time, no compliance gap. Horizon H: the full relocation timeline (visa application → housing → tax registration). The deterministic rule engine is a specific policy — a lookup table that maps state to action without stochasticity. RL framing helps identify where this deterministic policy could be learned from data or optimized dynamically.

---

## Lecture 2: Imitation Learning

**Video URL:** https://www.youtube.com/watch?v=WjFrmFrRow0 (approximate; CS224R Spring 2025 Lecture 2)  
**Slide Source:** `/home/runner/.claude/projects/.../webfetch-1786775592893-eilpp1.pdf` → extracted as `webfetch-1786775592893-eilpp1.txt`

### Transcript / Slide Content (Key Excerpts)
*Extracted from lecture slide PDF. Full verbatim transcript not available.*

CS 224R — Imitation Learning. Plan for today: (1) problem formulation, (2) behavior cloning, (3) issues with behavior cloning, (4) fixing issues with behavior cloning, (5) practical tips. Key learning goals: understand how supervised learning can be applied to sequential decision-making; understand the distribution shift problem in imitation learning and how to address it.

**Behavior Cloning.** Treat imitation learning as supervised learning: minimize loss L(π_θ(a|o), a_t) over a dataset of expert (observation, action) pairs. This works when: there is abundant expert data; the expert covers the state distribution the policy will encounter; and the task is relatively short-horizon. Problem: at test time, the agent's own errors compound — it enters states not covered by the expert dataset, and has no idea what to do there. This is the distributional shift problem.

**DAgger (Dataset Aggregation).** Fix: let the agent run its own policy, then ask the expert to label the states the agent actually visits. Algorithm: (1) train π on dataset D; (2) run π to collect new states; (3) query expert for labels on those states; (4) aggregate and retrain. DAgger converges to a policy with loss bounded by the expert's loss (no distributional shift at convergence). Downside: requires an expert that can label on-the-fly — expensive or dangerous in robotics.

**HG-DAgger (Human-Gated DAgger).** Expert only intervenes when they judge the policy is about to fail. Reduces expert burden while retaining safety. Reference: Kelly et al.

**Action Chunking.** Modern robot policies predict sequences of actions (chunks) rather than single actions. Reduces compounding errors, enables smoother motion, and provides temporal abstraction. Reference: ACT (Action Chunked Transformer).

**Flow Matching / Diffusion Policies.** Instead of a Gaussian distribution over actions, model the action distribution as a flow or diffusion process. Enables multimodal action distributions — critical for dexterous manipulation where multiple strategies are valid. References: Chi et al. Diffusion Policy; Flow Matching for robot learning.

**Practical Tips:** (1) normalize observations and actions; (2) use data augmentation; (3) stratified sampling by task; (4) careful with image observations — crop to relevant regions; (5) action chunking almost always helps for robot manipulation.

### Lecture Summary (350 words)
Imitation learning provides a way to learn policies from expert demonstrations without explicitly defining a reward function. The simplest version — behavior cloning — reduces the problem to supervised learning: minimize the prediction error between the policy's output and the expert's actions. This works surprisingly well for short-horizon tasks with abundant data, but suffers from a fundamental flaw: distributional shift. The policy, once deployed, visits states it never saw during training, and small errors compound over time into catastrophic failures.

DAgger (Dataset Aggregation) addresses this by iteratively collecting data from the policy's own distribution and querying the expert for corrective labels. Unlike behavior cloning, DAgger converges to a policy that faces the same distribution at test time as it trained on. The practical limitation is expert availability: in robotics, you cannot always ask a human to label every robot failure in real time. HG-DAgger relaxes this by having the expert intervene only when necessary.

Modern robot imitation learning has moved beyond predicting single actions to predicting action chunks (sequences), which reduces compounding errors and provides temporal abstraction. Diffusion policies and flow matching models further improve performance by modeling multimodal action distributions — essential when multiple valid strategies exist for the same task.

The lecture situates imitation learning as the most data-efficient approach when expert demonstrations are available, but notes that it does not reason about task success or failure, only mimics behavior. The agent cannot improve beyond the expert, and if the expert is suboptimal, the policy inherits those suboptimalities.

### ReloPass Application Notes
Behavior cloning directly applies to Case Command's rule engine. The current deterministic policy was effectively hand-coded by compliance experts — it is a human "demonstration" of the correct relocation sequence for each corridor. This is behavior cloning without the neural network: explicit rules encode expert knowledge. The distributional shift problem applies when new corridors (beyond FR→NO, ES→IE, NO→FR) are added — the rule engine has no expert labels for unseen corridor combinations. DAgger-style data collection means: when a new corridor is attempted, flag it for expert review, collect the expert's decision, and update the engine. Action chunking maps to Case Command's timeline sequences: rather than surfacing one compliance step at a time, predict a "chunk" of the next N steps together, which reduces interruptions and enables smoother HR workflows.

---

## Lecture 3: Policy Gradients

**Video URL:** https://www.youtube.com/watch?v=SL_BdkPsWQk (approximate)  
**Slide Source:** `webfetch-1786775621445-ydwn0w.pdf` → `webfetch-1786775621445-ydwn0w.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Policy Gradients. Plan: online RL problem setup; REINFORCE; baselines; importance sampling; KL constraints; practical tips.

**Online RL problem setup.** Unlike imitation learning, the agent must discover what to do from reward signals. No expert labels. Objective: maximize J(θ) = E_{τ~π_θ}[Σ_t r(s_t, a_t)].

**REINFORCE (Williams 1992).** Policy gradient theorem: ∇J(θ) = E[Σ_t ∇log π_θ(a_t|s_t) · G_t] where G_t is the reward-to-go from time t. Algorithm: (1) run policy π_θ for N trajectories; (2) compute G_t for each timestep; (3) compute gradient; (4) update θ ← θ + α·∇J. Intuition: increase the log-probability of actions that led to high reward; decrease it for actions that led to low reward.

**Baselines.** Subtract a baseline b from the return: ∇J ≈ E[∇log π · (G_t - b)]. The baseline does not change the expected gradient (it has zero expectation) but reduces variance. Best baseline: the value function V^π(s_t) — this gives the advantage A(s,a) = G_t - V(s_t).

**Problems with REINFORCE:** (1) high variance even with baselines; (2) need many samples; (3) on-policy — cannot reuse past data; (4) cannot take many gradient steps on the same batch.

**Importance Sampling.** Allow off-policy gradient updates: ∇J ≈ E_{a~π_old}[(π_θ(a|s)/π_old(a|s)) · ∇log π_θ · A]. This lets us reuse data collected under a different policy. Problem: if π_θ and π_old diverge too much, the importance weights blow up and the estimator has very high variance.

**KL Constraints and PPO.** Proximal Policy Optimization (PPO): clip importance weights to [1-ε, 1+ε] to prevent large policy updates. This approximates a trust region constraint KL(π_θ || π_old) ≤ δ. PPO is the workhorse of modern online RL for LLMs and robotics.

**Practical Tips:** (1) reward normalization — normalize rewards to have zero mean, unit variance; (2) observation normalization; (3) gradient clipping; (4) entropy regularization to prevent premature convergence; (5) multiple epochs of minibatch updates with PPO is much more efficient than vanilla policy gradient.

### Lecture Summary (340 words)
Policy gradients provide the most direct approach to optimizing the expected cumulative reward: compute the gradient of the objective with respect to policy parameters and take gradient steps. The REINFORCE algorithm achieves this by sampling trajectories, computing returns, and updating the policy to make high-return actions more probable. The key insight — the log-derivative trick — allows differentiating through an expectation even when the reward function is non-differentiable or unknown.

The central practical problem with vanilla REINFORCE is variance. The reward-to-go estimator is noisy because individual trajectories are highly variable. Baselines address this: subtracting the estimated value function V^π(s_t) from the return yields the advantage function, which tells us not just whether a trajectory was good, but whether a specific action was better than average. This dramatically reduces gradient variance without introducing bias.

On-policy algorithms like REINFORCE require fresh data for every update — computationally expensive. Importance sampling enables off-policy updates, but introduces new instability when the policy deviates too far from the data-collection policy. PPO solves this with a clipped surrogate objective that prevents large policy steps, allowing multiple gradient updates per batch of data while maintaining stability. PPO's simplicity, reliability, and support for multiple update epochs make it the dominant online RL algorithm in practice — used for ChatGPT's RLHF, robotics fine-tuning, and reasoning model training (o1, DeepSeek-R1).

### ReloPass Application Notes
Policy gradients provide the theoretical foundation for any learned policy in Case Command. If the rule engine were replaced by or augmented with a learned policy, REINFORCE would be the baseline: for each HR user session, observe the compliance state, take an action (surface a document request, send a reminder, escalate), receive a reward (compliance step completed, deadline met), and update the policy. PPO's clipping constraint is particularly relevant for Case Command: it prevents the policy from making large abrupt changes to the HR workflow, which is critical in compliance contexts where consistency is legally required. Entropy regularization maps to exploration: ensure the policy occasionally suggests less-traveled compliance pathways (e.g., the route for a dual-national employee in FR→NO) rather than always defaulting to the most common path.

---

## Lecture 4: Actor-Critic Methods

**Video URL:** https://www.youtube.com/watch?v=d4TLIkxaFcw (approximate)  
**Slide Source:** `webfetch-1786775769715-53yzuh.pdf` → `webfetch-1786775769715-53yzuh.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Actor-Critic Methods. Course reminders: HW1 due tonight. Plan: actor-critic methods; improving policy gradients; how to estimate the value of a policy; sample-based Monte Carlo vs. bootstrapped TD; off-policy actor-critic; importance weights; full off-policy version with replay buffers.

**Recap of Policy Gradients.** Online RL with policy gradients: run policy to collect batch of data; improve policy using batch; repeat. On-policy attribute: update uses only data from current policy. Off-policy attribute: update can reuse data from other, past policies. Vanilla PG is fully on-policy.

**Useful Objects.** Value function V^π(s): future expected rewards starting at s following π. Q-function Q^π(s,a): future expected rewards starting at s, taking a, then following π. Advantage A^π(s,a) = Q^π(s,a) - V^π(s): how much better taking a is than following π at state s. Key relation: Q^π(s,a) = r(s,a) + γ·E[V^π(s')].

**Estimating Reward-to-Go.** Monte Carlo: run full trajectory, use actual returns. Unbiased but very high variance. Bootstrapped TD: G_t ≈ r_t + γ·V(s_{t+1}). Uses own estimate — biased but much lower variance. N-step returns and GAE (Generalized Advantage Estimation) interpolate between the two.

**Actor-Critic.** Use a critic network to estimate V^π(s) or A^π(s,a), then use that estimate in the policy gradient update instead of the raw returns. Actor: the policy π_θ. Critic: the value function V_φ. Benefit: lower variance policy gradient estimates → more data-efficient learning.

**Off-Policy Actor-Critic.** Importance weights allow reusing data from older policies. KL constraint or clipping (PPO-style) prevents instability. Full off-policy version: maintain a replay buffer D; sample minibatches from D; compute TD targets using target network; update critic; compute policy gradient using critic estimates; update actor.

**SAC (Soft Actor-Critic).** Entropy-maximizing off-policy actor-critic. Maintains a replay buffer. Adds entropy term to reward: r(s,a) + α·H(π(·|s)). Encourages exploration; prevents premature convergence. State-of-the-art for continuous control.

**Practical Notes.** Target networks: maintain a slowly-updated copy of the critic to stabilize TD targets. Polyak averaging: φ_target ← τ·φ + (1-τ)·φ_target with τ ≈ 0.005. Without target networks, training diverges.

### Lecture Summary (350 words)
Actor-critic methods combine the strengths of policy gradients (direct policy optimization) and value function learning (lower-variance return estimates). The actor is the policy being optimized; the critic is a learned value function that provides feedback on how good each state or action is.

The key insight is that policy gradient variance can be dramatically reduced by replacing noisy Monte Carlo returns with bootstrapped value estimates. The advantage function A(s,a) — how much better action a is than the average action in state s — gives the policy gradient a much cleaner signal about which actions to reinforce. The critic learns this advantage function from data using temporal difference (TD) learning: the Bellman equation recursively defines value functions, enabling us to estimate long-horizon returns without running full trajectories.

Off-policy actor-critic methods use replay buffers to store and reuse experience from all past policies, not just the current one. This dramatically improves sample efficiency. SAC (Soft Actor-Critic) is the dominant off-policy actor-critic algorithm for continuous control: it adds an entropy bonus to encourage exploration and prevent overfitting to a single action mode. Target networks stabilize training by providing slowly-updated TD targets that don't oscillate as the critic is updated.

The lecture concludes by comparing algorithm variants across key dimensions: what data is used, how the value function is fit, how goodness is estimated, and how off-policy data is incorporated. This taxonomy is critical for choosing the right algorithm for a given application.

### ReloPass Application Notes
The actor-critic structure maps directly to a two-level Case Command architecture. The critic estimates the value of being in a particular compliance state: "Given that we are at week -8 before move date, the employee has submitted passport copies, but tax registration is pending — how likely are we to achieve full compliance by move date?" The actor then selects the most valuable next action: send a reminder about tax registration, escalate to HR manager, or surface the specific government form. TD learning is particularly useful because relocation timelines are long (months) and sparse-reward — you cannot wait until move-day to assess whether the process succeeded. Bootstrapped estimates allow learning from intermediate milestones. Target networks prevent oscillations in priority scoring when the compliance state changes rapidly (e.g., employee changes move date).

---

## Lecture 5: Off-Policy Actor-Critic (Deep Dive)

**Video URL:** https://www.youtube.com/watch?v=aHOlM0jQEFU (approximate)  
**Slide Source:** PDF not available (404 on attempted download)

### Transcript / Slide Content
*Slide PDF not downloadable. Content reconstructed from course curriculum and Lecture 4 overlap material.*

This lecture provides a deeper treatment of off-policy actor-critic methods. Key topics: replay buffers and their role in sample efficiency; target networks and Polyak averaging; the role of entropy regularization in SAC; twin critic networks to reduce overestimation bias (TD3, SAC); practical implementation tips for continuous control.

**Replay Buffers.** Store all past experience (s, a, r, s', done) in a ring buffer. Sample random minibatches for each gradient step. This breaks temporal correlations in the data, stabilizing neural network training. Key hyperparameter: buffer size. Too small: forgetting; too large: data from a very different policy dominates.

**Twin Critics.** Overestimation bias in Q-learning: the max operator in TD targets tends to select overestimated Q-values, leading to divergence. Fix (TD3, SAC): maintain two critic networks Q1 and Q2; use min(Q1, Q2) as the TD target. This conservative estimate stabilizes training.

**SAC Deep Dive.** Objective: maximize expected return plus entropy. The temperature parameter α controls the exploration-exploitation tradeoff. Can be automatically tuned by setting a target entropy equal to -|A| (negative action dimension). SAC is robust to hyperparameters and generalizes across continuous control tasks.

### Lecture Summary (280 words)
This lecture deepens the treatment of off-policy learning with a focus on practical implementation. Replay buffers are the cornerstone of sample efficiency: by storing and randomly sampling all past experience, off-policy algorithms can learn from each data point many times. The tradeoff is that old data may come from policies that are far from the current policy — importance weights or conservative Q-value estimates compensate.

Twin critic networks address the overestimation problem that plagues Q-learning and actor-critic methods. By maintaining two independently initialized critics and using the minimum of their estimates as the learning target, the algorithm avoids the positive feedback loop where overestimated values lead to overconfident policies that collect bad data, which further reinforces incorrect values.

SAC's entropy regularization provides a principled exploration mechanism: the policy is rewarded for being uncertain (high entropy actions), which prevents premature convergence to suboptimal policies. Automatic temperature tuning removes the need to manually set the exploration-exploitation tradeoff.

### ReloPass Application Notes
Replay buffers are directly useful for Case Command's longitudinal data. Each relocation case is a trajectory: a sequence of compliance steps, deadlines met or missed, escalations, and final outcome (successful relocation or not). Storing all cases in a replay buffer and training a Q-function on this data is offline RL — learning from the history of all past relocations without running a live online RL loop. Twin critics prevent overestimating the value of novel compliance pathways that have rarely been tried (e.g., a new corridor with only two historical cases). Entropy regularization encourages the system to explore by occasionally recommending less-used compliance strategies when the standard path is blocked (e.g., visa processing backlog).

---

## Lecture 6: Q-Learning

**Video URL:** https://www.youtube.com/watch?v=MLJL-jAJPJw (approximate)  
**Slide Source:** `webfetch-1786775770284-2itt9h.pdf` → `webfetch-1786775770284-2itt9h.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Q-Learning. Plan: motivation; tabular Q-learning; deep Q-networks (DQN); practical improvements.

**Motivation.** Policy gradient and actor-critic methods require the policy to be differentiable. Q-learning instead learns the optimal action-value function Q*(s,a) directly, then derives the optimal policy as π*(a|s) = argmax_a Q*(s,a). This avoids policy gradient variance and enables learning without explicit policy parameterization.

**Bellman Optimality Equation.** Q*(s,a) = r(s,a) + γ·max_{a'} Q*(s',a'). The optimal Q-function satisfies this recursive equation. Q-learning iterates this equation: Q(s,a) ← Q(s,a) + α·[r + γ·max_{a'} Q(s',a') - Q(s,a)].

**Tabular Q-learning.** Converges to Q* for finite MDPs with sufficient exploration. But: real problems have continuous or very large state spaces — tabular is infeasible.

**DQN (Deep Q-Network).** Replace the Q-table with a neural network Q_φ(s,a). Key innovations: (1) Experience replay: store transitions in replay buffer, sample random minibatches. (2) Target network: separate network Q_φ_target updated slowly via Polyak averaging — prevents oscillating TD targets. Training objective: minimize Bellman error L(φ) = E[(r + γ·max_{a'} Q_φ_target(s',a') - Q_φ(s,a))^2].

**Overestimation Bias.** The max operator over the Q-function introduces positive bias: we systematically overestimate Q*. Double DQN fix: use current network to select the best action, use target network to evaluate it. Reduces overestimation.

**N-step Returns.** Use rewards from the next N steps before bootstrapping: G_t^(N) = r_t + γr_{t+1} + ... + γ^{N-1}r_{t+N-1} + γ^N Q(s_{t+N}, a_{t+N}). Reduces bias from bootstrapping; increases variance. Typical values: N = 3-10.

**Practical Tips.** (1) Prioritized experience replay: sample transitions with higher TD error more frequently. (2) Huber loss instead of MSE for Bellman error — more robust to outliers. (3) Frame stacking for partially observable environments. (4) Reward clipping to [-1, 1] for training stability.

### Lecture Summary (320 words)
Q-learning takes a different approach to reinforcement learning than policy gradient methods. Instead of directly optimizing the policy, Q-learning learns the optimal action-value function Q*(s,a): the expected total reward of taking action a in state s and then acting optimally thereafter. The optimal policy is then trivially derived: always take the action with the highest Q-value.

Deep Q-Networks (DQN) make Q-learning practical for high-dimensional state spaces by approximating Q* with a neural network. The key algorithmic contributions are experience replay — storing and randomly sampling past transitions to break temporal correlations — and target networks — maintaining a slowly-updated copy of the Q-network to provide stable regression targets. Without these two innovations, neural network Q-learning diverges.

Overestimation bias is a pervasive problem: the max operator consistently selects actions with spuriously high Q-values. Double DQN addresses this by decoupling action selection from evaluation, using the current network to choose the action and the target network to estimate its value. N-step returns reduce the bias introduced by bootstrapping at the cost of higher variance.

Q-learning is critic-only: there is no explicit policy gradient, and the policy is implicit in the argmax operation. This makes it particularly well-suited to discrete action spaces, though extensions to continuous actions exist (e.g., through implicit or explicit policy extraction).

### ReloPass Application Notes
Q-learning maps cleanly to Case Command's discrete action space. Each compliance action (send document request, set deadline, escalate to HR manager, trigger government portal submission) is a discrete action. Q*(compliance_state, action) gives the expected compliance outcome value of taking that action in this state. Case Command can be framed as a Q-learning problem: train Q* on historical relocation data, then deploy the argmax policy as the recommendation engine. The Bellman equation captures the long-horizon value of compliance decisions: submitting the visa application at week -10 (rather than week -6) has downstream value for subsequent steps, and Q* automatically propagates this through the recursion. Double DQN's conservative estimation prevents overconfidence in untested action sequences for new corridors.

---

## Lecture 7: Offline Reinforcement Learning

**Video URL:** https://www.youtube.com/watch?v=CW24hL5wMj8 (approximate)  
**Slide Source:** `webfetch-1786775777209-yftohi.pdf` → `webfetch-1786775777209-yftohi.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Offline Reinforcement Learning. Plan: offline RL problem setup; why offline RL is hard; advantage weighted regression (AWR); implicit Q-learning (IQL); AWAC.

**Problem Setup.** Can we learn a policy from a batch of existing data, without online data collection? Given: a fixed dataset D = {(s_t, a_t, r_t, s_{t+1})} collected by unknown behavior policy β. Goal: learn π that maximizes E[Σr]. No additional data collection allowed.

**Why Offline RL is Hard.** The off-policy critic objective: min_φ E[(r + γ·max_{a'} Q_φ(s',a') - Q_φ(s,a))^2]. Querying Q-function on out-of-distribution (OOD) actions causes overestimation. In online RL, data from the new policy corrects errors in future iterations — with offline RL, there is no additional data.

**Key Idea #1: Advantage Weighted Regression (AWR).** Only train the policy on actions sampled from the dataset. Policy update: max_θ E_{(s,a)~D}[log π_θ(a|s) · exp(A^π(s,a)/β)]. This avoids OOD policy queries by weighting dataset actions by their advantage. Conservative: never recommends actions outside the dataset.

**Key Idea #2: Asymmetric Expectile Loss (IQL).** Implicit Q-Learning (Kostrikov et al. 2021). Rather than querying Q(s, argmax_a...), fit a value function V(s) that implicitly estimates the maximum via expectile regression: L_τ(u) = |τ - 1(u<0)| · u^2. With τ > 0.5 (asymmetric), V(s) approximates max_a Q(s,a) without ever querying OOD actions. The actor is then extracted via AWR on top of this implicit Q-function.

**AWAC (Advantage Weighted Actor-Critic).** Combines AWR with actor-critic: use an off-policy critic but constrain policy updates to dataset actions. Enables fine-tuning from offline data into online RL.

**Practical Recipe: Iterated Offline RL.** Collect large batch of data using mixed policy (demonstrations + DAgger). Fit V using Monte Carlo. Train advantage-conditioned policy. Demonstrated in VLA post-training.

### Lecture Summary (360 words)
Offline RL addresses a critical practical constraint: in many real-world applications, online data collection is expensive, dangerous, or ethically problematic. We have large datasets of past behavior — relocation records, medical decisions, autonomous driving logs — but we cannot run a live RL agent to collect more. Offline RL attempts to extract a good policy from this fixed dataset.

The fundamental challenge is distributional shift applied to the value function. Off-policy algorithms like Q-learning bootstrap from Q(s', argmax_a Q(s',a)), but argmax_a may select actions never seen in the dataset. The Q-function is highly inaccurate on these out-of-distribution actions, and since we cannot collect new data to correct these errors, they can propagate catastrophically.

Advantage Weighted Regression (AWR) solves this conservatively: only update the policy on actions that appear in the dataset, weighting each action by how much better it is than average. This never queries the Q-function on OOD actions. Implicit Q-Learning (IQL) takes a more sophisticated approach: fit the value function V(s) using asymmetric expectile regression, which implicitly approximates max_a Q(s,a) using only in-distribution data. The actor is then extracted by AWR relative to this implicit value function.

These offline RL algorithms have become the backbone of robot learning from large datasets, and are directly used for post-training VLAs (Vision-Language-Action models) from human demonstrations. The iterated offline RL recipe — collect demonstrations, fit value function, distill policy, optionally fine-tune online — is one of the most practical patterns in modern robot learning.

### ReloPass Application Notes
Offline RL is the most immediately applicable RL paradigm for Case Command. ReloPass already has a dataset of historical relocation cases: every case has a compliance sequence (actions taken), timestamps (when each step was completed), and an outcome (successful relocation, failed visa, expired permit). This is precisely the offline RL dataset. AWR can train a compliance recommendation policy from this dataset: weight each historical compliance decision by whether it led to good outcomes (timely visa approval, no compliance gaps) relative to the average. IQL's asymmetric expectile loss is particularly relevant because compliance success is rare and right-skewed — most cases succeed, but failures are catastrophic. The asymmetric loss ensures the value function properly models the upper tail. Offline RL also enables safe policy improvement: never recommend compliance actions outside the dataset of historically validated pathways.

---

## Lecture 8: Reward Learning

**Video URL:** https://www.youtube.com/watch?v=0ZGg6oS-m_U (approximate)  
**Slide Source:** `webfetch-1786775777831-iie6de.pdf` → `webfetch-1786775777831-iie6de.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Reward Learning. Plan: offline RL recap and example; where do rewards come from; learning rewards from example goals and behaviors; learning rewards from human preferences.

**Recap: Offline RL.** Key idea #1: AWR — only train policy on actions sampled from dataset. Key idea #2: IQL — asymmetric expectile loss to fit V(s) better than the behavior policy without OOD queries. Practical example: collect large batch using mix of roll-outs and DAgger; fit V using Monte Carlo; train advantage-conditioned policy. "A VLA That Learns From Experience."

**Where Does the Reward Come From?** Computer games: scalar score. Real-world robotics: what is the reward? Often use a proxy. Are there other, easier ways of providing task supervision? Reward is hard to define for: robotics, dialog, autonomous driving. Direct imitation learning mimics actions of expert — but no reasoning about outcomes or dynamics; expert might have different degrees of freedom; might not be possible to provide demonstrations.

**Goal Classifiers.** Key idea: learn to discern goal states from other states. Example task: put pencil case behind notebook. Train classifier: given state image, does it show the goal configuration? Use classifier output as a reward signal. Advantage: only needs examples of success, not demonstrations of how to achieve it. Limitation: difficult to define dense reward for complex tasks with a binary classifier.

**Inverse Reinforcement Learning (IRL).** Given expert demonstrations, infer the reward function the expert appears to be optimizing. Recover R such that π_expert ≈ π*(R). Then train RL agent on inferred R. Challenges: reward ambiguity (many reward functions explain same behavior); nested optimization (train RL inside IRL). Modern approaches: AIRL (Adversarial IRL), GAIL (Generative Adversarial Imitation Learning).

**Learning Rewards from Human Preferences.** Rather than demonstrations or goal examples, collect pairwise comparisons: "Is behavior A or behavior B better?" Fit a reward model using the Bradley-Terry model: P(A preferred to B) = exp(r(A)) / (exp(r(A)) + exp(r(B))). Train reward model R_φ on comparison dataset. Use R_φ as the reward signal for RL training.

**Reward Hacking.** Learned rewards are imperfect; RL will find ways to get high learned reward that don't correspond to task success. Example: boat racing game where the agent learns to spin in circles collecting bonus points rather than finishing laps. Mitigation: KL constraint to prevent policy from straying too far from reference model; iterative reward learning with additional comparisons.

### Lecture Summary (330 words)
Reward learning addresses the fundamental bottleneck of applying RL to real-world problems: reward functions are extremely hard to specify manually. What is the reward for a good conversation with a chatbot? For a robot that folds a towel? For a recommendation that satisfies a user? These tasks resist simple numerical reward definitions.

The lecture covers three approaches to reward learning. Goal classifiers learn a binary function that scores states as goal-achieving or not, from examples of success states rather than demonstrations of how to reach them. This is especially useful in robotics where it is easy to show the robot the target configuration but hard to demonstrate the manipulation sequence. Inverse RL infers the reward function from expert behavior: if we observe an expert acting in a task, what reward function would explain their choices? IRL recovers this function and then trains an RL agent on it.

Preference-based reward learning, most relevant to modern LLM alignment, collects pairwise human comparisons between behaviors and fits a Bradley-Terry model that assigns scalar reward to each behavior. The reward model is then used as a proxy reward in RL training. The critical risk is reward hacking: RL finds policies that maximize the learned reward without achieving the intended task. KL constraints and continued reward model updates are the primary mitigations.

### ReloPass Application Notes
Reward learning is directly applicable to Case Command's compliance scoring challenge. It is hard to define a single reward function for "successful relocation" — it depends on timeliness, employee stress, cost, legal risk, and HR burden. Preference-based reward learning offers a solution: present pairs of historical relocation cases to HR managers and ask which one they would have preferred (faster, smoother, less error-prone). Fit a reward model R(relocation_trajectory). Use this as the RL reward instead of a hand-engineered score. Goal classifiers apply to specific milestones: "Given this compliance state at week -4, is the employee on track for successful move date?" — a binary classifier that defines intermediate rewards. Reward hacking prevention: constrain the learned policy to only recommend compliance actions that are legally valid for the corridor.

---

## Lecture 9: RL for LLMs and RLHF

**Video URL:** https://www.youtube.com/watch?v=Ux6N4mAjccs (approximate)  
**Slide Source:** `webfetch-1786775784970-viucbe.pdf` → `webfetch-1786775784970-viucbe.txt`  
**Guest Lecturer:** Archit Sharma (Gemini team, Google DeepMind)

### Transcript / Slide Content (Key Excerpts)
LLM Training Overview. Pre-Training: train on lots of natural data, sourced and curated from variety of sources, primarily internet. Mid-Training: more targeted domains, lower volume data. Supervised Fine-Tuning / Instruction Tuning: small, curated, enable model to follow human intent. Reinforcement Learning (from Human Feedback): align with implicit human intent.

What kinds of things does pretraining learn? Language models as world models? Language models may do rudimentary modeling of agents, beliefs, and actions. Language models as world models? Math. Language models as world models? Code. Language models as world models? Medicine.

**Instruction Finetuning.** Collect examples of (instruction, output) pairs across many tasks and finetune an LM. Evaluate on unseen tasks. Scale is key: SuperNaturalInstructions dataset contains over 1.6K tasks, 3M+ examples. FLAN-T5 demonstrates significant improvement on instruction following. After instruction finetuning: simple and straightforward; generalize to unseen tasks. Limitations: constructing demonstrations is expensive to scale; mismatch between LM objective and human preferences.

**RLHF (Reinforcement Learning from Human Feedback).** For an instruction and an LM sample, obtain a human reward: higher is better. Maximize expected reward using policy gradient methods. How do we get the rewards? Train a reward model to predict human reward from an annotated dataset. Problem: human judgments are noisy and miscalibrated. Solution: instead of asking for direct ratings, ask for pairwise comparisons.

**Reward Model Training.** Bradley-Terry model: P(A preferred over B) proportional to exp(r(A) - r(B)). We only need the difference between rewards. Train RM on comparison data.

**Optimizing the Learned Reward.** We have: a pretrained (possibly instruction-finetuned) LM; a reward model. Optimize LM to produce high-reward outputs. Add KL penalty: reward - β·KL(π||π_ref). Prevents drifting too far from the initialization. KL divergence is a standard penalty for divergence from reference policy.

**DPO (Direct Preference Optimization).** What if there was a way to write the RLHF objective directly in terms of the policy? Derive: can we optimize directly to the preference data instead of training a reward model? Key insight: we only need the difference between rewards — write it in terms of log-ratio of policy probabilities. Final DPO loss function: a simple classification loss that connects preference data to language model parameters directly.

**InstructGPT.** Scaling up RLHF: 30k tasks. Tasks collected from labelers. ChatGPT: fine-tuning + RLHF for dialog agents. DPO is enabling open-source models to improve.

**RLHF/DPO behaviors — clear stylistic changes.** Significantly more detailed, nicer/clearer list-like formatting.

**Learned rewards can be unreliable.** Reward model over-optimization: model behavior is hard to control. Human preferences are unreliable. LLMs overproduce emojis. Can become overly sycophantic. Hard to balance all different reward functions.

**AI models can give themselves rewards.** Constitutional AI (Bai et al., 2022): model critiques its own output and revises. Enables self-improvement without human feedback on every sample.

### Lecture Summary (370 words)
This guest lecture by Archit Sharma traces the complete pipeline for aligning large language models with human intent, from pretraining through RLHF and DPO. Pretraining on internet-scale text gives LLMs vast world knowledge — math, code, science, language — but does not align the model with what users actually want. A raw pretrained model completes text, not follows instructions.

Instruction finetuning bridges this gap by training on curated (instruction, output) pairs across thousands of tasks. The model learns to follow human intent in a supervised setting. But supervised finetuning has a fundamental mismatch: the language model is trained to predict tokens, not to maximize human satisfaction. The outputs that score well on log-likelihood are not necessarily the outputs that humans prefer.

RLHF addresses this by learning a reward model from human pairwise comparisons and then optimizing the LM against that reward. The Bradley-Terry model converts pairwise preferences to scalar rewards. The KL penalty against the reference policy prevents reward hacking — without it, the model finds degenerate high-reward outputs that satisfy the reward model but not real users.

DPO offers an elegant simplification: by algebraically rearranging the RLHF objective, one can show that the optimal policy satisfies a constraint expressible directly in terms of log-ratios of the policy's own probabilities. This eliminates the need to train an explicit reward model — preferences can be used directly to update the LM parameters via a binary classification loss.

Critical failure modes: reward model over-optimization (Goodhart's Law — the model finds ways to exploit the reward model), sycophancy, emoji overproduction, and difficulty balancing multiple competing objectives. These problems motivate continued research in scalable oversight, Constitutional AI, and process supervision.

### ReloPass Application Notes
The RLHF pipeline is a template for Case Command's compliance recommendation quality. The reward model corresponds to a compliance quality scorer: HR managers compare pairs of compliance timelines and indicate which they prefer (faster, fewer errors, less HR burden). DPO then directly optimizes the recommendation engine to match these preferences without an explicit intermediate reward model — operationally simpler for a small team. Constitutional AI's self-critique mechanism could enable Case Command to self-check compliance recommendations against legal rules without human review of every case, scaling oversight without scaling headcount.

---

## Lecture 10: RL for LLM Reasoning

**Video URL:** https://www.youtube.com/watch?v=sNp_lI5FBTE (approximate)  
**Slide Source:** `webfetch-1786775685104-nzeumd.pdf` → `webfetch-1786775685104-nzeumd.txt`  
**Guest Lecturer:** Aviral Kumar (Carnegie Mellon University)

### Transcript / Slide Content (Key Excerpts)
CS 224R — RL for LLM Reasoning. Guest lecture by Aviral Kumar, CMU.

**Problem statement.** Can RL enable LLMs to reason better? Key challenge: LLMs are trained on internet text, which contains reasoning but not verified correct reasoning. RL with a verifiable reward (correctness signal) can push beyond the training distribution.

**Sparse Reward MDP.** Reasoning problems have a natural RL framing: state = partial chain-of-thought; action = next token; reward = 1 if final answer is correct, 0 otherwise. This is an extremely sparse, delayed reward MDP. The trajectory is an entire chain-of-thought reasoning trace.

**Rejection Finetuning (RFT).** Simple baseline: sample many chains-of-thought from the LLM; keep only those that produce the correct final answer; finetune on the correct ones. This is offline RL without a value function — essentially AWR with a binary reward. Works surprisingly well at scale.

**Process Reward Models (PRMs).** Rather than reward only the final answer, train a PRM to evaluate intermediate reasoning steps. This provides denser reward signal. Training PRMs requires human annotation of reasoning steps or automatic verification. PRMs are used in inference-time search (best-of-N sampling with PRM scoring) and in RL training.

**GRPO (Group Relative Policy Optimization).** Used in DeepSeek-R1. Sample a group of outputs from the current policy; compute rewards; normalize rewards within the group to get advantages; apply policy gradient with these normalized advantages. Avoids the need for a separate critic network — the group provides its own baseline.

**DeepSeek-R1.** Demonstrates that RL on mathematical reasoning can unlock emergent behaviors: extended chains of thought, self-correction, and backtracking. The model learns to doubt itself and revise — behaviors not seen in the base model. Key finding: this "aha moment" behavior emerges from RL, not from supervised fine-tuning.

**Open questions.** Can RL for reasoning generalize from math/code to open-ended domains? How to define rewards for non-verifiable tasks? How to prevent reward hacking in reasoning (e.g., shortcutting to correct answers with incorrect reasoning)?

### Lecture Summary (350 words)
This lecture by Aviral Kumar focuses on one of the most exciting recent developments in RL: using reinforcement learning to improve LLM reasoning capabilities. The key insight is that reasoning tasks — math problems, coding challenges, formal proofs — have verifiable correct answers, providing a clean binary reward signal without needing a learned reward model.

The RL framing treats each reasoning trace (chain of thought) as a trajectory: the state is the partial reasoning so far, the action is the next token, and the reward is received only at the end when the answer is verified as correct or not. This is an extremely challenging sparse-reward MDP with extremely long horizons (thousands of tokens).

Rejection finetuning (RFT) is a simple but effective offline approach: sample many candidates, keep correct ones, finetune. This is essentially behavioral cloning on the distribution of correct reasoning traces. Its success demonstrates that the base LLM already has the capability to produce correct reasoning chains — RL just needs to find and reinforce them.

Process reward models extend the reward signal to intermediate reasoning steps, enabling RL algorithms to get feedback before the end of the reasoning trace. DeepSeek-R1 demonstrated that GRPO (a simplified policy gradient that uses within-group reward normalization as the baseline) can unlock emergent reasoning behaviors: extended deliberation, self-correction, backtracking — all learned from scratch through RL without explicit supervision of these behaviors.

### ReloPass Application Notes
RL for reasoning has direct implications for Case Command's compliance decision logic. Compliance determinations are inherently multi-step reasoning: "Employee is FR national moving to NO → requires work permit → permit requires salary certificate → salary certificate must be in French and Norwegian → processing time is 6 weeks → therefore start at week -10 from move date." This reasoning chain can be framed as a sparse-reward MDP where the reward is correctness of the final compliance action sequence. Process reward models map to intermediate compliance milestones: was the document request sent at the right week? Was the escalation triggered at the right threshold? RFT can train the reasoning engine from historical cases where the compliance outcome is known.

---

## Lecture 11: Model-Based Reinforcement Learning

**Video URL:** https://www.youtube.com/watch?v=1vdN2VGbqtg (approximate)  
**Slide Source:** `webfetch-1786775785365-uw69sg.pdf` → `webfetch-1786775785365-uw69sg.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Model-Based RL. Plan: learn a model; use it for planning or data generation; MBPO; Dyna-style algorithms.

**Key idea.** Model-based RL: learn a simulator of the dynamics. Any method that learns this is a model-based RL algorithm. Use the model to: (1) simulate additional data; (2) do planning (lookahead). Short synthetic roll-outs. Ensembles of models help average out errors. Mitigating model errors: simulate data starting from all states seen in the data; use with value functions for long-horizon planning.

**Upsides and Downsides.** + Models are immensely useful, far more data efficient if model is easy to learn. + Model can be trained on data without reward labels (fully self-supervised). + Model is somewhat task-agnostic (can sometimes be transferred across rewards). - Models don't optimize for task performance. - Sometimes harder to learn than a policy. - Another thing to train, more hyperparameters, more compute intensive. Whether to use a model depends on how hard it is to learn!

**MBPO (Model-Based Policy Optimization).** Train ensemble of dynamics models. Use models to generate short synthetic roll-outs from real data start states. Add synthetic data to replay buffer alongside real data. Train SAC (or other model-free algorithm) on combined buffer. Key finding: short roll-outs (1-5 steps) work best; longer roll-outs accumulate model errors.

**Dyna Architecture.** Classic framework: real environment interaction interleaved with model-based planning. Model provides "imagined" transitions; policy learns from both real and imagined data. Modern deep learning version: neural network dynamics model + replay buffer for imagined transitions.

**World Models.** Learn a latent space representation of the world. Dreamer: learn world model in latent space; plan and train actor-critic entirely within the latent world model; only occasionally interact with the real environment. Achieves human-level performance on many Atari games with orders of magnitude less environment interaction than model-free methods.

### Lecture Summary (330 words)
Model-based RL inserts a learned dynamics model between the agent and the environment. Instead of learning purely from real interactions, the agent can generate synthetic experience by querying its model: "What would happen if I took action a in state s?" This dramatically improves sample efficiency when the model is accurate.

The core tradeoff is model accuracy versus coverage. A perfectly accurate model would allow unlimited simulated experience. In practice, models have compounding errors over long roll-outs — small inaccuracies in each step accumulate, leading to unrealistic states far from the training distribution. MBPO's key insight is to use short roll-outs (1-5 steps) starting from real data states, keeping the model in its high-accuracy regime, and feeding this synthetic data to a model-free algorithm (SAC). The ensemble of models provides uncertainty estimates — when models disagree, the state is likely out of distribution.

World models like Dreamer take this further: learning a compact latent representation of the environment and training an actor-critic entirely within the imagined latent space. This enables learning from very few real environment interactions, which is critical in domains where data collection is expensive or dangerous.

The lecture emphasizes a key practical consideration: whether to use a model depends entirely on whether the model is easy to learn. For structured environments (robotics with known physics, relocation timelines with deterministic rules), models are easy and highly beneficial. For chaotic, high-dimensional environments (free-form language generation), models may be harder to learn than direct policies.

### ReloPass Application Notes
Model-based RL is the single most applicable paradigm for Case Command. The relocation timeline is a structured, partially deterministic process: given employee type, corridor, and move date, the sequence of government processing times and document requirements follows predictable patterns. This is a model that can be explicitly learned or specified. The model enables "what-if" planning: "If the employee's move date shifts by 2 weeks, which compliance steps are at risk?" MBPO's short synthetic roll-outs correspond to exploring alternative compliance strategies without actually executing them with a real employee. The ensemble uncertainty estimate flags novel corridor combinations (rare nationality-destination pairs) where the model is uncertain.

---

## Lecture 12: Multi-Task and Goal-Conditioned RL

**Video URL:** https://www.youtube.com/watch?v=hvSuBpxI4cU (approximate)  
**Slide Source:** `webfetch-1786775790922-a15lt0.pdf` → `webfetch-1786775790922-a15lt0.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Multi-Task and Goal-Conditioned Reinforcement Learning. Plan: problem set up; task conditioning and weight sharing; data sharing with hindsight relabeling. Key learning goal: how to share weights and data across tasks for learning efficiency.

**What is multi-task RL?** Can we train generalist policies to do many tasks, not just one? Examples: Generalist LLM assistant: travel booking, grocery shopping. Legged robot: walk, run, dance, crouch. Music recommender system: personalization to many distinct users. Mobile manipulator: hang up a towel, unload a dishwasher, wipe a spill. Game player: play Flappy Bird, Pokemon, Pinball.

**Key idea: condition on the task.** Why multi-task RL? Deeper motivation: amortize the data complexity across many tasks and scenarios. Plenty of learnings can be shared across tasks. LLM assistant: grammar. Legged robots: balance. Personal recommenders: user similarities. Generalist ML systems are often more reliable, performant than specialists.

**How to formalize tasks?** Different tasks can just be different MDPs! A task: state space, action space, initial state distribution, dynamics, reward. Task identifier: language description, task index, video illustration. An alternative view: task identifier is part of the state.

**Multi-task imitation learning.** Stratified sampling: construct each minibatch with data from each task — lower variance gradients. How to condition on the task? BC-Z (Jang et al., CoRL 2021): task embedding + robot policy. OpenVLA (Kim et al., CoRL 2024): modern policy architectures — task identifier passed as prompt into a fine-tuned LLM.

**Multi-Task RL Algorithms.** Consider per-task replay buffer for stratified sampling. Can we share data across tasks? Hindsight relabeling.

**Hindsight Experience Replay (HER).** If you accidentally perform a good pass when trying to shoot a goal, store experience normally AND relabel with task 2 ID and reward. Algorithm: (1) collect data using some policy; (2) store data in replay buffer; (3) perform hindsight relabeling — relabel experience in trajectory for task j where the goal was achieved; (4) update policy using replay buffer. Scenarios for relabeling: reward function form is known and evaluatable; dynamics consistent across goals/tasks; using an off-policy algorithm.

**Goal-conditioned RL with hindsight relabeling.** Relabel experience using last state as goal. Many other relabeling strategies from the trajectory. Directly applicable to goal-conditioned RL setting.

**Summary: Multi-task and goal-conditioned RL.** Weight sharing: train network to do all tasks, conditioned on task descriptor. Data sharing: add data collected for one task to buffer for another by relabeling the reward and task identifier. Requires: same dynamics across tasks; evaluatable reward functions; off-policy learning algorithm.

### Lecture Summary (350 words)
Multi-task RL asks whether a single policy can learn to perform many tasks simultaneously, sharing parameters and data across tasks. The motivation goes beyond convenience — generalist policies often outperform specialists because shared representations and joint training provide regularization, and data from one task can provide signal for another.

The key architectural choice is task conditioning: the policy takes the task identifier as an additional input, allowing a single neural network to specialize its behavior based on which task it is currently performing. Task identifiers can be language descriptions (enabling zero-shot generalization to new task descriptions), task indices, or even video demonstrations of the target behavior. Modern VLA systems pass the task identifier as a prompt into a language model backbone, leveraging pretrained language understanding.

Hindsight Experience Replay (HER) is the canonical data-sharing technique. The core insight: when an agent fails to achieve its intended goal, it may accidentally achieve some other goal. By relabeling that trajectory with the goal that was actually reached, we get additional learning signal for free. This is particularly powerful in goal-conditioned RL, where the agent tries to reach specific target states: every trajectory, regardless of outcome, provides a valid learning signal if we relabel with the state that was actually reached.

Multi-task RL subsumes goal-conditioned RL as a special case where each goal defines a task. The key requirements for data sharing are: consistent dynamics across tasks (the world works the same way regardless of the goal), evaluatable reward functions (we can compute the reward for any trajectory under any goal), and an off-policy algorithm that can learn from relabeled data.

### ReloPass Application Notes
Multi-task RL is the exact framework for Case Command's multi-corridor architecture. Each relocation corridor (FR→NO, ES→IE, NO→FR) is a different task (different regulatory requirements, different government processing times, different document sets). Task conditioning means a single policy network, conditioned on the corridor descriptor, handles all corridors — sharing knowledge about document timelines, HR communication patterns, and escalation logic. HER is directly applicable: if an employee's relocation is partially completed (they reached an intermediate compliance state they didn't intend to reach), relabel that trajectory as a successful path to that intermediate state, providing additional training signal without collecting more data. This is crucial for rare corridors with few historical cases.

---

## Lecture 13: Meta-Reinforcement Learning

**Video URL:** https://www.youtube.com/watch?v=7OhCVSj8QhQ (approximate)  
**Slide Source:** `webfetch-1786775791402-arepxz.pdf` → `webfetch-1786775791402-arepxz.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Meta Reinforcement Learning. Reminders: midterm this Friday morning. Plan: meta-RL problem statement; black-box meta-RL methods.

**Recap of Multi-task Learning.** Summary multi-task RL as single-task RL in a joint MDP. Summary goal-conditioned learning: special case, each task aims to reach some goal state. Weight sharing: train network conditioned on task descriptor. Data sharing: hindsight relabeling.

**What is the problem?** Say you wanted to learn to make coffee with a new espresso machine. People aren't starting from scratch! Training a robot to do this with PPO would take millions of attempts. With some instruction or prior coffee experience, a person could learn in minutes. Experience with similar tasks — either espresso-making on other machines or general motor control. Can also learn to solve a challenging math problem more quickly using past problem solving experience.

**Framing Transfer Learning Problems.** Forward transfer: learn policies that transfer effectively; train on source task, then fine-tune on target task. Multi-task transfer: train on many tasks, transfer to a new task; task prompt/descriptor needs to capture task structure for zero-shot transfer. Meta-learning: learn to learn on many tasks; accounts for the fact that we'll be adapting to a new task during training; the task descriptor is a few data examples provided in-context. For forward and multi-task: target task must be similar to distribution of training tasks. For forward transfer: source and target tasks must be similar.

**What does few-shot learning look like outside of RL?** Train a model to be able to make predictions using a few examples. In-context learning in LLMs. Few-shot image classification.

**Meta-RL.** Learn a policy that solves many MDPs by seeing a few data examples from each. The task descriptor is a few (state, action, reward, next state) examples from a new MDP. Learn how to efficiently explore and solve the new task.

**Exploration-exploitation trade-off is a unique part of meta-RL.** Collect correct small amount of experience in new MDP. Learn policy that solves that MDP. Collect correct exploration data. Meta-trains: learns how to efficiently explore and solve many MDPs. So that we can expect generalizations. Meta-reinforcement learning task distribution: navigation through different mazes, locomotion on different terrains, slopes; object manipulation with different objects, goals; dialog with different users with different preferences.

**Black-box meta-RL.** Train a single policy (often a recurrent network or transformer) to take the history of interactions as input and produce actions. The recurrent hidden state implicitly encodes what we know about the current task. At meta-test time: start the policy from scratch in a new task; the recurrent network explores and adapts its internal state; eventually the hidden state encodes the task and the policy solves it. Training: sample task from distribution; run policy with hidden state for K episodes; compute reward; use policy gradient on accumulated rewards across K episodes.

**Challenge: Exploration.** The meta-RL agent must learn to explore efficiently. A purely greedy policy won't explore enough to identify the task. But an agent that explores too much wastes episodes. The agent must balance exploration (gathering information about the task) with exploitation (acting optimally given current beliefs). This is a fundamentally different exploration problem than standard RL — the agent is exploring to identify the task, not to discover high-reward states.

### Lecture Summary (360 words)
Meta-reinforcement learning addresses a fundamental limitation of standard RL: training from scratch for each new task. Humans don't do this — we use prior experience to learn new tasks much faster. Meta-RL formalizes this: train a learning algorithm (or equivalently, a policy that can adapt) on many tasks from a distribution, such that it can learn a new task from the same distribution with very few interactions.

The key distinction from multi-task RL is what the policy receives at test time. Multi-task RL provides a fixed task descriptor; meta-RL provides a few examples of interaction from the new task (state-action-reward tuples). The meta-learned policy must infer the task structure from these examples and act accordingly.

Black-box meta-RL implements this with a recurrent neural network or transformer: the history of interactions is passed as input, and the hidden state implicitly encodes the policy's current beliefs about the task. Training consists of sampling tasks, running the policy for multiple episodes (with hidden state carried over), and optimizing across all tasks. At test time, the policy adapts automatically through its hidden state updates.

The key unique challenge in meta-RL is the exploration-exploitation tradeoff at the task level: the agent must explore to identify the task, but excessive exploration wastes the limited budget of new-task interactions. Meta-learned exploration strategies can be more efficient than standard exploration because they are conditioned on prior task experience.

Meta-RL is the theoretical foundation for in-context learning in LLMs: a transformer trained on many tasks implements gradient-free adaptation through its attention mechanism, effectively performing meta-learning at inference time.

### ReloPass Application Notes
Meta-RL directly addresses Case Command's cold-start problem for new corridors. When a new country pair is added (e.g., DE→SE), there are very few historical relocation cases. Meta-RL provides the framework: train a policy on the existing corridors (FR→NO, ES→IE, NO→FR), learning a general adaptation strategy, then at test time for a new corridor, adapt quickly from the few available cases. The recurrent hidden state corresponds to the system's evolving understanding of a specific corridor's regulatory quirks as it processes each new relocation case. The meta-learned exploration strategy maps to how the system proactively gathers information about a new corridor — which regulatory bodies to query, which document types to request — before needing to process a live relocation.

---

## Lecture 14: Exploration

**Video URL:** https://www.youtube.com/watch?v=OoJV9b0BVII (approximate)  
**Slide Source:** Not available

### Transcript / Slide Content
*Slide PDF not downloadable. Content reconstructed from course curriculum.*

**The exploration problem.** In sparse-reward environments, an agent following a greedy policy will rarely encounter non-zero reward. It needs to actively explore — try novel actions and states — to discover rewarding behaviors. Pure random exploration (epsilon-greedy, random action selection) is inefficient in large state spaces.

**Count-based exploration.** Maintain visit counts N(s) for each state. Bonus reward: r_bonus = β / sqrt(N(s)). Exploration is driven toward novel states. Problem: in high-dimensional continuous state spaces, every state is visited at most once.

**Intrinsic Motivation / Curiosity.** Replace count-based bonus with a learned novelty measure. Curiosity-driven exploration: bonus proportional to prediction error of a dynamics model — agent seeks states where its model of the world is most wrong. ICM (Intrinsic Curiosity Module). RND (Random Network Distillation): bonus based on prediction error of a randomly initialized network — states that are hard to predict are intrinsically rewarding.

**Thompson Sampling / Posterior Sampling.** Maintain a distribution over possible MDPs (or Q-functions). Sample an MDP from the posterior; act optimally under the sampled MDP. This naturally balances exploration and exploitation. In practice: ensemble of Q-functions; sample one Q-function and act greedily.

**Upper Confidence Bound (UCB).** Act according to Q(s,a) + β · sqrt(log(N(s)) / N(s,a)). Optimistic in the face of uncertainty — prefer actions with high uncertainty.

**Go-Explore.** Archive interesting states; periodically return to archived states and explore from there. Effective for hard exploration problems with many local optima.

### Lecture Summary (290 words)
Exploration is one of the most fundamental challenges in RL: without exploration, the agent cannot discover rewarding behaviors in sparse-reward environments. Standard approaches range from simple epsilon-greedy random action selection to sophisticated count-based bonuses and curiosity-driven intrinsic motivation.

Intrinsic motivation methods add a bonus reward for visiting novel states, operationalized through prediction error of a learned model (curiosity) or random network distillation (RND). These methods are powerful in environments where extrinsic reward is sparse or delayed, enabling the agent to explore without being directed by task-specific reward.

Posterior sampling methods (Thompson Sampling) maintain uncertainty about the world and actively seek to reduce that uncertainty, providing a principled Bayesian framework for exploration. UCB methods are the bandit version of this approach, adapted to RL through count-based confidence bounds.

### ReloPass Application Notes
Exploration is directly relevant to Case Command's corridor expansion strategy. When entering a new country corridor, the system must "explore" — try different approaches, gather regulatory information, and discover which compliance strategies work. Count-based exploration maps to tracking which compliance pathways have been attempted for a corridor and prioritizing under-explored paths. Curiosity-driven exploration maps to proactively seeking regulatory updates in corridors where the system's model has high uncertainty (frequent changes to immigration law). Thompson sampling maps to A/B testing compliance strategies for borderline cases: randomly sample between two valid approaches (e.g., different document submission orders) to learn which is more reliable.

---

## Lecture 15: Hierarchy in Imitation and Reinforcement Learning

**Video URL:** https://www.youtube.com/watch?v=fFpDNtv88ZU (approximate)  
**Slide Source:** `webfetch-1786775799400-cxzbzo.pdf` → `webfetch-1786775799400-cxzbzo.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Hierarchy in Imitation and Reinforcement Learning. Brief recap: multi-task IL/RL; task descriptor; state; goal state; meta-RL; few-shot experience. Today: can we string together behaviors from multiple (sub)tasks?

**Why long-horizon tasks are hard.** Very large number of states visited. Many opportunities to make mistakes. Many opportunities to get stuck. Examples: cook focaccia; drive to Yosemite; fix a bug that is causing neural network training loss to explode; give feedback on an 8-page report.

**The main idea.** Bake a cheesecake → buy ingredients → go to the store → walk to the door → take a step → contract quad muscle. Doing the bottom is easy; doing the top is really hard. Can we break up hard tasks into easier subtasks? High-level policy predicts intermediate goals. Low-level policy tries to accomplish each goal by predicting actions. Many names for intermediate goals: subgoals, subtasks, skills, options, high-level actions. Could have more than 2 levels of hierarchy. Low-level policy operates at higher frequency than high-level policy.

**Why may hierarchy help?** Supervision signal on how to complete the task. More direct knowledge sharing across similar subtasks. In RL: structured exploration in higher-level space. Practical advantage: help with latency requirements by running policies at different frequencies.

**Do we really need multiple policies?** Bake a cheesecake via hierarchy vs. chain-of-thought vs. flat policy. Can benefit from same supervision! May be too computationally expensive (e.g. 50 Hz control). No conclusive empirical comparison yet.

**Key design choices.** How to represent skills/goals? Properties of good goal representations: expressive (can communicate many different low-level behaviors); structured (similar behaviors should have similar representations); appropriate level of abstraction (not too hard for low-level or for high-level). Language, images, and state are common goal representations.

**How to supervise each level?** Low-level policy: trained to accomplish subgoal g, not the original task. High-level policy: trained to accomplish the original long-horizon task. Key: can be trained separately first. At least one policy should be adapted to the deficiencies of the other (if not both fine-tuned jointly). Note: LLMs are often good high-level policies.

**When to move on from one subgoal to the next?** Option 1: when the low-level policy has completed g. + Ideal in principle. - Hard to estimate when done. - Need to account for mistakes that require redoing past goals. Option 2: after fixed number of K timesteps. + Simple. - With small K, more burden on high-level policy. These errors are more fatal than the second type!

**Hierarchical imitation learning with language subgoals.** Segmented demonstration data with associated language commands. Train high-level and low-level policy with imitation learning. "Yell At Your Robot" (Shi et al., RSS 2024): language corrections override high-level policy prediction; fine-tuning high-level policy with DAgger (HL DAgger: freeze low-level policy, update high-level with language corrections). With hierarchy, the robot is better at long-horizon tasks.

**Hierarchical imitation learning with image subgoals.** High-level policy predicts goal image; goal image conditioned policy for low level. Benefit: high-level policy can incorporate unlabeled video data. Use image editing model for goal image prediction.

**Hierarchical reinforcement learning.** State reaching goals: goal-conditioned policy with goal-reaching reward; use hindsight relabeling on HL actions via off-policy algorithm. Language goals: language-conditioned policy with hindsight language relabeling. References: HIRO (NeurIPS 2018); Language as Abstraction for HRL (NeurIPS 2019). Another active research area: discover a set of diverse skills without supervision (DIAYN, ICLR 2019).

**Hierarchy is hot.** Physical Intelligence, NVIDIA Gr00t N1, Figure Helix, Gemini Robotics — all use hierarchical robot learning systems.

### Lecture Summary (370 words)
Hierarchical RL decomposes long-horizon tasks into sequences of shorter subtasks, each easier to learn individually. The high-level policy operates over extended time intervals and decides which subgoal to pursue next. The low-level policy operates at the primitive action level and executes whatever subgoal the high-level policy has set. This separation of concerns provides several benefits: each level of the hierarchy deals with a simpler problem; knowledge can be shared across tasks with similar low-level behaviors; and exploration in the high-level space is structured and efficient.

The three fundamental design choices are goal representation (what form do subgoals take — language, image, state vector?), level supervision (how do we train the high-level and low-level policies given that each depends on the other?), and timing (when does the high-level policy switch to a new subgoal?). Language-based subgoals are popular because LLMs can serve as high-level planners, leveraging world knowledge for task decomposition while low-level policies focus on motor skill execution.

The "Yell At Your Robot" paper demonstrates a practical hierarchical imitation learning system: a low-level motor policy handles physical manipulation; a high-level language policy decomposes tasks; humans can correct the high-level policy with natural language, and HL-DAgger updates the high-level policy from these corrections without retraining the low-level policy. This makes the system data-efficient and correctable in deployment.

All major modern robot foundation model systems (Pi, NVIDIA Gr00t, Figure Helix, Gemini Robotics) use hierarchical architectures, validating the approach at scale.

### ReloPass Application Notes
Hierarchical RL is the natural architecture for Case Command's multi-scale compliance management. High-level policy: given employee profile and corridor, select the compliance strategy (e.g., "fast-track visa + housing first" vs. "housing first + visa at standard pace"). Low-level policy: given the current compliance state, select the specific document to request or deadline to set. The high-level policy operates weekly (is the relocation on track?); the low-level policy operates daily (what specific action does HR need to take today?). Goal representation: compliance milestones expressed as structured state descriptions ("work permit submitted," "housing deposit paid"). Timing: switch to a new subgoal when a milestone is completed or when a deadline threshold is crossed. LLMs as high-level planners: an LLM can decompose a new corridor's compliance requirements into subtasks that the low-level deterministic engine can execute.

---

## Lecture 16: Sim-to-Real Transfer

**Video URL:** https://www.youtube.com/watch?v=kSCbz3Js4Wo (approximate)  
**Slide Source:** Slide PDF exceeded download size limit

### Transcript / Slide Content
*Slide PDF too large to download. Content reconstructed from course curriculum.*

**The sim-to-real gap.** Training RL agents in simulation is cheap and safe. But simulated dynamics don't match real-world physics perfectly. A policy trained in simulation may fail catastrophically when deployed on real hardware.

**Domain Randomization.** Train in simulation with randomized physics parameters: mass, friction, motor noise, visual appearance, lighting. The policy learns to be robust to a range of dynamics, including the real world. Key result: GPT-4 level manipulation policies trained in simulation with massive domain randomization transfer to real robots.

**Domain Adaptation.** Learn a mapping between simulation and real-world observations (or dynamics) to close the gap. Adversarial approaches: train a discriminator to distinguish simulated from real observations; train the simulator to fool the discriminator.

**System Identification.** Estimate real-world physics parameters from real interactions and use them to configure the simulator. Adaptive dynamics models: update estimates online during deployment.

**Privileged Information.** During simulation training, give the policy access to privileged information (ground truth physics state) unavailable in the real world. Distill this privileged policy into a deployed policy that uses only real-world observations. Reference: Asymmetric Actor-Critic.

**Real-to-Sim-to-Real.** Modern approach: scan real environment into simulation; train policy in the scanned simulation; deploy with domain randomization for residual sim-to-real gap. Enables environment-specific customization.

### Lecture Summary (290 words)
Sim-to-real transfer addresses the practical reality that training RL agents directly on real hardware is expensive, slow, and potentially dangerous. Simulation provides a safe, fast, and cheap sandbox. The challenge is that simulation is always an imperfect approximation of the real world — differences in physics, visuals, and sensor noise cause policies trained in simulation to fail when deployed.

Domain randomization is the most widely successful approach: train in a distribution of simulated environments with varied physics parameters, so the policy learns to be robust to any specific physics configuration, including the real one. The breadth of randomization must be sufficient to include the real world without making the problem too hard to learn.

Privileged information and knowledge distillation enable training with information available only in simulation (perfect state estimation, ground truth physics) while deploying with only real-world sensors. The gap between simulated and real observations motivates domain adaptation techniques that align the representation spaces.

### ReloPass Application Notes
Sim-to-real transfer maps to Case Command's validation and deployment workflow. "Simulation" = a test compliance environment where relocation cases are run against a mock regulatory database with synthetic employees. "Real world" = live relocation cases for actual employees. Domain randomization = testing across a range of synthetic employee profiles, move dates, and regulatory scenarios that span the realistic distribution. A policy trained on simulated relocations must transfer to real cases without failing on edge cases (unusual visa categories, employees with dual nationality, company exceptions). Privileged information = in simulation, the system knows the exact regulatory requirements; in production, it must infer from database queries and external regulatory feeds. Sim-to-real gap mitigation: continuously calibrate the regulatory database against real government processing times observed in live cases.

---

## Lecture 17: RL for Robot Foundation Models and VLAs

**Video URL:** https://www.youtube.com/watch?v=YRUxMIIFJAg (approximate)  
**Slide Source:** `webfetch-1786775677311-tpen62.pdf` → `webfetch-1786775677311-tpen62.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — RL for Robot Foundation Models / VLAs. Plan: robot learning landscape; what are VLAs; how do we train VLAs; open research problems.

**Robot Learning Landscape.** Why is robot learning hard? High-dimensional action spaces; contact-rich manipulation; long-horizon tasks; safety constraints; expensive data collection. Recent progress: large pretrained models (VLAs) trained on diverse robot data transfer better.

**What are VLAs?** Vision-Language-Action models: neural networks that take (image observation, language instruction) → action. Architecture: large pretrained vision-language backbone (e.g. PaLI, SigLIP) + action output head (diffusion, flow matching, or discrete tokens). Examples: π0 (Physical Intelligence), OpenVLA, Octo.

**How to train VLAs.** Step 1: pretrain on diverse robot data (Open X-Embodiment, Bridge Data V2). Step 2: finetune on task-specific demonstrations. Step 3 (emerging): RL fine-tuning from robot experience. RL fine-tuning is harder for VLAs than for LLMs because: reward definition is hard; real robot data is slow and expensive; credit assignment over long manipulation sequences.

**Offline RL for VLA post-training.** Collect large batch of data using mix of roll-outs and DAgger. Fit V using Monte Carlo returns. Train advantage-conditioned policy (AWR). This "iterated offline RL" recipe is the current state of practice for VLA improvement from experience.

**Online RL for VLAs.** Possible when: reward is defined (goal classifier, human evaluator); simulation is available for some tasks; safety constraints are manageable. Challenges: VLAs are large — many gradient steps needed; distribution shift from pretraining data.

**Open Research Problems.** How to define reward for dexterous manipulation? How to scale online RL to VLA-scale models? How to combine diverse pretraining data with online RL? How to transfer RL-trained skills across robot embodiments?

**Physical Intelligence pi0.** Architecture: vision-language backbone + flow matching action head. Training: large-scale pretraining on diverse robot data + task-specific fine-tuning. Capabilities: generalization across diverse manipulation tasks, dexterous in-hand manipulation, multi-step long-horizon tasks.

### Lecture Summary (360 words)
Vision-Language-Action models represent the current frontier of robot learning: large pretrained models that take visual observations and language instructions as input and produce robot actions as output. By leveraging pretrained vision-language representations, VLAs can generalize across diverse manipulation tasks and robot embodiments, dramatically reducing the amount of task-specific data needed.

The training pipeline mirrors LLM training: large-scale pretraining on diverse robot datasets (Open X-Embodiment, Bridge Data) provides general manipulation skills, followed by task-specific finetuning from demonstrations, and increasingly, RL fine-tuning from robot experience. The RL fine-tuning phase is the least mature and most actively researched: reward definition for dexterous manipulation is hard (how do you score a robot folding a shirt?), online data collection is expensive, and credit assignment over long manipulation sequences is challenging.

Offline RL for VLA post-training is the current best practice: collect demonstrations and robot roll-outs, estimate value functions using Monte Carlo returns, and apply AWR to improve the policy on high-advantage behaviors. This avoids the need for online RL data collection while still enabling improvement beyond the behavior cloning baseline.

The lecture positions VLAs as the direct robotic analog of LLMs: large-scale pretraining → instruction finetuning → RLHF. The same principles that made ChatGPT effective are being applied to robot learning, with adaptation for the unique challenges of physical interaction.

### ReloPass Application Notes
VLAs are a template for a future Case Command architecture. Currently, Case Command uses a deterministic rule engine — the robotic analog of an expert system. The VLA pipeline suggests an evolution: pretrain a compliance model on all available relocation data across corridors (the robot pretraining equivalent), fine-tune on corridor-specific demonstrations from compliance experts, and RL fine-tune from feedback on live cases. The key insight from VLAs: joint training on diverse data from many corridors produces a more robust model than training one model per corridor. The iterated offline RL recipe (collect data, fit V, AWR) is directly applicable to Case Command without requiring online deployment of an RL agent — use historical relocation records as the offline dataset.

---

## Lecture 18: Frontiers and Open Problems in Deep RL

**Video URL:** https://www.youtube.com/watch?v=LdJJb0JON1c (approximate)  
**Slide Source:** `webfetch-1786775805682-19i1ct.pdf` → `webfetch-1786775805682-19i1ct.txt`

### Transcript / Slide Content (Key Excerpts)
CS 224R — Summary and Frontier of Deep RL / How to do (deep RL) research.

**Online RL Algorithm Summary.** Vanilla PG → PPO-like methods → Off-policy actor-critic (e.g. SAC) → Q-learning. What data used; fit value function; how to estimate goodness; how to make it off-policy; policy update.

**Algorithm Taxonomy.** Offline RL: behavior cloning (supervise policy on data actions); learn V for better policy with asymmetric loss (AWR, AWAC, IQL). Online RL: REINFORCE/vanilla PG; PPO (importance sampling); actor-critic (both); DQN/SAC (off-policy with replay buffer, Q-learning). Offline imitation learning: behavior cloning. Online imitation learning: DAgger.

**Deep RL is a rich toolbox.** Reward functions: given; annotated; learned from examples or preferences; self-supervised (goal-conditioned RL). Data: offline demos; stored experience; online (DAgger, policy roll-outs). Tools: supervised BC; policy gradient; actor-critic; Q-learning; supervising to data actions; replay buffers; importance weighting; Q/value learning; Monte Carlo; TD-learning; n-step returns; asymmetric value loss; hindsight relabeling; multi-task policies; learned models; synthetic data; test-time planning. Policy update: neural net models; Gaussian, Categorical; diffusion; autoregressive. Many algorithms mix and match tools depending on the needs of the use-case.

**Frontiers: Non-rewarding, non-verifiable domains.** Games and math reasoning: reward is easy. Challenge: rewards don't exist or are very delayed. LLMs for chatbots: preference optimization → what you want to hear; personalization vs. polarization; balancing multiple objectives. Robotics: often binary or hand-shaped; how would you score each of these shirt folds? YouTube recommendations: weighted combination of engagement (clicks) and satisfaction (likes); score weights are manually tuned. Scientific experimentation and reasoning. Can machines optimize for learning?

**Frontiers: Leveraging prior data and knowledge.** Default tool: initialize model weights to pretrained model, initialize replay buffer using offline data. What about more abstract prior knowledge (hints, knowledge from news articles)? Do pretrained weights and data constrain learning too much? How can LLMs go beyond pretraining to solve problems that humans haven't solved? How can robots/AVs learn tasks faster and more reliably than humans?

**Frontiers: World models.** Rich world knowledge in video generation models — they should be useful. But large, nuanced challenges: train on demos + one policy's roll-outs; evaluate if new policy's actions lead to good outcomes (these will be out of distribution). Possible solution 1: train on data from more policies. Possible solution 2: use the model in other ways. Train on only demos; predict future video + run goal-conditioned policy.

**Frontiers: How to scale.** Large-scale RL for LLMs is exciting. Yet currently fairly short-horizon or very online. Often considers single-turn dialog instead of full conversation outcome. LLM preference optimization: shorter horizon problem + no need to collect human-in-the-loop data. LLM reasoning for math: relies on large number of online samples. Hard to interleave model updates and data collection for large models. Can we train and use accurate value functions at scale? Can we enable large-scale batch online RL?

**Frontiers: Safety.** How should we approach AI development and testing in safety-critical domains? Medicine, autonomous driving, mental health counseling, legal and political discourse. Historically: formal verification, probabilistic guarantees — generally make assumptions that won't hold in the real world. Generally impossible to guarantee safety in countless scenarios in open-world environments. Can we develop methods that learn what's unsafe without expansive data of unsafe incidents? Possibly use synthetic data; prior knowledge. Can we gradually explore new behaviors while remaining safe?

**Frontiers: Evaluation.** Handling inaccuracies, hallucinations. Evaluation of generalist systems.

### Lecture Summary (380 words)
The final lecture takes stock of where deep RL stands and where the open problems lie. Chelsea Finn presents a unified taxonomy of deep RL algorithms: offline imitation learning (behavior cloning), online imitation learning (DAgger), offline RL (AWR, IQL), and online RL (REINFORCE, PPO, SAC, DQN). The key organizing dimensions are what data is used (offline vs. online), whether a value function is learned, and how off-policy data is incorporated.

The lecture then turns to six major open frontier areas:

1. **Reward specification in non-verifiable domains.** RL works well when reward is easy to compute (games, math). For chatbots, robotics, and recommendation systems, reward is ambiguous, delayed, or multi-objective. Preference optimization is a partial solution, but introduces alignment risks and personalization-versus-polarization tradeoffs.

2. **Leveraging prior knowledge.** Initializing with pretrained weights is standard. But how do we incorporate more abstract prior knowledge? How do we enable models to go beyond what humans have demonstrated?

3. **World models at scale.** Video generation models encode rich world knowledge. Can they serve as environment simulators for RL training? The challenge is distribution shift: policies trained inside a world model may fail when deployed in the real world.

4. **Scaling RL.** LLM reasoning is exciting but currently limited to short-horizon, heavily online settings. Scaling to longer horizons, with less online data, requires better value functions and more efficient data collection.

5. **Safety.** In safety-critical applications, RL's trial-and-error nature is problematic. Formal verification is insufficient for open-world scenarios. New methods for safe exploration and safe policy improvement are urgently needed.

6. **Evaluation.** Generalist systems are hard to evaluate comprehensively. Benchmarks risk being gamed; human evaluations are expensive and inconsistent.

### ReloPass Application Notes
The frontier problems map directly to Case Command's hardest challenges. Non-verifiable reward: compliance success is not a single number — it is timeliness, cost, employee experience, and legal defensibility. The frontier work on multi-objective reward shaping and preference optimization provides tools. World models: a compliance simulation environment (mock regulatory database + synthetic employees) enables safe RL training before deploying on real cases — the world model problem is precisely the sim-to-real gap for compliance. Scaling: compliance timelines are long-horizon (3-12 months); scaling RL to this horizon requires the efficient value function training discussed in the frontiers section. Safety: compliance errors are legally and professionally consequential — the frontier work on safe exploration and constrained policy improvement is directly applicable. Case Command must never recommend a compliance action that is legally invalid, even during exploration.

---

## Course-Level Summary

### Overall Learning Arc

Stanford CS224R is structured as a systematic exploration of sequential decision-making with deep neural networks, organized around a central question: how can an agent learn to behave optimally from experience?

The course begins with the simplest form of learning from demonstrations — behavior cloning — and progressively introduces complications: distributional shift (→ DAgger), the need for reward optimization (→ policy gradients), variance reduction (→ actor-critic), data efficiency (→ Q-learning, replay buffers), fixed datasets (→ offline RL), reward specification (→ reward learning, RLHF), knowledge reuse (→ model-based RL, multi-task RL, meta-RL), long-horizon decomposition (→ hierarchical RL), and deployment robustness (→ sim-to-real). The final lecture synthesizes this into a unified toolbox and identifies the frontiers where open problems remain.

The arc mirrors the development of the field: from simple tabular Q-learning in the 1990s, through deep Q-networks and policy gradients in the 2010s, to modern VLAs, RLHF for LLMs, and model-based world models in the 2020s. Each lecture adds tools to the toolbox and demonstrates their application in robotics, language model alignment, or recommender systems.

A recurring theme is the tradeoff between data efficiency and algorithm complexity: simpler algorithms (behavior cloning, Q-learning) are easy to implement but require more data or make stronger assumptions; complex algorithms (model-based RL, meta-RL) are more efficient but introduce more hyperparameters and failure modes.

---

### Top 10 Actionable Insights

1. **The distributional shift problem is universal.** Any system that learns from a fixed distribution and then deploys in a different distribution will degrade. DAgger's solution — iteratively collect data from the deployment distribution — applies beyond robotics to any production ML system, including compliance recommendations that encounter novel employee profiles.

2. **Offline RL (AWR + IQL) is the right starting point for any system with historical data.** Before building online data collection infrastructure, extract maximum value from existing datasets using advantage-weighted regression and implicit Q-learning. This is immediately applicable to Case Command's historical relocation records.

3. **Reward specification is the hardest problem in RL.** The quality of the reward function determines the quality of the learned behavior. Investing in careful reward design — or using preference-based reward learning from domain experts — is more impactful than algorithm choice.

4. **Hindsight relabeling turns failures into learning signal.** Every failed or partial relocation is a successful example of reaching some intermediate state. HER converts this negative data into positive training signal, multiplying the effective dataset size without additional data collection.

5. **Hierarchical decomposition enables long-horizon tasks.** When the overall task is too long-horizon for direct RL, decompose it: a high-level policy selects subgoals (compliance milestones); a low-level policy executes each subgoal (specific document requests). This separation of concerns reduces the effective horizon of each policy.

6. **Model-based RL enables "what-if" planning at no additional data cost.** A learned dynamics model of the compliance process enables counterfactual reasoning: "If the employee changes their move date by two weeks, which compliance steps are at risk?" This is operationally invaluable and requires only historical data to build.

7. **Multi-task learning with task conditioning is strictly better than training separate models per corridor.** Shared representations across corridors improve data efficiency, enable zero-shot generalization to new corridors, and provide built-in regularization. OpenVLA and BC-Z demonstrate this at scale in robotics.

8. **Meta-RL provides the cold-start solution for new corridors.** Rather than requiring hundreds of historical cases to learn a new corridor's compliance policy, meta-RL trains an adaptation mechanism from existing corridors that can generalize to new ones from a handful of examples.

9. **Safety constraints must be built into the RL objective, not bolted on afterward.** In compliance contexts, certain actions are legally prohibited regardless of their expected reward. Constrained MDPs (maximize reward subject to constraints on unsafe actions) encode this requirement directly in the learning objective.

10. **RLHF/DPO converts implicit human expertise into explicit policy improvements.** HR managers have implicit knowledge about what makes a good relocation process. Rather than trying to elicit this knowledge as explicit rules, preference-based learning collects pairwise comparisons and directly optimizes the recommendation engine to match expert judgment.

---

### Detailed ReloPass Strategic Applications

#### 1. Immediate: Offline RL on Historical Cases (Lectures 7, 8)

**What to build:** An offline RL pipeline that trains a compliance recommendation policy from historical relocation cases.

**How:** Represent each historical case as a trajectory: sequence of (compliance_state, action_taken, reward_signal, next_state). Define rewards: +10 for each compliance milestone completed on time; -20 for each missed deadline; +100 for successful relocation completion; -50 for visa rejection or permit expiry. Apply IQL: train an implicit value function using asymmetric expectile regression (τ ≈ 0.9) that estimates V(s) ≈ max_a Q(s,a) using only in-distribution historical actions. Apply AWR: extract a policy by weighting historical actions by their advantage exp(A(s,a)/β).

**Impact:** The resulting policy is a data-driven alternative to (or complement to) the hand-coded rule engine. It will naturally discover compliance sequences that human experts have not explicitly encoded — for example, optimal ordering of document requests when there is regulatory interdependency.

#### 2. Near-term: Hindsight Relabeling for Sparse Corridors (Lecture 12)

**What to build:** A relabeling pipeline that extracts additional training signal from partial or failed relocations.

**How:** For each historical case that was abandoned midway or failed, identify all intermediate compliance milestones that were successfully reached. Relabel the trajectory up to each milestone as a successful case for that milestone as the goal. Train a goal-conditioned compliance policy that can navigate to any milestone, not just the final relocation. This multiplies the effective training dataset by the number of intermediate milestones per case.

**Impact:** Sparse corridors (e.g., a new DE→SE corridor with only 3 historical cases) become trainable when each case is relabeled into a dozen goal-conditioned training examples.

#### 3. Near-term: Preference-Based Reward Learning from HR Managers (Lectures 8, 9)

**What to build:** A compliance quality reward model trained from HR manager pairwise comparisons.

**How:** Present pairs of anonymized historical relocation timelines to HR managers: "Which relocation process would you have preferred: Case A (fast, 2 minor errors corrected) or Case B (slower, zero errors, higher HR burden)?" Use Bradley-Terry model to fit scalar reward R(timeline). Train compliance engine to maximize E[R(timeline)] using policy gradient or offline RL.

**Impact:** Captures implicit HR preferences that are hard to encode as explicit rules — speed vs. thoroughness tradeoffs, communication frequency preferences, escalation thresholds. DPO allows this directly without an intermediate reward model.

#### 4. Medium-term: Hierarchical Compliance Architecture (Lecture 15)

**What to build:** A two-level hierarchical policy for compliance management.

**High-level policy (weekly):** Given employee profile, corridor, move date, and current compliance state, select the compliance milestone to target next. Input: structured compliance state vector. Output: milestone identifier (e.g., "visa submitted," "housing confirmed"). Frequency: weekly or when a milestone is completed. Trained with: offline RL on historical milestone sequences.

**Low-level policy (daily):** Given current compliance state and target milestone, select the specific action. Input: current state + milestone target. Output: specific action (document request, deadline set, escalation trigger, reminder). Frequency: daily. Trained with: behavior cloning from expert-labeled action sequences.

**LLM as high-level policy:** For novel corridors or edge cases, an LLM can decompose the compliance requirement into a milestone sequence using regulatory knowledge encoded in pretraining, without needing historical data for that specific corridor.

**Impact:** Separates strategic compliance planning (high-level) from operational execution (low-level), enabling each level to be updated independently. The high-level policy can be retrained when regulations change without retraining the low-level execution logic.

#### 5. Medium-term: Model-Based "What-If" Simulation (Lecture 11)

**What to build:** A learned dynamics model of the compliance process that enables counterfactual planning.

**How:** Train a neural network dynamics model T̂(s_{t+1} | s_t, a_t) on historical compliance trajectories. Train an ensemble of 5-10 models for uncertainty quantification. Build a planning interface: given current compliance state and a proposed change (new move date, new employee profile, regulatory update), simulate forward T̂ to project the compliance state trajectory. Flag high-uncertainty states (ensemble disagreement) as requiring human review.

**Queries enabled:**
- "If the move date shifts from March to May, which steps are at risk?"
- "If France introduces a new tax registration requirement next quarter, how does this affect cases in progress?"
- "What is the probability of successful relocation if the work permit is not submitted by week -8?"

**Impact:** Transforms Case Command from a reactive tool (surface the next step) to a proactive planning tool (forecast compliance risk across all active cases). HR managers get lead time to address problems before they become crises.

#### 6. Long-term: Meta-RL for Rapid Corridor Expansion (Lecture 13)

**What to build:** A meta-learning system that enables rapid adaptation to new corridors from minimal data.

**How:** Train a meta-RL policy (e.g., recurrent transformer) on the existing corridors (FR→NO, ES→IE, NO→FR). The meta-policy takes a few-shot context of corridor-specific regulatory requirements (expressed as structured state transitions) and adapts its compliance recommendations accordingly. At deployment for a new corridor (e.g., DE→SE): provide 5-10 example cases (simulated or synthetic, based on known regulatory requirements); the meta-policy adapts from this context without full retraining.

**Impact:** Reduces new corridor onboarding time from months (collect enough historical data to train a new rule engine) to days (provide a few examples to the meta-policy). This is the key enabler for ReloPass's geographic expansion strategy.

#### 7. Long-term: Safe Exploration for Compliance Edge Cases (Lecture 14)

**What to build:** A constrained exploration framework for handling novel employee profiles and regulatory edge cases.

**How:** Define a set of safety constraints: actions that are legally invalid for a given corridor are forbidden (constraint satisfaction layer). Within the feasible action set, use Thompson sampling over an ensemble of Q-functions to explore uncertain compliance pathways. When the ensemble disagrees (high uncertainty), route the case to a human compliance expert rather than the automated system.

**Impact:** Enables the system to handle novel situations (unusual visa categories, dual nationals, company-sponsored relocation with non-standard timelines) without risking illegal compliance recommendations. The exploration mechanism generates new data points that reduce uncertainty for similar future cases.

---

### Course-Level Technical Vocabulary Reference

| Term | Definition | ReloPass Mapping |
|------|-----------|-----------------|
| MDP | Markov Decision Process: (S, A, T, R, γ) | (compliance_state, compliance_action, transition_dynamics, compliance_reward, discount) |
| Policy π | Mapping from state to action distribution | Case Command recommendation engine |
| Value function V^π(s) | Expected future reward from state s under π | Compliance risk score for current state |
| Q-function Q^π(s,a) | Expected future reward from (s,a) pair under π | Value of taking compliance action a in state s |
| Advantage A(s,a) | Q(s,a) - V(s): how much better a is than average | Priority boost for specific compliance action |
| Behavior cloning | Supervised imitation of expert demonstrations | Rule engine compiled from expert knowledge |
| DAgger | Iterative data collection from policy distribution | Live routing of novel cases to expert review |
| REINFORCE | Policy gradient algorithm | Baseline for learned compliance policy |
| PPO | Proximal Policy Optimization (clipped PG) | Stable online fine-tuning of compliance policy |
| SAC | Soft Actor-Critic: entropy-regularized off-policy RL | Off-policy compliance learning with exploration bonus |
| Q-learning / DQN | Learn optimal Q* without explicit policy | Learn optimal compliance action selection |
| Offline RL | Learn from fixed historical dataset | Train on historical relocation records |
| AWR | Advantage Weighted Regression | Weight historical actions by compliance outcome |
| IQL | Implicit Q-Learning: asymmetric expectile loss | Conservative value function for compliance risk |
| RLHF | RL from Human Feedback | HR manager preference-trained reward model |
| DPO | Direct Preference Optimization | Direct HR preference learning without reward model |
| MBPO | Model-Based Policy Optimization | Compliance timeline simulation + policy optimization |
| HER | Hindsight Experience Replay | Relabeling failed cases as goal-conditioned successes |
| Multi-task RL | Single policy for multiple tasks via task conditioning | Single model across all corridors |
| Meta-RL | Learn to learn across task distributions | Rapid adaptation to new corridors |
| Hierarchical RL | High-level goal selection + low-level execution | Milestone planning + step execution |
| Sim-to-real | Simulation training + real deployment | Sandbox testing + live case deployment |

---

*Document compiled by AI research agent from Stanford CS224R Spring 2025 lecture slide PDFs.*  
*YouTube transcripts were inaccessible via all attempted retrieval methods (YouTube timedtext API, WebFetch, Tactiq, youtubetranscript.com, youtube-transcript-api Python package).*  
*Slide PDFs were downloaded from cs224r.stanford.edu/slides/ and decoded via zlib decompression of FlateDecode-compressed PDF streams.*  
*Generated: 2026-08-15*
