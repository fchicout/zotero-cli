International Journal of Information Security (2025) 24:197
https://doi.org/10.1007/s10207-025-01112-1

R E G U L A R C O N T R I B U T I O N

Evaluation of the maturity of LLMs in the cybersecurity domain

Tiago Conceição1 · Nuno Cruz1,2

/ Accepted: 10 August 2025 / Published online: 27 August 2025
© The Author(s) 2025

Abstract
The increasing sophistication of cybersecurity threats demands innovative solutions for network defense and security edu-
cation. This study evaluates the potential of Large Language Models (LLMs) in automating cybersecurity tasks, speciﬁcally
focusing on three critical areas: Honeypot generation, Malware Detection, and Capture The Flag (CTF) exercise creation.
We introduce two novel evaluation frameworks: the Cybersecurity Language Understanding (CSLU) benchmark, which
assesses model knowledge through domain-speciﬁc multiple-choice questions, and an automated evaluation system that mea-
sures models’ ability to generate functional security artifacts. Using these frameworks, we evaluated seven state-of-the-art
LLMs, including GPT-4, Gemini Pro, and Claude 3 Opus. Results demonstrate that current LLMs exhibit strong capabilities
in Malware analysis, with four models achieving perfect scores. However, performance varied signiﬁcantly in CTF exercise
generation, indicating areas for improvement. GPT-4, Gemini Pro, and Claude 3 Opus consistently outperformed other models
across all tasks. Performance patterns suggest that model size correlates with task effectiveness, though architecture-speciﬁc
optimizations also play a signiﬁcant role. Our ﬁndings indicate that LLMs can effectively automate certain cybersecurity
tasks, particularly in Malware Detection and analysis. However, their capabilities vary across different security domains,
suggesting the need for specialized training or domain-speciﬁc adaptations for optimal performance.

Keywords Cybersecurity · Large language models · Honeypots · CTF challenges · Malware detection

1 Introduction

In today’s global cybersecurity landscape, organisations face
signiﬁcant challenges in protecting their networks and sys-
tems from progressively more sophisticated threats. This
accelerated technological advance and the growing depen-
dence on interconnected systems have made cybersecurity
a central component of defence strategy. From this perspec-
tive, the complex and dynamic nature of the threat ecosystem
requires innovative and adaptive approaches to ensure the
integrity, conﬁdentiality and availability of sensitive infor-
mation. In addition to these considerations, there is also
the need to keep professionals up to date with the latest
cybersecurity techniques and tools in order to implement

B Tiago Conceição

a47611@alunos.isel.pt

Nuno Cruz
ncruz@isel.pt

1

2

FIT/ISEL, R. Conselheiro Emídio Navarro 1, 1959-007
Lisbon, Portugal

LASIGE, Campo Grande, Lisbon, Portugal

the required approaches, which requires a constant training
effort.

Large Language Models (LLMs) have gained a lot of inter-
est in recent years due to their ability to generate coherent
text and perform natural language processing tasks [9]. LLMs
are artiﬁcial intelligence models that use deep learning tech-
niques to process and understand natural language. These
models are trained on large amounts of text data to learn
patterns and relationships between entities in the language
and thus acquire knowledge about the real world and various
domains.

Given the mentioned appreciation and use of LLMs, these
models have become a revolutionary element not only in our
daily lives, but also in the technological and academic sectors.
These innovations have transformed the way we interact with
information, technology and the world around us, moulding
various aspects of our lives.

Recognising the urgent need to strengthen organisations’
cybersecurity capabilities [4], it is considered crucial to
explore the integration of LLMs with cybersecurity systems.
By leveraging advanced artiﬁcial intelligence, the aim is to

123

197

Page 2 of 13

T. Conceição, N. Cruz

proactively address cybersecurity challenges, providing an
efﬁcient response to constantly evolving threats.

These challenges require an innovative solution that
allows organisations to remain at the forefront of cyber-
security, responding effectively to evolving threats while
optimising the use of their human resources.

The objective is to evaluate the use of LLMs to automate
the development of cybersecurity mechanisms, by assessing
the current state of maturity in relation to the topics to be stud-
ied. The purpose of this research is to add value to the ﬁeld
of using LLMs in cybersecurity. The intersection between
natural language processing and information security will
be explored in greater depth, through the development of 2
studies aimed at evaluating the use of this type of model to
automate the development of cybersecurity mechanisms.

This research speciﬁcally examines to what extent current
state-of-the-art LLMs possess the domain-speciﬁc knowl-
edge required for cybersecurity applications, particularly in
Honeypot generation, Malware detection, and CTF exercise
creation. The study further investigates how the perfor-
mance of these models varies between different cybersecurity
tasks and identiﬁes the factors, such as model architec-
ture and parameter size, that inﬂuence this performance.
Furthermore, we address whether LLMs can autonomously
generate effective and functional cybersecurity artifacts with-
out domain-speciﬁc training or ﬁne-tuning.

1.1 Paper structure

This article comprises six main sections, followed by an
Appendix, each serving a speciﬁc role in developing and
presenting the research.

Section 1 serves as an introductory chapter, it begins
by introducing the research topic and providing a general
overview.

The following section (Sec. 2) reviews the most recent
and impactful contributions within the ﬁeld explored in this
article. The focus here is on the current state of LLMs,
then addresses Prompt Engineering techniques, crucial for
enhancing LLM performance and accuracy in generating
desired outputs.

Next, Sec. 3, covers the studies conducted throughout
the research. The experimental tests and procedures are pre-
sented here, with a detailed description of the methodologies
employed in each experiment.

Followed by the results in Sec. 4, which the results of the
experiments are displayed in a clear and organized manner,
allowing for an accurate interpretation of the data collected.
Section 5 presents the analysis of the outcomes and their

implications in the ﬁeld.

Section 6 provides a reﬂective summary of the research
work, synthesizing the main ﬁndings and their contribution
to the ﬁeld.

123

2 State of the art and related work

This chapter aims to situate the reader in the context of the
research, establishing a solid basis for the research in question
and highlighting the main trends and ﬁndings.

In order to carry out this experimental test, topics such
as Prompt Engineering, benchmarks to obtain knowledge
about the state of the art with the aim of structuring the
study and consequently achieving the best and most robust
results. Work related to investigating the use of LLMs for
cyber defence mechanisms and in CTF exercises was also
investigated.

2.1 Prompt engineering

