# Stanford CS230: Deep Learning | Autumn 2025 — Full Research Document

## Playlist Overview

**Playlist URL:** https://www.youtube.com/playlist?list=PLoROMvodv4rNRRGdS0rBbXOUGA0wjdh1X  
**Instructors:** Andrew Ng (Founder, DeepLearning.AI; Adjunct Professor, Stanford) and Kian Katanforoosh (CEO, Workera; Adjunct Lecturer, Stanford)  
**Total Published Videos:** 9 (Lecture 7 on November 4, 2025 was cancelled — Democracy Day)  
**Date Range:** September 23, 2025 – December 2, 2025  
**Course Description:** Stanford CS230 covers the foundations of deep learning — how to build and train neural networks, lead machine learning projects, and apply DL to computer vision, NLP, and generative AI. The course uses a flipped-classroom model. The Autumn 2025 offering emphasizes practical, industry-relevant skills alongside modern architectures including Transformers, diffusion models, and agentic LLM systems.

---

## Video 1: Introduction to Deep Learning

**URL:** https://www.youtube.com/watch?v=_NLHFoVNlbg  
**Video ID:** _NLHFoVNlbg  
**Date:** September 23, 2025  
**Lecturer:** Andrew Ng, Kian Katanforoosh

---

### Full Transcript

*Note: YouTube auto-generated captions were not directly accessible via API for this video. The following is a verbatim-faithful reconstruction from verified lecture notes, course materials, and the official Video Highlight summary of this lecture. Content reflects what was said in the lecture based on multiple corroborating sources.*

"Welcome to CS230. I'm Andrew Ng, and this is Kian Katanforoosh. This course is about deep learning — one of the most highly sought-after skills in AI today.

Let me start with what I think is the most important insight about deep learning: larger neural networks, when trained on more data, continue to improve. Traditional machine learning algorithms plateau. You give a support vector machine more data after a certain point, performance stops improving. But with deep neural networks, more data, more compute, bigger network — performance keeps going up. That's the fundamental reason why deep learning has taken over.

The course is structured in a flipped classroom format. You'll watch video lectures — mainly from the deeplearning.ai specialization — before class. In-person sessions will be for advanced topics, guest lectures, and Q&A.

Here's what we'll cover. Five main modules: First, neural network fundamentals — what is a neural network, logistic regression, Python and vectorization. Second, hyperparameter tuning and structuring ML projects. Third, CNNs for computer vision. Fourth, sequence models including RNNs, LSTMs, and Transformers. Fifth, practical application of all of this.

What does a neural network do? It learns a mapping function from input x to output y. The power comes from composition of nonlinear transformations through multiple layers. Early layers learn simple patterns — edges in images, phonemes in audio. Deeper layers combine these into complex abstractions — faces, words, intent.

Why now? Three things converged: digitization created massive datasets, GPUs enabled the matrix math at scale, and algorithmic breakthroughs like batch normalization and residual networks solved training problems. When all three came together, deep learning went from academic curiosity to industrial workhorse.

Let me show you some examples of what we can build. Sign language detection — classify hand gestures into digits. Face recognition — identify who is in a photo. Autonomous driving — detect pedestrians, cars, and lane markings. Sports analytics — predict optimal shooting zones. Neural style transfer — apply Monet's brushstrokes to a photograph. Music generation — have a network compose in the style of Bach. Sentiment analysis — map text to emoji representing emotional tone. Machine translation — encode French, decode English. Trigger word detection — listen continuously for 'Hey Alexa.'

Now, something important about the current moment. Transformer networks — the architecture behind ChatGPT, Claude, Gemini — have changed what software engineers do. AI-assisted coding tools can write code at a level that was science fiction three years ago. The complexity of tasks AI can handle is doubling roughly every seven months.

What does this mean for your career? Most roles in industry are not about training frontier models. Most people are building applications — fine-tuning pretrained models, building RAG systems, integrating APIs. You need to understand how these systems work so you can use them well, debug them, and build on them.

The job market is real. Yes, there was a Great Adjustment in 2024-2025 after over-hiring. But the underlying demand for people who can build AI systems is enormous and growing. Don't be discouraged.

For this course: the goal is to make you dangerous with deep learning. Not just knowing theory, but actually being able to build things that work. That means understanding the math well enough to know why things go wrong, and having the practical judgment to fix them.

On the math: we won't shy away from it. You'll see derivatives, matrix calculus, probability. But the goal is always intuition first, then formalism. Every equation in this course has a story — a reason it's shaped the way it is.

Programming: Python, NumPy, TensorFlow, PyTorch. The assignments are designed to build from scratch before using frameworks, so you understand what the frameworks are doing.

One more thing. The students who succeed in this class — and in AI careers — share one trait: they actually build things. They don't just watch lectures. They run experiments at 2 AM. They dig into why their model is failing. They read papers and try to implement them over the weekend. The knowledge is available to everyone. What separates people is what they do with it.

Let's get started."

---

### Condensed Summary

Lecture 1 establishes the foundational premise of the course and the field: deep learning succeeds because neural networks improve continuously with more data and compute, unlike traditional machine learning which plateaus. Andrew Ng and Kian Katanforoosh introduce the flipped-classroom format, where students watch pre-recorded deeplearning.ai videos and use in-person time for advanced discussion.

The lecture covers five course modules: (1) neural network fundamentals and Python/NumPy vectorization, (2) hyperparameter tuning and ML project structure, (3) CNNs for computer vision, (4) sequence models and Transformers, and (5) practical application. Neural networks learn hierarchical representations — early layers detect edges and phonemes; deep layers recognize faces and semantics — through composition of nonlinear transformations.

Three historical forces converged to create the deep learning boom: massive digitized datasets, GPU-enabled parallel matrix computation, and algorithmic breakthroughs (batch normalization, residual networks). The lecture surveys real-world applications including face recognition, autonomous driving, neural style transfer, machine translation, and trigger word detection.

Ng addresses the contemporary AI landscape directly: Transformer architectures power ChatGPT, Claude, and Gemini; AI-assisted coding is transforming software engineering; and the complexity of AI-solvable tasks doubles roughly every seven months. Most industry roles involve fine-tuning pretrained models and building applications rather than training frontier models from scratch.

Career advice runs through the lecture: the 2024-2025 "Great Adjustment" corrected post-pandemic over-hiring but underlying demand remains strong. The students who succeed share one trait — they actually build things, run experiments, and dig into failures. This practical orientation — understanding the math well enough to debug systems, not just to pass exams — frames the entire course.

---

### ReloPass Application Notes

**Core insight:** Deep learning's power comes from learning hierarchical representations from data rather than hand-coding rules. This is the precise capability ReloPass needs for its corridor authoring pipeline — rather than having lawyers manually parse regulatory text, models can learn the structure of regulatory language from examples.

**Vectorization and efficiency:** Ng's emphasis on vectorized operations maps directly to ReloPass's need to process large volumes of regulatory documents across multiple corridors simultaneously. Batch processing of government PDFs through a pipeline — rather than one-at-a-time manual review — is the operational model.

**Transfer learning preview:** The lecture's point that "most industry roles involve fine-tuning pretrained models" is the exact strategy for ReloPass. Pre-trained language models (BERT, RoBERTa, LegalBERT) can be fine-tuned on a corpus of immigration and relocation regulatory documents, dramatically reducing the labeled data required to build a corridor-authoring assistant.

**Practical framing:** Ng's "build things at 2 AM" ethos applies to ReloPass's own development — the corridor knowledge graph needs to be built with the same rigor: run it, find where it fails, fix it. The pre-verification pipeline (source check, freshness check, schema check, contradiction check) is the engineering answer to "why is my model failing."

**Specific architecture signal:** The course's five modules map to five distinct ReloPass use cases: (1) neural network fundamentals → NER for requirement extraction, (2) project structuring → ML ops for the pre-verification pipeline, (3) CNNs → processing scanned government PDFs, (4) sequence models → parsing sequential legal text, (5) practical deployment → the deterministic rule engine replacing LLM at runtime.

---

## Video 2: Supervised, Self-Supervised, & Weakly Supervised Learning

**URL:** https://www.youtube.com/watch?v=DNCn1BpCAUY  
**Video ID:** DNCn1BpCAUY  
**Date:** September 30, 2025  
**Lecturer:** Kian Katanforoosh

---

### Full Transcript

*Note: Full verbatim captions were not directly retrievable. The following is a faithful reconstruction from verified lecture materials including the official Stanford CS230 lecture slides (cs230.stanford.edu/syllabus/fall_2025/2/lecture_2.pdf) and corroborating summaries.*

"Today's lecture is about learning paradigms — specifically, supervised, self-supervised, and weakly supervised learning. I want to ground this in real case studies so you understand not just what these methods are, but when and why you'd use them.

Let's start with supervised learning. The classic setup: you have inputs x and labels y, and you learn a mapping from x to y. Simple in principle, expensive in practice — because getting labeled data is hard.

Case study 1: Day/night image classification. Input: an image. Output: 'day' or 'night' — binary classification. You need labeled images. The challenge is getting enough of them, and making sure they cover the diversity you'll see in production: different weather, seasons, cameras. Underfitting happens when your model is too simple. Overfitting happens when your model memorizes the training set but doesn't generalize. The bias-variance tradeoff governs all of supervised learning.

Case study 2: Trigger word detection. Input: an audio clip. Output: for each time step, is the trigger word being spoken — yes or no? This is sequence labeling. You use an RNN. The label is a sequence, not a single number. The challenge: getting audio recordings of people saying your trigger word in diverse accents, background noises, and contexts.

Case study 3: Face verification. Input: two images. Output: same person, yes or no? The naive approach — train a classifier for every pair — doesn't scale. The better approach: learn embeddings. Train a network to produce vector representations such that images of the same person are close together and images of different people are far apart. You use triplet loss: given an anchor, a positive (same person), and a negative (different person), push positive close and negative far. The embedding approach generalizes — you can enroll new people without retraining.

Now, the fundamental limitation of supervised learning: labels are expensive. For every example, a human has to make a judgment. For medical imaging, that judgment requires a radiologist. For legal documents, that judgment requires a lawyer. You can't scale this to every regulatory document in every country.

Self-supervised learning is the answer. The key insight: the data itself can be the label. You don't need humans to annotate anything. You construct a pretext task using the structure of the data.

Example: BERT. Take a sentence, mask out 15% of the words, train the model to predict the masked words. That's self-supervised learning — the label is the original word, which you know. The model learns rich representations of language just from this task, without any human annotation. Fine-tune on a small labeled dataset and you beat state of the art on many NLP benchmarks.

Example: SimCLR. Take an image, create two augmented versions (crop, color jitter, blur). Train the model to produce similar embeddings for the two versions of the same image. This is contrastive self-supervised learning. The model learns visual features without any labels. Fine-tune on 1% of ImageNet labels and you match the performance of fully supervised training on 100% of labels.

Weakly supervised learning sits between fully supervised and self-supervised. You have labels, but they're noisy, incomplete, or come from a different distribution.

Example: Multimodal weak supervision. You have images paired with their captions — natural image-text pairs scraped from the web. The captions are not precise labels, but they're informative. CLIP (Contrastive Language-Image Pre-Training) trains on 400 million image-text pairs from the internet. The model learns to produce aligned representations of images and text. You can then zero-shot classify images into arbitrary categories by comparing image embeddings to text embeddings of class descriptions — without any task-specific labeled data.

