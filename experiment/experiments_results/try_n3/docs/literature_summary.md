# Resumen de literatura relevante

## 1. Prompt injection e instruction injection

**Prompt injection** es la técnica por la que un atacante introduce texto en la entrada de un
LLM para alterar su comportamiento más allá de lo previsto por el diseñador del sistema. El
término fue popularizado por Riley Goodside (2022) y formalizado posteriormente como vector de
ataque sistemático por Perez y Ribeiro (2022) en el artículo *«Ignore Previous Prompt: Attack
Techniques For Language Models»*.

La distinción entre **direct prompt injection** (el atacante controla directamente la entrada
del usuario) e **indirect prompt injection** (el atacante contamina una fuente externa que el
modelo lee) es clave para este TFG. En el escenario indirecto, el usuario hace una pregunta
legítima pero el sistema RAG recupera un documento que contiene instrucciones maliciosas. Esta
variante fue analizada en profundidad por Greshake et al. (2023) en *«Not What You've Signed
Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection»*,
que demostró que modelos integrados con buscadores, calendarios y correo electrónico son
vulnerables a ataques indirectos mediante páginas web o documentos contaminados.

---

## 2. Sistemas RAG y su superficie de ataque

Los sistemas de **Retrieval-Augmented Generation** (Lewis et al., 2020) añaden un componente
de recuperación documental al pipeline del LLM. El modelo recibe como contexto los documentos
más relevantes para la pregunta, lo que amplía su base de conocimiento sin necesidad de
reentrenamiento. Sin embargo, este diseño introduce una frontera de confianza difusa: el modelo
no distingue de forma nativa entre su system prompt (instrucciones del desarrollador) y el
contenido de los documentos recuperados.

Esta ambigüedad es la raíz del problema que estudia este TFG. En un sistema RAG sin defensas,
el modelo trata los documentos recuperados con el mismo nivel de autoridad que el system prompt,
lo que permite que un documento contaminado anule o modifique el comportamiento esperado.

---

## 3. Taxonomía de ataques

Este trabajo adopta la siguiente clasificación, inspirada en la literatura y en OWASP LLM Top 10:

- **Instruction override:** el documento intenta que el modelo ignore el system prompt y adopte
  nuevas instrucciones (ej.: «ignora las instrucciones anteriores»).
- **Context contamination:** el documento introduce información falsa que el modelo asume como
  normativa válida, alterando el contenido de la respuesta sin necesariamente anular el prompt.
- **Tool abuse:** el documento fuerza la invocación de una herramienta que el usuario no ha
  solicitado. En sistemas agentes reales esto podría producir acciones no autorizadas.
- **Data exfiltration simulation:** el documento induce al modelo a revelar datos internos
  (identificadores, notas privadas) que no deberían aparecer en la respuesta al usuario.

---

## 4. Mitigaciones documentadas

La literatura propone diversas estrategias defensivas, con eficacia variable:

**Separación explícita de contextos.** Etiquetar los documentos recuperados como fuente no
confiable y separarlos visualmente del system prompt ha mostrado reducir la tasa de éxito de
ataques de instruction override (Willison, 2022; Schulhoff et al., 2023). Este mecanismo es
el que implementa la configuración C3 del experimento.

**Políticas de uso de herramientas.** Restricciones explícitas en el system prompt sobre cuándo
está permitido invocar una herramienta reducen el tool abuse, aunque pueden generar falsos
negativos (el modelo rechaza usar la herramienta ante una solicitud legítima). Este es el
mecanismo añadido en C4.

**Instrucción-siguiendo con sanitización.** Algunos trabajos proponen filtrar el input antes de
enviarlo al modelo (keyword blocking, regex sobre patrones de injection). Sin embargo, estos
filtros son fácilmente eludibles mediante reformulación y no se evalúan en este TFG.

**Fine-tuning y RLHF defensivo.** Entrenar el modelo específicamente para resistir instrucciones
de injection produce mejoras, pero requiere datos etiquetados y capacidad de cómputo fuera del
alcance de este trabajo (Ziegler et al., 2019; Ouyang et al., 2022).

---

## 5. Marcos de referencia

**OWASP LLM Top 10 (2025).** La vulnerabilidad LLM01:2025 (*Prompt Injection*) es la primera
de la lista y cubre tanto la variante directa como la indirecta. La vulnerabilidad LLM06:2025
(*Excessive Agency*) describe el riesgo de sistemas LLM con acceso a herramientas que pueden
ejecutar acciones no autorizadas. Ambas son directamente relevantes para este experimento.

**MITRE ATLAS.** La matriz ATLAS (Adversarial Threat Landscape for AI Systems) incluye la
técnica AML.T0051 (*LLM Prompt Injection*) y el táctico *Initial Access* mediante manipulación
de datos de entrenamiento o contexto. Las familias de ataque del TFG se corresponden con
variantes de estas técnicas.

---

## 6. Referencias clave

1. Goodside, R. (2022). Exploiting GPT-3 prompts with malicious inputs. Twitter thread.
2. Perez, F. y Ribeiro, I. (2022). Ignore Previous Prompt: Attack Techniques For Language Models.
   *NeurIPS ML Safety Workshop*.
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

*Versión: 1.0 — julio de 2026*