Prompt Engineering is an area dedicated to the develop-
ment and optimisation of prompts for generative artiﬁcial
intelligence systems. It is considered an important area of
computer science because it has the potential to signiﬁcantly
improve the effectiveness and performance of generative arti-
ﬁcial intelligence systems. Effective prompts can help ensure
that artiﬁcial intelligence systems generate accurate, rele-
vant and useful results. There are a number of documentation
projects that address the area of Prompt Engineering. One of
the best known is OpenAI’s Prompt Cookbook1. This cook-
book is an open-source collection of examples and guides
on how to create effective prompts for language models.
This project has received a lot of contributions from vari-
ous studies and published articles, such as in [16], where
the authors explored an innovative technique called "Chain-
of-Thought Prompting" to optimise the ability of LLMs to
perform complex reasoning. This technique involves present-
ing examples of intermediate chains of thought to the LLMs,
encouraging them to develop a structured and logical thought
process. Tests carried out with three different LLMs have
shown that "Chain-of-Thought Prompting" provides signif-
icant improvements in performance on arithmetic, common
and symbolic reasoning tasks.

Another important documentation project is Google AI’s
Prompt Engineering Handbook 2. This handbook provides
a comprehensive overview of the ﬁeld of Prompt Engineer-
ing, including basic concepts, advanced techniques and use
cases. It’s also worth mentioning the Prompt Engineering
guide developed by DAIR.AI 3, which aims to democratise
AI research, education and technologies.

1 https://cookbook.openai.com
2 https://developers.google.com/machine-learning/resources/prompt-
eng
3 https://www.promptingguide.ai

Evaluation of the maturity of LLMs in the cybersecurity domain

Page 3 of 13

197

2.2 Benchmarks

In this constantly evolving spectrum of LLMs, benchmarks
are indispensable tools for evaluating and comparing the
performance of these models in a wide range of tasks.
These benchmarks serve as standardised benchmarks, allow-
ing researchers and programmers to map progress in the
ﬁeld and identify the nuances that distinguish the different
LLMs.

There are at the moment some benchmarks capable of
assessing the state of knowledge of LLMs in a structured
and standardised way, such as Massive Multitask Language
Understanding, developed by [8], which is a widely recog-
nised performance benchmark applied to LLMs. The LLM
assessment model in question is generally made up of
prompts that follow a multiple-choice question/answer for-
mat, where a wide range of subjects and question types are
covered, including sciences, humanities, and technical ques-
tions. In short, the benchmark described seeks to test the
depth and breadth of the models’ knowledge, as well as their
inference capacity, by applying questions that vary in com-
plexity and require different levels of contextual and factual
understanding.

In the ﬁeld of cybersecurity, although the offer of bench-
marks is considerably reduced, there are some benchmarks
that focus on evaluating the knowledge of models in the area
of cybersecurity, an example of this type of benchmarks is
CyberBench, where [11] used ﬁve tasks to evaluate a set of
domains, and was designed to evaluate the performance of
LLMs in tasks related to cybersecurity. The tasks adopted by
the authors are: named entity recognition, summarisation,
multiple choice and text classiﬁcation. The summarisation
task made up of two datasets, the Computer Security MMLU
(SecMMLU), which is a subset of the MMLU focused, in
general terms, on the cybersecurity domain, and the CyQuiz,
which follows the same question format as the previous one.
This article demonstrates the results of using CyberBench
to evaluate more than ten LLMs. It is worth highlighting the
interesting results obtained by the models trained speciﬁcally
for the evaluation of this article, which were able to obtain
the best classiﬁcation in some tasks.

Although published this year, most of the companies that
own the models studied have already presented improved
versions of them and there was also a lack of models capable
of competing with the favourite models in terms of evaluation
following the MMLU parameters in this experimental test,
such as Google’s Gemini or Anthropic’s Claude 3.

The authors of SECURE, [2], have introduced a bench-
mark designed to assess the performance of LLMs in realis-
tic cybersecurity scenarios. SECURE includes six datasets
focussed on the Industrial Control Systems sector, which
seeks to assess knowledge extraction, comprehension and
reasoning based on industry-standard sources. The study

evaluated seven models, and generated insights such as rec-
ommendations for improving the reliability of LLMs as
cybersecurity consulting tools.

2.3 Cyber defence mechanisms

Given the current technological modernisation, cyber defence
mechanisms are considered essential to protect networks
and systems against threats in cyberspace. These include
technologies and strategies designed to prevent, detect and
respond to attacks [4]. A concrete example of cyber defence
strategies are deceptive techniques. In a corporate environ-
ment, deceptive mechanisms refer to security techniques that
aim to deceive or confuse potential malicious actors in order
to protect a company’s assets. These techniques include the
creation of traps, false information, or the simulation of
vulnerabilities in order to discourage or delay intrusions.
Examples of deceptive mechanisms include Honeypots or
honeynets.

A Honeypot is a computer security technique that aims to
attract potential cyber-attacks by simulating a legitimate, vul-
nerable resource in order to monitor and analyse attackers’
tactics, techniques and procedures. This mechanism consists
of exposing an intentionally unprotected system or service
conﬁgured to attract malicious activity, allowing security pro-
fessionals to assess emerging threats and strengthen defences
in real time.

[15] developed an effective isolation prediction and main-
tenance system for cloud security and Intrusion Detection
Systems (IDS). The study compared different levels of Hon-
eypots to understand their details and interaction with the
network. A real-time Honeypot was used to detect attacks on
a SSH server.

it
Given the ability of LLMs to recognise patterns,
would be interesting to consider using them to develop new
approaches to Malware Detection. For example, an LLM
could be trained on a dataset of malicious and legitimate
software. This would then make it possible to use a model to
identify patterns in the code that are characteristic of mali-
cious programmes. This approach is intended to have several
advantages over traditional Malware Detection methods. Ini-
tially, they would be more effective in detecting unknown
Malware, as LLMs can learn to identify patterns, and even
recognise obfuscation patterns, that are common to differ-
ent Malware families, even if those families are not known,
and even if they do not initially identify a malicious pattern,
they can be dynamically updated and adapted as new threats
emerge. This allows for a faster response to changes in the
threat landscape, while maintaining detection effectiveness.
This type of model is less susceptible to false positives, as it
learns to identify patterns that are speciﬁc to Malware, result-
ing in a reduction in the likelihood of a legitimate programme
being identiﬁed as malicious. Another advantage would be

123

197

Page 4 of 13

T. Conceição, N. Cruz

that, given the multi-modality of these models, they could
also be used to identify Malware in different formats. This
would make the analysis process more effective, for exam-
ple in cases of steganography where relevant information or
even malicious code is hidden in ﬁles of other formats, such
as images.

