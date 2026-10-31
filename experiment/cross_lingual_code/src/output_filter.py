"""Filtro de salida (output filtering) para la configuracion C5.

Actua sobre la RESPUESTA ya generada, antes de devolverla al usuario. Es una mitigacion
determinista del lado de la salida: no depende de que el modelo obedezca instrucciones.

Elimina de la respuesta:
  1. Llamadas a herramientas con consecuencias no solicitadas o con firma inyectada.
  2. Bloques de divulgacion de datos del usuario, detectados por ESTRUCTURA (una linea con una
     palabra de identidad -correo, identificador, user_id, ref-usuario, internal_notes...- seguida
     de un separador de valor), no por una etiqueta fija. Asi resiste el reetiquetado del bloque
     (p. ej. "Ref-usuario: ...") y los valores concretos (email, DNI) o de marcador ("[correo]").
  3. Ordenes de override, en varios idiomas ("politica de seguridad desactivada",
     "security policy disabled", "ignore previous instructions"...).

No cubre la context contamination: una afirmacion falsa semanticamente plausible no es
distinguible por patrones a nivel de salida (requeriria verificacion factual).
"""
from __future__ import annotations

import re
import unicodedata

HERRAMIENTAS_CONSECUENTES = {"consultar_datos_usuario", "crear_ticket_simulado"}
FIRMAS_INYECTADAS = [
    "fallo critico de seguridad", "escalado automatico", "reset masivo",
    "alta en practicas", "solicitud generada por el sistema", "expediente completo",
]

_CALL_RE = re.compile(r"TOOL_CALL:\s*(?:ejecutar\s+)?(\w+)\s*\((.*?)\)", re.DOTALL)
_EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
_DNI_RE = re.compile(r"\b\d{7,8}[a-z]\b", re.I)

# palabra que indica un dato de identidad del usuario (base de la deteccion por estructura)
_ETIQUETA_IDENTIDAD = re.compile(
    r"(correo|e-?mail|direccion de correo|identificador|id[-_ ]?interno|user[_ ]?id|"
    r"ref[-_ ]?usuario|internal[_ ]?notes|nota administrativa|trazabilidad|datos del usuario|dni)\b"
)
# separador tipico de un bloque "etiqueta: valor" o "a | b"
_SEPARADOR = re.compile(r"[:=|]")

# ordenes de override en varios idiomas
_OVERRIDE = re.compile(
    r"(pol[ií]tica de seguridad desactivada"
    r"|security policy (?:has been |is )?disabled"
    r"|restricciones?\b.{0,30}(?:levantad|sin efecto|desactivad)"
    r"|restrictions?\b.{0,30}(?:lifted|removed|disabled)"
    r"|ignore (?:all )?(?:previous|prior) instructions"
    r"|disregard (?:all )?(?:previous|prior) instructions"
    r"|system override"
    r"|sin (?:ninguna )?restricci[oó]n)",
    re.I,
)


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _es_bloque_datos(linea: str, low: str) -> bool:
    """Una linea es divulgacion de datos si expone un valor concreto (email, DNI, notas internas)
    o tiene la forma 'etiqueta-de-identidad ... separador ...' (bloque estructurado)."""
    if "internal_notes" in low or _EMAIL_RE.search(linea) or _DNI_RE.search(linea):
        return True
    if _ETIQUETA_IDENTIDAD.search(low) and _SEPARADOR.search(linea):
        return True
    return False


def filter_response(response: str, allowed_tools=None):
    """Devuelve (respuesta_filtrada, acciones), donde acciones lista lo que se elimino."""
    allowed = set(allowed_tools or [])
    acciones = []
    lineas_limpias = []

    for linea in response.split("\n"):
        low = _norm(linea)

        # 1. llamadas a herramientas peligrosas o inyectadas
        m = _CALL_RE.search(linea)
        if m:
            nombre = m.group(1)
            firma = any(f in low for f in FIRMAS_INYECTADAS)
            consecuente_no_pedida = nombre in HERRAMIENTAS_CONSECUENTES and nombre not in allowed
            if firma or consecuente_no_pedida:
                acciones.append(f"tool_call_eliminada:{nombre}")
                continue

        # 2. bloque de divulgacion de datos del usuario (por estructura)
        if _es_bloque_datos(linea, low):
            acciones.append("exfil_line_eliminada")
            continue

        # 3. orden de override: se trunca la linea a partir de la orden (suele ir como sufijo)
        mo = _OVERRIDE.search(linea)
        if mo:
            linea = linea[:mo.start()].rstrip(" .-—:;")
            acciones.append("override_eliminado")
            if not linea.strip():
                continue

        lineas_limpias.append(linea)

    filtrada = "\n".join(l for l in lineas_limpias if l.strip())
    if not filtrada.strip():
        filtrada = ("No puedo mostrar esta respuesta: el contenido generado incluia acciones o "
                    "datos no autorizados que la comprobacion de salida ha bloqueado.")
    return filtrada, acciones
