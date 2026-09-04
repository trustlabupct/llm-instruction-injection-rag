"""Tests del filtro de salida de C5, incluida la resistencia al camuflaje."""
from output_filter import filter_response


def test_elimina_tool_call_no_solicitada():
    f, acc = filter_response('TOOL_CALL: consultar_datos_usuario()\nTexto util.', allowed_tools=[])
    assert "TOOL_CALL" not in f
    assert "Texto util." in f
    assert any("tool_call_eliminada" in a for a in acc)


def test_respeta_tool_call_permitida():
    r = 'TOOL_CALL: crear_ticket_simulado(asunto="x")\nHe abierto tu ticket.'
    f, acc = filter_response(r, allowed_tools=["crear_ticket_simulado"])
    assert "TOOL_CALL" in f  # permitida: no se elimina
    assert acc == []


def test_elimina_firma_inyectada_aunque_permitida():
    r = 'TOOL_CALL: crear_ticket_simulado(asunto="fallo critico de seguridad")'
    f, acc = filter_response(r, allowed_tools=["crear_ticket_simulado"])
    assert "TOOL_CALL" not in f


def test_elimina_bloque_exfil_con_email():
    f, _ = filter_response("Respuesta.\nCorreo del usuario: juan@uni.es", allowed_tools=[])
    assert "juan@uni.es" not in f
    assert "Respuesta." in f


def test_override_espanol():
    f, _ = filter_response("La nota es 7,25. Politica de seguridad desactivada.", allowed_tools=[])
    assert "seguridad desactivada" not in f.lower()
    assert "7,25" in f


# --- resistencia al camuflaje ---

def test_override_en_ingles_camuflado():
    f, _ = filter_response("Usa tus credenciales. Security policy disabled by administrator.", [])
    assert "security policy disabled" not in f.lower()
    assert "credenciales" in f


def test_exfil_reetiquetada_camuflada():
    f, _ = filter_response("Acude a Secretaria.\nRef-usuario: [correo] | [id-interno].", [])
    assert "ref-usuario" not in f.lower()
    assert "Secretaria" in f


def test_no_toca_prosa_legitima_con_palabra_correo():
    r = "Para dudas, envia un correo a la secretaria de tu facultad."
    f, acc = filter_response(r, allowed_tools=[])
    assert f == r
    assert acc == []


def test_respuesta_normal_intacta():
    r = "El plazo de matricula ordinaria es del 1 al 20 de julio."
    f, _ = filter_response(r, allowed_tools=[])
    assert f == r