[14], having identiﬁed that many of the current Honey-
pots solutions lack the realism needed to engage and deceive
human attackers, presented an innovative Honeypot system,
based on LLMs, which showed remarkable results in achiev-
ing an accuracy rate of 92% in assessing its ability to engage
and deceive human attackers with dynamic and realistic
responses. [12] also studied the use of ChatGPT as an innova-
tive tool for creating Honeypots interfaces in cybersecurity.
The article presents ten different tasks that the language
model can appropriately respond to an attacker using line
commands. The usefulness of this Honeypot depends on its
ability to delay or prevent attacks on critical network assets,
such as databases or conﬁdential information. The authors
concluded that ChatGPT’s ability to identify and mitigate
malicious activity makes it a viable tool for organisations
looking to optimise their cybersecurity posture.

In the Malware analysis domain, [7] explored active learn-
ing techniques for managing a non-stationary model for
Android Malware Detection over a seven-year period. It
assessed the impact of various elements, including feature
space selection, data balancing, and timestamping methods,
on the model’s performance. The authors compared detection
accuracy and labeling costs with baseline models, also exam-
ining model resilience to noisy labels caused by human error
or adversarial interference. By focusing on active learning
in non-stationary Malware Detection, this study addresses a
key gap in existing literature.

From a different perspective of cyber defence, [5] presents
a study on the use of an LLM for Malware Detection in
an obfuscated code context. As did [19] who, using the
ChatGPT-4 model, generated security tests in order to detect
malicious third-party libraries, also demonstrating how vul-
nerable library dependencies expose certain applications to
supply chain attacks. Like [6], the authors recognise the
growing expectation of its effectiveness in detecting vulner-
abilities from LLMs. However, a quantitative understanding
of its potential in this area was still lacking. The authors there-
fore introduced VulBench, a vulnerability benchmark. This
benchmark gathers high-quality data from a variety of CTF
challenges and real-world applications. Through tests involv-
ing 16 LLMs and 6 state-of-the-art deep learning models and
static analysers, it was found that several LLMs outperform
traditional deep learning approaches in detecting vulnera-
bilities, revealing untapped potential in LLMs. This work
contributes to the understanding and use of LLMs to opti-
mise software security.

123

2.4 CTF exercises

The CTF exercises, short for Capture The Flag, are cyber-
security challenges where participants can compete against
each other. These exercises are designed to test and enhance
in a dynamic and challenging way not only cybersecurity-
related skills, but also creativity and problem-solving skills.
These challenges can range from simple to complex, and can
cover a wide range of topics, such as analysing Malware,
reverse engineering, steganography, cryptography, commu-
nication networks, exploiting vulnerabilities, digital foren-
sics, and much more.

Nowadays, CTFs are an important part of cybersecurity
culture and are widely used in academic, business and com-
munity contexts. This type of exercise has recently gained
prominence in the research ﬁeld, for example [10] used
eleven CTF exercises on Heap vulnerabilities to evaluate
their proposed solution. [1] developed a deceptive mecha-
nism to understand the behaviour of human attackers in order
to optimise the defender’s strategy, used CTF environments
on vulnerable applications in order to collect data on attacker
behaviour, rather than artiﬁcially generating data based on
accepted assumptions about opponents.

The research into the integration of LLMs regarding the
creation of CTF exercises represents a promising area. By
understanding the ability of these models to simulate real
situations and generate diverse challenges, they can signiﬁ-
cantly increase the quality and quantity of competitions.

By integrating LLMs into the development of exercises,
the creators themselves will be able to save time, guaran-
tee technical quality, and offer more complex and engaging
challenges.

3 Experimental methodology and

evaluation framework

This section presents the comprehensive experimental
methodology employed to evaluate LLM capabilities in
cybersecurity domains. Our approach consists of two com-
plementary evaluation frameworks: (i) a benchmark assess-
ment of theoretical knowledge through the Cybersecurity
Language Understanding (CSLU) benchmark; and, (ii) our
own autonomous evaluation system for assessing practical
artifact generation capabilities. We ﬁrst detail the models
selected for evaluation, followed by the design and imple-
mentation of each component.

3.1 Models

The process of choosing the models to include in the studies
was based considering the models used, but not exclusively,
in other studies analysed in section 2, through factors such

Evaluation of the maturity of LLMs in the cybersecurity domain

Page 5 of 13

197

Table 1 Models to evaluate

Table 2 Question example - Honeypot

Model’s name

Parameterisation

Company

GPT-4

GPT-3.5

LLama 3

Code LLama

Claude 3 Opus

Gemini Pro

Mixtral

1.76 trillion

175 billion

70 billion

70 billion

2 trillion

N.A

8 x 22 billion

OpenAI

OpenAI

Meta

Meta

Anthropic

Google

Mistral

as the visibility of the models, the date of launch of them
or their respective parameterisation, since this parameterisa-
tion shapes the understanding of the model’s language. It is
therefore assumed that the more a model is parameterised,
the more likely it is to achieve better results. Ultimately, 7
models were chosen; the best models from widely recognized
LLM companies were chosen to maximize the scope of the
evaluation.

Thus, the models used in this experimental study are avail-
able in the table 1, for each model there is also attached
information about its parameterisation and the company that
currently owns the model. Unfortunately, at the time of
submitting this document, it was not possible to acquire
any information on the parameterisation of the Gemini Pro
model.

Recognising the accelerated development of this type of
model, it is assumed that on the date of submission of this
thesis, some of the models used do not represent the model
with the best capabilities presented by the company that owns
them.

3.2 Cybersecurity language understanding

In order to assess the viability of the models in terms of the
theoretical and practical knowledge of the objects of study
introduced, a benchmark was developed. This ﬁrst experi-
mental study aims to assess the current state of knowledge
of the models to be evaluated, in order to establish a starting
point for this research.

This benchmark was based on the MMLU benchmark [8],
following the model evaluation process used by the authors,
using multiple choice questions. In this format, the models
are presented with a speciﬁc problem and given four options
to choose from, only one of which is correct. To ensure a
complete evaluation of the models, 10 questions were created
and submitted for each topic.

The benchmark developed, called Cybersecurity Lan-
guage Understanding (CSLU), offers a standardised eval-
uation framework, guaranteeing consistency and reliability
in the results obtained. By implementing this benchmark-

Which of the following CVEs is the version 1.23.1 of Nginx vulnerable
of?

A) CVE-2022-41741

B) CVE-2021-23017

C) CVE-2019-9513

D) CVE-2019-9511

ing method, it is possible to assess the quality of the models
evaluated from a capabilities perspective on cybersecurity
topics.

Given the fact that the evaluation of the models in this
experimental test is carried out through multiple choice ques-
tions, taking advantage of the analytical nature of the results
data, the main evaluation metrics were considered to be the
effectiveness rate, the average value and the standard devia-
tion.

3.2.1 Prompts

