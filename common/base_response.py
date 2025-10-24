#!-*- utf-8 -*-

from django.http import JsonResponse


class BadRequestResponse(JsonResponse):
    def __init__(self, code: int = 400, msg: str = "Bad Request"):
        JsonResponse.__init__(self, status=400, data={"code": code, "msg": msg})


class OkResponse(JsonResponse):
    def __init__(self, code: int = 200, msg: str = "ok"):
        JsonResponse.__init__(self, status=200, data={"code": code, "msg": msg})
