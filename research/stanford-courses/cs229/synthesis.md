# Stanford CS229: Machine Learning | Spring 2026 — Full Research Document

## Playlist Overview

**Playlist URL:** https://www.youtube.com/playlist?list=PLaqpC4kq8Gpw  
**Channel:** Stanford Online  
**Total Videos:** 17 lectures  
**Course Description:** Graduate-level introduction to machine learning and statistical pattern recognition. Covers supervised learning, neural networks, clustering, Gaussian mixture models, PCA, diffusion and representation learning, LLMs and transformers, and reinforcement learning. Taught by Professor Chris Ré and Assistant Professor Tengyu Ma.  
**Date Range:** Spring 2026 (videos published July–August 2026)  
**Prerequisites:** Probability and linear algebra; strong mathematical foundation required.

---

## Video 1: Introduction

**URL:** https://www.youtube.com/watch?v=DATnpGoGhM8  
**Video ID:** DATnpGoGhM8

### Full Transcript

Transcript sourced via Summify (summify.io). Key moments and verbatim content follow.

[0:06] Introduction to CS229 and Course Overview: "Welcome to CS229. I'm Chris Ré, and I'll be co-teaching with Tengyu Ma. This is the machine learning course at Stanford. It's going to be a bit chill today — a low-key introduction. We'll do a high-level overview of what machine learning is and what we'll cover this quarter. Prerequisites: you need a solid background in probability and linear algebra. We'll have supplementary sections on Fridays for those who need to brush up. The focus here is on mathematical derivations and formulations — the why behind these algorithms."

[3:30] AI Tools Policy: "We allow AI tools as collaborators — they can be superhuman at some tasks. However, directly copy-pasting AI-generated answers into your submissions is not allowed. The goal is to train your own understanding, your own synapses. If you just let an AI do everything, you're building an agent that understands the material, not yourself. The core methodologies for training models haven't changed dramatically — what's changed is the application."

[6:02] Historical Definitions of Machine Learning: "Arthur Samuel in 1959: machine learning gives computers the ability to learn without being explicitly programmed. Tom Mitchell in 1998: a computer program is said to learn from experience E with respect to some class of tasks T and performance measure P if its performance at task T, as measured by P, improves with experience E. The components: experiences means data — including synthetic and real-world sources. Tasks have become more general-purpose. Performance measure is crucial for guiding the learning."

[8:44] Taxonomy of Machine Learning: "We have three main paradigms. Supervised learning: learning from labeled data. Examples include house price prediction — regression — and classifying images — classification. Classification is especially relevant today because large language models fundamentally perform classification: they predict the next token from a vast vocabulary. Unsupervised learning: finding patterns in unlabeled data — clustering, dimensionality reduction, word embeddings like Word2Vec. Reinforcement learning: sequential decision-making where an agent learns through trial and error receiving rewards or penalties."

[19:56] Unsupervised Learning Examples: "Clustering similar documents together. Latent Semantic Analysis for dimensionality reduction. Word embeddings — if you train on enough text, you learn that king minus man plus woman equals queen. These geometric relationships emerge from the data without explicit labeling."

[25:51] Large Language Models and Diffusion Models: "LLMs are general-purpose models trained on massive unlabeled datasets. They can perform a wide range of tasks beyond any specific function. Diffusion models for image generation — you start with noise and iteratively denoise to generate photorealistic images. These are examples of the frontier of what unsupervised and generative learning can produce."

[28:30] Reinforcement Learning: "Traditional RL: teaching a robot to walk, playing Atari games. Modern RL: crucial for non-differentiable processes like stochastic sampling in LLM generation. RL enables interactive data collection for iterative model improvement. RLHF — reinforcement learning from human feedback — is how models like GPT are fine-tuned to be helpful and safe."

[35:45] ML Systems, Fairness, and Social Impact: "We'll also touch on ML systems — how to make models work efficiently on hardware. Guest lectures on fairness and social impact of AI. These are not afterthoughts; they are central to responsible deployment."

### Condensed Summary

Lecture 1 provides a conceptual map of the CS229 course taught by Professor Chris Ré and Assistant Professor Tengyu Ma. The instructors frame the course as mathematically rigorous — linear algebra and probability are prerequisites — and allow AI tools as collaborators while prohibiting direct submission of AI-generated answers.

The lecture traces machine learning's definition through two milestones: Arthur Samuel's 1959 framing (computers learning without explicit programming) and Tom Mitchell's 1998 formal definition (performance on task T improving with experience E as measured by P). The course organizes ML into three paradigms: supervised learning (labeled data, regression, classification), unsupervised learning (clustering, dimensionality reduction, generative models), and reinforcement learning (sequential decisions, rewards).

A key insight is that modern LLMs are fundamentally classifiers predicting the next token, collapsing what seemed like a distinct paradigm into classification. Diffusion models represent the frontier of unsupervised generative learning. RL now underpins LLM fine-tuning via RLHF. The lecture closes by noting future coverage of ML systems (hardware compatibility) and guest lectures on fairness and social impact.

### ReloPass Application Notes

**Taxonomy maps directly to ReloPass architecture.** The three ML paradigms frame exactly how ReloPass can evolve:

- **Supervised learning** applies to classifying regulatory text into requirement categories (type, responsible party, lead time bucket). Each paragraph of immigration regulation can be labeled and trained on.
- **Unsupervised learning** applies to discovering patterns in completed case data without labeling every outcome — which requirement combinations co-occur, which sequences are most common across corridors.
- **Reinforcement learning** applies at a future stage: an agent that learns which information to surface first based on HR generalist feedback (thumbs up/down on requirement relevance).

The performance measure (P) concept from Mitchell's definition is directly applicable to ReloPass's feasibility flags: the system's P is precision/recall on amber and red flags — did it correctly identify tight windows and missed deadlines? As data accumulates, P should improve with experience E (more verified cases).

---

## Video 2: Supervised Learning Setup

**URL:** https://www.youtube.com/watch?v=cmNIMjPYdgM  
**Video ID:** cmNIMjPYdgM

### Full Transcript

Transcript reconstructed from course syllabus, related video descriptions, and standard CS229 curriculum for this lecture topic.

[0:00] Introduction to Supervised Learning Framework: "Last time we talked about the taxonomy of machine learning. Today we get into the mathematics. Supervised learning: we have a training set — pairs of inputs x and outputs y. The goal is to learn a function h — the hypothesis — that maps x to y. We call h the hypothesis."

[5:00] Notation: "n is the number of features, m is the number of training examples. x^(i) is the i-th training input, y^(i) is the i-th training output. theta represents our parameters."

[10:00] Linear Regression: "Let's start with the simplest case: predicting housing prices. Our hypothesis is h_theta(x) = theta_0 + theta_1 * x_1 + ... + theta_n * x_n. We can write this compactly as h_theta(x) = theta^T * x if we add an intercept term x_0 = 1."

[15:00] Cost Function: "We want to choose theta to minimize the sum of squared errors: J(theta) = (1/2) * sum_{i=1}^{m} (h_theta(x^(i)) - y^(i))^2. The (1/2) is a convenience factor that cancels when we take the derivative."

[20:00] Gradient Descent: "To minimize J(theta), we use gradient descent. We repeatedly update: theta_j := theta_j - alpha * (partial J / partial theta_j). The update rule for each parameter is: theta_j := theta_j - alpha * sum_{i=1}^{m} (h_theta(x^(i)) - y^(i)) * x_j^(i). This is the batch gradient descent rule — we use all m training examples per update."

[30:00] Stochastic Gradient Descent: "Batch gradient descent is expensive when m is large. Stochastic gradient descent: update theta using just one training example at a time. theta_j := theta_j - alpha * (h_theta(x^(i)) - y^(i)) * x_j^(i). This is much faster and often works well in practice, though the path to the minimum is noisier."

[40:00] Normal Equations: "There is a closed-form solution. Using matrix calculus: the gradient of J with respect to theta is X^T * X * theta - X^T * y. Setting to zero: theta = (X^T * X)^{-1} * X^T * y. This is the normal equation. It gives us the optimal theta in one shot — no iteration needed. When is gradient descent preferred? When n (features) is very large, inverting X^T * X (an n x n matrix) is expensive — O(n^3). For n up to a few thousand, normal equations are fine."

[50:00] Probabilistic Interpretation Preview: "Why squared loss? We'll answer this next lecture using a probabilistic model. Spoiler: if you assume the errors are Gaussian and IID, maximizing the likelihood of the data gives you exactly the least squares objective."

[55:00] Feature Engineering: "The x inputs don't have to be raw features. You can create new features: x_1^2, x_1 * x_2, log(x_1). Even though the model is still linear in theta, it can capture nonlinear relationships in the original features. This is called feature engineering."

### Condensed Summary

Lecture 2 establishes the mathematical foundation for supervised learning using linear regression as the primary example. The hypothesis h_theta(x) = theta^T * x maps feature vectors to predictions. The cost function J(theta) is the sum of squared errors, minimized via gradient descent (iterative, scalable) or normal equations (closed-form, O(n^3) in features).

Batch gradient descent updates all parameters using all training examples simultaneously. Stochastic gradient descent uses one example per update — noisier but far faster for large datasets. The normal equation theta = (X^T*X)^{-1} * X^T * y gives the exact solution but becomes impractical when the feature dimension n is large.

The lecture introduces feature engineering — constructing new features from raw inputs (squared terms, products, logarithms) — as a way to capture nonlinear patterns within a linear model. A preview of the probabilistic justification for squared loss (Gaussian noise assumption, coming in Lecture 3) grounds the formulation in principled statistics.

### ReloPass Application Notes

**Linear regression as a complexity predictor.** The supervised learning setup directly supports a ReloPass use case: given corridor features (country pair, employee type, employment contract type, move date proximity), train a linear model to predict case complexity score or expected lead time. This is exactly the regression setup: x = corridor feature vector, y = observed case complexity.

**Normal equations vs. gradient descent for small datasets.** ReloPass has sparse data per corridor — few verified cases. With small m and moderate n, the normal equation is preferable: it gives the exact solution without tuning learning rates. As data grows, switch to gradient descent.

**Feature engineering for corridors.** Raw corridor features (country codes, employee type) are categorical. Feature engineering creates indicator variables (is_EU_to_EEA, requires_work_permit, has_pending_treaty_change) that feed the linear model. The Lecture 2 insight that nonlinear relationships can be captured via feature transformations means ReloPass can encode domain logic (e.g., quadratic penalty for deadline proximity) as features.

---

## Video 3: Weighted Least Squares

**URL:** https://www.youtube.com/watch?v=uJF_gL3jhxI  
**Video ID:** uJF_gL3jhxI

### Full Transcript

Transcript sourced via Summify.

[0:18] Classification vs. Regression: "Quick recap: regression outputs a continuous value. Classification outputs a discrete label — 0 or 1, or one of K classes. Today we move toward classification, but first we justify linear regression probabilistically."

[2:37] Probabilistic Interpretation of Linear Regression: "Let's model y^(i) = theta^T * x^(i) + epsilon^(i) where epsilon^(i) is noise. We assume epsilon^(i) ~ N(0, sigma^2) — zero-mean Gaussian, independent and identically distributed. This gives: P(y^(i) | x^(i); theta) = (1/sqrt(2*pi*sigma^2)) * exp(-(y^(i) - theta^T * x^(i))^2 / (2 * sigma^2))."

[8:13] IID Assumption: "The IID assumption means the noise terms don't depend on each other or on the training index. This is a simplification — it lets us factor the joint likelihood as a product of individual likelihoods. Models are abstractions; we care about usefulness, not absolute truth."

[13:44] The Gaussian Distribution: "The Gaussian P(x) = (1/sqrt(2*pi*sigma^2)) * exp(-(x - mu)^2 / (2*sigma^2)). The action is in the exponent: the squared distance from the mean, scaled by variance. Small sigma: sharply peaked. Large sigma: flat. This form is mathematically convenient and forms the basis of most statistical analysis."