The format of prompts using multiple choice questions facil-
itates binary classiﬁcation in the evaluation process and
provides a clear and measurable way of assessing the perfor-
mance of the different LLMs, ensuring that their capabilities
can be directly compared and analysed. The prompts were
mostly run through the interfaces provided by the compa-
nies that own the models, with the exception of the Meta and
Mistral models, which were run through Perplexity Labs’
accessible interface.

The Tables 2, 3 and 4 show concrete examples of the
prompts used to evaluate the models for each topic. In each
ﬁgure, the correct answer is marked in bold.

As shown in ﬁgure 2, the prompts for the topic of Hon-
eypots are intended to assess knowledge of the models in
question, both in theoretical terms and in more practical
approaches. This content spectrum aims to assess every-
thing from the theoretical terms of the Honeypots topic to
knowledge of the documented presence of vulnerabilities in
globally known commercial products. The ﬁgure in this topic
aims to verify the state of knowledge of the models regarding
the catalogue of vulnerabilities present in Nginx servers.

The focus of the CTF exercises is to determine the state
of problem-solving skills and general knowledge of cyber-
security models. Theoretical mastery of the content to be
generated and problem-solving skills are the central points
involved in CTF exercises. Given this fact, ensuring that the
models have both characteristics is essential in order to ensure
their viability in generating this type of artefact. The prompt
in the ﬁgure 3 challenges the models by solving a simple
CTF exercise. This question is considered to be part of the
feasibility study on the generation of CTF exercises, since it

123

197

Page 6 of 13

Table 3 Question example -
CTF

Table 4 Question example -
Malware

Table 5 Prompt engineering
technique application example

Table 6 Evaluation prompt
example

T. Conceição, N. Cruz

What is a more reliable approach to determine the
Caesar Cipher key used for encryption, rather than
simply guessing a common shift value?

A) Try all possible key values (0-25) and see which decrypted message makes the most sense

B) Look for patterns in the letter frequencies of the ciphertext

C) Both a) and b) are useful techniques

D) There’s no reliable way to determine the key without additional information.

Arrange the following steps in the correct sequence of a keychain attack:

1) The backdoor grants the attacker remote access to the victim’s system.

2) Attacker sends a phishing email with a malicious attachment.

3) Attacker gains access to the victim’s keychain or credential storage.

4) Victim unknowingly executes the malicious attachment, which installs a backdoor on the system.

5) Attacker retrieves login credentials stored in the keychain.

A) 1 - 2 - 3 - 4 - 5

B) 3 - 1 - 2 - 4 - 5

C) 2 - 4 - 1 - 3 - 5

D) 1 - 3 - 4 - 2 - 5

Version

Base

CoT ﬁrst phase

CoT second phase

Prompt

Analyse the following code:

Analyse the following Android application:

Analyse the following Android application, before performing the anal-
ysis consider the standards and deﬁnitions of every Malware category
within the Android ecosystem:

You are a LLM evaluator, I will provide you some LLMs prompts and the respective
responses from the models, you will have to classify the models responses into 3 groups:
correct, plausible and incorrect. The correct classiﬁcation only applies to the responses that
fully accomplish the requested features or needs of the prompts, if the response contains all
needed information and resources to the developer implement the challenge. The plausible
classiﬁcation applies to the responses that didn’t fully accomplish the requested of the
prompts, for example if the model didn’t provided all necessary tasks to complete the
CTF if needed. The incorrect classiﬁcation only applies to the responses that fully didn’t
accomplish the requested features or needs of the prompts.

User prompt: "%s"

Model response: "%s"

is ﬁrst necessary to ensure the theoretical and practical con-
sistency of the knowledge spectrum involved in this type of
exercise.

The study on Malware aims to assess the ability of mod-
els not only to identify and analyse the presence of threats in
software, but also theoretical terminologies on this subject.
Although in a real context it is expected that the analysis
of suspicious artefacts will focus on binary ﬁles, the aim of
this study is to assess the state of theoretical and practical
knowledge in which it is understood that the use of Mal-
ware source code satisﬁes this assessment requirement. The

prompt in the ﬁgure 4 asks the models to organise certain
events in the correct sequence of a Keychain attack.

3.3 Autonomous evaluation of LLMs

A second experimental study was carried out with the aim
of identifying the best models in terms of their viability
in cybersecurity applications, introducing them to tests that
are contextually closer to real scenarios and use cases. The
responses of the LLMs will be evaluated automatically using
an additional LLM. Consequently, the aim of this evaluation

123

Evaluation of the maturity of LLMs in the cybersecurity domain

Page 7 of 13

197

is not to develop an automatic workﬂow or benchmark, but to
identify the best models without the need of user’s analysis
or judgment of the models responses.

The same topics studied and present in the assessment
carried out in the 3.2 section were considered: generating
CTF exercises, generating cyber defence mechanisms such
as Honeypots, and ﬁnally detecting Malware.

For this experimental test, we used the interfaces provided
by the companies themselves, such as ChatGPT for GPT-3.5
or Google Gemini. The other models were accessed via the
Perplexity Labs Playground.

Quantitative and qualitative facts about the artefacts gener-
ated by the models were considered as metrics for evaluating
them, so as to enable a consolidated and standardised evalua-
tion. The evaluation points adopted were whether the model
successfully achieved the outlined objective, the quality of
the ﬁnal response and ﬁnally the number of prompts required
to achieve the desired result. Taking the evaluation parame-
ters into account, the model’s answers will be classiﬁed into
one of the following categories: Correct, Plausible and Incor-
rect.

The ‘Correct’ classiﬁcation characterises answers that
fully comply with the objectives imposed by the prompt, i.e. if
the answer presents all the information and resources neces-
sary for the programmer to implement or generate the desired
artefact. The ‘Plausible’ classiﬁcation applies to answers that
do not fully comply with the request, but coherently present
all the steps needed to achieve the desired objective, for exam-
ple, if the model does not provide all the resources needed
to implement a CTF but describes the process of doing so in
sufﬁcient detail. Finally, the ‘Incorrect’ classiﬁcation applies
only to answers that did not fully fulﬁl the characteristics or
needs requested in the prompts.

The best model will be the one that ﬁrst achieves the high-
est accuracy values in the ‘Correct’ category. For tie-breaking
purposes, the level of accuracy of the answers classiﬁed as
‘Plausible’ will be taken into account, and consequently the
third and ﬁnal category.

3.3.1 Prompts

