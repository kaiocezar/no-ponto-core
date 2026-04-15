"""Paginação cursor padrão da API."""

from rest_framework.pagination import CursorPagination as _CursorPagination
from rest_framework.response import Response


class CursorPagination(_CursorPagination):
    """
    Cursor pagination com resposta no padrão { data: [...], meta: {...} }.

    Mais eficiente que offset pagination para tabelas grandes.
    Evita drift de páginas em listagens em tempo real (novos agendamentos
    entrando enquanto o usuário navega).
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"

    def get_paginated_response(self, data: list) -> Response:
        return Response(
            {
                "data": data,
                "meta": {
                    "next_cursor": self.get_next_link(),
                    "previous_cursor": self.get_previous_link(),
                    "count": self.page.paginator.count  # type: ignore[union-attr]
                    if hasattr(self.page, "paginator")
                    else None,
                },
            }
        )

    def get_paginated_response_schema(self, schema: dict) -> dict:
        return {
            "type": "object",
            "properties": {
                "data": schema,
                "meta": {
                    "type": "object",
                    "properties": {
                        "next_cursor": {"type": "string", "nullable": True},
                        "previous_cursor": {"type": "string", "nullable": True},
                        "count": {"type": "integer", "nullable": True},
                    },
                },
            },
        }
