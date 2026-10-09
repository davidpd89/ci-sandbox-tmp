#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibilidad histórica de Metricool: integración retirada.

Metricool está cancelado para este proyecto. Este módulo conserva los nombres
públicos que todavía pueden importar scripts históricos, pero toda operación de
OAuth/tokens falla antes de abrir navegador, servidor local o conexión remota.
"""

from pathlib import Path

TOKENS_FILE = Path(__file__).parent / "metricool_tokens.json"
TOKEN_ENDPOINT = "https://app.metricool.com/oauth/token"
AUTH_ENDPOINT = "https://app.metricool.com/oauth/authorize"
REG_ENDPOINT = "https://app.metricool.com/oauth/register"
MCP_ENDPOINT = "https://ai.metricool.com/mcp"

_MESSAGE = (
    "Metricool está retirado/cancelado en este proyecto. "
    "No autenticar, leer, programar, publicar, corregir ni confirmar mediante Metricool; "
    "usar publicación/programación manual y nativa."
)


class MetricoolRetired(RuntimeError):
    """La integración Metricool ya no es una vía operativa."""


def _refuse_metricool():
    raise MetricoolRetired(_MESSAGE)


def gen_pkce():
    _refuse_metricool()


def register_client():
    _refuse_metricool()


def exchange_code(code, verifier, client_id):
    _refuse_metricool()


def refresh_access_token(tokens):
    _refuse_metricool()


def load_tokens():
    _refuse_metricool()


def save_tokens(tokens):
    _refuse_metricool()


def get_valid_token():
    _refuse_metricool()


def do_login():
    _refuse_metricool()


if __name__ == "__main__":
    _refuse_metricool()