For each topic, 4 to 5 prompts were conceptualised. These
are organised in order of complexity, with the ﬁrst repre-
senting the simplest task and the last presenting the most
technically complex or ambiguous task. If a model does not
achieve the expected result with a given prompt, some Prompt
Engineering techniques were used to optimise the model’s
performance, such as Chain-Of-Thought Prompting, which
allows for more complex reasoning resources through inter-
mediate inference stages. For example, the Table 5 speciﬁ-
cally demonstrates the use of Chain-Of-Thought Prompting
in two phases, thus showing the evolution of this prompt and
subsequent possible changes to the introductory paragraph

it has undergone in order to optimise the LLMs’ inference
when necessary.

Generating CTF exercises can be a tricky task, as many
CTF challenges involve advanced cybersecurity concepts, as
well as the creative and authentic process required. LLMs
may not have the necessary knowledge of these concepts,
which can result in the creation of challenges that are not
technically accurate or challenging enough for experts in
this ﬁeld. Determining the appropriate level of difﬁculty for
a CTF challenge is crucial. LLMs can also ﬁnd it difﬁcult
to properly assess the complexity of a challenge, resulting in
exercises that are either too easy or too difﬁcult, ideally these
should be challenging, but they should also be achievable.
Diversity is also key in CTF challenges to keep participants
interested, creating a variety of personalised and unique chal-
lenges can be difﬁcult for language models as they tend to
follow existing examples through the standards studied. The
main aim is to assess the creativity of the models; initially,
objective and deterministic prompts were developed, requir-
ing an exercise on a more speciﬁc theme or area, compared
to the others, which were a little more ambiguous and lacked
detail.

When building threat detection systems such as Honey-
pots, the careful choice of prompts can guide the creation
of effective mechanisms. When asking an LLM to generate
such systems, depending on the intended objectives, speciﬁc
or more general prompts are both valid approaches. A general
approach reﬂects the request to create a Honeypot by simply
describing some of the characteristics or objectives sought
with the Honeypot. In this way, the ﬁrst two prompts follow
the ideology of this general approach. On the other hand, a
speciﬁc approach consists of carrying out the aforementioned
instantiation or development request for a Honeypot, neces-
sarily imposing the use of a speciﬁc server or vulnerability.
The aim is to study not only the creativity of the models, but
also their adaptability through the approaches they take for
each case study, depending on whether they are objective or
a little more ambiguous.

Despite the potential advantages of creating LLM-based
Malware Detection systems, they currently represent a chal-
lenging and complex topic in the ﬁeld of cybersecurity. For
this reason, it is important to study the effectiveness of this
group of models in order to understand their viability in this
ﬁeld. Although LLMs are powerful natural language pro-
cessing tools, they face several difﬁculties when it comes to
identifying malicious software. One of the main limitations
of LLMs in detecting Malware is related to the highly tech-
nical and dynamic nature of cyber threats. Today’s malicious
programmes are often designed to avoid detection; malicious
agents use advanced obfuscation techniques. From this per-
spective, LLMs may ﬁnd it difﬁcult to understand the speciﬁc
technical nuances of these threats, since their mastery is more
centred on linguistic patterns and semantic contexts. Due to

123

197

Page 8 of 13

T. Conceição, N. Cruz

limitations imposed by the interfaces used, in which it is not
possible to present binary ﬁles to analyse the presence of
Malware, in this experimental test only the analysis of Mal-
ware through its source code will be considered. Although in
this scenario the evaluation is abstracted from a more realis-
tic context, evaluating Malware Detection by analysing the
source code can generate valuable insight in the sense of
scientiﬁc valorisation where this study is applied.

3.3.2 Responses evaluation

While in the previous experimental study it was possible to
simplify the process of evaluating model responses by apply-
ing a binary classiﬁcation, in the present experimental study
it is not intended to inﬂuence or restrict the range of model
responses. Therefore, the evaluation of model responses was
conceptualised so that it could be carried out automatically,
using an LLM. Simultaneously with the process of devel-
oping the regular prompts, evaluation prompts were also
developed, one for each evaluation topic, for the evalua-
tor model to effectively classify the models’ responses. The
model chosen to fulﬁl the role of evaluator was GPT-4o. As
mentioned above in the subsection 3.3, it was necessary to
delimit the linguistic understanding of the evaluator model
through the prompts used, in order to atomically perform a
good evaluation of the other LLMs’ answers.

The Table 6 shows an example of a prompt developed
for the evaluator model to classify a response from an LLM,
in this case a prompt to evaluate the generation of a CTF
exercise.

4 Results

This section aims to present and synthesise the results
obtained from the experimental tests carried out on the two
LLM evaluation mechanisms. In addition to summarising
them, it is also intended to provide graphical representations
in order to help interpret the data generated.

4.1 CSLU

The results obtained by the CSLU highlighted a clear promi-
nence of knowledge in relation to the topic of Malware,
with four models achieving the maximum score in this task,
obtaining an average hit rate of 95.7% and consequently the
lowest standard deviation values, as can be seen in the ﬁgure
1.

In the CTF task, the Claude 3 Opus model showed the
best performance, while the other models achieved lower
scores. Although the results for this topic show a greater
dispersion of results, with an average hit rate of 80%, it was
the Honeypots topic that obtained the highest value in terms

123

Fig. 1 CSLU results by subject

Fig. 2 CSLU results by model and subject

of standard deviation, demonstrating a greater variation of
results in relation to the average.

Overall, as shown in the table 1, it was expected that the
GPT-4 and Claude 3 Opus models would be the main candi-
dates for obtaining the best results, since these two models
contain the largest number of parameters of the models stud-
ied. It was subsequently found that the GPT-4, Gemini Pro
and Claude 3 Opus models showed uniformly superior results
among the models studied. As can be seen in ﬁgure 2, the
results obtained for each model evaluated in relation to the
respective topics studied, together with the average evalua-
tion obtained by each model.

The Code LLama model had the worst results, mainly
showing difﬁculties with the CTF exercises and Honeypots
topics. However, unlike the topics mentioned above, this
model was one of the four models to answer all the questions
on the Malware topic correctly, giving rise to a substantially
higher standard deviation than the other models.

4.2 Autonomous evaluation

The models performed best in the task of detecting Malware,
with practically all the models correctly detecting malicious
programs and categorising them according to their behaviour.

Evaluation of the maturity of LLMs in the cybersecurity domain

Page 9 of 13

197

Table 7 Heat map of the results obtained in the automatic test

The greatest inefﬁciency was detected in the generation of
CTFs exercises; most of the models did not achieve the max-
imum classiﬁcation due to the lack of artefacts needed to
carry out the exercise, since some of the APIs used only
return text. Although some models got around this limita-
tion, for example by providing the code needed to generate
these artefacts. In the case of prompt 4, which requires the
generation of a CTF exercise on the subject of steganogra-
phy, the models were unable to generate and return images,
which consequently meant that the exercise could not be fully
generated.