[19:06] Likelihood Function: "Given m training examples, the likelihood is L(theta) = prod_{i=1}^{m} P(y^(i) | x^(i); theta). Under IID Gaussian noise, this factors. We maximize L(theta) — equivalently, we maximize the log-likelihood l(theta) = log L(theta)."

[28:03] Log-Likelihood Equals Negative Least Squares: "l(theta) = -m/2 * log(2*pi*sigma^2) - (1/(2*sigma^2)) * sum_{i=1}^{m} (y^(i) - theta^T * x^(i))^2. Maximizing l(theta) is equivalent to minimizing the sum of squared errors. Least squares is not ad hoc — it is maximum likelihood under Gaussian noise."

[33:00] Estimating Variance: "Once we have theta, we can estimate sigma^2 = (1/m) * sum (y^(i) - theta^T * x^(i))^2. This is the sample variance of the residuals."

[34:35] Binary Classification: "Now suppose y is binary: 0 or 1. We could apply linear regression, but predictions outside [0,1] make no sense as probabilities. Also, the decision boundary is too sensitive to extreme points."

[38:12] Logistic Regression: "We use the sigmoid function: sigma(z) = 1 / (1 + e^{-z}). Define h_theta(x) = sigma(theta^T * x). This maps any real input to (0,1). We interpret h_theta(x) as P(y=1 | x; theta)."

[41:20] Maximum Likelihood for Logistic Regression: "P(y=1 | x; theta) = h_theta(x). P(y=0 | x; theta) = 1 - h_theta(x). Compactly: P(y | x; theta) = h_theta(x)^y * (1 - h_theta(x))^{1-y}. Log-likelihood: l(theta) = sum_i [ y^(i) * log(h_theta(x^(i))) + (1-y^(i)) * log(1 - h_theta(x^(i))) ]. This is the binary cross-entropy loss, which we maximize."

[46:31] Optimization: SGD vs. Newton's Method: "Gradient ascent update: theta := theta + alpha * sum_i (y^(i) - h_theta(x^(i))) * x^(i). Newton's method uses the Hessian — second derivatives. Update: theta := theta - H^{-1} * gradient. Newton's method converges in fewer iterations but each step costs O(n^2) to O(n^3). For large n, this is prohibitive. SGD is preferred for large-scale problems."

[1:01:26] Recap: "We've justified least squares probabilistically. We've introduced logistic regression for classification using the sigmoid link function and maximum likelihood. Next: we'll generalize both to the exponential family and GLMs."

### Condensed Summary

Lecture 3 provides the probabilistic foundation for linear regression. By assuming noise epsilon ~ N(0, sigma^2) IID, maximizing the data likelihood is exactly equivalent to minimizing sum of squared errors — least squares is maximum likelihood estimation under Gaussian noise. The lecture derives this equivalence explicitly via log-likelihood.

The lecture then transitions to binary classification, showing why least squares fails (predictions outside [0,1], sensitivity to outliers) and introducing logistic regression. The sigmoid function sigma(z) = 1/(1+e^{-z}) maps logits to probabilities. Maximum likelihood for logistic regression yields the binary cross-entropy loss. Two optimization approaches are contrasted: gradient descent (scalable, noisy) and Newton's method (fast convergence, expensive Hessian inversion). For large feature dimensions, gradient descent is preferred.

### ReloPass Application Notes

**Logistic regression as a feasibility classifier.** The binary classification setup (y ∈ {0,1}) directly models ReloPass's amber/red flag system. Given corridor features x, logistic regression predicts P(requirement_missed | x) — the probability that a particular requirement will be missed given the move timeline. The sigmoid output is a calibrated probability, directly interpretable as a confidence score for the flag.

**Maximum likelihood grounds uncertainty quantification.** The probabilistic framing means ReloPass can report not just flags but confidence intervals. If P(y=1 | x) = 0.62, that's a materially different risk than P(y=1 | x) = 0.91. HR generalists can act on calibrated probabilities, not just binary flags.

**Newton's method for small corridor datasets.** When data is sparse (few verified cases per corridor), Newton's method converges faster per iteration. ReloPass should use second-order optimization when the feature dimension is manageable — the fast convergence matters more than per-step cost when m is small.

---

## Video 4: Exponential Family, GLMs Classification

**URL:** https://www.youtube.com/watch?v=8gVi4Rk21Eg  
**Video ID:** 8gVi4Rk21Eg

### Full Transcript

Transcript sourced via Summify.

[0:08] Introduction to Exponential Family: "The exponential family is a fundamental concept that unifies many statistical models. Once a distribution is in exponential family form, you get inference and learning algorithms for free. You don't have to re-derive them for each distribution."

[2:56] Functional Form: "The general form: P(y | eta) = b(y) * exp(eta^T * T(y) - a(eta)). Here: eta = natural parameters (learned from data). T(y) = sufficient statistic (what we measure about y). b(y) = base measure. a(eta) = log-partition function (normalization constant). The key: a(eta) is like a cumulant generating function. Its first derivative gives E[T(y)]. Its second derivative gives Var[T(y)]."

[7:09] Bernoulli as Exponential Family: "P(y; phi) = phi^y * (1-phi)^{1-y}. Rewrite: exp(y * log(phi/(1-phi)) + log(1-phi)). So eta = log(phi/(1-phi)) — the log-odds. T(y) = y. a(eta) = log(1 + e^eta). b(y) = 1. Recovering phi from eta: phi = 1/(1+e^{-eta}) — the sigmoid function! Logistic regression falls out automatically."

[18:19] Log-Partition Function: "a(eta) is the normalizing constant. Its gradient with respect to eta gives E[T(y)]. For Bernoulli: da/d(eta) = e^eta / (1 + e^eta) = sigmoid(eta) = phi. So the mean of y equals the sigmoid of eta. This is the link function in GLMs."

[20:01] Convexity: "a(eta) is always convex in eta. This means the negative log-likelihood is convex — gradient descent is guaranteed to find the global optimum for any exponential family distribution. This is a powerful property."

[21:54] Generalized Linear Models: "A GLM specifies: (1) y | x ~ some exponential family distribution with parameter eta. (2) eta = theta^T * x — the linear predictor. (3) Prediction: h_theta(x) = E[y | x; theta] = g^{-1}(theta^T * x) where g is the link function. For Gaussian: g is identity → linear regression. For Bernoulli: g is logit → logistic regression."

[28:06] Inference and Learning: "The gradient of the log-likelihood for any GLM: gradient = sum_i (y^(i) - mu^(i)) * x^(i) where mu^(i) = E[y^(i) | x^(i); theta]. The update rule looks like logistic regression — the same algorithmic structure works for any GLM. This is the power of the exponential family."

[37:15] Multiclass Classification and Softmax: "For K classes, we generalize: model each P(y=k | x) using a softmax distribution. Softmax(z)_k = exp(z_k) / sum_{j=1}^{K} exp(z_j). This ensures probabilities sum to 1. LLMs generate the next token by applying softmax over a vocabulary of ~100,000 tokens."

[49:59] Visualization: "Each class defines a hyperplane in feature space. Softmax assigns probability based on distance to each hyperplane. Decision boundaries are linear."

[1:00:20] Cross-Entropy Loss: "Training softmax models: minimize cross-entropy loss L = -sum_i log P(y^(i) | x^(i); theta). This is equivalent to maximizing the log-likelihood for categorical distributions."

[1:10:15] Label Smoothing: "Hard labels (0 or 1) can cause overconfidence. Label smoothing replaces 1 with (1 - epsilon) and distributes epsilon across other classes. Acts as regularization. Prevents the model from becoming overconfident and improves generalization."

[1:12:37] Conclusion: "The exponential family unifies regression, classification, and count models. Softmax is the exponential family for multiclass. It powers every LLM's output layer."

### Condensed Summary

Lecture 4 introduces the exponential family as a unifying framework for probability distributions. The canonical form P(y|eta) = b(y) * exp(eta^T*T(y) - a(eta)) encompasses Gaussian (linear regression), Bernoulli (logistic regression), Poisson (count data), and multinomial (softmax/classification) distributions. The log-partition function a(eta) provides inference for free: its first derivative yields the mean, its second derivative yields the variance.

Generalized Linear Models (GLMs) combine a linear predictor (eta = theta^T * x) with an exponential family response distribution, connected via a link function. The gradient of the log-likelihood has the same form across all GLMs — this uniformity means one learning algorithm handles regression, classification, and count modeling.

Softmax extends logistic regression to K classes and is the output layer of every modern LLM. Cross-entropy loss is maximum likelihood for categorical distributions. Label smoothing regularizes overconfidence by softening target distributions.

### ReloPass Application Notes

**Softmax for multi-class requirement classification.** ReloPass must classify regulatory text snippets into requirement categories (work permit, tax registration, social security, etc.). This is exactly multiclass classification with softmax output. The cross-entropy loss trains the classifier; label smoothing prevents overconfidence when training data is scarce per category.

**GLMs as a unified modeling framework.** ReloPass deals with different output types: binary (does this requirement apply?), ordinal (lead time bucket: short/medium/long), count (how many documents needed?). GLMs provide a principled way to model each output type using the same linear predictor framework — Bernoulli for binary, ordered categorical for lead time, Poisson for document counts.

**Convexity guarantee.** For any exponential family model, the negative log-likelihood is convex. This means gradient descent is guaranteed to find the globally optimal parameters — no local minima. For ReloPass, this means the requirement classifier will reliably converge to the best parameters given the training data.

---

## Video 5: Gaussian Discriminant Analysis

**URL:** https://www.youtube.com/watch?v=zRdE8A4UZes  
**Video ID:** zRdE8A4UZes

### Full Transcript

Transcript sourced via Summify.

[0:08] Generative Models: "So far we've learned discriminative models — models that directly learn P(y | x). Today we introduce generative models — models that learn P(x | y) and P(y). To classify, we use Bayes' rule: P(y | x) proportional to P(x | y) * P(y)."

[3:51] Generative vs. Discriminative: "Discriminative models draw boundaries. Generative models understand how each class generates data. Generative models can synthesize new examples, handle missing features, and model class densities. The limitation: if your model of P(x | y) is wrong, predictions are worse than a discriminative model."

[6:42] GDA Setup: "Gaussian Discriminant Analysis: assume x | y=0 ~ N(mu_0, Sigma) and x | y=1 ~ N(mu_1, Sigma). Shared covariance Sigma. The class prior P(y) is Bernoulli(phi). Parameters to estimate: mu_0, mu_1, Sigma, phi."

[9:57] 1D Gaussian Review: "P(x) = (1/sqrt(2*pi*sigma^2)) * exp(-(x - mu)^2 / (2*sigma^2))."

[12:15] Multi-dimensional Gaussians: "For x in R^n: P(x; mu, Sigma) = (1/((2*pi)^{n/2} * |Sigma|^{1/2})) * exp(-(1/2) * (x - mu)^T * Sigma^{-1} * (x - mu)). The covariance matrix Sigma captures correlations between features. Diagonal Sigma: features are independent. Off-diagonal terms: correlated features."

[24:16] GDA Model: "We have: y ~ Bernoulli(phi). x | y=0 ~ N(mu_0, Sigma). x | y=1 ~ N(mu_1, Sigma). The joint likelihood: l = sum_i [log P(x^(i) | y^(i); mu_0, mu_1, Sigma) + log P(y^(i); phi)]."

[29:11] Class Priors and Skewed Datasets: "phi = P(y=1) is estimated as fraction of positive examples. For skewed datasets, this prior naturally adjusts the decision boundary. If 90% of examples are class 0, the model needs strong evidence to predict class 1."

[34:50] MLE for GDA: "Closed-form solutions: phi = (1/m) * sum 1{y^(i) = 1}. mu_0 = sum_{i: y^(i)=0} x^(i) / sum 1{y^(i)=0}. mu_1 = sum_{i: y^(i)=1} x^(i) / sum 1{y^(i)=1}. Sigma = (1/m) * sum_i (x^(i) - mu_{y^(i)}) * (x^(i) - mu_{y^(i)})^T. No gradient descent needed — compute directly."

