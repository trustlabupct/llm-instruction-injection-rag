# TFG — Evaluación experimental de ataques de *instruction injection* en sistemas LLM con RAG

**Autora:** Sofía González Sancho · Grado en Ciencia de Datos
**TRUST Lab — Universidad Politécnica de Cartagena**

Este repositorio reúne **todo el Trabajo Fin de Grado**: la memoria, la presentación de
defensa con sus materiales de apoyo, el código completo del experimento y la documentación
metodológica. Está organizado en carpetas numeradas para poder revisarlo por partes.

---

## De qué trata

Un sistema **RAG** (Retrieval-Augmented Generation) responde preguntas usando documentos que
recupera automáticamente. El problema: el modelo **no distingue** entre las instrucciones de su
desarrollador y el contenido de esos documentos. Si un atacante cuela un documento con
instrucciones ocultas, el modelo puede obedecerlas. Es la **inyección indirecta de
instrucciones**, la vulnerabilidad nº 1 de la lista OWASP para aplicaciones con LLM.

Este trabajo monta un banco de pruebas **local y reproducible** (modelo `llama3.1:8b` vía Ollama)
y mide, bajo **cinco configuraciones de defensa (C1–C5)**, cuántas veces funcionan los ataques y
cuánto se resiente la utilidad del asistente. La aportación propia es **C5**, un filtro de salida
que consigue a la vez el ataque más bajo (14,8 %) y la utilidad más alta (62,5 %).

---

## Cómo está organizado

| Carpeta | Contenido |
|---|---|
| **`01_memoria/`** | La memoria del TFG (`memoria_tfg.docx`): documento principal, con figuras y tablas. |
| **`02_presentacion/`** | La presentación de defensa (`presentacion_defensa.pptx`) y el **glosario** de términos (`glosario_terminos.md`). |
| **`03_codigo/`** | El **proyecto de software** completo: el experimento, documentación de apoyo, el modelo, las defensas, los tests, el panel interactivo y el despliegue con Docker. Tiene su propio README técnico. |

---

## Por dónde empezar

- **Para leer el trabajo** → `01_memoria/memoria_tfg.docx`.
- **Para seguir la defensa** → `02_presentacion/` (diapositivas + glosario).
- **Para ejecutar el experimento** → `03_codigo/README.md` (instrucciones con Docker o en local).

---

## Resultados en una tabla

| Config. | Defensa | ASR (ataque) | Utilidad |
|---|---|---|---|
| C1 | ninguna | 70,4 % | 50,0 % |
| C2 | + herramientas | 74,1 % | 53,1 % |
| C3 | + etiquetado de fuentes | 66,7 % | 62,5 % |
| C4 | + política estricta | 29,6 % | 34,4 % |
| **C5** | **+ filtro de salida (aportación propia)** | **14,8 %** | **62,5 %** |

*Modelo local `llama3.1:8b`, temperatura 0 y semilla fija → resultados deterministas y
reproducibles. Contrastado con intervalos de confianza (bootstrap) y test de McNemar.*