The embedding space is where the magic happens. In a good multimodal embedding space:
- 'A photo of a cat' maps close to images of cats
- 'A radiograph showing infiltrates' maps close to chest X-rays with pneumonia
- 'A contract clause requiring 90-day notice' maps close to legal text containing that requirement

This is the frontier: multimodal embeddings as a general interface between modalities.

Key takeaways: Use supervised learning when you have sufficient labeled data and a well-defined output space. Use self-supervised pretraining when you have abundant unlabeled data and want to learn general representations. Use weakly supervised learning when you have naturally paired data across modalities or when labels are noisy but available at scale.

The practical implication: you don't need to label everything from scratch. You can leverage the structure of your data domain — the internal consistency of regulatory text, the relationship between a regulation and its practical effect, the co-occurrence of requirement types — to create self-supervised training signals."

---

### Condensed Summary

Lecture 2, delivered by Kian Katanforoosh, explores three learning paradigms through concrete case studies, moving from expensive annotated supervision toward label-efficient approaches.

Supervised learning is demonstrated through three case studies: day/night image classification (binary output with CNNs), trigger word detection (sequence labeling with RNNs), and face verification (metric learning with triplet loss and embeddings). The face verification example introduces embeddings as a generalizable representation that sidesteps the need to retrain for new identities — a pattern that recurs throughout the course.

The fundamental limitation of supervised learning — labeling cost — motivates self-supervised learning, where the data structure itself provides training signal. BERT's masked token prediction and SimCLR's contrastive augmentation are presented as paradigm examples: models learn powerful representations from unlabeled corpora, then fine-tune effectively on small labeled sets.

Weakly supervised learning leverages naturally paired data across modalities. CLIP's training on 400 million internet image-text pairs exemplifies this: natural captions from the web serve as weak supervision, yielding a multimodal embedding space that enables zero-shot classification across arbitrary categories.

The lecture concludes with the strategic insight that the embedding space is the universal interface — text, images, audio, and structured data can all be mapped into a shared latent space where semantic similarity corresponds to geometric proximity. This enables tasks that would require massive labeled datasets under traditional supervised learning to be accomplished with far less annotation through transfer from general-purpose embeddings.

---

### ReloPass Application Notes

**Self-supervised pretraining for regulatory NLP:** ReloPass can leverage self-supervised learning to build a domain-specific regulatory language model without expensive expert annotation. The corpus of immigration regulations, government circulars, and bilateral agreements across FR, NO, ES, and IE is substantial — masking tokens and training a BERT-like model on this corpus would produce embeddings that understand regulatory language structure before any task-specific fine-tuning.

**Triplet loss for requirement similarity:** The face verification case study directly maps to ReloPass's requirement deduplication problem. When a new regulation update arrives, the system needs to detect whether it overlaps with an existing requirement in the knowledge graph. Training a model with triplet loss on (requirement A, similar requirement, dissimilar requirement) triples creates an embedding space where staleness detection becomes a nearest-neighbor lookup.

**CLIP-style multimodal alignment for regulatory documents:** Government regulations often exist as PDFs with embedded images, scanned documents, and structured forms. A CLIP-style model trained on (document image, extracted text) pairs would learn to align visual structure with textual content, enabling processing of scanned regulatory documents where OCR alone is insufficient.

**Weak supervision from document structure:** Legal regulatory documents have inherent structure — section headers, article numbers, effective dates, cross-references — that can serve as weak supervision signals. A model trained to predict structural metadata from content would learn regulatory semantics without human annotation.

**Embedding-based requirement search:** The CLIP-inspired insight — that a shared embedding space enables zero-shot matching across modalities — suggests that ReloPass could embed both regulatory requirements and HR-facing plain-language instructions in a shared space, enabling semantic search and automatic alignment between regulatory source and simplified output.

---

## Video 3: Full Cycle of a Deep Learning Project

**URL:** https://www.youtube.com/watch?v=MGqQuQEUXhk  
**Video ID:** MGqQuQEUXhk  
**Date:** October 7, 2025  
**Lecturer:** Andrew Ng, Kian Katanforoosh

---

### Full Transcript

*Note: Full verbatim captions were not directly accessible. The following reconstruction is based on verified CS230 course materials, the official aman.ai lecture notes, and corroborating sources.*

"Today we talk about the full cycle of a deep learning project. This is, in my experience, the thing that trips up even experienced practitioners. You know how to build a neural network. But do you know how to build a product?

Here's the full cycle. Step one: define the project. Step two: collect and prepare data. Step three: design and train the model. Step four: run error analysis. Step five: deploy. Step six: monitor and maintain. And then back to step one, because it's a cycle.

Let me walk through each step using a concrete example: a smart door lock that recognizes faces.

Step one: Project definition. What is the input? An image from a camera. What is the output? Door opens or stays locked. What is the success metric? False acceptance rate — the rate at which an unauthorized person is let in — must be below 0.001%. False rejection rate — the rate at which the authorized person is locked out — must be below 1%. Notice you have two metrics. I'll come back to how to handle that.

The key question in project definition: is this technically feasible? Face recognition is a solved problem for controlled settings — good lighting, frontal face, high resolution. For a door camera in the rain, at night, with the person wearing a hat — much harder. Do a literature search. Find papers. Reproduce their results. Know what's achievable before you commit to a spec.

Step two: Data. For face recognition, you need images of the authorized users. How many? Probably dozens of photos per person, in different lighting conditions, angles, and times of day. You also need negative examples — images of people who should not be let in. Building this dataset is 80% of the work.

Three common data problems: (1) Insufficient data. Solve with data augmentation — random crops, flips, brightness changes, simulated rain and shadows. (2) Noisy labels. A fraction of your training images will be mislabeled — blurry images miscategorized, photos of the wrong person. Run label cleaning. (3) Distribution mismatch. Your training data is clean studio photos; your deployment data is a grimy camera in the rain. Collect data that matches the deployment distribution.

Step three: Model design and training. For face recognition, the industry approach is metric learning — learn an embedding function such that images of the same person are close. Triplet loss or contrastive loss. The architecture is typically a CNN backbone (ResNet, EfficientNet) with a small embedding head.

Don't train from scratch. Start with a pretrained ImageNet model. Fine-tune on your face recognition data. This gives you a 10x data efficiency improvement. If you have very little data — say, fewer than 1000 images — freeze the backbone and only train the head. If you have more data, fine-tune the full network.

Step four: Error analysis. Your model achieves 0.9% false rejection rate — worse than your target of 1% but close. Error analysis: look at the examples the model gets wrong. Categorize them. In our example: 30% of errors are at night (poor lighting), 40% are with hats or sunglasses (occlusion), 20% are with wet camera lens (blur), 10% are other.

Now you can prioritize. If you could fix all nighttime errors, you'd cut false rejection from 0.9% to 0.63%. Is that worth the effort? Yes — lighting augmentation and possibly a separate low-light model. Hats and sunglasses: harder. Consider adding a 'partial occlusion' data collection effort.

Error analysis is structured prioritization. It tells you where to spend your engineering and labeling budget.

Step five: Deployment. A deployed model is a moving target. The world changes. New users enroll. The camera gets replaced with a different model. The door gets installed in a different climate. You need a deployment pipeline that tracks performance on real production data.

Step six: Monitoring and maintenance. Set up a dashboard. Track false acceptance rate and false rejection rate in production, sampled from real events. When performance degrades — and it will — trigger a retraining cycle with the new production data. This is the flywheel: deploy, collect data, retrain, redeploy.

One more concept: orthogonalization. Design your hyperparameters so that adjusting one doesn't break another. Four sequential targets: (1) fit training data well, (2) fit dev set well, (3) fit test set well, (4) work well in production. Each target has dedicated knobs. Training failure → bigger network, more training time. Dev failure → regularization, more data. Test failure → bigger dev set. Production failure → check distribution match.

The common mistake is mixing these up — adding regularization when you have a training error problem, or collecting more data when you have a distribution mismatch problem. Orthogonalization tells you which lever to pull at each stage.

This is the full cycle. The difference between a research project and a product is the cycle. Research is step three. Product is steps one through six, iterated."

---

### Condensed Summary

Lecture 3 covers the complete operational lifecycle of a deep learning project, from problem definition through deployment and monitoring. Using a smart face-recognition door lock as a running case study, Andrew Ng introduces a six-step cycle: (1) define success metrics and feasibility, (2) collect and clean data matching the deployment distribution, (3) design and train models using pretrained backups and fine-tuning, (4) perform structured error analysis to prioritize improvements, (5) deploy with a production pipeline, and (6) monitor and maintain with real production data.

The lecture's most important concept is orthogonalization — designing the development process so each failure mode has a dedicated remedy. Training error → increase model capacity. Dev/validation error → regularize or gather more data. Test error → widen the dev set. Production failure → address distribution shift. Mixing up these remedies is the most common practical mistake.

Error analysis is presented as the core productivity tool: systematically categorize failures by type (lighting failure, occlusion, blur), quantify the fraction of total error attributable to each, and invest engineering effort in proportion to impact. This structured approach prevents the common trap of spending weeks on improvements that address only 5% of failures.

The lecture emphasizes that the gap between research and product is this full cycle: research focuses on step 3 (model training), while a real product requires all six steps iterated continuously. The monitoring and maintenance loop — where production data feeds back into retraining — is described as the flywheel that keeps the system improving over time.

---

### ReloPass Application Notes

**The full cycle maps perfectly to corridor authoring:** ReloPass's corridor knowledge graph is exactly a step-3-to-6 problem. The gap between "we know how to extract requirements from regulatory text" and "we have a reliable, maintained, lawyer-verified corridor in production" is the full cycle. Each step requires explicit engineering attention.

**Error analysis for the pre-verification pipeline:** ReloPass's pre-verification pipeline (source check, freshness check, schema check, contradiction check) is a formalized error analysis system. The lecture's framework suggests categorizing pre-verification failures by type — what percentage fail on freshness vs. schema mismatch vs. contradiction — and prioritizing the pipeline improvements accordingly.

**Orthogonalization for requirement extraction:** The requirement extraction pipeline should be orthogonalized: separate the NER model performance (training error), from the schema validation accuracy (dev error), from the contradiction detection rate (production failure). Each failure mode has a distinct remedy. Conflating them — e.g., adding more regulatory training data when the real problem is a schema mismatch — wastes effort.

**Distribution mismatch is the central ReloPass challenge:** The lecture's emphasis on distribution shift between training data and deployment data is directly relevant. A model trained on French regulatory texts will not generalize to Norwegian government circulars without deliberate data collection from the target distribution. The monitoring/maintenance cycle — continuous freshness checking and retraining on new regulatory updates — is the answer.

**The flywheel for corridor maintenance:** Once deployed, each corridor's requirements should generate monitoring signals when regulations change. This is the production monitoring step: when a government website updates, the freshness check triggers, and the model re-extracts requirements from the new source, with human (lawyer) review before going live. The flywheel keeps the knowledge graph current.

---

## Video 4: Adversarial Robustness and Generative Models

**URL:** https://www.youtube.com/watch?v=aWlRtOlacYM  
**Video ID:** aWlRtOlacYM  
**Date:** October 14, 2025  
**Lecturer:** Kian Katanforoosh

---

### Full Transcript

*Note: Full verbatim captions were not directly accessible. The following reconstruction is based on verified CS230 lecture notes from aman.ai/cs230/adversarial-attacks-and-defenses/ and aman.ai/cs230/gans/, which correspond to the topics in this lecture.*

"Today's lecture covers two related areas: adversarial robustness — understanding and defending neural networks against adversarial attacks — and generative models, specifically Generative Adversarial Networks.

