#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stub histórico de Metricool MCP: integración retirada y fail-closed.

Se mantienen las funciones públicas para que imports antiguos fallen de forma
explícita en vez de reactivar silenciosamente el workflow cancelado.
"""

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


def mcp_call(method, params=None, call_id=1):
    _refuse_metricool()


def list_tools():
    _refuse_metricool()


def call_tool(tool_name, arguments):
    _refuse_metricool()


if __name__ == "__main__":
    _refuse_metricool()
