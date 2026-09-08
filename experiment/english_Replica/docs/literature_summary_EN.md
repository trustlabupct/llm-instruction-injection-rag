# Summary of relevant literature

## 1. Prompt injection and instruction injection

**Prompt injection** is the technique by which an attacker introduces text into an LLM's input to
alter its behavior beyond what the system designer intended. The term was popularized by Riley
Goodside (2022) and later formalized as a systematic attack vector by Perez and Ribeiro (2022) in
the paper *"Ignore Previous Prompt: Attack Techniques For Language Models"*.

The distinction between **direct prompt injection** (the attacker directly controls the user's
input) and **indirect prompt injection** (the attacker poisons an external source that the model
reads) is key to this thesis. In the indirect scenario, the user asks a legitimate question but
the RAG system retrieves a document that contains malicious instructions. This variant was
analyzed in depth by Greshake et al. (2023) in *"Not What You've Signed Up For: Compromising
Real-World LLM-Integrated Applications with Indirect Prompt Injection"*, which demonstrated that
models integrated with search engines, calendars, and email are vulnerable to indirect attacks
via poisoned web pages or documents.

---

## 2. RAG systems and their attack surface

**Retrieval-Augmented Generation** systems (Lewis et al., 2020) add a document-retrieval
component to the LLM pipeline. The model receives the most relevant documents for the question
as context, which expands its knowledge base without requiring retraining. However, this design
introduces a blurred trust boundary: the model does not natively distinguish between its system
prompt (developer instructions) and the content of the retrieved documents.

This ambiguity is the root of the problem studied in this thesis. In a RAG system without
defenses, the model treats retrieved documents with the same level of authority as the system
prompt, which allows a poisoned document to override or modify the expected behavior.

---

## 3. Taxonomy of attacks

This work adopts the following classification, inspired by the literature and by the OWASP LLM
Top 10:

- **Instruction override:** the document attempts to get the model to ignore the system prompt
  and adopt new instructions (e.g., "ignore the previous instructions").
- **Context contamination:** the document introduces false information that the model assumes to
  be valid normative content, altering the content of the response without necessarily
  overriding the prompt.
- **Tool abuse:** the document forces the invocation of a tool that the user has not requested.
  In real agentic systems this could produce unauthorized actions.
- **Data exfiltration simulation:** the document induces the model to reveal internal data
  (identifiers, private notes) that should not appear in the response to the user.

---

## 4. Documented mitigations

The literature proposes several defensive strategies, with varying effectiveness:

**Explicit context separation.** Labeling retrieved documents as an untrusted source and
visually separating them from the system prompt has been shown to reduce the success rate of
instruction override attacks (Willison, 2022; Schulhoff et al., 2023). This is the mechanism
implemented by configuration C3 of the experiment.

**Tool-use policies.** Explicit restrictions in the system prompt on when a tool may be invoked
reduce tool abuse, although they can produce false negatives (the model refuses to use the tool
in response to a legitimate request). This is the mechanism added in C4.

**Instruction-following with sanitization.** Some works propose filtering the input before
sending it to the model (keyword blocking, regex over injection patterns). However, these
filters are easily bypassed through rephrasing and are not evaluated in this thesis.

**Defensive fine-tuning and RLHF.** Training the model specifically to resist injection
instructions produces improvements, but requires labeled data and computing capacity beyond the
scope of this work (Ziegler et al., 2019; Ouyang et al., 2022).

---

## 5. Reference frameworks

**OWASP LLM Top 10 (2025).** Vulnerability LLM01:2025 (*Prompt Injection*) is first on the list
and covers both the direct and indirect variants. Vulnerability LLM06:2025 (*Excessive Agency*)
describes the risk of LLM systems with access to tools that can execute unauthorized actions.
Both are directly relevant to this experiment.

**MITRE ATLAS.** The ATLAS matrix (Adversarial Threat Landscape for AI Systems) includes
technique AML.T0051 (*LLM Prompt Injection*) and the *Initial Access* tactic via manipulation of
training data or context. The attack families in this thesis correspond to variants of these
techniques.

---

## 6. Key references

1. Goodside, R. (2022). Exploiting GPT-3 prompts with malicious inputs. Twitter thread.
2. Perez, F. and Ribeiro, I. (2022). Ignore Previous Prompt: Attack Techniques For Language
   Models. *NeurIPS ML Safety Workshop*.
3. Greshake, K. et al. (2023). Not What You've Signed Up For: Compromising Real-World
   LLM-Integrated Applications with Indirect Prompt Injection. *arXiv:2302.12173*.
4. Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.
   *NeurIPS 2020*.
5. Schulhoff, S. et al. (2023). Ignore This Title and HackAPrompt: Exposing Systemic
   Vulnerabilities of LLMs through a Global Scale Prompt Hacking Competition. *arXiv:2311.16119*.
6. OWASP (2025). OWASP Top 10 for Large Language Model Applications.
   https://owasp.org/www-project-top-10-for-large-language-model-applications/
7. MITRE ATLAS (2024). Adversarial Threat Landscape for Artificial Intelligence Systems.
   https://atlas.mitre.org/

---

*Version: 1.0 — July 2026*