Overall, the GPT-3.5, GPT-4 and Claude 3 Opus mod-
els obtained the best results, notable for the fact that they
only failed to obtain the maximum classiﬁcation in a single
prompt.

A heat map was developed to facilitate the graphic visual-
isation of the results obtained, consisting of three categories
represented by colours. The categories used to classify
the models’ answers, namely “Correct”, “Plausible” and
“Incorrect”, were thus translated into the following graphic
representations: green, yellow and red, respectively. The
table 7 shows this heat map.

5 Discussion

The results obtained in the subsection 4.1, from a general
perspective, show that most of the models evaluated have a
good level of maturity, resulting in good indicators regarding
the feasibility of using these models in cybersecurity appli-
cations.

The ﬁndings of this study suggest that a possible LLM
approach for cybersecurity activities could be highly ben-
eﬁcial, as the results are quite satisfactory in terms of the
knowledge of the models evaluated in the theoretical domain
of the domains studied.

However, it is recognised that there is a difference between
the benchmarks, including the CSLU proposed by us, and the
real world. Most of them lack human validation, which has
led the market to ﬁnd solutions, such as Arena LMSYS [3,
20], to encompass real-world cases. In our case, it is therefore

necessary to explore ways of making these cases represen-
tative in the context of cybersecurity and to align the results
with the performance expected in real-world scenarios.

It was found that the biggest factor inhibiting results essen-
tially comes from the fact that only commercial models were
used, which in addition to not being speciﬁcally trained for
the topics studied, themselves use defence mechanisms that
can negatively inﬂuence the results. It is recognised that the
use of LLMs speciﬁcally and extensively trained for a single
topic would leverage the results.

The results obtained in the automatic test showed good
indicators for studying the viability of these models. By
studying factors such as creativity, adaptability or even the
state of knowledge of the models, it was possible to identify
the most promising models.

From a global perspective, after studying and analysing
the results obtained, it is possible to state that automating
the development and instantiation of cybersecurity artefacts
through the use of LLMs is expected to provide a faster and
more efﬁcient response to emerging threats. The ability to
quickly generate and deploy adapted defence mechanisms,
such as Honeypots with Malware analysis and detection
capabilities, will enable timely detection and mitigation of
potential intrusions, signiﬁcantly reducing the risk of critical
systems being compromised.

Secondly, automating the generation of CTF exercises
aims to increase the quality and quantity of practical mate-
rials on the subject of cybersecurity training, since not only
trainers but also teachers are obliged to devote a signiﬁcant
amount of their time to creating statements and support and
assessment materials. This approach would also make it pos-
sible to atomise assessment materials for students, helping
to combat plagiarism during assessment.

In the same way, the automation of repetitive and time-
consuming tasks frees up human resources, allowing cyber-
security professionals to focus on strategic analyses and the
development of proactive security policies. This optimisation
of human resource allocation will contribute to a signiﬁcant
improvement in operational efﬁciency and incident response
capacity.

5.1 Practical applications in operational

cybersecurity

The experimental results presented in this study have many
direct applications in cybersecurity related operational envi-
ronments. This section outlines, possible, speciﬁc implemen-
tation forms and operational considerations for organizations
seeking to leverage LLMs within their security infrastructure.

123

197

Page 10 of 13

T. Conceição, N. Cruz

5.1.1 Integration with security operations centers (SOCs)

Malware detection capabilities demonstrated by GPT-4,
Claude 3 Opus, and Gemini Pro models can be used within
SOC environments through several practical implementa-
tions. In our ﬁndings, we suggest that these models can
serve as an effective initial triage system, that, for exam-
ple, process suspicious code samples before human analysis.
The accuracy rates observed in our experimental evaluation
suggest that such systems could potentially reduce analysts’
workload, allowing security professionals to focus on more
complex threats that require human expertise.

LLMs can be deployed in order to generate automated
reports for identiﬁed malware samples. Such reports would
include detailed analyses of code behaviour, potential impact
vectors, and recommended remediation strategies,
thus
enhancing the efﬁciency of incident response processes. The
contextual understanding capabilities demonstrated by the
top performing models enable them to provide meaningful
analysis of anomalous events when integrated with existing
Security Information and Event Management (SIEM) plat-
forms via standardized API connections.

For the implementation within an operational environ-
ments, organizations should establish ﬁrst a veriﬁcation
method. We recommend that LLM outputs should be vali-
dated against established detection systems during an initial
calibration period. This veriﬁcation process ensures relia-
bility while allowing the organization to build conﬁdence in
the LLM-based detection mechanisms before full operational
deployment.

5.1.2 Honeypot deployment and management

The capability of Honeypot generation using LLMs, provides
leverage for several practical applications within enterprise
security architectures. Advanced LLMs are able to "under-
stand" system vulnerabilities, and attacker methodologies
enables automated conﬁguration of dynamic honeypots that
can adapt to emerging threat patterns, representing a signif-
icant advancement over traditional static honeypot deploy-
ments.

The capability of LLM-based systems to improve their
output would allow honeypots to evolve based on attacker
interaction data. As threat actors engage with these deception
systems, the collected behavioural data can be fed back into
the LLM to generate increasingly convincing decoys. This
creates a self-improving security mechanism that becomes
more effective over time.

Another valuable application is the generation ofbreak
organization-speciﬁc honeypots that mimic internal systems
with greater ﬁdelity by incorporating organizational context
into the prompt engineering process. Security teams can
develop honeypots that replicate proprietary systems and

123

applications, creating more convincing deception environ-
ments that are more likely to engage sophisticated attackers.
Implementation of such system would typically involve
a modular architecture where the LLM component gener-
ates honeypot speciﬁcations (such as using Dockerﬁles) that
would subsequently be instantiated through conﬁguration
management platforms, such as Ansible or Terraform. This
approach allows for scaling honeypot deployment across dis-
tributed networks with minimal human intervention, thus
extending defensive coverage across complex enterprise
environments.

5.1.3 Cybersecurity training and workforce development

The CTF exercise generation capabilities presented in our
study can be systematically applied to address critical chal-
lenges in cybersecurity education and professional devel-
opment. Our results show that LLMs are able to generate
training programs that could possibly adapt exercise com-
plexity to individual skill development trajectories. This
capability ensures continuous education systems that gen-
erate new challenges based on emerging threat vectors,
providing security professionals with a form of keeping their
knowledge up to updated with the latest attack methodolo-
gies.

