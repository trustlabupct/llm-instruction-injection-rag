"""Tests del parseo y ejecucion de herramientas simuladas."""
import mock_tools


def test_parse_llamada_con_kwargs():
    calls = mock_tools.parse_tool_calls('TOOL_CALL: crear_ticket_simulado(asunto="a", descripcion="b")')
    assert calls == [("crear_ticket_simulado", {"asunto": "a", "descripcion": "b"})]


def test_parse_llamada_posicional():
    calls = mock_tools.parse_tool_calls('TOOL_CALL: crear_ticket_simulado("hola", "mundo")')
    assert calls == [("crear_ticket_simulado", {"asunto": "hola", "descripcion": "mundo"})]


def test_parse_consultar_sin_args():
    calls = mock_tools.parse_tool_calls("TOOL_CALL: consultar_datos_usuario()")
    assert calls == [("consultar_datos_usuario", {})]


def test_parse_varias_llamadas():
    txt = ('TOOL_CALL: consultar_datos_usuario(user_id="x")\n'
           'texto intermedio\n'
           'TOOL_CALL: buscar_documento(query="y")')
    calls = mock_tools.parse_tool_calls(txt)
    assert [c[0] for c in calls] == ["consultar_datos_usuario", "buscar_documento"]


def test_parse_texto_sin_llamadas():
    assert mock_tools.parse_tool_calls("una respuesta normal sin herramientas") == []


def test_execute_sin_efecto_real_y_canario():
    r = mock_tools.execute("consultar_datos_usuario", {"user_id": "demo"})
    assert r["internal_notes"] == "Informacion simulada no revelable"
    assert "@" in r["email"]


def test_execute_herramienta_desconocida():
    r = mock_tools.execute("herramienta_inexistente", {})
    assert "error" in r
