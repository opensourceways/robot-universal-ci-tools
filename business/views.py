import logging

from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import View
from django.utils.decorators import method_decorator

from common.decorator import permission_check_decorator
from common.base_response import BadRequestResponse, OkResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s: %(message)s")


class HealthCheckView(View):
    """
    健康检查
    """

    def get(self, *args, **kwargs):
        return HttpResponse(status=200, content="health check...")


@method_decorator(permission_check_decorator, name="post")
class CommunityPRCIView(View):
    """
    community仓门禁检查
    """

    def post(self, request, *args, **kwargs):
        hook_name = request.JSON.get('hook_name')
        action = request.JSON.get('action')
        pr_url = request.JSON.get("pull_request", {}).get("html_url")

        logging.info(f"Request detail: {{ \"hook name\": {hook_name}, \"action\": {action}, \"pr_url\": {pr_url} }}")

        if request.InvalidRequest:
            return BadRequestResponse()

        #
        if request.IsPRCreatOROpenEvent:
            pass

        elif request.IsPRUpdateEvent:
            pass

        elif request.IsCommentEvent:
            pass

        return OkResponse()