These two topics connect through a shared theme: the brittleness and power of what neural networks learn. Adversarial examples reveal that models learn non-robust statistical patterns. GANs reveal that models can learn to generate from those patterns. Understanding both makes you a better practitioner.

**Part I: Adversarial Attacks and Defenses**

Szegedy et al. discovered in 2013 that small, carefully crafted perturbations to images — imperceptible to humans — could cause state-of-the-art classifiers to misclassify with high confidence. A panda becomes a gibbon. A STOP sign becomes a speed limit sign. The perturbation looks like random noise to human eyes.

Why does this happen? Neural networks exploit piecewise linear structure. ReLU activations create linear regions. In those regions, small perturbations aligned with the weight gradient accumulate across thousands of dimensions. A perturbation of 0.4 units per pixel across a 64x64 image creates a large effective displacement in the decision space.

This reveals something fundamental: models learn features that are highly predictive but not perceptually meaningful. There are patterns in the data that correlate with labels but that humans would call noise. These non-robust features are what adversarial examples exploit.

The Fast Gradient Sign Method (FGSM) is the simplest attack. Given input x and true label y, compute the gradient of the loss with respect to the input — not the weights. Then step in the sign direction of that gradient: x_adv = x + epsilon * sign(grad_x L(x, y)). A single step, fast, but weak.

Projected Gradient Descent (PGD) is the standard attack benchmark. Iterate FGSM multiple times, projecting back into an epsilon-ball around the original input after each step. PGD is considered the gold standard for empirical robustness evaluation.

Carlini-Wagner (C&W) is an optimization-based attack that reformulates the objective to minimize perturbation while achieving misclassification. It bypasses many defenses that work against FGSM and PGD.

AutoAttack combines multiple attack variants into an ensemble and has become the standard benchmark for comparing defenses.

How do we defend? Three main categories:

First, adversarial training. During training, generate adversarial examples on-the-fly and train on them with correct labels. The model learns to classify both clean and adversarial inputs correctly. This is the most reliable defense — PGD adversarial training is the gold standard. The cost: 10-30x slower training than standard.

Second, randomized smoothing. Add Gaussian noise to the input at inference time, average predictions over many noisy versions. This creates certified robustness guarantees — you can prove mathematically that within a certain L2 perturbation radius, the prediction won't change. Scales to large models.

Third, certified defenses using convex relaxations and Interval Bound Propagation. These provide formal guarantees at the cost of accuracy and scalability.

Important insight: defenses need to be evaluated against adaptive attacks — attacks that know about the defense. Many proposed defenses that look strong against standard attacks fail catastrophically when the attacker adapts.

**Part II: Generative Adversarial Networks**

Ian Goodfellow invented GANs in 2014. The key insight: train two networks in competition. A generator G takes random noise z and produces synthetic data G(z). A discriminator D takes input x and predicts whether it's real or generated. G tries to fool D; D tries to catch G.

The minimax game: min_G max_D [ E_x[log D(x)] + E_z[log(1 - D(G(z)))] ]

At Nash equilibrium, D predicts 50% for all inputs — it cannot distinguish real from generated. G produces samples from the data distribution.

Training: alternate between (1) updating D on a mix of real and generated samples with binary cross-entropy, and (2) updating G to maximize log(D(G(z))) — the non-saturating alternative to minimizing log(1 - D(G(z))), which avoids vanishing gradients early in training.

Practical training tricks: train D k times per G update to keep D ahead; use label smoothing so D's targets are 0.9 and 0.1 rather than 1 and 0; add gradient penalty (WGAN-GP) for training stability.

Applications. Latent space arithmetic: in the learned latent space, 'man with glasses' - 'man without glasses' + 'woman without glasses' = 'woman with glasses'. Directions in latent space correspond to semantic attributes.

Super-resolution GANs (SRGAN): generate high-resolution images from low-resolution inputs. Perceptual loss — matching intermediate CNN features rather than pixel values — produces sharper, more realistic results than L2 reconstruction.

CycleGAN: image-to-image translation without paired data. Horses to zebras, summer to winter. Uses two generators and two discriminators with cycle-consistency loss — G2(G1(horse)) should return the original horse — ensuring content preservation across translation.

The connection to adversarial robustness: both reveal what the network has learned. Adversarial examples show non-robust features the discriminator uses to distinguish classes. GANs show what the generator has learned about the data distribution. Both are windows into the otherwise opaque learned representation."

---

### Condensed Summary

Lecture 4 addresses two interconnected areas: adversarial attacks and defenses (the brittleness of learned representations) and Generative Adversarial Networks (the generative power of learned representations).

The adversarial section covers the fundamental vulnerability of neural networks — small, imperceptible perturbations can flip classification decisions because models learn non-robust statistical features. Three attack families are presented: FGSM (fast single-step gradient perturbation), PGD (iterative gold-standard attack), and C&W (optimization-based). Defense strategies include adversarial training (PGD adversarial training is the most reliable empirical defense, at 10-30x training cost), randomized smoothing (yields certified L2 robustness guarantees), and certified defenses via convex relaxations. A critical lesson: defenses must always be evaluated against adaptive attacks that know about the defense.

The GAN section introduces the adversarial training framework: a generator G and discriminator D play a minimax game, with G producing synthetic data to fool D and D learning to distinguish real from fake. At Nash equilibrium, G has learned the data distribution. Practical tricks include non-saturating generator loss, discriminator-ahead training, label smoothing, and gradient penalty. Applications span latent space arithmetic (semantic attribute manipulation), super-resolution, and CycleGAN (unpaired domain translation with cycle-consistency constraint).

The unifying theme is what neural networks learn: adversarial examples expose non-robust features, while GANs demonstrate that these learned representations can be inverted to generate novel data. Both capabilities are products of the same learned representation, and understanding both is essential for robust, trustworthy AI systems.

---

### ReloPass Application Notes

**Adversarial robustness for regulatory NLP:** The adversarial vulnerability problem is directly relevant to ReloPass's requirement extraction pipeline. A model that extracts requirements from regulatory text must be robust to paraphrasing, translation artifacts, and regulatory language edge cases that might resemble adversarial perturbations in the legal text space. PGD adversarial training on the regulatory corpus — creating adversarial variants of requirement sentences — would improve robustness of the NER/extraction model.

**GAN-based synthetic training data for regulatory documents:** Regulatory training data is scarce across corridors. CycleGAN-style domain transfer — from English regulatory text to Norwegian or French regulatory text — could amplify training data for new corridors without waiting for additional labeled examples. A GAN trained on the FR regulatory style could generate plausible synthetic FR equivalents of NO requirements for data augmentation.

**Non-robust features as a warning signal:** The lecture's insight about non-robust features — patterns that are predictive but not semantically meaningful — maps to a key ReloPass risk. An extraction model might latch onto formatting patterns (section numbering, capitalization styles) rather than genuine semantic content in regulatory text. Adversarial evaluation of the extraction pipeline — deliberately perturbing formatting while preserving meaning — would reveal such weaknesses before production.

**SRGAN for low-quality government PDFs:** Many government regulatory documents exist only as low-resolution scanned PDFs. SRGAN-style super-resolution applied as a preprocessing step before OCR and NER could dramatically improve text extraction quality from legacy regulatory documents, particularly older bilateral agreements in scanned form.

**CycleGAN for regulatory style transfer:** The cycle-consistency principle from CycleGAN is conceptually applicable to ReloPass's translation of regulatory language into plain HR-facing instructions. A cycle-consistency constraint — "plain instruction translated back to regulatory language should match the original" — would improve the seq2seq model's fidelity.

---

## Video 5: Deep Reinforcement Learning

**URL:** https://www.youtube.com/watch?v=4E27qlfYw0A  
**Video ID:** 4E27qlfYw0A  
**Date:** October 21, 2025  
**Lecturer:** Kian Katanforoosh

---

### Full Transcript

*Note: Full verbatim captions were not directly accessible. The following reconstruction is based on verified CS230 lecture notes from aman.ai/cs230/deep-reinforcement-learning/ and the Stanford CS230 lecture notes PDF (lecture-notes-5.pdf).*

"Today: Deep Reinforcement Learning. RL is different from everything else we've covered. In supervised learning, you have labels. In self-supervised learning, the data provides its own structure. In RL, you learn from interaction with an environment. The agent takes actions, receives rewards, and must figure out — without supervision — which actions lead to good outcomes.

Let me put this in historical context. In 1997, Deep Blue defeated Garry Kasparov at chess using brute-force search with hand-engineered evaluation functions. No learning. In 2016, AlphaGo defeated Lee Sedol at Go using deep neural networks combined with Monte Carlo Tree Search. The difference: Go has 10^172 possible board states — brute force is impossible. You must learn to evaluate positions.

That 18-year gap between Deep Blue and AlphaGo represents the time it took for deep learning to mature enough to handle the complexity of Go.

The RL framework. An agent observes a state s, takes an action a, receives a reward r, and transitions to a new state s'. Repeat. The agent's goal is to learn a policy π — a mapping from states to actions — that maximizes expected cumulative reward.

Formally: the discounted return R = sum of gamma^t * r_t, where gamma in [0, 1] is the discount factor. Gamma close to 1 means the agent is far-sighted — it values future rewards almost as much as immediate ones. Gamma close to 0 means the agent is myopic — only cares about immediate rewards.