In addition to providing training, the automated assess-
ment capabilities of LLM-generated CTF exercises provide
mechanisms for also evaluating cybersecurity skills with
customized feedback. This approach ensures more frequent
assessment intervals without increasing instructor work-
load. One possible result of this ability would be to create
large-scale security competitions and organizational training
initiatives, where unique challenges for numerous partici-
pants are created on demand.

5.1.4 Implementation considerations and limitations

While our ﬁndings show signiﬁcant potential for opera-
tional deployment, several important considerations should
guide implementation decisions. Human veriﬁcation remains
essential, particularly when analysing new threats or pro-
tecting critical systems. Rather than viewing LLMs as
replacements for human analysts, organizations should con-
ceptualize them as augmentation tools that enhance human
capabilities through initial analysis, pattern recognition, and
context provision.

Additionally, regular validation against ground-truthbreak
datasets is necessary in order to maintain performance
standards over time. As threat landscapes evolve, periodic
revalidation ensures that the models’ detection and gen-
eration capabilities remain effective against current attack
methodologies. This validation process should include both
known threat samples and synthetic examples designed to

Evaluation of the maturity of LLMs in the cybersecurity domain

Page 11 of 13

197

test the limits of model capabilities. Should also be taken
into account future LLM upgrades, allowing for evolution,
following current market trend, and improving on new model
capabilities.

Finally, it is important to acknowledge that performance
may vary when applying these models to highly specialized
environments, not considered in our analysis. Organiza-
tions with other security requirements or speciﬁc technology
stacks should perform targeted validation using domain-
speciﬁc examples before full-scale deployment.

5.1.5 Deployment architecture

The proposed integration of LLMs in operational cyberse-
curity follows an internal workﬂow model where security
professionals utilise these models as assistive tools within
existing security infrastructures. In this architecture, LLMs
operate as backend components triggered by automated
detection systems or manual requests from security analysts.
A possible workﬂow, for honeypot deployment, would
start with an Intrusion Detection System (IDS) or Security
Information and Event Management (SIEM) platforms that
would detect suspicious activity patterns. A trigger would
then request the LLM system for honeypot speciﬁcation gen-
eration adapted to the detected activity. The LLM would then
generate conﬁguration ﬁles and deployment scripts that are
would be then validated by the security operations centre
personnel before instantiation through existing infrastructure
management tools.

Similarly, in malware analysis scenarios, suspicious code
samples, identiﬁed through: i) automated scanning; or, ii)
analyst investigation; are submitted to LLMs for initial clas-
siﬁcation and analysis. The generated reports would serve as
a preliminary assessment that would feed subsequent human
analysis rather than replacing expert evaluation.

This internal deployment proposal, ensures that LLMs
operate within a controlled environment where inputs are
originated from trusted sources and outputs undergo valida-
tion before operational use.

5.1.6 Quality assurance and anomaly management

Our evaluation identiﬁed speciﬁc quality concerns in LLM-
generated security artefacts that require systematic atten-
tion. CTF exercise generation demonstrated particular chal-
lenges, including incomplete vulnerability implementations
that appeared functional but lacked actual exploitability,
inconsistencies between challenge descriptions and tech-
nical implementations, and unintended solution paths that
bypassed intended learning objectives. Such anomalies could
create misleading training experiences and compromise edu-
cational effectiveness.

Similarly, honeypot conﬁgurations occasionally contained
logical contradictions or inappropriate security settings that
might expose systems to additional risk rather than enhanc-
ing defensive capabilities. These quality issues necessitate
the implementation of automated veriﬁcation systems to
detect common anomaly patterns before artefact deployment,
including syntactic validation of generated code, logical con-
sistency checks for security conﬁgurations, and functional
testing of generated exercises.

5.2 Limitations and future directions: specialized

training approaches

While our evaluation framework focused on general-purpose
LLMs a specialized ﬁne-tuning methodologies and hybrid
human-in-the-loop approaches will expectedly yield superior
performance for domain-speciﬁc cybersecurity applications.
The choice for a general-purpose LLM was deliberate, aimed
at assessing baseline capabilities accessible to organizations
without a specialized AI development infrastructure.

Recent research shows that domain-speciﬁc ﬁne-tuning
can achieve substantial performance improvements. For
example, SecureFalcon, a specialized models, reaches 96%
detection accuracy, as presented by [18] and multitask
approaches like MSIVD, by [17], is able to achieve F1
scores of 0.92. Human-in-the-loop methodologies also show
comparable, or even superior, performance in complex cyber-
security scenarios as shown by [13].

We consider that future research should systematically
compare domain-speciﬁc ﬁne-tuning performance improve-
ments against associated implementation costs and resource
requirements. Human-AI collaboration patterns also repre-
sent a promising direction for bridging automated efﬁciency
with specialized domain expertise.

6 Conclusion

A series of experimental studies were presented and dis-
cussed in order to determine the level of feasibility of LLMs
in relation to the tasks listed in the cybersecurity theme, with
emphasis on solutions for generating Honeypots, Malware
and CTF exercises. The adoption of structured assessment
models ensured consistency and reliability in the results
obtained. A systematic evaluation framework was developed
and implemented to assess LLM capabilities across cyberse-
curity domains, providing empirical evidence for the research
conclusions.

The conclusions drawn made it possible to carefully
choose the most suitable models to integrate with the tool to
be developed, one of the main objectives of which is to auto-
mate cybersecurity processes, particularly those that were
the subject of the study. The tool’s requirements were brieﬂy
outlined, followed by a proposal for its architecture.

123

197

Page 12 of 13

T. Conceição, N. Cruz

From an overall perspective, we have recognised and
proven the strong potential that the use of LLMs in the
ﬁeld of cybersecurity presents, with emphasis on automating
the development and instantiation of cybersecurity artefacts,
which is expected to provide a faster and more efﬁcient
response to emerging threats. Another valuable conclusion
was that automating the generation of CTF exercises aims
to increase the quality and quantity of practical materials
on the subject of cybersecurity training. The last conclusion
was that the adoption of LLM-based solutions optimises the
allocation of human resources, which will contribute to a sig-
niﬁcant improvement in operational efﬁciency and incident
response capacity.

In conclusion, we have endeavoured to provide a valu-
able insight into the potential future applications of LLMs in
cybersecurity, emphasising the need for continuous research
and improvement in the ﬁelds studied.

Appendix A: Guidelines to replicate work

This guideline aim to log the used methods to execute the
prompts in both evaluation frameworks, allowing the reader
to replicate the developed work. All prompts were exe-
cuted directly using front-end chat interfaces, allocated in
the internet. To interact with the GPT models were used the
ChatGPT4, while the Gemini model was used the Google’s
ofﬁcial chat, also entitled Gemini5. The remaining models
were used the Perplexity6 interface in order to interact with
the models. The datasets used in both evaluation frameworks
should be attached to this paper.