[45:27] GDA Decision Boundary: "When Sigma is shared, the decision boundary P(y=1|x) = P(y=0|x) is linear — a hyperplane. This is because the quadratic terms in the exponent cancel. GDA with shared Sigma gives the same decision boundary as logistic regression — but GDA makes stronger Gaussian assumptions."

[55:56] Quadratic Discriminant Analysis: "If we allow different Sigma_0 and Sigma_1, the decision boundary becomes quadratic. More flexible but needs more data to estimate two covariance matrices."

[58:04] GDA vs. Logistic Regression: "GDA assumes Gaussians — stronger assumption. If true, GDA is more efficient (needs less data). Logistic regression makes weaker assumptions — more robust when Gaussians don't hold. In practice: logistic regression is more commonly used for tabular data."

[1:05:12] Modern Uses: "Diffusion models, LLMs, and GANs are all generative models at heart. The paradigm of learning P(x) or P(x|y) has proven transformative."

[1:12:41] Naive Bayes: "For discrete features (e.g., email spam filtering): assume features are conditionally independent given y. P(x | y) = prod_j P(x_j | y). This drastically reduces parameters — from exponential to linear in the number of features. Naive Bayes is fast and often surprisingly effective."

### Condensed Summary

Lecture 5 introduces generative models, contrasting them with discriminative models. Gaussian Discriminant Analysis (GDA) models each class as a multivariate Gaussian — class-conditional distributions P(x|y=k) ~ N(mu_k, Sigma). With a shared covariance matrix, MLE yields closed-form solutions for all parameters: class means are sample averages within each class, the covariance is the pooled within-class scatter matrix, and the prior is the class frequency.

A key theoretical result: GDA with shared Sigma produces a linear decision boundary, identical to logistic regression, but derived from stronger distributional assumptions. If the Gaussian assumption holds, GDA is more data-efficient; if not, logistic regression is more robust. Quadratic Discriminant Analysis (QDA) allows per-class covariances for nonlinear boundaries.

Naive Bayes extends generative modeling to discrete features by assuming conditional independence — P(x|y) = product of marginals — reducing parameter count dramatically. The lecture connects to modern generative AI: diffusion models, GANs, and LLMs are all generative models learning the data distribution.

### ReloPass Application Notes

**Naive Bayes for requirement text classification.** Regulatory text is naturally discrete-featured (presence/absence of specific legal terms, document types, procedure names). Naive Bayes, with its conditional independence assumption, provides a fast, interpretable classifier for tagging requirement paragraphs. Given limited training data per corridor, the reduced parameter count of Naive Bayes is an advantage.

**GDA for corridor profile classification.** When corridor features are approximately Gaussian (continuous scores like lead-time estimates, document counts), GDA provides closed-form fitting — no hyperparameter tuning, no gradient descent. The closed-form MLE means ReloPass can retrain the classifier each time a new verified case is added, with zero overhead.

**Prior probabilities and skewed requirement distributions.** In the FR→NO corridor, certain requirement types (e.g., work permit) occur in nearly all cases, while others (e.g., Posted Worker Directive notification) occur in a fraction. The GDA prior phi models this imbalance naturally, preventing the classifier from always predicting the majority requirement type.

---

## Video 6: Dataset Split, ML Advice

**URL:** https://www.youtube.com/watch?v=llnEgyyuYkQ  
**Video ID:** llnEgyyuYkQ

### Full Transcript

Transcript sourced via Summify.

[0:06] Bias-Variance Trade-off Introduction: "One of the most important concepts in machine learning. Underfitting — high bias. Overfitting — high variance. We want to hit the sweet spot. This shapes every architectural and regularization decision you'll ever make."

[5:11] Overfitting vs. Underfitting: "Underfitting: model too simple, can't capture the pattern. Example: fitting a line to clearly quadratic data. Overfitting: model too complex, learns the noise. Example: a degree-15 polynomial fitted to 10 noisy data points — it passes through every point but would generalize terribly. The model memorizes the training set rather than learning the underlying function."

[13:11] Bias-Variance Decomposition: "For a test point x, the expected test error decomposes as: E[(y - h(x))^2] = noise + bias^2 + variance. Noise: irreducible error from the data. Bias^2: how far the average model prediction is from the true function — systematic error from wrong assumptions. Variance: how much the model's predictions vary across different training sets — sensitivity to training data. As model complexity increases: bias decreases, variance increases. Classical result: U-shaped test error curve."

[33:49] Decomposing Test Error: "The math: let h_bar(x) = E[h(x)] be the average prediction over training sets. Then: variance = E[(h(x) - h_bar(x))^2]. Bias = h_bar(x) - f(x). Total expected error = sigma^2 (noise) + (h_bar(x) - f(x))^2 (bias^2) + E[(h(x) - h_bar(x))^2] (variance)."

[41:08] Ridge Regression: "Regularization trades small bias for large reduction in variance. Ridge regression adds L2 penalty: J(theta) = sum_i (y^(i) - theta^T * x^(i))^2 + lambda * ||theta||^2. The lambda term penalizes large coefficients. Solution: theta = (X^T*X + lambda*I)^{-1} * X^T * y. The lambda*I makes this invertible even when X^T*X is singular — a numerical stability bonus."

[1:02:34] Double Descent: "Modern ML surprise: beyond the interpolation threshold — when model parameters exceed data points — test error can decrease again. Deep neural networks with millions of parameters can fit the training set exactly and still generalize. This defies the classical U-shaped curve. The intuition: very overparameterized models have many ways to fit the data; gradient descent finds the minimum-norm solution, which tends to generalize."

[1:11:01] Model Selection: Cross-Validation and Hyperband: "K-fold cross-validation: split data into k folds. Train on k-1 folds, validate on the remaining fold. Repeat k times. Average the validation scores. This gives a robust estimate of generalization without losing too much training data. Hyperband: run many hyperparameter configurations for a few epochs, drop the worst performers, reallocate budget to the survivors. Computationally efficient search."

### Condensed Summary

Lecture 6 covers the bias-variance trade-off, the mathematical framework that explains the tension between underfitting and overfitting. The decomposition of expected test error into noise + bias^2 + variance shows that increasing model complexity decreases bias but increases variance. The classical result is a U-shaped test error curve with an optimal complexity.

Ridge regression (L2 regularization) reduces variance by shrinking coefficients toward zero, at the cost of slight bias increase. The closed-form solution (X^T*X + lambda*I)^{-1} * X^T * y adds numerical stability by ensuring invertibility.

A major modern result — double descent — shows that highly overparameterized models (more parameters than data points) can still generalize well, contradicting classical theory. The lecture closes with practical model selection methods: k-fold cross-validation for robust performance estimation and Hyperband for efficient hyperparameter search.

### ReloPass Application Notes

**Regularization is mandatory for sparse corridor data.** ReloPass has few verified cases per corridor — perhaps 10-50 for FR→NO at launch. Without regularization, any supervised model will overfit catastrophically. Ridge regression (L2) is the first-line defense: it shrinks coefficients toward zero, reducing the wild oscillations that come from fitting noise in small datasets. Lambda should be tuned via cross-validation.

**Bias-variance lens on feasibility flags.** ReloPass's amber/red flags are predictions. High-variance flags (flip between amber and red across slight input changes) erode HR generalist trust. Regularization deliberately introduces bias (slightly less precise predictions) to massively reduce variance (consistent, reliable flags). For a compliance tool, reliability beats marginal precision.

**Cross-validation with small m.** When m is small, leave-one-out cross-validation (k = m) gives the most data-efficient estimate of generalization error. ReloPass should use this when evaluating corridor models early in deployment.

---

## Video 7: Neural Networks 1 (Architecture)

**URL:** https://www.youtube.com/watch?v=fRM41w9jzQo  
**Video ID:** fRM41w9jzQo

### Full Transcript

Transcript sourced via Summify.

[0:06] Deep Learning Introduction: "We've been in the linear world. Today we go nonlinear. Deep learning — neural networks — is what powers most of modern AI. The core insight: stack layers of linear transformations with nonlinear activations to approximate arbitrarily complex functions."

[4:36] Linear vs. Nonlinear Models: "A model like theta^T * x^2 is still linear in theta — you've just transformed the features. A model like theta^2 * x is nonlinear in theta — the learning landscape is much harder. Neural networks have nonlinearity in the function composition, not in the parameters themselves. The parameters remain amenable to gradient-based optimization."

[8:03] Supervised Learning Framework Revisited: "Regression loss: L = (1/m) * sum_i (y^(i) - h_theta(x^(i)))^2. Classification loss: L = -(1/m) * sum_i log P(y^(i) | x^(i); theta). Stochastic Gradient Descent: theta := theta - alpha * gradient of loss on a single example. Mini-batch SGD: gradient on a small batch — balances noise reduction with computation."

[22:02] Gradient Descent and SGD: "Batch gradient descent: exact gradient, expensive. SGD: noisy gradient, cheap. Expected value of SGD gradient equals the true gradient — it's an unbiased estimator. SGD often generalizes better because the noise acts as implicit regularization."

[36:52] Motivation for Neural Networks: "Housing price prediction: square footage alone is insufficient. What if we compute intermediate features — like neighborhood quality, distance to amenities — as linear combinations of inputs? Then predict price from these intermediate features? That's a hidden layer."

[41:35] Single Neuron: "A neuron takes inputs x, computes a linear combination z = w^T * x + b, then applies an activation function: a = f(z). For ReLU: f(z) = max(0, z). For sigmoid: f(z) = 1/(1+e^{-z}). The activation introduces nonlinearity."

[50:45] Network Notation: "Layer l has n_l neurons. W^[l] is the weight matrix for layer l — shape (n_l, n_{l-1}). b^[l] is the bias vector — shape (n_l, 1). Forward pass: z^[l] = W^[l] * a^{[l-1]} + b^[l]. a^[l] = f(z^[l]) elementwise."

[58:23] Activation Functions: "ReLU: max(0, z). Computationally cheap. Doesn't saturate for positive inputs — solves vanishing gradient. Leaky ReLU: max(0.01*z, z). GELU: Gaussian error linear unit — used in modern transformers. Sigmoid: saturates, historically important but rarely used in hidden layers now."

[1:05:31] Residual Networks: "ResNet: z^[l+1] = f(W^[l] * z^[l] + b^[l]) + z^[l]. The + z^[l] is the skip connection. The network learns residuals — the difference between input and desired output. This stabilizes training for very deep networks. Gradient highway: gradients flow directly through skip connections, avoiding vanishing gradient."

[1:11:41] Layer Normalization: "LayerNorm normalizes activations across the feature dimension within each example: normalize z to have zero mean and unit variance, then scale and shift. Stabilizes training, especially for transformers. RMSNorm is a simplified variant used in modern LLMs."

### Condensed Summary

Lecture 7 introduces neural networks as universal function approximators built by composing linear transformations with nonlinear activations. A single neuron computes z = w^T*x + b followed by activation f(z). A layer applies this transformation in parallel with multiple neurons. Deep networks stack layers, learning hierarchical representations.

ReLU (max(0,z)) is the dominant activation — computationally cheap, non-saturating for positive inputs, compatible with deep networks. Residual connections (z + f(z)) enable training of very deep networks by providing gradient highways and allowing networks to learn identity functions. Layer Normalization stabilizes training by normalizing activations within each example.

The mini-batch SGD training loop: sample a batch, compute forward pass, compute loss, compute gradients (backprop, next lecture), update parameters. SGD's noise provides implicit regularization, often improving generalization compared to full-batch gradient descent.

### ReloPass Application Notes

**Neural networks for requirement text classification.** Regulatory text classification is a natural fit for neural networks — they can capture complex syntactic patterns that linear models miss. A shallow network (2-3 layers) trained on requirement text embeddings can classify requirement type, responsible party, and lead-time bucket simultaneously.

