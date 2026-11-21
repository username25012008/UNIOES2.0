import json

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser
from rest_framework.views import exception_handler as drf_handler


class StrictJSONParser(JSONParser):
    """Тело запроса — только JSON-объект; массивы и числа дают 400, а не 500."""

    def parse(self, stream, media_type=None, parser_context=None):
        data = super().parse(stream, media_type, parser_context)
        if not isinstance(data, dict):
            raise ParseError("Ожидался JSON-объект")
        return data


def exception_handler(exc, context):
    from django.core.exceptions import ValidationError as DjVE
    from rest_framework.response import Response
    if isinstance(exc, (ValueError, TypeError, DjVE)) and not isinstance(exc, json.JSONDecodeError):
        return Response({"detail": "Некорректные данные запроса"}, status=400)
    return drf_handler(exc, context)