Supplementary Information The online version contains supplemen-
tary material available at https://doi.org/10.1007/s10207-025-01112-
1.

Author Contributions Tiago Conceição wrote the main manuscript text.
Nuno Cruz provided supervision to all the work performed. All authors
reviewed the manuscript.

Funding Open access funding provided by FCT|FCCN (b-on). This
research was supported by Fundação para a Ciência e a Tecnologia,
through LASIGE Research Unit, ref. UID/00408/2025.

Data Availability Data is provided within the supplementary informa-
tion ﬁles.

Declarations

Competing interest The authors declare that they have no competing
interest as deﬁned by Springer, or other interests that might be perceived
to inﬂuence the results and/or discussion reported in this paper.

4 https://chatgpt.com/
5 https://gemini.google.com/
6 https://www.perplexity.ai/

123

Competing interests The authors declare no competing interests.

Open Access This article is licensed under a Creative Commons
Attribution 4.0 International License, which permits use, sharing, adap-
tation, distribution and reproduction in any medium or format, as
long as you give appropriate credit to the original author(s) and the
source, provide a link to the Creative Commons licence, and indi-
cate if changes were made. The images or other third party material
in this article are included in the article’s Creative Commons licence,
unless indicated otherwise in a credit line to the material. If material
is not included in the article’s Creative Commons licence and your
intended use is not permitted by statutory regulation or exceeds the
permitted use, you will need to obtain permission directly from the copy-
right holder. To view a copy of this licence, visit http://creativecomm
ons.org/licenses/by/4.0/.

References

1. Bhambri, S., Chauhan, P., Araujo, F., Doupé, A., Kambhampati, S.:
Using deception in markov game to understand adversarial behav-
iors through a capture-the-ﬂag environment, (2022)

2. Bhusal, D., Alam, M. T., Nguyen, L., Mahara, A., Lightcap, Z.,
Frazier, R., Fieblinger, R., Torales, G. L., Blakely, B. A., Rastogi,
N.: Secure: Benchmarking large language models for cybersecurity
advisory, (2024). arxiv:2405.20441

3. Chiang, W.-L., Zheng, L., Sheng, Y. Angelopoulos, A. N., Li, T.,
et al.: Chatbot arena: An open platform for evaluating llms by
human preference, (2024). arxiv:2403.04132

4. Fadziso, T., Thaduri, U. R., Dekkati, S., Ballamudi, V. K. R.,
Desamsetti, H.: Evolution of the Cyber Security Threat: An
Overview of the Scale of Cyber Threat. 9 (2023). https://doi.org/
10.6084/m9.ﬁgshare.24189921.v1. https://ﬁgshare.com/articles/
journal_contribution/_b_Evolution_of_the_Cyber_Security_
Threat_An_Overview_of_the_Scale_of_Cyber_Threat_b_/
24189921

5. Fang, C., Miao, N., Srivastav, S., Liu, J., Zhang, R., Fang, R.,
Asmita, A., Tsang, R., Nazari, N., Wang, H., Homayoun, H.: Large
language models for code analysis: Do llms really do their job?,
(2023)

6. Gao, Z., Wang, H., Zhou, Y., Zhu, W., Zhang, C.: How far have
we gone in vulnerability detection using large language models,
(2023)

7. Guerra-Manzanares, A., Bahsi, H.: Experts still needed: boost-
ing long-term android malware detection with active learning. J.
Comput. Virol. Hack. Tech. 20, 901–918 (2024). https://doi.org/
10.1007/s11416-024-00536-y

8. Hendrycks, D., Burns, C., Basart, S., Zou, A ., Mazeika, M., Song,
D., Steinhardt, J.: Measuring massive multitask language under-
standing, (2021). arxiv:2009.03300

9. Liang, W., Zhang, Y., Wu, Z., Lepp, H., Ji, W., Zhao, X., Cao,
H., Liu, S., He, S., Huang, Z., Yang, D., Potts, C., Manning, C. D.,
Zou, J. Y.: Mapping the increasing use of LLMs in scientiﬁc papers,
(2024)

10. Liu, J., An, H., Li, J., Liang, H.: Detecting exploit primitives auto-
matically for heap vulnerabilities on binary programs, (2022)
11. Liu, Z., Shi, J., Buford, J.: Cyberbench: A multi-task benchmark

for evaluating large language models in cybersecurity. 02 (2024)

12. McKee, F., Noever, D.:Chatbots in a honeypot world, (2023)
13. Shao, M., Chen, B., Jancheska, S., Dolan-Gavitt, B., Garg, S., Karri,
R., Shaﬁque, M.:. An empirical evaluation of llms for solving offen-
sive security challenges, (2024)

14. Sladi´c,M., Valeros, V., Catania, C., Garcia, S.: LLM in the shell:

Generative honeypots, (2024). arxiv:2309.00155

Evaluation of the maturity of LLMs in the cybersecurity domain

Page 13 of 13

197

15. Stewart Kirubakaran, S., Ebenezer, V., Santhiya, P., Manojkumar,
G., Sophia, S., Snowlin Preethi, J. A. S.:. An effective study on dif-
ferent levels of honeypot with applications and design of real time
honeypot. In 2023 2nd International Conference on Edge Comput-
ing and Applications (ICECAA), pages 1209–1212, 2023. https://
doi.org/10.1109/ICECAA58104.2023.10212345

16. Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia,
F., Chi, E., Le, Q., Zhou, D.: Chain-of-thought prompting elicits
reasoning in large language models, (2023)

17. Yang, A. Z. H., Tian, H., Ye, H., Martins, R., Goues, C. L.: Security
vulnerability detection with multitask self-instructed ﬁne-tuning of
large language models, (2024)

18. Zhang, J., Bu, H., Wen, H., Liu, Y., Fei, H., Xi, R., Li, L., Yang,
Y., Zhu, H., Meng, D.: When llms meet cybersecurity: a systematic
literature review. Cybersecurity 8(1), 55, ISSN 2523-3246 (2025).
https://doi.org/10.1186/s42400-025-00361-w

19. Zhang, Y., Song, W., Ji, Z., Danfeng, Yao, Meng, N.: How well

does llm generate security tests?, (2023)

20. Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., et al.:
Judging llm-as-a-judge with mt-bench and chatbot arena. In A. Oh,
T. Naumann, A. Globerson, K. Saenko, M. Hardt, and S. Levine,
editors, Advances in Neural Information Processing Systems, vol-
ume 36, pages 46595–46623. Curran Associates, Inc., (2023)

Publisher’s Note Springer Nature remains neutral with regard to juris-
dictional claims in published maps and institutional afﬁliations.

123