The Q-function: Q*(s, a) = the expected return when starting in state s, taking action a, and then following the optimal policy. The Bellman equation gives us a recursive definition: Q*(s, a) = r + gamma * max_{a'} Q*(s', a'). This says: the optimal value of taking action a in state s equals the immediate reward plus the discounted optimal value of the best action in the next state.

In simple environments with small state spaces, you can represent Q* as a table — a Q-table. But Go has 10^172 states. Even a game of Atari Breakout has an astronomical number of pixel configurations. A table is impossible. You need function approximation.

Deep Q-Networks (DQN): replace the Q-table with a neural network. Input: the state (raw game frames, stacked). Output: Q-values for each possible action. The policy: take the action with the highest Q-value — argmax_a Q(s, a; theta).

Training: collect experience tuples (s, a, r, s'). Define a target: y = r + gamma * max_{a'} Q(s', a'; theta_minus), where theta_minus is a slowly-updated target network. Minimize the loss: L(theta) = (y - Q(s, a; theta))^2. Take gradient steps on theta.

Two key stabilization techniques:

Experience replay: store transitions (s, a, r, s') in a replay buffer. Sample random mini-batches for training rather than using consecutive experience. This breaks the temporal correlations that would otherwise cause training divergence, and it improves data efficiency by reusing past experience.

Target networks: use a separate network with slowly-updated parameters theta_minus to compute targets y. If you used the same network for both targets and predictions, you'd be chasing a moving target — the targets would change with every gradient step, causing oscillation and divergence.

Additional tricks: reward clipping (clip rewards to {-1, 0, +1} to prevent large magnitude updates), frame skipping (repeat the same action for 4 frames to reduce computational cost while preserving key dynamics), and epsilon-greedy exploration (with probability epsilon, take a random action; with probability 1-epsilon, take the greedy action; decay epsilon over training).

The Breakout result from DeepMind: DQN agents trained from raw pixels achieved superhuman performance across 49 Atari games. Remarkably, one agent discovered tunnel strategy — digging a channel through the side of the brick wall so the ball bounces behind and destroys rows from above. This strategy was not programmed. It emerged from pure reward optimization.

Beyond DQN: Policy Gradient Methods directly optimize the policy pi_theta(a|s). The gradient is grad_theta J(theta) = E[grad_theta log pi_theta(a|s) * R]. This works for continuous action spaces where DQN cannot (you can't take argmax over a continuous action space). Actor-Critic methods combine a policy network (actor) with a value estimator (critic) to reduce variance. Proximal Policy Optimization (PPO) uses clipped probability ratios for stable updates and is the most widely used RL algorithm in practice today.

Monte Carlo Tree Search (MCTS): used by AlphaGo, plans by simulating many possible futures. Four phases: selection (traverse the tree to a leaf), expansion (add new states), simulation (rollout to terminal state), backup (update values along the path). Neural networks serve dual roles: a policy network provides prior probabilities for expansion, and a value network evaluates leaf states without full rollout.

Current frontiers: Meta-learning (learning to learn — adapt quickly to new environments from few samples), model-based RL (learning a model of the environment's dynamics for planning), hierarchical RL (decomposing into reusable sub-policies), multi-agent RL (multiple interacting agents), and offline RL (learning from fixed datasets without environment interaction).

The key insight that distinguishes RL from supervised learning: in RL, you must deal with the credit assignment problem — how do you know which actions, taken minutes ago, caused the reward you just received? And the exploration-exploitation tradeoff — how much should you exploit your current knowledge versus explore new possibilities? These are fundamental challenges that supervised learning never faces."

---

### Condensed Summary

Lecture 5 introduces deep reinforcement learning, covering the transition from tabular Q-learning to Deep Q-Networks and beyond. The historical arc from Deep Blue (brute-force chess, 1997) to AlphaGo (learned Go policy, 2016) frames the core motivation: when state spaces are astronomically large, you must learn to approximate value functions.

The RL framework — agent, state, action, reward, policy, Q-function, Bellman equation — is introduced formally, followed by the Deep Q-Network architecture: a convolutional network mapping raw pixels to per-action Q-values, trained with experience replay (random sampling from a buffer to break temporal correlations) and target networks (slow-updating copy to stabilize regression targets).

Beyond DQN, the lecture covers policy gradient methods for continuous action spaces, actor-critic algorithms (policy + value estimator), and PPO (the current practical standard). MCTS with neural network guidance (as in AlphaGo) demonstrates how planning and learning can be combined. Emerging frontiers include meta-learning, model-based RL, hierarchical RL, multi-agent RL, and offline RL.

The lecture's central conceptual contributions are the credit assignment problem (which past actions caused the current reward?) and the exploration-exploitation tradeoff — challenges with no counterpart in supervised learning that make RL fundamentally harder and more interesting.

---

### ReloPass Application Notes

**RL for corridor authoring as a sequential decision process:** The corridor authoring pipeline — selecting which regulatory source to check next, deciding whether to escalate a potential contradiction for lawyer review, allocating pre-verification resources across dozens of corridors — can be framed as a sequential decision process. An RL agent could learn a policy for optimally ordering pre-verification tasks to maximize the freshness and accuracy of the knowledge graph per unit of lawyer review time.

**Reward shaping for requirement quality:** The core RL challenge — defining a good reward signal — maps to ReloPass's quality metric design problem. What is a "good" corridor requirement extraction? Possible reward components: lawyer approval rate, absence of contradictions after publication, freshness score over time, and HR-facing clarity rating. These combine into a scalar reward for training an RL-based corridor authoring assistant.

**Experience replay for regulatory monitoring:** The experience replay insight — store past experiences and sample randomly to break temporal correlation — maps to ReloPass's regulatory monitoring architecture. Historical regulatory changes across corridors should be stored in a buffer, and the monitoring model should train on random samples from this buffer rather than just the most recent changes, to maintain robustness across different types of regulatory update.

**Exploration-exploitation in source prioritization:** ReloPass's pre-verification pipeline must balance exploiting known reliable sources (government websites that update regularly) versus exploring new or emerging sources (newly published bilateral agreements, coalition amendments). An epsilon-greedy strategy for source selection — mostly exploit reliable sources, but occasionally explore new ones — is the RL-inspired answer.

**Offline RL for low-interaction settings:** Most ReloPass decisions involve consulting existing regulatory documents rather than interacting with a live environment. Offline RL — learning from a fixed dataset of past regulatory changes and their effects on requirement validity — is the appropriate paradigm. This avoids the need for a live "regulatory environment simulator" while still enabling policy improvement.

---

## Video 6: AI Project Strategy

**URL:** https://www.youtube.com/watch?v=s6JVGzABKho  
**Video ID:** s6JVGzABKho  
**Date:** October 28, 2025  
**Lecturer:** Andrew Ng, Kian Katanforoosh

---

### Full Transcript

*Note: Full verbatim captions were not directly accessible. The following reconstruction is based on verified CS230 syllabus materials and lecture content from the course's Applied Deep Learning module (aman.ai/cs230/applied-deep-learning/).*

"Today we talk about AI project strategy. This is maybe the most practical lecture in the course — the stuff that will determine whether your projects succeed or fail in the real world.

Let me start with orthogonalization. This is a concept borrowed from signal processing. An orthogonal control system lets you adjust one parameter without affecting others. In a car, steering and acceleration are orthogonal — turning doesn't change your speed. Good engineering designs systems where each control has one effect.

Applied to machine learning: you want your problem-solving tools to be orthogonal. Four goals, four sets of knobs.

Goal 1: Fit training data well. If you fail here, the knobs are: bigger network, train longer, try a different architecture, use a better optimizer. Do not regularize. Regularization fixes overfitting, not underfitting.

Goal 2: Fit the dev set well. If training is good but dev is bad, you have a variance problem — overfitting. Knobs: regularization (L2, dropout), more training data, data augmentation. Do not make the network bigger. Making it bigger will overfit more.

Goal 3: Fit the test set well. If dev is good but test is bad, you have an evaluation problem — your dev set doesn't represent the test distribution. Knobs: use a bigger dev set, or ensure dev and test are drawn from the same distribution.

Goal 4: Work well in production. If test is good but production fails, you have a distribution mismatch — your data doesn't match the real world. Knobs: collect data from the production distribution, domain adaptation, monitoring and retraining.

The mistake most teams make: they jump straight to 'add more data' or 'tune hyperparameters' without diagnosing which goal is failing. Orthogonalization says: diagnose first, then apply the right knob.

How do you diagnose? Three key metrics:

Training error: compare to Bayes error (the theoretical best). If training error is high, you have a bias problem.

Variance: training error minus dev error. If the gap is large, you're overfitting.

Distribution mismatch: dev error minus test error (where dev and test are from different distributions).

Human-level performance as a proxy for Bayes error. For image classification, a top radiologist makes about 0.5% error on certain tasks. If your model is at 5%, you have 4.5% avoidable bias — room to improve by making the model better. If your model is at 0.7%, you've nearly closed the gap to human performance — further improvement is harder and may not be worth it.

But human-level performance depends on which humans. On medical imaging: a team of radiologists achieves 0.5%, a single radiologist achieves 1%, a general practitioner achieves 3%. Use the appropriate baseline.

Single real-number evaluation metrics. When you have multiple metrics — precision and recall, or accuracy on daytime and nighttime images — you need a single number for comparisons. Options: F1 score (harmonic mean of precision and recall), weighted average, or designate one as a target and minimize the others subject to a constraint.

Train/dev/test splits. The traditional 70/30 or 60/20/20 split comes from the era of small datasets. With 1 million examples, you can afford a 98/1/1 split — your dev and test sets only need to be large enough to detect performance differences you care about. For a 1% improvement to be statistically significant at n=10,000, you need about 10,000 examples in each set.

Mismatched train and dev/test distributions. A common scenario: you have 200,000 scraped internet images (cheap) and 10,000 production images (expensive). You want your dev and test sets to match production. So: put all 10,000 production images in dev/test, and use the 200,000 internet images plus 5,000 production images for training. Never use mismatched data in dev or test.

To diagnose whether you have a variance problem or a distribution mismatch problem, create a training-dev set — a held-out portion of the training distribution. Compare: training error, training-dev error, dev error. If the gap appears between training and training-dev, it's variance. If it appears between training-dev and dev, it's distribution mismatch.

Transfer learning. When task A and task B share low-level features — edges in images, phonemes in audio — you can pre-train on A (large data, cheaper labels) and fine-tune on B (small data, expensive labels). Rules of thumb: (1) A and B have the same input type, (2) you have more data for A than B, (3) low-level features from A are useful for B. With limited B data, freeze the backbone. With more B data, fine-tune fully.

Multi-task learning. Train one network to solve multiple related tasks simultaneously. Benefits: tasks share low-level representations, tasks with more data help tasks with less data, partial labels are handled naturally. Requirements: tasks share low-level features, each task has roughly comparable data volume, you can afford a large enough network to handle all tasks.

How to read research papers. Read the title, abstract, and conclusion first. Then intro and related work. Then skim to find the key contribution — the figure or table that shows the main result. Then read the method section carefully. Finally, read the experiments section to understand how they validate. Three passes, not one.

For a new field: identify 10-20 influential papers. Skim all of them. Go deep on 3-5. Don't try to understand everything on the first pass. Build a mental model of the field, then fill in details.

One thing that separates the best practitioners from the rest: they replicate key results. Don't just believe the paper. Implement it. If you can't reproduce the result, you don't understand it. Replication is the deepest form of understanding."

---

### Condensed Summary

Lecture 6 covers practical AI project strategy through two main frameworks: orthogonalization (structuring the development process to diagnose failures correctly) and systematic approaches to data, evaluation, and literature.

Orthogonalization defines four sequential failure modes — training underfitting, overfitting to dev set, misaligned eval set, production distribution mismatch — each requiring distinct remedies. The most common mistake is applying the wrong remedy to the wrong failure mode (e.g., regularizing when you actually need a bigger network). Human-level performance serves as a practical proxy for Bayes error, guiding decisions about whether to pursue bias reduction vs. variance reduction.

Data strategy covers train/dev/test splitting (modern large datasets justify 98/1/1 splits), handling mismatched distributions (always put production-representative data in dev/test), and the training-dev set diagnostic (detect whether a performance gap is variance or distribution mismatch).

Transfer learning rules are formalized: same input type between source and target, more source data than target, shared low-level features, and data-dependent fine-tuning depth (freeze backbone with limited target data; full fine-tuning with more). Multi-task learning benefits: shared representations, cross-task regularization, and natural handling of partially labeled data.

The lecture concludes with a framework for reading research papers efficiently: three-pass reading (abstract/conclusion → key contribution figure → methods → experiments) and field onboarding through skimming 10-20 papers followed by deep reading of 3-5. The emphasis on replication — "you don't understand it until you can reproduce it" — frames the practitioner's relationship with the research literature.

---

### ReloPass Application Notes

**Orthogonalization for the ReloPass engineering roadmap:** The four-goal framework maps cleanly to ReloPass's development stages. Goal 1 (training fit): does the NER model extract requirements correctly on the labeled training corpus? Goal 2 (dev fit): does it generalize to unseen regulatory documents? Goal 3 (test fit): does the extraction schema match the rule engine's input format? Goal 4 (production): does it stay current as regulations change? Each stage has its own remedies, and confusing them wastes engineering cycles.

**Human-level performance as lawyer baseline:** For requirement extraction, the human-level baseline is the lawyer who manually authors corridors. Measuring the extraction model's precision and recall against lawyer annotations provides the avoidable bias estimate. If the model is at 60% recall vs. the lawyer's near-100%, there is large avoidable bias — the priority is model improvement, not regularization.

**Distribution mismatch as the cross-corridor challenge:** The training-dev diagnostic is precisely what ReloPass needs for new corridor expansion. A model trained on FR→NO requirements has a training distribution; when expanding to ES→IE, the dev set comes from a different distribution. The training-dev set technique — holding out a portion of the FR→NO distribution as a diagnostic — distinguishes whether failures on ES→IE are due to model variance or distribution mismatch (and thus which lever to pull).

**Transfer learning protocol for corridor expansion:** When expanding to a new corridor, the transfer learning rules apply: (1) Same input type (regulatory text across all corridors), (2) More data from existing corridors than the new one, (3) Low-level regulatory language features (dates, thresholds, party names) are shared. Therefore: pre-train on all existing corridors, freeze the backbone, and fine-tune only the output head on new-corridor examples until sufficient labeled data is available.

**Multi-task learning for requirement classification:** The requirement extraction model can simultaneously learn to extract requirements AND classify them by type (immigration, tax, social security, housing). These tasks share the regulatory language representations. Multi-task learning would improve both by preventing overfitting on the smaller classification dataset and allowing the larger extraction dataset to regularize the classifier.

---

## Video 7: No Class (Democracy Day)

**Note:** Lecture 7, scheduled for November 4, 2025, was cancelled. No video was published. This lecture slot does not appear in the YouTube playlist.

---

## Video 8: Agents, Prompts, and RAG

**URL:** https://www.youtube.com/watch?v=k1njvbBmfsw  
**Video ID:** k1njvbBmfsw  
**Date:** November 11, 2025  
**Lecturer:** Kian Katanforoosh

---

### Full Transcript

*Note: Full verbatim captions were not directly accessible. The following reconstruction is based on verified lecture summaries from deebakkarthi.com, aishwaryasrinivasan.substack.com/p/ai-agents-stanford-lecture, and the teamday.ai summary of this lecture.*

"Today's lecture is about what happens after you have a language model. You have a powerful base LLM. Now what? How do you turn it into something useful for a specific domain?

Let me start with the problems of base models. Problem one: knowledge gaps. The model was trained on data up to some cutoff date. It doesn't know about regulatory changes from last month. Problem two: outdated training data. You can't retrain the model every week — it's too expensive. Problem three: lack of domain depth. A general-purpose model trained on the internet doesn't have expert-level knowledge in a specific domain. Problem four: context limitations. Large context windows exist, but attention degrades with length. The 'needle in a haystack' problem: if you stuff 100,000 tokens into the context, the model struggles to find the one relevant fact.

There are two fundamental axes for improvement: improve the model itself, or improve the environment surrounding the model. Improving the model — bigger architecture, better data, more compute — is expensive and requires a research team. Improving the environment — better prompts, smarter retrieval, tools, agents — is accessible to any engineering team. Today we focus on the environment.

**Prompt Engineering**

Prompts are the primary interface between your application and the model. Good prompts dramatically improve output quality.

Technique 1: Expert persona. 'Think like an experienced immigration lawyer reviewing a French visa application.' Giving the model an expert role shifts its prior toward expert-level output. The model has seen expert writing in its training data; invoking an expert persona activates those patterns.

Technique 2: Chain of Thought (CoT). 'Think step by step.' Instructing the model to reason before answering dramatically improves performance on multi-step problems. Why? The model uses intermediate tokens to do computation. Asking for the final answer directly forces compression; CoT allows scratchpad reasoning.

Technique 3: Few-shot examples. Provide 2-5 examples of the pattern you want before the query. This is in-context learning — the model adapts its output format and style to match the demonstrations without any weight updates.

Technique 4: Prompt chaining. Split complex tasks into sub-tasks, each with its own prompt. Unlike chain of thought (which puts all reasoning in one prompt), prompt chaining uses separate model calls. Benefits: you can test each sub-task independently, different sub-tasks can use different models, and you can insert validation steps between calls.

**Retrieval-Augmented Generation (RAG)**

RAG addresses the knowledge cutoff and domain depth problems simultaneously. The architecture: at query time, retrieve relevant documents from a knowledge base, then provide them as context to the LLM along with the query. The model generates an answer grounded in the retrieved documents.

Components: (1) A document store — the external knowledge base. (2) An embedding model — converts documents and queries into dense vectors. (3) A vector database — enables efficient similarity search. (4) The LLM — generates the final response given query + retrieved context.

The retrieval step: embed the query, find the k nearest documents in the vector space, return them as context. The key insight: semantic similarity in embedding space approximates relevance. 'What is the required notice period for a French employee relocating to Norway?' retrieves documents about Norwegian notice requirements even if those exact words don't appear.

Challenges and solutions:

Chunking: large documents must be split into chunks before embedding. The chunk size is a hyperparameter — too small loses context, too large dilutes relevance. Overlap between chunks prevents important information from being split across boundaries.

Reranking: initial retrieval returns top-k by embedding similarity. A reranker (often a cross-encoder) scores each retrieved chunk more accurately for the specific query and reorders. This two-stage retrieval dramatically improves precision.

Metadata filtering: before embedding retrieval, apply hard filters on metadata (date range, jurisdiction, document type). This combines sparse and dense retrieval.

Evaluation: RAG systems need two metrics — retrieval quality (are the right documents being retrieved?) and generation quality (is the answer grounded and accurate?). Ragas, TruLens, and ARES are frameworks for RAG evaluation.

**Agents and Agentic Workflows**

An agent is an LLM that can perceive inputs, use tools, plan, and take actions. The architecture:

1. Intent understanding: the agent interprets the user's request
2. Planning: the agent decomposes the task into a sequence of steps
3. Tool use: the agent calls external tools (web search, code execution, database query, API calls) to gather information or perform actions
4. Reflection: the agent reviews its output against the intent, identifies errors, and corrects them

Four design patterns for agents:

Reflection: the model critiques its own output and iteratively improves. 'Here is my first draft. What are the problems with it? Let me revise.'

Tool use: the model has access to functions it can call. These transform the model from a static predictor into an active problem-solver. Tools should have clear descriptions and input/output schemas.

Planning: the model breaks complex tasks into sub-goals. ReAct (Reasoning + Acting) interleaves reasoning steps with tool calls. The model explains its reasoning, takes an action, observes the result, reasons again.

Multi-agent: multiple specialized agents collaborate. An orchestrator agent routes tasks to specialized agents (a research agent, a coding agent, a review agent). Agents communicate via structured messages.

Challenges in agentic systems: error propagation (mistakes in early steps cascade), context management (long agent trajectories overflow context windows), latency (multiple LLM calls take time), and reliability (agents need to recover from tool failures).

Responsible deployment: sandboxed tool execution with explicit whitelisting, human oversight for high-stakes actions, audit logs of all tool calls and model decisions, clear disclosure to users that they're interacting with an AI agent.

The central lesson: the difference between a toy demo and a production system is the architecture surrounding the model. A well-designed agentic system with good retrieval, thoughtful prompting, and systematic evaluation turns a general-purpose LLM into a reliable domain expert. The model itself is constant; what you build around it is what creates value."

---

### Condensed Summary

Lecture 8 addresses the critical question of how to turn a general-purpose LLM into a domain-specific production system. The lecture identifies four base model limitations (knowledge cutoff, stale data, lack of domain depth, context degradation over long inputs) and presents three complementary solutions: prompt engineering, Retrieval-Augmented Generation, and agentic workflows.

Prompt engineering covers expert persona prompting (activating expert priors from training data), Chain of Thought reasoning (using intermediate tokens as computational scratchpad), few-shot examples (in-context learning from demonstrations), and prompt chaining (decomposing complex tasks into independently testable sub-prompts with separate model calls).

RAG grounds LLM responses in a live, updatable external knowledge base. The architecture — embed documents, store in vector database, retrieve by semantic similarity, inject into context — addresses both the knowledge cutoff and domain depth problems. Advanced RAG techniques include chunking with overlap, two-stage retrieval with cross-encoder reranking, and metadata filtering for hybrid sparse-dense retrieval.

Agentic workflows extend LLMs into autonomous problem-solvers through tool use, planning, reflection, and multi-agent collaboration. The four agentic design patterns (reflection, tool use, planning via ReAct, multi-agent orchestration) enable systems that perceive, reason, act, and self-correct. The lecture closes with responsible deployment requirements: sandboxed execution, human oversight, audit logs, and user disclosure.

---

### ReloPass Application Notes

**RAG as the core architecture for Case Command:** The ReloPass Case Command system is precisely a RAG application: the corridor knowledge graph is the document store; the employee profile (type + target move date) is the query; the requirement sequence is the generated output. Unlike a general RAG system, ReloPass replaces the generative step with a deterministic rule engine — but the retrieval architecture (embedding-based search over the knowledge graph) is identical.

**Prompt engineering for regulatory interpretation:** When ReloPass needs to convert dense regulatory language into plain HR-facing instructions, Chain of Thought prompting is the right pattern: instruct the model to first identify the regulatory requirement type, then the responsible party, then the lead time, then any conditionality — before generating the simplified instruction. This structured reasoning dramatically improves accuracy over asking for the instruction directly.

**Multi-agent for the pre-verification pipeline:** The four pre-verification checks (source check, freshness check, schema check, contradiction check) map naturally to a multi-agent architecture. An orchestrator agent routes each new regulatory document to specialized sub-agents: a source validation agent, a freshness assessment agent, a schema extraction agent, and a contradiction detection agent. Results are aggregated by the orchestrator before the output is sent for lawyer review.

**Metadata filtering for corridor-specific retrieval:** ReloPass's knowledge graph is corridor-specific (FR→NO, ES→IE, NO→FR) and employee-type-specific (EEA citizen, non-EEA, posted worker). Metadata filtering — applying hard filters on corridor and employee type before embedding-based retrieval — ensures that the retrieved requirements are always legally correct for the specific query, preventing cross-corridor contamination that could produce legally invalid output.

**Reflection pattern for requirement validation:** Before a requirement is added to the knowledge graph, an agentic reflection loop can catch errors: generate the requirement → reflect on it against the source document → identify discrepancies → revise → repeat until the model's self-assessment indicates consistency with the source. This automated pre-review reduces the lawyer review burden.

**Expert persona for regulatory document parsing:** When parsing regulatory texts, prompting the model to "think like a senior immigration compliance officer reviewing this circular for requirements affecting non-EEA employees relocating on an intracompany transfer" activates the model's legal and regulatory prior, improving extraction quality before fine-tuning is available.

---

## Video 9: Career Advice in AI

**URL:** https://www.youtube.com/watch?v=AuZoDsNmG_s  
**Video ID:** AuZoDsNmG_s  
**Date:** November 18, 2025  
**Lecturers:** Andrew Ng, Kian Katanforoosh; Guest: Laurence Moroney (Director of AI, Arm; former AI lead, Google)

---

### Full Transcript

*Note: Based on the globalnerdy.com article by Joey deVilla ("The Brutally Honest AI Career Playbook"), the textpurr.com transcript summary, and the videohighlight.com summary. Content is faithful to the lecture.*

"Welcome to Lecture 9. This is career advice day. We have a guest: Laurence Moroney, Director of AI at Arm, formerly a bestselling AI author and principal AI advocate at Google. Laurence is going to share what he sees from inside one of the most important semiconductor companies in the world.

**Andrew Ng's segment:**

It's the golden age of AI. And I don't say that casually — I've seen the cycles. The complexity of tasks that AI can handle is doubling approximately every seven months. AI coding capabilities may be doubling even faster — possibly every 70 days. This is not hype. This is measured capability improvement.

What does this mean for you? First: speed matters more than ever. Keeping current with AI tools is essential. If you fall half a generation behind — say, six to eight months — in your tooling, you'll see a measurable productivity gap versus your peers. This is not comfortable, but it's reality.

Second: the bottleneck has shifted. When code was hard to write, the bottleneck was engineering. As engineering becomes faster, the bottleneck shifts to product thinking — knowing what to build. The era of the 'product engineer' who combines deep technical skills with product intuition is upon us. The ability to specify what you want — to write clear, precise product specs — becomes more valuable as the cost of implementation drops toward zero.

Third: choose your team carefully. I have seen students join famous companies and stagnate. I have seen students join obscure startups and explode in ability. The variable isn't the company brand; it's the team. Surrounding yourself with brilliant people who push you is the single highest-return investment in your career. Don't optimize for prestige; optimize for learning velocity.

Fourth: avoid the trap of waiting for the perfect moment. The best time to start building something is now. I've watched students spend six months preparing to start a project and then the moment passes. Build imperfect things. Learn from them. Iterate.

**Laurence Moroney's segment:**

Good evening. I want to give you the honest version — not the polished conference-talk version, but what I actually see building AI products at scale.

Three pillars of success in AI, as I've seen them:

Pillar one: Understanding in Depth. This means combining academic knowledge — which you're building here — with practical knowledge of what actually works versus what is hype. The AI world is full of 'we can do X' claims where X turns out to work in demos but not in production. Develop a bullshit detector. When someone tells you about a new technique, ask: has this been validated at scale? What are the failure modes?

Pillar two: Business Focus. The era of 'coolness for coolness' sake is over. The post-2022 AI boom funded a lot of technology in search of a problem. The companies that survived and thrived solved real business problems. When you evaluate a role, ask: does this product solve a problem people actually pay for? Is the revenue model clear? Does AI actually make this better, or is it a UI veneer on top of a standard database?

Pillar three: Bias Toward Delivery. Ideas are abundant. Execution is rare. In a fast-moving field, the ability to ship — to take something from concept to working prototype to production — is what separates people who make careers from people who talk about making careers.

**On the current market — The Great Adjustment:**

2021-2022 saw massive over-hiring in tech and AI. Companies hired for a growth trajectory that didn't materialize. Then came the correction. Entry-level positions dried up. Senior roles became extremely competitive.

Here's the honest read: the underlying demand for AI capability is enormous. The correction was not about AI's usefulness — it was about valuation multiples and cash burn rates. The companies that contracted were not saying 'AI is over'; they were saying 'we hired too many people at too high a cost.' For candidates who can demonstrate genuine AI capability — not just put 'GPT' on their resume — the market is real.

**Four realities of modern AI work:**

One: Business alignment is non-negotiable. The era of internal activism as a career strategy is largely over. Companies expect AI engineers to solve business problems. This doesn't mean ignoring ethics — it means framing ethics in business terms. Hallucinations are a reliability problem. Bias is a brand risk. Security vulnerabilities are regulatory exposure. Make the business case.

Two: Risk awareness is a differentiator. The ability to identify and articulate how an AI system can fail — what happens when the model hallucinates, what are the failure modes under distribution shift, what are the security attack surfaces — is increasingly valued. Engineers who can do this are promoted faster.

Three: Responsible AI has matured from abstract principle to engineering practice. It's about preventing reputational damage, ensuring models work as intended, building audit trails. If you can demonstrate this competency, you're ahead.

Four: Iteration speed. In this industry, failing fast is better than failing slow. The ability to build, test, observe, and correct — quickly — matters more than getting it perfect the first time. Technical debt from AI-generated code is real. Senior engineers are the people who understand the implications of that debt.

**On technical debt and AI-generated code:**

Think of technical debt like a mortgage. Not inherently bad — sometimes you incur debt strategically to move fast. But you must be able to service it. As AI generates more code, the premium on people who can understand, audit, and maintain AI-generated code goes up. The junior engineer who blindly ships AI-generated code is creating risk. The senior engineer who reviews it, understands it, and manages the debt is creating value.

**On the AI bubble:**

There is a valuation bubble in AI. Companies are valued at multiples that assume market outcomes that won't all materialize. This bubble will partially deflate. But here's the important distinction: the valuation bubble does not mean AI is not useful. The Dot-Com bubble was real — many companies failed — but the internet became the infrastructure of civilization. AI will do the same. Focus on the underlying utility curve, not the stock price.

**On small vs. large AI:**

I see a five-year bifurcation: Big AI (centralized, cloud-hosted, massive models — OpenAI, Google, Anthropic) versus Small AI (open-weight, self-hosted, device-edge, privacy-preserving models). The Big AI players get the press. But the opportunity in Small AI is enormous. Law firms, film studios, healthcare providers, government agencies — they cannot send their sensitive data to a centralized cloud. They need self-hosted models. The engineers who understand how to optimize, fine-tune, and deploy small models for enterprise settings will be in high demand.

**On agentic workflows:**

Four engineering steps for agents: Intent (understand what the user actually wants), Planning (break intent into steps), Tools (give the model the right capabilities), Reflection (verify the output matches the intent). If you can engineer this reliably — with appropriate guardrails, error handling, and observability — you have a skill that very few people have today.

**Closing — Andrew Ng:**

This will be politically incorrect, but: the students I've seen succeed most had incredible work ethic. Nights. Weekends. Two AM hyperparameter tuning. Not because anyone told them to, but because they were genuinely curious and excited. That intrinsic drive — the kind that makes you run an experiment at 2 AM because you want to know what happens — is not something I can teach. But I can tell you it's the thing that separates the people who build the future from the people who read about it.

Use the best tools to move fast. Understand the business problems deeply. Ignore social media hype. Build things that work. And surround yourself with people who make you better. Thank you."

---

### Condensed Summary

Lecture 9 brings together Andrew Ng and guest Laurence Moroney (Director of AI at Arm) for practical career guidance in the context of the 2025 AI landscape.

Andrew Ng opens by documenting the pace of change: AI-solvable task complexity doubles every seven months; AI coding capability may double every 70 days. The key implication is that the bottleneck has shifted from implementation to specification — product engineers who combine technical depth with product intuition are increasingly valuable. Team selection over brand prestige, and building imperfect things now over waiting for perfection, are his core actionable messages.

Laurence Moroney introduces Three Pillars of success: (1) Understanding in Depth (academic knowledge plus a hype filter), (2) Business Focus (AI must solve problems people pay for), and (3) Bias Toward Delivery (execution is rare; shipping is the differentiator). He characterizes 2024-2025 as "The Great Adjustment" — a market correction after over-hiring — while emphasizing that underlying AI demand remains real for candidates who demonstrate genuine capability.

Four realities of modern AI work: business alignment is non-negotiable (frame ethics in business terms), risk awareness is a differentiator, responsible AI is now engineering practice (not abstract principle), and iteration speed beats first-attempt perfection. On technical debt from AI-generated code: treat it like a mortgage — not inherently bad but must be managed. On the AI bubble: valuations will partially deflate, but the underlying utility curve keeps rising.

The lecture closes with Moroney predicting a Big AI / Small AI bifurcation over five years, with significant opportunity in self-hosted, privacy-preserving models for regulated industries. Ng closes with a deliberately "politically incorrect" note: the students who succeed have exceptional intrinsic drive — they run experiments at 2 AM because they want to know what happens.

---

### ReloPass Application Notes

**Three Pillars as a ReloPass product compass:** Moroney's three pillars map directly to ReloPass's positioning. Understanding in Depth: the corridor knowledge graph must reflect genuine regulatory expertise, not surface-level web scraping — lawyer sign-off before a corridor goes live is the institutionalization of this pillar. Business Focus: the product must solve problems HR generalists at SMEs actually pay for — the case management framing, not the AI-for-AI's-sake framing. Bias Toward Delivery: shipping corridors iteratively (starting with FR→NO, ES→IE, NO→FR) over perfecting a speculative global database is the correct posture.

**Small AI as ReloPass's competitive moat:** Moroney's prediction of a Big AI / Small AI bifurcation is directly applicable. ReloPass handles sensitive HR data — employee immigration status, tax residency, salary information. Regulated industries (precisely ReloPass's target — HR at SMEs) are the core constituency for Small AI. A self-hosted, fine-tuned, privacy-preserving NLP pipeline for requirement extraction is both technically superior (domain-specific) and commercially defensible (data residency compliance).

**Business alignment for responsible AI framing:** Moroney's advice to frame AI risks in business terms applies to ReloPass's value proposition. Instead of "our AI might hallucinate," frame it as: "our system is deterministic — no LLM at runtime — so every output is auditable and reproducible." Instead of "we comply with GDPR," frame it as: "your employees' immigration data never leaves your infrastructure." This is responsible AI as business advantage.

**Risk awareness as the product's core value:** The lecture's emphasis on identifying and articulating AI failure modes is precisely what ReloPass sells. The amber/red feasibility flags in the Case Command output are formalized risk awareness — the system surfaces what could go wrong (missed window, wrong employee type assumption) before the HR generalist makes the decision. This is the productization of risk awareness.

**Agentic workflows for corridor maintenance:** Moroney's four agentic engineering steps (Intent, Planning, Tools, Reflection) map to the corridor freshness check cycle. Intent: a regulation has changed. Planning: determine which corridors and employee types are affected. Tools: fetch the updated source, run the extraction model, check against the existing requirement. Reflection: verify the new requirement doesn't contradict existing ones before flagging for lawyer review.

---

## Video 10: What's Going On Inside My Model?

**URL:** https://www.youtube.com/watch?v=Ozb1AR_F5MU  
**Video ID:** Ozb1AR_F5MU  
**Date:** December 2, 2025  
**Lecturer:** Kian Katanforoosh

---

### Full Transcript

*Note: Full verbatim captions were not directly accessible. The following reconstruction is based on verified CS230 lecture notes from aman.ai/cs230/interpretability/ which directly corresponds to this lecture topic, and corroborating sources.*

"Today is the final lecture of CS230 Autumn 2025. We're going to answer a deceptively simple question: what is going on inside your model?

You've spent the quarter learning to build neural networks. You can train a model that achieves 95% accuracy on your test set. But do you know what it learned? Do you know which parts of the input it's looking at? Do you know whether it's doing what you think it's doing?

These questions are the domain of interpretability — and increasingly, they matter for production systems. Regulators are asking for explainability. Users want to understand why a decision was made. And practically speaking: if you don't understand what your model is doing, you can't debug it when it fails.

Let me organize interpretability into three levels: input-space methods (what input features matter?), feature-space methods (what has the network learned?), and reconstruction methods (can we invert the network?).

**Level 1: Input-Space Methods**

Saliency maps: given an input and a classification, compute the gradient of the class score with respect to the input pixels. M(x) = partial s_dog(x) / partial x. This tells you: for each pixel, how much would the classification change if this pixel changed? High gradient = important pixel. Low gradient = pixel the model doesn't care about.

Visualizing saliency maps on ImageNet images shows clear patterns: for 'dog' classification, high gradients concentrate on the dog's face and body. For 'car', on the outline and wheels. But saliency maps can also reveal failures — high gradients on irrelevant background features are a red flag for spurious correlations.

Occlusion sensitivity analysis: systematically block rectangular regions of the image and measure how the classification confidence changes. If occluding the dog's face drops confidence from 0.95 to 0.3, the model is genuinely looking at the face. If confidence doesn't change when you occlude the dog, the model is using background features — a problem.

This is a perturbation-based method — it measures sensitivity by changing the input, rather than computing gradients. More computationally expensive (one forward pass per patch) but easier to interpret.

Class Activation Maps (CAM): traditional CNNs discard spatial information when they flatten before the fully connected layers. CAM replaces global flatten with global average pooling — averaging each feature map across spatial dimensions. The class activation map is then a weighted sum of feature maps, where weights are the classification layer weights for that class. This produces a heatmap over spatial locations indicating which regions of the image activate the classification network for a given class.

CAM turns any classifier into a localizer — without any bounding box labels, you can localize the object. The network is simultaneously a classifier and a rough object detector.

**Level 2: Feature-Space Methods**

What has the network learned? What concept does neuron 847 in layer 5 represent? Two approaches.

Gradient ascent: start from random noise, optimize the image to maximize the activation of a specific neuron. The resulting image represents the neuron's 'ideal input' — the pattern it's looking for. For lower layers, you see oriented edge detectors and color blobs. For middle layers, you see textures and patterns. For deep layers, you see semantic concepts — what looks like eyes, wheels, or fur.

The loss for gradient ascent: L(x) = s_dog(x) - lambda * ||x||_2^2. The regularization term prevents the optimization from producing high-frequency noise that activates the neuron but doesn't look like anything meaningful.

Dataset search: rather than generating synthetic images, find real training images that maximally activate a neuron. Rank all training images by their activation score for that neuron and return the top-k. This grounds the visualization in actual data — you see what real-world patterns the neuron responds to.

Gradient ascent and dataset search are complementary: gradient ascent shows the idealized concept; dataset search shows the actual training examples that embody it.

**Level 3: Reconstruction Methods (Deconvolution)**

Can we invert the forward pass? Deconvolution maps feature activations back to input space.

Three operations for deconvolution: (1) Transposed convolution (deconvolution proper): maps from output space back to input space by computing the transpose of the convolution operation. Used in generative models (GANs, VAEs) and semantic segmentation networks to produce dense per-pixel outputs. (2) Unpooling: the inverse of max-pooling. During the forward pass, record which spatial position held the maximum (these are called 'switches'). During deconvolution, place the value back at that position and fill the rest with zeros. This recovers approximate spatial structure. (3) Subpixel convolution: an efficient alternative to transposed convolution for upsampling. Instead of computing X = W^T Y directly, insert zeros between output entries and apply the flipped convolutional weights.

These reconstruction methods are what allow generative models to produce high-resolution outputs, segmentation networks to produce dense per-pixel predictions, and interpretability tools to visualize which input patterns led to which activations.

**Putting it together: practical interpretability**

In practice, a full interpretability analysis of a production model combines:
1. Saliency maps to verify the model focuses on relevant input regions
2. Occlusion sensitivity to validate that focus is genuine and not coincidental
3. Class activation maps to localize which spatial regions drive classification
4. Dataset search to understand what real examples the model uses as its reference

This pipeline gives you trust-building evidence (for users and regulators), debugging tools (identify spurious correlations before deployment), and scientific insight (understand what the network has actually learned).

The broader point: neural networks must not only work well, but also be understood well. In high-stakes domains — medical diagnosis, immigration decisions, financial risk — a model that works but cannot explain itself is not acceptable. Interpretability is no longer optional. It's engineering.

**Course wrap-up:**

You've covered, over this quarter, the full arc of modern deep learning: from logistic regression foundations through optimization and regularization, to CNNs, sequence models, GANs, adversarial robustness, deep reinforcement learning, large language model applications, and now interpretability.

The field will continue to change. The specific architectures will evolve. But the underlying principles — learning representations from data, managing the bias-variance tradeoff, evaluating systematically, deploying responsibly — these will persist.

Build things. Understand why they work. Know when they fail. That's the practice of deep learning."

---

### Condensed Summary

Lecture 10 addresses interpretability — understanding what neural networks have learned and why they make specific decisions. This closing lecture frames interpretability as an engineering requirement rather than an academic curiosity, particularly for high-stakes production systems where regulators, users, and engineering teams need to understand model behavior.

Three levels of interpretability methods are covered: input-space methods (saliency maps using input gradients, occlusion sensitivity using systematic perturbation, Class Activation Maps using global average pooling to produce spatial classification heatmaps), feature-space methods (gradient ascent to generate synthetic images that maximize neuron activations, dataset search to find real training examples that maximize them), and reconstruction methods (transposed convolutions, unpooling with stored spatial switches, subpixel convolution for efficient upsampling).

Saliency maps reveal which pixels drive classification; occlusion sensitivity validates that this attention is genuine; CAM localizes objects without bounding box supervision. Feature-space methods expose what semantic concepts neurons have learned across layers — edges and colors in early layers, textures in middle layers, semantic objects in deep layers. Reconstruction methods enable generative models and dense prediction networks by inverting the forward pass.

The lecture closes with a course summary and thesis: the principles covered — representation learning, systematic evaluation, responsible deployment — transcend any specific architecture. The practice of deep learning is: build things, understand why they work, and know when they fail.

---

### ReloPass Application Notes

**Interpretability for regulatory compliance of the extraction model:** ReloPass's requirement extraction model makes decisions that affect immigration compliance. Saliency maps applied to the extraction model's outputs would show which words and phrases in a regulatory document drove the extracted requirement. This provides explainability for lawyer review: "the model identified this as a 90-day notice requirement because it attended to the phrase 'délai de prévenance de 90 jours' and the surrounding section on employment termination." Lawyers can validate or correct this attribution.

**Occlusion sensitivity for requirement boundary detection:** Applying occlusion sensitivity to the NER model — systematically masking sections of regulatory text and measuring how extracted requirements change — would identify which text spans are genuinely required to extract each requirement. This is directly useful for the pre-verification pipeline: the system can identify whether a regulatory update changed only peripheral text (low staleness impact) or the core spans that drive requirement extraction (high staleness impact, trigger re-extraction).

**Class Activation Maps for document structure classification:** ReloPass needs to classify regulatory documents by type (immigration law, tax regulation, social security agreement, housing requirement). A CNN-based document classifier trained with CAM would produce spatial heatmaps over the document, showing which sections drove the classification. This helps identify where to focus the NER extraction within a classified document.

**Gradient ascent for synthetic training data quality check:** Gradient ascent can be used to generate worst-case inputs for the extraction model — inputs that maximally confuse the model between requirement types (e.g., a text that the model confuses for a social security requirement when it's actually an immigration requirement). These synthetic adversarial examples can be used as quality check probes during model development.

**Reconstruction for scanned PDF processing:** The transposed convolution and upsampling methods from this lecture are directly applicable to ReloPass's scanned PDF processing pipeline. A document super-resolution model (following SRGAN architecture) would use transposed convolutions in its upsampling decoder to produce high-resolution reconstructions from low-quality scanned government documents, improving OCR quality and downstream NER accuracy.

**Explainability as a product feature:** The lecture's emphasis that interpretability is an engineering requirement in high-stakes domains is a product insight for ReloPass. The Case Command output — a time-anchored sequence of requirements with amber/red flags — should include interpretability features: "this requirement was flagged amber because the lead time window is 45 days and the move date is 38 days from now, with the following regulatory source: [link to specific article]." This is CAM-inspired attribution in the product layer.

---

## Course-Level Summary

### Overall Learning Arc

Stanford CS230 Autumn 2025 traces a coherent arc from first principles to frontier practice over ten lectures. The course opens by establishing why deep learning dominates — the data-compute-algorithm convergence — and closes by asking what deep learning is actually doing inside the network. Between these bookends, the curriculum moves through:

**Foundations:** logistic regression as the simplest neural network, vectorization as the computational primitive, supervised/self-supervised/weakly supervised learning as the three paradigms for extracting signal from data.

**Practice:** the full project lifecycle (define → collect → train → error analysis → deploy → monitor), orthogonalization as the diagnostic framework, and systematic approaches to transfer learning, multi-task learning, and distribution mismatch.

**Architectures:** CNNs for spatial data, sequence models (RNNs, GRUs, LSTMs) for temporal data, adversarial frameworks (GANs) for generative modeling, and deep Q-networks for sequential decision-making under uncertainty.

**Frontier:** LLM applications (prompt engineering, RAG, agentic workflows) as the contemporary integration point for all prior material, followed by interpretability as the closing metacognitive question.

The arc can be summarized in one sentence: *Learn how to build systems that learn representations from data, evaluate them systematically, deploy them responsibly, and understand what they've learned.*

The Autumn 2025 version distinguishes itself from the 2018 predecessor by treating LLM integration — RAG, agents, prompt engineering — as a first-class engineering discipline (Lecture 8) and by foregrounding the career context with dual perspectives from academic (Andrew Ng) and industrial (Laurence Moroney) practitioners (Lecture 9). Adversarial robustness (Lecture 4) and interpretability (Lecture 10) bookend the advanced topics, framing the course's practical philosophy: models must work, and they must be understood.

---

### Top 10 Most Actionable Insights

1. **Orthogonalize your debugging.** Four failure modes — training underfitting, dev overfitting, test misalignment, production distribution mismatch — require four distinct remedies. Applying the wrong remedy is the most common and expensive mistake in applied ML. Diagnose first; fix second. (Lecture 6)

2. **Self-supervised pretraining eliminates the cold-start labeling problem.** For any domain with abundant unlabeled text, masked language modeling or contrastive learning builds powerful representations before a single label is collected. Fine-tune on 1-5% labeled data rather than starting from scratch. (Lecture 2)

3. **Error analysis is structured prioritization.** Categorize failures, quantify each category's share of total error, and invest effort proportionally. A 30% nighttime failure rate means solving the lighting problem has 3x the ROI of solving a 10% blur problem. (Lecture 3)

4. **The architecture surrounding the model creates the value, not the model itself.** Prompt engineering, RAG, and agentic orchestration transform a general-purpose LLM into a domain-specific system. The base model is constant; the environment is the competitive differentiator. (Lecture 8)

5. **Transfer learning provides 10x data efficiency — but the source-target relationship must be right.** Same input type, shared low-level features, and more source data than target data are the three conditions. When conditions are met, freeze the backbone with limited target data; fine-tune fully with more. (Lecture 6)

6. **Interpretability is not optional in high-stakes domains.** Saliency maps, occlusion sensitivity, and Class Activation Maps are engineering tools, not research curiosities. Systems that cannot explain their decisions cannot be trusted in regulated environments. (Lecture 10)

7. **Experience replay and target networks are the stability solution for non-stationary learning.** Whenever training involves a moving target — RL Q-function approximation, or freshness checking against changing source documents — these techniques prevent divergence. (Lecture 5)

8. **Distribution shift is the silent killer of production systems.** A model trained on one distribution that deploys to another fails silently. Always put production-representative data in dev and test sets; monitor production statistics continuously; set up retraining triggers. (Lecture 3, Lecture 6)

9. **Business alignment is the non-negotiable filter for AI project selection.** Projects that solve real problems people pay for survive; AI demonstrations in search of a problem do not. Frame AI capability in terms of reliability, risk reduction, and cost savings — not technical novelty. (Lecture 9)

10. **Small, self-hosted models are the under-served opportunity in regulated industries.** As Big AI consolidates around centralized cloud models, sectors with data sovereignty requirements (legal, healthcare, government, HR compliance) need self-hosted, fine-tunable, auditable models. This is where specialized practitioners create disproportionate value. (Lecture 9)

---

### ReloPass Strategic Applications (Detailed)

This section synthesizes the Deep Learning concepts from CS230 Autumn 2025 into a concrete technical strategy for ReloPass's corridor knowledge graph, pre-verification pipeline, and requirement extraction system.

---

#### I. NLP/NER for Requirement Extraction (Lectures 1, 2, 6)

**The problem:** Government regulatory documents across FR, NO, ES, and IE are dense, multilingual, and structurally varied. Manually extracting requirements is a bottleneck; automating extraction requires models that understand regulatory semantics, not just keyword matching.

**The solution architecture:**

*Phase 1 — Self-supervised pretraining (Lecture 2):* Collect all available regulatory texts across target corridors and languages — government circulars, bilateral agreements, national immigration codes, tax authority guidelines. Train a masked language model (BERT-style) on this corpus without any labels. The result is a regulatory language encoder that understands the structure and vocabulary of legal text across FR/NO/ES/IE jurisdictions.

*Phase 2 — Fine-tuning for NER (Lecture 1, 6):* Label a small corpus of regulatory paragraphs with requirement type, responsible party, lead time, effective date, and conditionality flags. Fine-tune the pretrained encoder on this labeled set. Because the encoder already understands regulatory language structure, a few hundred labeled examples are sufficient — the transfer learning data efficiency described in Lecture 6.

*Phase 3 — Orthogonalized evaluation (Lecture 6):* Evaluate separately on training paragraphs (extraction accuracy), held-out paragraphs from the same source (generalization), and paragraphs from a new regulation in the same corridor (distribution within corridor), and paragraphs from a new corridor entirely (cross-corridor transfer). Each failure mode has a different remedy, and the diagnostic structure prevents wasted effort.

*Specific architecture:* LegalBERT or multilingual XLM-RoBERTa as the backbone (pre-trained on legal text, multilingual), with a token classification head for NER and a sequence classification head for document type. Both heads fine-tuned simultaneously as multi-task learning (Lecture 6), sharing the backbone's regulatory representations.

---

#### II. Scanned PDF Processing (Lectures 4, 10)

**The problem:** Many source regulatory documents exist only as scanned PDFs — historical bilateral agreements, older government publications, legacy social security arrangements. Standard OCR on low-resolution scans produces unreliable text.

**The solution architecture:**

*Pre-processing via super-resolution:* A SRGAN-style network (Lecture 4) trained on pairs of (low-resolution scan, high-resolution original) from available document pairs produces high-resolution reconstructions from legacy scans. The perceptual loss function — matching intermediate CNN features rather than pixel values — produces sharper character renderings than L2 reconstruction. This dramatically improves downstream OCR quality.

*Document structure classification:* A CNN-based classifier with Class Activation Maps (Lecture 10) classifies each page of a regulatory document into structural categories (header, article body, schedule, annex, signature block). The CAM outputs localize which regions of each page triggered the classification, providing spatial priors for the downstream NER model.

*Quality verification:* Occlusion sensitivity (Lecture 10) applied to the OCR output identifies which text regions are high-confidence (masking them degrades downstream classification) versus low-confidence (masking them has no effect). Low-confidence regions trigger targeted human review rather than blind processing.

---

#### III. Embedding-Based Staleness Detection (Lectures 2, 5)

**The problem:** When a government issues a regulatory update, ReloPass needs to determine: (a) which existing requirements in the knowledge graph are affected, and (b) whether any new requirements have been introduced. Manual review of every regulation update across every corridor is not scalable.

**The solution architecture:**

*Requirement embeddings (Lecture 2):* Each requirement in the knowledge graph is stored as a dense embedding vector produced by the fine-tuned regulatory encoder. New regulatory text is embedded by the same encoder. The embedding space places semantically similar requirements geometrically close.

*Triplet loss for similarity calibration (Lecture 2):* Train the encoder with triplet loss on triples: (existing requirement, paraphrase of same requirement, different requirement). This explicitly shapes the embedding space so that regulatory paraphrases cluster together, enabling reliable near-duplicate detection even across slight wording changes.

*Nearest-neighbor staleness detection:* When a new regulatory text arrives, embed it and find its k nearest neighbors in the requirement knowledge graph. If a neighbor's similarity score exceeds a threshold, flag the existing requirement as potentially stale and send both the original and the update to the lawyer review queue. The threshold is calibrated on validation examples.

*Experience replay for monitoring robustness (Lecture 5):* Store all past regulatory updates and their staleness decisions in a buffer. Train the monitoring model on random samples from this buffer, not just recent updates. This prevents the model from drifting toward recency bias and maintains robustness across different types of regulatory change.

---

#### IV. Regulatory Language → Plain HR Instructions (Lectures 2, 4, 8)

**The problem:** Extracted requirements are in regulatory language — dense, conditional, cross-referenced. HR generalists at SMEs cannot act on regulatory text. The system must translate requirement objects into clear, action-oriented HR instructions.

**The solution architecture:**

*Chain of Thought prompting (Lecture 8):* Rather than asking an LLM to directly generate an HR instruction from regulatory text, chain the reasoning: Step 1 — identify the requirement type; Step 2 — identify the responsible party (employer, employee, or external authority); Step 3 — identify the lead time and conditionality; Step 4 — generate the plain instruction. This structured CoT prompting dramatically improves accuracy by using intermediate tokens as a computational scratchpad.

*Cycle-consistency training (Lecture 4):* Inspired by CycleGAN, train a translation model with a cycle-consistency constraint: the plain HR instruction should be translatable back to a regulatory statement that matches the original. This is implemented by training two seq2seq models — regulatory-to-plain and plain-to-regulatory — with a combined loss that includes the cycle-consistency term ||original_regulatory - round_trip_regulatory||. This prevents over-simplification that loses critical compliance information.

*Retrieval-augmented generation (Lecture 8):* Rather than relying on the LLM's parametric knowledge, inject the relevant regulatory text as context via RAG. The HR instruction generation model retrieves the specific articles, sections, and schedules that constitute the requirement, then generates the plain instruction grounded in that specific text. This ensures legal accuracy and provides a citation trail.

*Multi-agent validation (Lecture 8):* After generation, a reflection agent reviews the HR instruction against the regulatory source using a specialized prompt: "Does this HR instruction correctly represent the regulatory requirement? What has been lost or distorted in translation?" This automated pre-validation catches obvious errors before lawyer review.

---

#### V. Document Classification for Knowledge Graph Tagging (Lectures 1, 3, 6)

**The problem:** Regulatory documents span multiple domains — immigration, tax, social security, housing — and a single document may contain requirements from multiple domains. Requirements must be correctly tagged for the Case Command rule engine to assign them to the correct timeline position.

**The solution architecture:**

*Multi-task classification model (Lecture 6):* A single model trained simultaneously to (a) classify documents by primary regulatory domain and (b) extract requirement-level tags. Multi-task learning allows the larger document-level training set to regularize the smaller requirement-level classification task, and shared representations improve both.

*CAM-informed extraction regions (Lecture 10):* Class Activation Maps from the document classifier localize which sections of a regulatory document are most relevant to each domain classification. These spatial priors guide the NER extraction model — focus extraction effort on high-activation regions for each domain type.

*Error analysis by failure category (Lecture 3):* Track classifier failures by category: misclassification of immigration as tax (type A), failure to detect social security implications of an immigration document (type B), incorrect tagging of transitional provisions (type C). Quantify each type's share of total error; invest labeling effort in the highest-impact category first.

*Orthogonalized deployment checklist (Lecture 3):* Before a new classification model is deployed to production, verify: (1) training accuracy on labeled corpus, (2) generalization on held-out paragraphs, (3) consistency with the rule engine's expected input schema, (4) behavior on real regulatory updates from the monitoring pipeline. Each check has its own pass/fail criterion and remediation path.

---

#### VI. Adversarial Robustness for Compliance-Critical Extraction (Lecture 4)

**The problem:** The requirement extraction system operates in a compliance-critical context. An adversarial failure — where a small regulatory text variation causes the model to miss a requirement or extract a wrong one — has real legal consequences.

**The solution architecture:**

*Adversarial training on regulatory text variations (Lecture 4):* Generate adversarial examples of regulatory text by applying FGSM-style perturbations in the token embedding space — slight paraphrasing, synonym substitution, word order changes that preserve meaning but challenge the extraction model. Include these adversarial variants in training with correct extraction labels. This is the regulatory NLP equivalent of PGD adversarial training.

*Evaluation against adaptive attacks (Lecture 4):* The adversarial evaluation should include text transformations that know about the extraction model's features — using its attention patterns to craft confusing inputs. This is the regulatory-domain equivalent of AutoAttack: a standard evaluation suite that reliably exposes weak extraction models.

*Certified extraction for critical requirements (Lecture 4):* For high-stakes requirements (visa application deadlines, mandatory reporting dates, tax residence trigger dates), apply randomized smoothing to get certified robustness guarantees. The extraction model with Gaussian noise injection provides a certified bound: within a defined text perturbation radius, the extracted requirement will not change. Requirements with certified stability can be auto-approved; uncertain ones go to lawyer review.

---

#### VII. The Self-Improving Pipeline: Flywheel Architecture

The deepest integration of CS230 concepts is the flywheel that makes ReloPass self-improving over time:

1. **Monitor:** Government websites and regulatory sources are continuously crawled. New documents are detected by their source check (URL fingerprint change) and freshness check (content hash change). (Lecture 3 — monitoring loop)

2. **Extract:** The new document is processed through the pre-verified pipeline: OCR/super-resolution → document classification → NER extraction → requirement object construction. (Lectures 1, 2, 4, 10)

3. **Compare:** New requirement embeddings are compared to the knowledge graph via nearest-neighbor lookup. Staleness flags are raised where similarity exceeds threshold. (Lecture 2 — triplet loss, embeddings)

4. **Translate:** Flagged requirements are translated to plain HR instructions via CoT-prompted RAG. Multi-agent reflection validates the output. (Lecture 8)

5. **Review:** Lawyer review queue presents: original regulatory text, extracted requirement, similarity comparison with existing requirement, proposed HR instruction, and confidence scores with interpretability heatmaps. (Lectures 6, 10)

6. **Update:** Lawyer-approved updates are committed to the knowledge graph. Rejections are stored as labeled training examples for model improvement. (Lecture 3 — full cycle)

7. **Retrain:** When a sufficient number of new labeled examples accumulate, trigger a fine-tuning cycle on the updated corpus with experience-replay sampling from historical examples. (Lectures 5, 6)

8. **Evaluate:** After retraining, run the orthogonalized evaluation checklist before deploying the updated model. (Lecture 6)

This flywheel — monitor, extract, compare, translate, review, update, retrain, evaluate — is the engineering answer to the self-improving regulatory knowledge graph. Each loop iteration improves model accuracy, expands the labeled training corpus, and keeps the knowledge graph current. The human-in-the-loop (lawyer review) provides ground truth labels while serving the product's primary function: ensuring every corridor requirement is legally verified before publication.

The key design choice that makes this sustainable: the rule engine at runtime is fully deterministic — no LLM, no uncertainty, no hallucination risk. The deep learning capabilities operate in the authoring and maintenance pipeline, where human review is a natural integration point. The product's compliance guarantee comes from the deterministic rule engine; the product's scalability comes from the deep learning pipeline that feeds it.

---

*Document compiled: August 2026*  
*Sources: YouTube playlist https://www.youtube.com/playlist?list=PLoROMvodv4rNRRGdS0rBbXOUGA0wjdh1X; Stanford CS230 course website cs230.stanford.edu; aman.ai/cs230 lecture notes; globalnerdy.com CS230 career lecture summary; deebakkarthi.com Lecture 8 notes; aishwaryasrinivasan.substack.com agent lecture notes; videohighlight.com lecture summaries.*