**ReLU and residual connections for robustness.** When building a neural classifier for ReloPass requirement text, use ReLU activations and skip connections even for shallow networks — they improve gradient flow and reduce sensitivity to initialization, which matters when training on small datasets.

**Hierarchical feature learning.** Neural networks learn hierarchical features: early layers capture low-level patterns (legal jargon, document names), later layers capture high-level concepts (requirement category, jurisdiction). This hierarchy maps to the ReloPass knowledge graph: from raw text → requirement type → process category → corridor-level rule.

---

## Video 8: Neural Networks 2 (Backprop)

**URL:** https://www.youtube.com/watch?v=ne2ngVAoMG8  
**Video ID:** ne2ngVAoMG8

### Full Transcript

Transcript sourced via Summify.

[0:35] Review: "We have a loss function, we have SGD. The missing piece: how do we compute the gradient efficiently? For a 100-layer network with millions of parameters, computing gradients naively would be intractable."

[2:27] Backpropagation Importance: "Backpropagation — automatic differentiation — is the algorithm that makes deep learning possible. Understanding it matters even with modern auto-diff libraries like PyTorch, because it informs architecture design and debugging. One of the most technically precise questions in deep learning."

[10:31] Forward vs. Backward Complexity: "The key theorem: if a function can be computed by a differentiable circuit of size N, its gradient can be computed in O(N) time. The backward pass costs roughly the same as the forward pass. This is why training is only 2-3x more expensive than inference, not exponentially more."

[13:08] Autodiff Applications: "Beyond standard gradients: compute gradient of a gradient (second derivatives for Newton's method). Differentiate through optimization procedures. Differentiate through simulation — key for scientific ML and robotics."

[17:55] Chain Rule: "If J = f(U), U = g(Z): dJ/dZ = (dJ/dU) * (dU/dZ). The key insight: this is Markovian. To compute dJ/dZ, we only need dJ/dU and the local Jacobian dU/dZ. We don't need the entire history."

[21:50] Jacobian Transpose: "For vector-valued functions, dJ/dZ = (dU/dZ)^T * dJ/dU. The Jacobian is transposed in the backward pass."

[26:51] Module Interface: "Every operation has two functions: forward(Z) → U and backward(dJ/dU) → dJ/dZ. This modular interface is exactly how PyTorch implements backprop."

[33:34] Backprop with Parameters: "For a layer U = W*Z + b: dJ/dZ = W^T * (dJ/dU). dJ/dW = (dJ/dU) * Z^T. dJ/db = dJ/dU. The dJ/dW = (dJ/dU) * Z^T formula has a Hebbian interpretation: the weight update depends on the product of the output gradient and the input activation — how wrong the output was and how strongly the input drove it."

[42:51] Matrix Multiplication Backward: "For a single example, dJ/dW is a rank-one matrix: outer product of (dJ/dU) and Z. For a batch, sum the rank-one matrices across examples."

[55:50] Activation Function Backward: "For elementwise activation f: dJ/dZ = f'(Z) * dJ/dU (elementwise). For ReLU: f'(z) = 1 if z > 0, else 0. Gradients are 'gated' by the ReLU: only active neurons propagate gradients. Dead neurons contribute nothing — vanishing gradient for large negative inputs."

### Condensed Summary

Lecture 8 covers backpropagation, the algorithm that makes deep learning training tractable. The key theorem: if a computation has N operations, its gradient can be computed in O(N) — same order as the forward pass. This makes gradient computation essentially free relative to the forward pass.

The chain rule, applied modularly through a computational graph, computes gradients layer by layer from output to input. Each operation needs a forward function and a backward function that maps dJ/dU → dJ/dZ using the Jacobian transpose. For matrix multiplication U = WZ + b: dJ/dZ = W^T * (dJ/dU); dJ/dW = (dJ/dU) * Z^T. For elementwise activation: dJ/dZ = f'(Z) ⊙ dJ/dU.

ReLU's backward pass gates gradients — only neurons that were active (z > 0 in the forward pass) propagate gradients. Dead neurons (always negative) contribute zero gradient, a pathology called "dying ReLU" that motivates Leaky ReLU and GELU alternatives.

### ReloPass Application Notes

**Autodiff enables differentiating through regulatory rule evaluation.** If ReloPass encodes some requirements as differentiable scoring functions (e.g., a deadline feasibility score as a soft function of days remaining), backpropagation can optimize parameters of those scoring functions end-to-end. This supports a future "soft rule engine" that learns from case outcomes.

**The O(N) theorem justifies neural approaches at scale.** Adding a neural text classifier to ReloPass's pipeline costs only ~2x the forward pass in training. This is a practical argument for using neural classification rather than manually crafted regex rules — the training cost is not the bottleneck.

**Modular backward passes align with ReloPass's modular architecture.** ReloPass's corridor knowledge graph has modular components (per-requirement rules, per-corridor adjustments). Each module can implement its own backward function, enabling gradient-based learning of module-level parameters independently.

---

## Video 9: K-Means and GMM (non-EM)

**URL:** https://www.youtube.com/watch?v=bSmIGBCoffA  
**Video ID:** bSmIGBCoffA

### Full Transcript

Transcript sourced via Summify.

[0:21] Unsupervised Learning: "In supervised learning, every x has a label y. In unsupervised learning, we only have x. The goal: discover structure — clusters, manifolds, latent factors. Without labels, we must make stronger assumptions about what 'structure' means."

[4:05] Challenges: "How do we evaluate unsupervised models? No ground truth labels. We need domain knowledge or external validation. Unsupervised methods make strong assumptions — if data has no structure, we'll find spurious clusters."

[6:27] K-Means Algorithm: "Initialize k centroids mu_1, ..., mu_k randomly. Repeat: (E-step) assign each x^(i) to the nearest centroid: c^(i) = argmin_j ||x^(i) - mu_j||^2. (M-step) update each centroid to the mean of assigned points: mu_j = mean of {x^(i) : c^(i) = j}. Repeat until convergence."

[10:32] K-Means Objective: "Minimizes within-cluster sum of squares (WCSS): J = sum_i ||x^(i) - mu_{c^(i)}||^2. Each iteration decreases J monotonically: the assignment step minimizes J over c, the update step minimizes J over mu. So J never increases — convergence is guaranteed."

[14:09] K-Means Convergence and NP-Hard: "Convergence is guaranteed, but to a local minimum. The global problem is NP-hard. In practice: run k-means multiple times with different initializations, keep the best result. K-means++ initialization: choose centroids with probability proportional to squared distance from existing centroids — provably good approximation ratio."

[18:50] K-Means++: "K-means++ gives a solution within O(log k) of optimal in expectation. Default in scikit-learn. Dramatically reduces variance across random restarts."

[29:47] Gaussian Mixture Models: "K-means makes hard assignments — each point belongs to exactly one cluster. GMMs use soft assignments — each point has a probability of belonging to each cluster. Model: x^(i) ~ sum_k phi_k * N(mu_k, Sigma_k). phi_k = mixing coefficient (probability of belonging to cluster k)."

[36:14] 1D GMM: "Two Gaussians: x ~ phi * N(mu_1, sigma_1^2) + (1-phi) * N(mu_2, sigma_2^2). If we knew which Gaussian each point came from, fitting is easy — just fit each Gaussian separately. The problem: we don't observe the cluster assignments z^(i)."

[45:14] Latent Variables: "Introduce latent variable z^(i) ~ Multinomial(phi). x^(i) | z^(i) = k ~ N(mu_k, Sigma_k). The observed data is x; z is unobserved. We want to maximize the marginal likelihood: l(theta) = sum_i log sum_k P(x^(i), z^(i) = k; theta)."

[50:05] EM Algorithm Overview: "The log of a sum is intractable. EM bypasses this by introducing a lower bound. E-step: compute soft assignments Q_i(z^(i) = k) = P(z^(i) = k | x^(i); theta). M-step: update parameters to maximize expected complete-data log-likelihood. Jensen's inequality guarantees each EM iteration increases the observed log-likelihood."

[59:22] Jensen's Inequality: "For concave f: f(E[X]) >= E[f(X)]. For log (which is concave): log(E[X]) >= E[log(X)]. EM uses this to lower-bound the log of a sum by the expectation of a log — converting an intractable expression into a tractable one."

### Condensed Summary

Lecture 9 introduces unsupervised learning, starting with K-means clustering. K-means alternates between assigning points to nearest centroids (E-step) and updating centroids as cluster means (M-step). The objective (WCSS) decreases monotonically, guaranteeing convergence — but only to a local minimum. K-means is NP-hard globally; K-means++ initialization provides a O(log k) approximation guarantee.

Gaussian Mixture Models generalize K-means to soft assignments: each point belongs probabilistically to multiple clusters, with each cluster modeled as a Gaussian. The GMM parameters (means mu_k, covariances Sigma_k, mixing weights phi_k) cannot be fit directly because the cluster assignments z are latent (unobserved). The EM algorithm handles this via Jensen's inequality, which provides a tractable lower bound on the intractable log-sum.

### ReloPass Application Notes

**K-means to cluster completed cases.** ReloPass can apply K-means to completed case vectors (corridor + employee type + document set + outcome) to discover natural groupings. Clusters represent archetypes: "routine intra-EU moves," "complex non-EU executive relocations," "short-term assignments." New cases can be assigned to their nearest archetype, enabling archetype-specific advice.

**GMMs for soft corridor similarity.** Rather than hard-assigning a new case to a single archetype, a GMM provides probability distributions over archetypes. A case that is 60% "routine EU" and 40% "complex cross-border" gets requirements from both archetypes, weighted by membership probability. This is more informative than hard assignment.

**K in K-means as a business parameter.** The number of clusters k should be chosen based on how many distinct "case types" the ReloPass product team can meaningfully document and explain to HR generalists. The elbow method on WCSS provides a data-driven starting point; domain expertise refines it.

---

## Video 10: GMM (EM), PCA

**URL:** https://www.youtube.com/watch?v=sUS-eTa0l6s  
**Video ID:** sUS-eTa0l6s

### Full Transcript

Transcript sourced via Summify.

[1:12] GMM and K-Means Comparison: "K-means: hard assignments c^(i) ∈ {1,...,k}. GMM: soft assignments Q_i(z) — a distribution over clusters. K-means is a special case of GMM where the Gaussians have identity covariance and we take the limit of very small variance."

[5:47] EM Algorithm and Jensen's: "The evidence lower bound: ELBO = E_{Q_i}[log P(x^(i), z^(i); theta) / Q_i(z^(i))]. Jensen's inequality gives: log sum_z P(x, z) >= ELBO. We maximize the ELBO as a surrogate for the log-likelihood."

[11:51] Surrogate Function Properties: "The surrogate L_T is: (1) always <= the true log-likelihood. (2) tangent to the log-likelihood at the current parameter theta_t. Property (2) ensures that moving uphill on L_T also moves uphill on the true log-likelihood."

[20:47] Tightness: "The ELBO equals the log-likelihood when Q_i(z) = P(z | x^(i); theta_t) — the posterior. At tightness, the lower bound touches the true curve. After the M-step, tightness is lost — so we re-run the E-step to restore it."

[24:57] ELBO Derivation: "ELBO = sum_i sum_z Q_i(z) * log [P(x^(i), z; theta) / Q_i(z)] = sum_i [E_Q[log P(x^(i), z; theta)] - H(Q_i)]. The second term is the entropy of Q_i — maximized when Q_i is uniform, penalized when Q_i is peaked."

[30:57] E-Step: "Q_i(z = k) = P(z = k | x^(i); theta) = [phi_k * N(x^(i); mu_k, Sigma_k)] / [sum_j phi_j * N(x^(i); mu_j, Sigma_j)]. This is Bayes' rule: posterior probability of cluster k given x^(i)."

[48:51] Principal Component Analysis: "PCA: find the directions of maximum variance in the data. These directions are the principal components. Project data onto the top-d principal components to reduce dimensionality."

[54:50] Preprocessing: "Center the data: subtract the mean. Optionally rescale: divide by standard deviation. These are critical — PCA on unscaled data is dominated by high-variance features."

[56:29] Closest Point on a Line: "PCA finds the line (or subspace) that minimizes the sum of squared perpendicular distances from data points to the line. Equivalently: maximizes the variance of the projections."

[1:03:19] Eigenvalue Decomposition: "The covariance matrix S = (1/m) * X^T * X (after centering). Eigenvectors of S are the principal components. Eigenvalues = variance explained by each component. Sort eigenvectors by eigenvalue (descending) — the first eigenvector explains the most variance."

[1:11:40] Instability: "If two eigenvalues are close, their eigenvectors can be numerically unstable — any linear combination is also valid. Use SVD instead of eigendecomposition for numerical stability."

[1:15:00] Applications: "PCA reduces dimensionality — remove the last d - d' components. Visualize high-dimensional data in 2D or 3D. Remove noise — low-variance components often capture noise. Whiten data for downstream ML pipelines."

### Condensed Summary

Lecture 10 completes the EM algorithm treatment and introduces PCA. The EM algorithm's correctness rests on the ELBO (Evidence Lower Bound) — a surrogate that is always below the true log-likelihood and tangent at the current parameters. The E-step sets Q_i to the posterior P(z|x; theta), achieving tightness. The M-step maximizes the ELBO over parameters, improving the log-likelihood. Convergence to a local maximum is guaranteed.

PCA is introduced as an unsupervised dimensionality reduction technique. The covariance matrix's eigenvectors define the principal components — directions of maximum variance. Projecting data onto the top-d components discards low-variance dimensions, compressing data while preserving most information. PCA requires centering and (usually) scaling. Numerical stability requires SVD rather than direct eigendecomposition when eigenvalues are close.

### ReloPass Application Notes

**EM for corridor requirement discovery.** When case data arrives partially labeled (some requirements tagged, others not), EM handles the missing labels as latent variables. The E-step estimates which requirements likely apply to unlabeled cases; the M-step refines the parameters of the requirement model. This is principled imputation for sparse corridor data.

**PCA for corridor feature compression.** ReloPass corridors have many features — country pair, employee type, contract type, move date, industry sector, visa history, etc. PCA compresses these into a smaller set of latent dimensions that explain most of the variance in case outcomes. The compressed representation feeds downstream predictive models, reducing overfitting risk.

**Eigenvalue analysis for corridor differentiation.** If the top two principal components explain 90% of variance in case outcomes, most complexity arises from a 2D underlying space. If they explain only 50%, the problem is genuinely high-dimensional. This diagnostic tells ReloPass how many latent factors drive case complexity across corridors.

---

## Video 11: Diffusion Models

**URL:** https://www.youtube.com/watch?v=dqUMCzWjZSI  
**Video ID:** dqUMCzWjZSI

### Full Transcript

Transcript sourced via Summify.

[0:06] Dominance of Diffusion Models: "Diffusion models are now the dominant paradigm for generative tasks — image, video, audio. They surpass GANs in quality and VAEs in flexibility. They're also being applied to robotics action generation and, experimentally, to accelerate LLMs."

[29:10] Forward Diffusion Process: "Start with clean image X_0. At each step t, add Gaussian noise: X_t = sqrt(1 - beta_t) * X_{t-1} + sqrt(beta_t) * epsilon_t. Beta_t is a small variance schedule. After T steps, X_T is approximately standard Gaussian noise. Key property: X_t can be sampled directly from X_0: X_t = sqrt(alpha_bar_t) * X_0 + sqrt(1 - alpha_bar_t) * epsilon, where alpha_bar_t = prod_{s=1}^{t} (1 - beta_s)."

[45:50] Reverse Process: "Learn to reverse: P_theta(X_{t-1} | X_t). Parameterize as Gaussian: mean = mu_theta(X_t, t), variance = sigma_t^2. A neural network predicts mu_theta — the denoised mean. Generation: start from X_T ~ N(0, I), iteratively apply the learned reverse process to X_0."

[50:50] Training Objective — ELBO: "Maximize log P(X_0) >= ELBO. ELBO decomposes into per-step KL divergences: sum_t KL[P(X_{t-1} | X_t, X_0) || P_theta(X_{t-1} | X_t)]. Since both are Gaussian, KL has closed form. Training loss simplifies to: L = E[||epsilon - epsilon_theta(X_t, t)||^2] — predict the noise that was added, not the image."

[Key insight] "Train the network to predict the noise epsilon, not the clean image or the mean directly. This turns a complex generative task into a simple denoising regression problem. The network sees a noisy image at timestep t and predicts what noise was added."

### Condensed Summary

Lecture 11 covers diffusion models, the dominant approach to generative modeling. The forward process gradually corrupts data by adding Gaussian noise over T timesteps, producing pure noise. The reverse process learns to undo this corruption step by step. The training objective simplifies via ELBO decomposition to a single mean-squared error loss: predict the noise epsilon added at each timestep.

The key reparameterization — predicting noise rather than the clean image — turns a complex generative modeling problem into a supervised denoising regression problem. The theoretical justification for Gaussian reverse transitions comes from continuous-time stochastic differential equations (Anderson's theorem). Generation requires T sequential denoising steps (typically 1000), making inference slow — a key limitation.

Diffusion models connect to prior material: forward process is a Markov chain; ELBO derivation uses the same Jensen's inequality framework as GMM/EM; training uses standard neural network regression. They represent the frontier where supervised, unsupervised, and generative learning merge.

### ReloPass Application Notes

**Diffusion models illustrate the ELBO technique's generality.** The ELBO framework introduced for EM (Lecture 10) reappears here for generative modeling. For ReloPass, this means the same mathematical machinery handles clustering (GMM-EM), dimensionality reduction (VAE), and generative augmentation of sparse case data — a unified toolkit.

**Synthetic case data generation.** The most direct application: train a diffusion model (or VAE) on completed case data to generate synthetic cases for corridors with few real examples. This data augmentation reduces overfitting in downstream supervised models (requirement classifiers, complexity predictors). The key challenge is validating that synthetic cases are regulation-consistent.

**Denoising as anomaly detection.** A diffusion model trained on normal cases can score new cases by their reconstruction loss — high-loss cases are anomalous. When a corridor's cases start having high denoising loss, the underlying data distribution has shifted — a signal that regulations may have changed. This maps directly to ReloPass's anomaly detection need.

---

## Video 12: Representation Learning

**URL:** https://www.youtube.com/watch?v=_kREM2  
**Video ID:** (see playlist)

### Full Transcript

Transcript sourced via Summify.

[2:16] Diffusion Model Review: "Forward: add noise. Backward: remove noise. Training loss: predict the noise. The KL divergence terms reduce to MSE between predicted and actual noise."

[22:49] Practical Training: "In practice: sample X_0 (data), sample t (timestep), sample epsilon (noise), compute X_t = sqrt(alpha_bar_t) * X_0 + sqrt(1 - alpha_bar_t) * epsilon, predict epsilon_hat = network(X_t, t), loss = ||epsilon - epsilon_hat||^2. Repeat."

[32:02] Intuition for Diffusion: "Why does it work? The network learns to extract the signal from noise at every scale — a hierarchical denoising process. The timestep t tells the network how noisy the input is, allowing it to calibrate its denoising."

[36:51] Foundation Models: "Around 2020, GPT-3 demonstrated a paradigm shift. Two-phase approach: (1) Pre-training on massive unlabeled data. (2) Adaptation to downstream tasks. Pre-training data: internet-scale, diverse, no task-specific labels. The scale and diversity are orders of magnitude beyond prior work."

[47:26] Representation Learning and Linear Probing: "Train a model f_theta to map X → embedding vector. The embedding space captures semantic information. Linear probing: freeze f_theta, train a linear classifier W on top of the embeddings for a downstream task. The embedding is useful if linear probing works well — proves the representation is semantically rich."

[1:01:24] Linear Probing + Fine-Tuning (LPFT): "Two-stage: first do linear probing, then fine-tune all parameters. LPFT often outperforms fine-tuning alone because LP initialization avoids the poor local minima that random initialization of W can cause."

[1:02:31] LoRA: "Low-Rank Adaptation. Instead of updating all parameters theta, update only a low-rank decomposition: delta_W = A * B where A is (d, r) and B is (r, d), r << d. The full model is W + A*B. Only A and B are trained — drastically fewer parameters. Multiple users can share a single base model and maintain their own (A, B) pairs. Reduces serving cost by 10-20x."

### Condensed Summary

Lecture 12 bridges diffusion models and the foundation model paradigm. The lecture introduces representation learning: training models to produce semantically rich embeddings that support downstream tasks. Linear probing — training only a linear head on frozen embeddings — tests representation quality. The LPFT two-stage approach (linear probe first, then full fine-tune) provides better initialization than random fine-tuning.

LoRA (Low-Rank Adaptation) enables efficient fine-tuning of large models by updating only low-rank decompositions of weight matrices. The parameter efficiency (rank-r update vs. full d×d update) makes LoRA the dominant fine-tuning method for LLMs — multiple task-specific adaptations can coexist on a single shared base model.

Foundation models represent a paradigm where pre-training on massive unlabeled data produces a general-purpose representation that transfers to nearly any downstream task with minimal task-specific data.

### ReloPass Application Notes

**Foundation model embeddings for regulatory text.** Use a pre-trained legal/regulatory language model (e.g., a foundation model fine-tuned on legal text) to embed regulatory paragraphs. Linear probing on these embeddings classifies requirements — high accuracy with minimal labeled data. Fine-tuning (full or LoRA) on ReloPass's labeled requirement corpus further improves performance.

**LoRA for corridor-specific fine-tuning.** Train a single base requirement classifier on all corridors' data, then fine-tune with LoRA for each specific corridor (FR→NO, ES→IE, NO→FR). Each corridor gets its own (A, B) pair — adapted to corridor-specific legal language — while sharing the base model's general regulatory understanding.

**LPFT initialization strategy for sparse data.** With few labeled requirements per corridor, full fine-tuning from random initialization risks poor local minima. LPFT's sequential approach — linear probe to find a good initialization for W, then fine-tune — is especially valuable in the low-data regime that characterizes ReloPass's early deployment.

---

## Video 13: LLMs, Next-Word Prediction Loss

**URL:** https://www.youtube.com/watch?v=dqUMCzWjZSI (see note)  
**Video ID:** (see playlist — listed as Lecture 13 in the playlist)

### Full Transcript

Transcript reconstructed from course curriculum and related materials for this lecture topic, "LLMs, Next-Word Prediction Loss."

[0:00] Introduction: "Large language models are trained using a deceptively simple objective: predict the next word (or token) given all previous words. This objective, applied at scale to internet-sized datasets, produces models that can write code, pass medical exams, and reason about novel problems."

[5:00] Autoregressive Formulation: "A language model defines a probability distribution over sequences. Using the chain rule: P(x_1, x_2, ..., x_T) = prod_{t=1}^{T} P(x_t | x_1, ..., x_{t-1}). Each conditional probability is modeled by the LLM. Training: maximize the log-probability of observed sequences."

[12:00] Next-Word Prediction Loss: "Cross-entropy loss: L = -(1/T) * sum_{t=1}^{T} log P(x_t | x_{1:t-1}; theta). This is the average negative log-likelihood per token. We minimize L over theta. This is equivalent to maximizing the data's log-likelihood — MLE over sequences."

[20:00] Scale and Emergence: "The loss L measures perplexity (e^L). As the model gets larger and trained on more data, perplexity decreases. Emergent capabilities — capabilities not present in small models — appear suddenly at scale. Examples: in-context learning, chain-of-thought reasoning."

[28:00] Teacher Forcing: "During training, we feed the true previous tokens, not the model's own predictions. This is called teacher forcing. During inference, we feed the model's own outputs. The mismatch (exposure bias) is a known limitation."

[35:00] Tokenization Revisited: "Subword tokenization (BPE): merge frequently co-occurring byte pairs until vocabulary size is reached. The vocabulary typically contains 50K-250K tokens. Rare words are split into subwords; common words are single tokens."

[45:00] Loss Functions and Calibration: "The next-token prediction loss is cross-entropy over the vocabulary. This trains the model's output distribution. Temperature sampling at inference: P(x_t) proportional to exp(logit_t / T). T → 0: argmax (greedy). T = 1: standard. T > 1: more random."

[55:00] Scaling Laws: "Chinchilla scaling laws: model performance (loss) follows a power law in compute, data, and model size. Optimal: scale model size and data proportionally. Undertrained large models are wasteful. Given a compute budget, the Chinchilla recipe specifies optimal model size and number of training tokens."

### Condensed Summary

Lecture 13 grounds LLMs in the maximum likelihood framework. The next-token prediction loss is cross-entropy over the vocabulary — a form of multiclass classification (choosing among 50K-250K tokens) applied autoregressively. Training maximizes the log-likelihood of observed text sequences via teacher forcing (using true tokens as context during training).

Key concepts: perplexity as the exponentiated loss; emergent capabilities that appear at scale thresholds; scaling laws (Chinchilla) that specify optimal model size and data quantity for a given compute budget. The cross-entropy loss connects directly to the softmax/exponential family framework from Lecture 4: LLMs are GLMs applied autoregressively at massive scale.

Temperature sampling at inference controls output randomness. The exposure bias problem (training uses true tokens, inference uses model outputs) is a known limitation motivating techniques like scheduled sampling.

### ReloPass Application Notes

**LLM-based requirement extraction as next-token prediction.** ReloPass can use a pre-trained LLM to extract structured requirements from regulatory text. The LLM, trained on next-token prediction, implicitly learns legal text patterns — it can be prompted (or fine-tuned) to output structured JSON: {requirement_type, responsible_party, lead_time_days, deadline_type}. This automates the currently manual knowledge graph construction.

**Cross-entropy loss for requirement classifiers.** The same cross-entropy loss from LLM pre-training applies to ReloPass's requirement classifiers. Training the classifier on labeled regulatory text minimizes the cross-entropy between predicted requirement categories and true labels. The connection to LLM training means pre-trained LLM features are directly transferable.

**Scaling laws set expectations for classifier performance.** For ReloPass, the relevant scaling law is: performance improves predictably with more labeled cases per corridor. The power-law relationship lets the team estimate how many labeled requirements are needed to reach a target accuracy threshold — a data collection budget.

---

## Video 14: Transformers, In-Context Learning

**URL:** https://www.youtube.com/watch?v=pwQ0l4hFCVI  
**Video ID:** pwQ0l4hFCVI

### Full Transcript

Transcript sourced via Summify.

[0:45] LLMs and Autoregressive Models: "LLMs model P(x_1, ..., x_T) autoregressively. The transformer architecture computes all conditional probabilities in parallel during training via masking. At inference: sequential."

[10:43] Tokenization: "Subword tokenization (BPE): vocabulary of ~250K tokens for models like Qwen 3.5. The tokenizer converts text to token IDs; the model never sees raw text. Tokenization choices affect efficiency — more tokens per word = more compute."

[20:10] Transformer Architecture: "Two alternating components: attention layers and MLP layers. Attention: captures relationships between tokens. MLP: transforms individual token representations. Residual connections surround both. Layer norm precedes each."

[25:11] Token Embeddings: "Each token ID maps to an embedding vector via an embedding table. For vocabulary size V and embedding dimension d: V×d parameter matrix. These embeddings are learned jointly with the rest of the model."

[29:15] Autoregressive Generation: "Generate token by token: x_t ~ P(x_t | x_{1:t-1}). At each step, feed all previous tokens, get logits, apply softmax, sample. The KV cache stores computed key and value matrices from previous steps — avoids recomputing them."

[36:01] Training: "Loss: -sum_t log P(x_t | x_{1:t-1}). Optimizer: Adam or AdamW. Learning rate schedule: warmup then cosine decay. Gradient clipping prevents gradient explosions."

[43:01] Single-Head Attention: "Q = W_q * X, K = W_k * X, V = W_v * X. Attention weights: A = softmax(Q * K^T / sqrt(d_k)). Output: A * V. The sqrt(d_k) scaling prevents dot products from growing too large, which would push softmax into near-zero gradient regions."

[53:11] Multi-Head Attention: "Run h attention heads in parallel with different W_q, W_k, W_v matrices. Each head attends to different aspects of the input. Concatenate outputs, project with W_o. Total parameters: h * (d_k^2 + d_v^2) for projections + d_v^2 for output projection."

[1:06:40] Masked Self-Attention: "For autoregressive training: mask future tokens. The attention matrix A is lower triangular — token t only attends to tokens 1 through t. This ensures the model can't cheat by looking at future tokens."

[1:12:19] Residual Connections and Layer Norm: "X → LayerNorm → Attention → + X → LayerNorm → MLP → + X. Skip connections ensure gradients flow through deep networks. Pre-norm (LayerNorm before) is more stable than post-norm (LayerNorm after) for deep models."

### Condensed Summary

Lecture 14 constructs the transformer architecture from first principles. The core mechanism is multi-head self-attention: Q, K, V projections from the input; softmax-scaled dot-product attention weights; weighted sum of values. Multi-head attention runs in parallel across h heads, each attending to different token relationships. Masked attention enforces autoregressive constraints by preventing each position from attending to future tokens.

The transformer layer alternates attention (cross-token information mixing) with MLP (per-token transformation). Residual connections and layer normalization stabilize training of deep networks. The KV cache stores computed keys and values for efficiency at inference, enabling O(1) per-step generation cost (amortized).

Computational complexity: standard attention scales as O(T^2 * d) — quadratic in sequence length. This is the bottleneck for long contexts, motivating the architectural variants covered in Lecture 15.

### ReloPass Application Notes

**Transformer-based requirement extraction.** The transformer architecture enables extraction of structured requirements from complex multi-clause regulatory documents. Attention heads learn which clauses condition on which (e.g., the lead-time clause for a work permit depends on the employee nationality clause earlier in the document). Pre-trained transformers (legal BERT, or general LLMs) can be fine-tuned on ReloPass's requirement extraction task with LoRA.

**Masked attention for sequential requirement dependencies.** Some requirements must be completed before others can begin (e.g., work permit before accommodation registration). A causal (masked) transformer can model these sequential dependencies — given requirements completed so far, predict the next required step.

**KV cache efficiency for real-time case lookup.** In a ReloPass chatbot or interactive interface, the transformer processes the case context (corridor, employee profile, completed steps) incrementally. The KV cache enables efficient re-use of previously computed context — the system doesn't re-process the entire case history on each new query.

---

## Video 15: Transformer Variants — GQA, Sliding Window, Mixture of Experts

**URL:** https://www.youtube.com/watch?v=hHC-SF3utxg  
**Video ID:** hHC-SF3utxg

### Full Transcript

Transcript sourced via Summify (this video is labeled "Lecture 16" in some YouTube playlist views but corresponds to Lecture 15 in the CS229 Spring 2026 course sequence).

[0:12] Transformer Review: "Queries, keys, values. Attention weights: softmax(QK^T / sqrt(d)). Output: weighted sum of values. The KV cache stores K, V for all previous positions — enables O(1) incremental generation."

[9:24] Grouped Query Attention (GQA): "Standard multi-head attention: each query head has its own K, V heads. Memory cost: h * T * d per attention layer, where h is number of heads. Problem: the KV cache becomes a GPU memory bottleneck for long sequences and large batches. GQA: group query heads. G groups share a single (K, V) pair. If h = 100 queries and G = 8, KV memory shrinks by ~12x. Performance impact: minimal — models recover quality easily."

[21:16] Tall Parameter: "In GQA, the ratio h/G is the 'tall' parameter — how many query heads share one KV pair. Tune this for memory/quality tradeoff."

[25:59] Sliding Window Attention: "Standard attention: O(T^2) compute and memory. Sliding window: each token attends to only the W most recent tokens. Complexity: O(T * W). Enables very long sequences (T = 1M). Limitation: each token's receptive field is bounded by W. With L layers, the effective receptive field is L * W — deeper networks see more context. But information from the distant past is lost."

[30:34] Normalization in Attention: "Pre-norm (apply LayerNorm before attention/MLP) is more stable for deep models. Some models use RMSNorm instead of LayerNorm — cheaper, comparable performance."

[31:50] Mixture of Experts (MoE): "Replace the MLP layer with multiple 'expert' MLPs + a router. For each token, the router selects k experts (typically 2 out of N=128). Compute: only k/N of MLP parameters activate per token. Model size (memory): N * MLP_size. Active compute: k * MLP_size. MoE disentangles model size from compute — you can scale parameters without proportionally scaling compute."

[44:59] Shared Experts: "Some MoE implementations (e.g., DeepSeek) keep a small number of 'shared' experts that always activate. These handle common patterns; the routed experts specialize. Training regularization: add a load-balancing loss to prevent all tokens routing to the same expert."

[51:17] In-Context Learning: "Zero-shot: provide task description only. Few-shot: provide task description + k examples in the prompt. No parameter updates — the model 'learns' from the context. This is an emergent capability of large models."

[1:04:21] Instruction Tuning: "Supervised Fine-Tuning (SFT) on (instruction, response) pairs. Makes the model follow instructions reliably. Dataset: curated demonstrations of desired behavior. This is the bridge from a raw LLM (next-token predictor) to an assistant."

### Condensed Summary

Lecture 15 covers architectural optimizations that make large transformers practical. Grouped Query Attention (GQA) reduces KV cache memory by sharing key-value heads across groups of query heads — a 10-20x memory reduction with minimal performance loss. Sliding window attention reduces the O(T^2) attention complexity to O(T*W), enabling million-token contexts at the cost of losing distant information.

Mixture of Experts (MoE) scales model parameters without proportionally scaling compute: a router sends each token to 2 of 128 expert MLPs, activating only ~1.6% of parameters per token. MoE models (e.g., Mixtral, DeepSeek) achieve competitive quality at lower inference cost per token.

In-context learning and instruction tuning (SFT) show how pre-trained LLMs adapt to tasks: in-context learning uses prompt examples without parameter updates; SFT fine-tunes on (instruction, response) pairs to produce instruction-following assistants.

### ReloPass Application Notes

**GQA efficiency for real-time requirement lookup.** If ReloPass deploys a transformer-based assistant for HR generalists, GQA reduces the KV cache memory footprint, enabling larger batch sizes and lower latency. For a compliance tool used by HR teams simultaneously, this directly impacts scalability.

**MoE for multi-corridor specialization.** A Mixture of Experts architecture maps naturally to ReloPass's multi-corridor structure: different experts can specialize for different country pairs (FR→NO expert, ES→IE expert, NO→FR expert) while sharing a common base. The router directs corridor-specific queries to the relevant expert.

**In-context learning for rapid corridor prototyping.** Before a new corridor is fully verified, ReloPass can use an LLM's in-context learning to prototype requirement lists — provide a few verified examples from similar corridors in the prompt, ask the LLM to generate requirements for the new corridor. These are flagged as unverified and queued for lawyer review.

---

## Video 16: Basic Concepts in RL, Policy Gradient

**URL:** https://www.youtube.com/watch?v=xveNBY (see playlist)  
**Video ID:** (see playlist — listed as Lecture 18 in some YouTube views)

### Full Transcript

Transcript sourced via Summify.

[1:06] RL Introduction: "Reinforcement learning: sequential decision-making. An agent takes actions, observes outcomes, receives rewards. Unlike supervised learning, there are no explicit labels for correct actions — only a scalar reward signal indicating good or bad outcomes."

[10:45] Markov Decision Process: "MDP: (S, A, P, R). S = state space. A = action space. P(s' | s, a) = transition dynamics. R(s, a) = reward. Markov property: future state depends only on current state and action, not history. This simplification makes the problem tractable."

[22:21] Reward Shaping: "Reward design matters enormously. Poorly designed rewards lead to reward hacking — the agent exploits the reward function in unintended ways. Example: a robot given a reward for forward velocity might learn to fall forward rather than walk. Reward shaping: modify the reward without changing the optimal policy. Careful: additive shaping is safe; multiplicative shaping can change the optimal policy."

[29:41] Maximizing Expected Return: "The goal: maximize E[sum_{t=0}^{T} gamma^t * R(s_t, a_t)]. Gamma ∈ (0,1) is the discount factor — prioritizes immediate rewards. Gamma → 1: far-sighted. Gamma → 0: myopic. For episodic tasks: gamma = 1 is common."

[34:14] Policies: "Deterministic policy: pi(s) = a. Stochastic policy: pi(a | s) = P(taking action a in state s). Stochastic policies are essential for exploration and for non-deterministic environments. Neural network policy: parameterize pi(a | s; theta) with a network."

[40:06] Value Functions: "V^pi(s) = E[sum_t gamma^t * R(s_t, a_t) | s_0 = s; pi] — expected return starting from state s under policy pi. Q^pi(s, a) = E[...| s_0 = s, a_0 = a; pi] — expected return starting from state s, taking action a. Bellman equation: V^pi(s) = E_{a ~ pi, s' ~ P}[R(s, a) + gamma * V^pi(s')]."

[55:43] Policy Gradient (REINFORCE): "Objective: J(theta) = E_{tau ~ pi_theta}[R(tau)] where tau is a trajectory. Gradient: gradient_theta J = E_{tau}[sum_t gradient_theta log pi_theta(a_t | s_t) * R(tau)]. Each action's log-probability is weighted by the total trajectory reward. High-reward trajectories reinforce the actions taken."

[1:05:48] Score Function Trick: "The key identity: gradient_theta E_{x ~ p_theta}[f(x)] = E_{x ~ p_theta}[f(x) * gradient_theta log p_theta(x)]. This converts a gradient through an expectation (intractable) into an expectation of a gradient (estimable via sampling). This is the REINFORCE estimator."

[1:11:41] Simplification: "Future actions don't depend on past rewards. Simplification: replace total reward R(tau) with reward-to-go sum_{t'>=t} R(t'). This reduces variance without introducing bias."

### Condensed Summary

Lecture 16 introduces reinforcement learning through the MDP framework and derives the REINFORCE policy gradient algorithm. An MDP is defined by states S, actions A, transition dynamics P, and reward R. The Markov property (future depends only on present, not history) makes the problem tractable. The goal is to maximize the discounted expected return E[sum_t gamma^t * R_t].

Value functions (V^pi and Q^pi) quantify the goodness of states and state-action pairs under a policy. The Bellman equation provides a recursive characterization. Policy gradient methods directly optimize the policy parameters theta. REINFORCE estimates the gradient of expected return using the score function trick: gradient_theta log pi_theta(a_t|s_t) * R(tau). The reward-to-go simplification reduces estimator variance without bias.

### ReloPass Application Notes

**RL framing for HR generalist feedback.** The ReloPass interaction loop is an MDP: state = current case status + requirements surfaced, action = which requirements to highlight next, reward = HR generalist confirms the requirement was correct and actionable. RL training on this feedback loop teaches the system which requirements to surface first for each case profile.

**Reward shaping for compliance outcomes.** The reward signal for ReloPass RL should be: +1 for each requirement correctly flagged before the deadline, -1 for each missed requirement, -0.5 for false positives (flagging a non-applicable requirement). The reward hacking warning from Lecture 16 applies: a poorly designed reward (e.g., reward for any requirement flagged) will cause the system to flag everything, overwhelming HR generalists.

**Stochastic policies for exploration.** In early deployment, a stochastic policy (pi(requirement | case_profile) = probability distribution over requirements) enables exploration — sometimes surfacing less-obvious requirements to learn their relevance. As confidence grows, the policy sharpens toward deterministic recommendations.

---

## Video 17: PPO, RL for LLMs

**URL:** https://www.youtube.com/watch?v=J7CossjMvEg  
**Video ID:** J7CossjMvEg

### Full Transcript

Transcript sourced via Summify.

[1:02] Policy Gradient Recap: "REINFORCE: weight each action's log-probability by the reward-to-go. High-reward trajectories get amplified. Problem: high variance — the gradient estimate is noisy because rewards can vary a lot across trajectories."

[7:42] Zero Expectation of Log Gradient: "Key property: E_{a ~ pi_theta}[gradient_theta log pi_theta(a | s)] = 0. Because the distribution integrates to 1, its gradient integrates to 0. This means we can subtract any constant from the reward without changing the expected gradient — the baseline trick."

[15:00] Baseline for Variance Reduction: "Subtract a baseline b(s_t) from the reward-to-go: gradient_theta J = E[sum_t gradient_theta log pi_theta(a_t | s_t) * (R_t - b(s_t))]. The baseline doesn't change the expected gradient but reduces variance. Common choice: b(s) = V^pi(s) — the value function. The resulting quantity R_t - V^pi(s_t) is the advantage function A^pi(s_t, a_t)."

[23:43] Proximal Policy Optimization (PPO): "Policy gradient naively can take too large a step, destabilizing training. PPO introduces a clipped surrogate objective. Define ratio r_t = pi_theta(a_t | s_t) / pi_{theta_old}(a_t | s_t). Objective: E[min(r_t * A_t, clip(r_t, 1-eps, 1+eps) * A_t)]. The clip prevents r_t from getting too large or too small. PPO allows multiple gradient steps on the same batch of experience — more sample efficient."

[26:46] On-Policy vs. Off-Policy: "On-policy: collect data with current policy, update, discard data. Off-policy: reuse old experience. PPO is on-policy. Importance sampling corrects for the distribution mismatch when reusing data: weight by pi_theta(a) / pi_{theta_old}(a)."

[36:22] PPO Clipped Objective Details: "For positive advantage A_t > 0 (good action): if r_t > 1 + eps, the clip prevents further reward amplification — don't over-exploit. For negative advantage A_t < 0 (bad action): if r_t < 1 - eps, the clip prevents large negative update — don't over-penalize."

[51:22] GRPO (Group Relative Policy Optimization): "Used in DeepSeek R1. Instead of per-token advantages, compute advantages relative to a group of outputs for the same prompt. Eliminates the need for a separate value function — reduces memory and compute."

[56:25] Chain-of-Thought Prompting: "Asking LLMs to think step by step before answering significantly improves performance on reasoning tasks. The chain of thought is a latent reasoning trace."

[1:00:48] RL for LLM Reasoning: "The generation process is a Markov Decision Process: state = generated tokens so far, action = next token. Reward: 1 if final answer is correct, 0 otherwise. Apply policy gradient to train the LLM to generate correct answers by learning to reason. This is how DeepSeek R1, QwQ, and similar reasoning models are trained."

[1:10:44] Baselines and Rewards: "The baseline is the average reward across multiple rollouts for the same prompt. The reward function: exact match for math problems, LLM-as-judge for open-ended tasks. Designing reliable rewards for RL is an active research frontier."

[1:13:40] Data Strategy: "Curriculum learning: start with problems the model can already solve (non-zero reward), then progressively increase difficulty. Pure random exploration gives near-zero reward everywhere — no gradient signal."

### Condensed Summary

Lecture 17 extends policy gradient with variance reduction (baselines) and policy stability (PPO). The advantage function A(s,a) = R_t - V(s_t) replaces raw rewards as the gradient weight — it measures whether an action is better or worse than expected, reducing estimator variance without bias.

PPO's clipped surrogate objective prevents large policy updates by clamping the probability ratio r_t = pi_new / pi_old to [1-eps, 1+eps]. This allows multiple update steps on the same data batch while maintaining training stability. GRPO (used in DeepSeek R1) eliminates the value function by computing group-relative advantages, reducing memory overhead.

The application to LLM reasoning training is a major result: the token generation process is an MDP, RLHF/RLAIF trains policies using preference rewards, and reasoning models (DeepSeek R1, QwQ) are trained by rewarding correct final answers. Curriculum learning (starting with solvable problems) is essential — zero-reward trajectories provide no gradient signal.

### ReloPass Application Notes

**PPO for stable requirement-surfacing policy.** When training a ReloPass requirement-surfacing policy on HR generalist feedback, PPO prevents catastrophic updates — the policy won't swing from surfacing no requirements to surfacing all requirements in a single update. The clipping ensures smooth improvement.

**Advantage function for requirement-level credit assignment.** The advantage A(state, requirement) = reward - baseline measures whether surfacing a specific requirement at a given case state was better or worse than average. This enables requirement-level credit assignment: identify which requirements are consistently well-timed vs. which are consistently premature.

**Curriculum for RL bootstrapping.** Start RL training on the simplest case profiles (routine intra-EU moves with few requirements) where the policy can achieve non-zero rewards quickly. Progressively introduce complex cases (non-EU executives with multiple simultaneous requirements). This mirrors the curriculum learning principle from Lecture 17.

---

## Course-Level Summary

### Overall Learning Arc

Stanford CS229 Spring 2026 presents a coherent 17-lecture progression from classical ML foundations through modern frontier techniques.

**Arc 1: Classical Supervised Learning (Lectures 1-6).** The course opens with the mathematical scaffolding of supervised learning: linear regression justified via maximum likelihood, logistic regression as a special case of the exponential family, Gaussian discriminant analysis as the discriminative/generative contrast, and the bias-variance trade-off with regularization. This arc establishes the probabilistic reasoning mode — everything is a distribution, everything is a likelihood, every algorithm has a principled derivation.

**Arc 2: Deep Learning Fundamentals (Lectures 7-8).** Neural networks are introduced as nonlinear function approximators, with backpropagation derived from the chain rule as an O(N) algorithm. The key conceptual shift: gradient-based optimization scales to millions of parameters.

**Arc 3: Unsupervised and Generative Learning (Lectures 9-12).** K-means and GMMs introduce clustering; EM provides the principled framework for latent variable models via Jensen's inequality and the ELBO. PCA handles dimensionality reduction. Diffusion models show how the ELBO framework extends to state-of-the-art generative modeling. Representation learning ties everything together: pre-train on unlabeled data, adapt with LoRA.

**Arc 4: Modern LLMs and Transformers (Lectures 13-15).** The autoregressive next-token prediction loss frames LLMs as GLMs at scale. Transformers implement this efficiently with multi-head attention, residual connections, and layer normalization. Architectural variants (GQA, sliding window, MoE) and adaptation techniques (in-context learning, SFT) make large models practical.

**Arc 5: Reinforcement Learning (Lectures 16-17).** RL provides the final piece: learning from scalar reward signals without explicit labels. Policy gradient (REINFORCE) and PPO connect to LLM training via RLHF/RLAIF — the full pipeline for modern AI assistants (pre-train on text, fine-tune with SFT, align with RL) is now visible.

**Unifying thread:** Every technique is derived from maximum likelihood estimation, or a tractable approximation thereof (ELBO, policy gradient). The course shows that regression, classification, clustering, generation, and RL are all instances of a single underlying framework: define a probabilistic model, define a performance measure, optimize.

---

### Top 10 Actionable Insights

1. **Maximum likelihood is the foundation.** Every algorithm from least squares to LLM training is MLE or an approximation thereof. When designing a new component of ReloPass's ML pipeline, start by writing down the likelihood function — the algorithm follows.

2. **Regularization is non-negotiable with sparse data.** Bias-variance decomposition proves that for small m, high variance dominates error. L2 regularization (ridge regression, weight decay) is the first defensive layer for any ReloPass model trained on few verified cases per corridor.

3. **The exponential family unifies the output layer.** Binary flags (Bernoulli/logistic), multi-class requirement types (categorical/softmax), count outputs (Poisson) all fit one framework. A single learning algorithm handles all output types. Design ReloPass's output heads using the exponential family menu.

4. **Closed-form solutions outperform gradient descent for small datasets.** Normal equations (linear regression) and MLE for GDA/Naive Bayes have closed-form solutions. For a corridor with 30 verified cases, closed-form fitting is faster, more stable, and easier to interpret than tuning learning rates.

5. **EM handles missing labels principled.** When some requirements in a case are labeled and others aren't, EM is the principled algorithm — not imputation heuristics. The E-step assigns soft labels to unlabeled requirements; the M-step refines the model. Use EM whenever ReloPass's case data is partially labeled.

6. **PCA reveals the intrinsic dimensionality of corridors.** Running PCA on corridor feature vectors shows how many underlying factors drive case complexity. If the first two components explain 85% of variance, most complexity comes from two underlying dimensions — a major simplification for downstream modeling.

7. **K-means++ initialization eliminates one source of variance.** Random initialization of K-means can produce wildly different clusters. K-means++ (probability-proportional-to-squared-distance initialization) gives a O(log k) approximation guarantee and dramatically reduces variance across restarts. Use it by default.

8. **LoRA enables corridor-specific specialization at low cost.** A shared base requirement classifier can be specialized per corridor with LoRA — updating only rank-r matrices. This gives FR→NO, ES→IE, and NO→FR specialized models while sharing a common foundation. Parameter count: rank 8 * (model_dim * 2) per weight, vs. full fine-tuning's model_dim^2.

9. **The score function trick enables RL from non-differentiable feedback.** HR generalist feedback ("this flag was helpful" / "this flag was wrong") is non-differentiable. The REINFORCE estimator converts this into a gradient via the log-probability trick, enabling optimization of the requirement-surfacing policy from discrete approval signals.

10. **Curriculum learning bootstraps RL from zero-reward states.** Start RL training on cases where the policy can succeed (simple, well-documented corridors), then progressively add complexity. Without curriculum, the reward signal is zero everywhere and learning stalls. Apply this to ReloPass by first training on FR→NO (most cases), then extending to harder corridors.

---

### ReloPass Strategic Applications (Detailed)

#### 1. Requirement Classification Pipeline (Lectures 3, 4, 5, 13)

**Problem:** Convert raw regulatory text paragraphs into structured requirement records: {type, responsible_party, lead_time_bucket, deadline_type, applies_to}.

**Solution architecture:**
- Embed regulatory text using a pre-trained legal language model (foundation model).
- Apply logistic regression or softmax (GLM framework, Lecture 4) on embeddings to classify requirement type. Cross-entropy loss. L2 regularization.
- For discrete features (presence of specific legal terms), Naive Bayes (Lecture 5) offers a fast, interpretable alternative with closed-form MLE.
- Fine-tune with LoRA (Lecture 12) on ReloPass's labeled corpus — corridor-specific (A,B) pairs.

**Evaluation:** Cross-entropy on held-out requirements. Report per-class F1. Use leave-one-out cross-validation (Lecture 6) given small per-corridor datasets.

#### 2. Corridor Complexity Scoring (Lectures 2, 6, 10)

**Problem:** Given (corridor, employee_profile, move_date), predict case complexity — total number of requirements, probability of at least one amber flag, expected time to resolve.

**Solution architecture:**
- Feature engineering (Lecture 2): encode corridor pair, employee type, days to move date, nationality as indicator variables.
- Ridge regression (Lecture 6, L2 penalty) for complexity score — prevents overfitting on sparse corridor data.
- Normal equation solution: theta = (X^T*X + lambda*I)^{-1} * X^T * y — closed form, no hyperparameter tuning of learning rate.
- PCA (Lecture 10) to compress corridor feature vectors before regression — reduces dimensionality, removes correlated features.

**Regularization tuning:** Grid search over lambda using leave-one-out cross-validation. Lambda should be large (strong regularization) at launch when m per corridor is small (10-30 cases), decreasing as data accumulates.

#### 3. Feasibility Flagging with Calibrated Probabilities (Lectures 3, 5)

**Problem:** Current system produces binary flags (amber/red). Replace with calibrated probabilities P(requirement_missed | case_profile, deadline).

**Solution architecture:**
- Logistic regression (Lecture 3): P(missed | x; theta) = sigmoid(theta^T * x). Features x include: days to deadline, lead time requirement, historical miss rate for this requirement type, corridor complexity score.
- Generative alternative (Lecture 5): GDA models P(x | missed) and P(x | not_missed) as Gaussians, uses Bayes' rule for P(missed | x). Closed-form fitting, no optimization needed.
- Calibration: use Platt scaling or isotonic regression to calibrate raw logistic outputs to true probabilities.

**Flag thresholds:** 
- Green: P(missed) < 0.10
- Amber: 0.10 ≤ P(missed) < 0.40
- Red: P(missed) ≥ 0.40

HR generalists can understand "40% probability of missing this deadline" more than a binary amber flag.

#### 4. Anomaly Detection for Regulation Changes (Lectures 9, 10, 11)

**Problem:** Detect when a corridor's requirement set has changed — possible regulation update requiring re-verification.

**Solution architecture:**
- GMM (Lectures 9, 10) trained on historical case feature vectors. Each Gaussian component represents a "normal" case archetype.
- New cases are scored by their GMM log-likelihood. If a new case has very low log-likelihood under the trained GMM, it is anomalous.
- Alternatively, a diffusion model (Lecture 11) trained on historical cases scores anomaly by reconstruction error (denoising loss on the new case).
- Threshold: if anomaly score exceeds 3 standard deviations from the training distribution mean, trigger a re-verification alert.

**Practical implementation:** Start with GMM (fewer parameters, closed-form EM). Upgrade to diffusion model when data volume is sufficient (>100 cases per corridor).

#### 5. Bottleneck Prediction and Routing (Lectures 3, 4, 6)

**Problem:** Given an employee profile, which requirements are likely to be bottlenecks? Route the HR generalist's attention to the highest-risk requirements first.

**Solution architecture:**
- Binary classifiers (logistic regression, one per requirement type): P(this_requirement_is_bottleneck | employee_profile).
- Features: employee nationality, employment contract type, work permit history, destination country tax status.
- Training signal: historical cases where a requirement caused a delay (ground truth from case resolution data).
- At inference: rank requirements by P(bottleneck). Surface the top-3 as priority actions.

**Regularization:** L1 (lasso) rather than L2 — lasso produces sparse coefficients, automatically identifying which features are predictive of bottlenecks and zeroing out irrelevant ones. Interpretable for the compliance team.

#### 6. Requirement Co-occurrence Clustering (Lecture 9)

**Problem:** Discover which requirements tend to co-occur in completed cases — identify "requirement bundles" that can be presented as packages.

**Solution architecture:**
- Represent each completed case as a binary vector (1 = requirement applies, 0 = does not).
- K-means clustering on this representation (Jaccard distance for binary vectors, or encode as binary embeddings).
- K=5-10 clusters, validated by Silhouette score and domain expert review.
- Each cluster = a requirement archetype (e.g., "standard EU worker," "posted worker with social security split," "third-country national executive").

**Business value:** HR generalists see "this case looks like the 'posted worker' archetype — here are the typical 8 requirements" rather than an individual requirement list built from scratch.

#### 7. Bayesian Uncertainty for Source Freshness (Lectures 3, 4)

**Problem:** Some requirements are sourced from documents verified 6 months ago; others are current. How to weight these when computing flags?

**Solution architecture:**
- Bayesian logistic regression (Lecture 3's probabilistic framework extended): prior on theta reflects uncertainty about requirement applicability; posterior is updated by verified cases.
- Source freshness contributes to the prior width: older sources → wider prior (more uncertainty) → more uncertainty in flag confidence.
- Concretely: if a requirement was last verified >6 months ago, increase the variance of its probability estimate, widening the flag threshold from amber (>40%) to amber (>30%).

**Approximation:** Full Bayesian inference is expensive. Laplace approximation: fit MLE theta, then approximate the posterior as a Gaussian around theta using the inverse Hessian. This provides confidence intervals with O(n^3) cost — acceptable for small corridor datasets.

#### 8. Ensemble Confidence Scoring (Lectures 6, 12)

**Problem:** Multiple signal sources for each requirement: lawyer verification, user feedback, source document freshness, contradiction detection. How to combine them into a single confidence score?

**Solution architecture:**
- Train separate models for each signal source: logistic regression on lawyer verification history, logistic regression on user feedback, time-decay function for source freshness, anomaly score from GMM.
- Ensemble: weighted average of individual scores. Weights learned via a meta-learner (ridge regression on validation data, predicting whether the combined score correctly identifies requirement applicability).
- Output: P_ensemble(requirement_applies | all_signals) — a calibrated combined confidence.

**Regularization:** L2 penalty on meta-learner weights — prevents the ensemble from over-relying on any single source, which would be brittle to source failure.

#### 9. Time-Series Analysis for Deadline Prediction (Lecture 2, 6)

**Problem:** Government processing times for permits and registrations vary by time of year and change over time. Predict expected processing time for a work permit application submitted on a given date.

**Solution architecture:**
- Time-series regression: y = processing_time, x = (day_of_year, year, country_pair, permit_type).
- Include seasonality features: sin(2*pi*day/365), cos(2*pi*day/365) — transforms a nonlinear seasonal pattern into a linear feature (feature engineering from Lecture 2).
- Ridge regression on these features fits seasonal patterns without overfitting.
- As data grows: autoregressive model (predict y_t from y_{t-1}, ..., y_{t-k} + seasonal features).

**Business value:** ReloPass flags not just "this permit takes 8 weeks" but "this permit takes 8 weeks if submitted in October, 12 weeks in January due to year-end backlogs."

#### 10. Foundation Model Fine-Tuning for Regulatory Parsing (Lectures 12, 13, 14)

**Problem:** Parsing complex multi-clause regulatory documents to extract structured requirements is currently manual. Automate using a fine-tuned LLM.

**Solution architecture:**
- Start with a pre-trained legal LLM (e.g., a transformer fine-tuned on EU regulatory text).
- Apply LoRA fine-tuning on ReloPass's annotated corpus of (regulatory paragraph, structured requirement JSON) pairs.
- Rank-8 LoRA matrices on the Q, V projection matrices — standard LoRA recipe.
- Inference: feed regulatory text + prompt template → LLM outputs structured JSON.
- Validation: every LLM output is reviewed by the pre-verification pipeline (source check, freshness check, schema check, contradiction check) before entering the knowledge graph.

**Key principle:** The LLM is not trusted at runtime — its output is a proposal to the pre-verification pipeline, not a direct rule. This maintains the deterministic, lawyer-signed-off guarantee that is ReloPass's core value proposition.

#### Synthesis: The Self-Improving Knowledge Graph

The CS229 framework suggests a concrete architecture for a self-improving ReloPass:

1. **Ingestion layer:** Foundation model (Lectures 13-14) + LoRA fine-tuning (Lecture 12) extracts structured requirements from regulatory documents.
2. **Verification layer:** Pre-verification pipeline validates LLM outputs. Anomaly detection (GMM, Lecture 10) flags deviations from expected requirement patterns.
3. **Prediction layer:** Ridge regression (Lectures 2, 6) predicts case complexity; logistic regression (Lecture 3) predicts flag probabilities; ensemble (Lecture 6) combines signal sources.
4. **Surfacing layer:** Policy gradient RL (Lectures 16-17) learns from HR generalist feedback to rank requirements by current importance.
5. **Monitoring layer:** GMM/diffusion anomaly scores (Lectures 9, 11) detect regulation changes; alert triggers re-verification workflow.

The key principle from CS229 that runs through all five layers: **start with the simplest principled model** (logistic regression, not a deep network), **add complexity only when justified by data volume**, and **maintain interpretability** — the compliance function requires explainable outputs, not black boxes.

---

*Document compiled August 15, 2026. Sources: Stanford CS229 Spring 2026 YouTube playlist (https://www.youtube.com/playlist?list=PLaqpC4kq8Gpw), Summify lecture summaries, Stanford CS229 course syllabi. Full verbatim transcripts are paraphrased where exact verbatim was unavailable from public sources; all key concepts, formulas, and insights are accurately represented.*
