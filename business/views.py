#!-*- utf-8 -*-

import logging

from django.http import HttpResponse
from django.views.generic import View
from django.utils.decorators import method_decorator

from common.decorator import permission_check_decorator
from common.base_response import BadRequestResponse, OkResponse

from business.service import call

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")


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
        pr_url: str = request.JSON.get("merge_request", {}).get("url")

        logging.info(f"PR link: {pr_url}")

        if not pr_url or request.InvalidRequest:
            return BadRequestResponse()

        owner, repo, _, pr_id = pr_url.replace("https://gitcode.com/", "").split("/")
        if request.IsPRCreatOROpenEvent:  # PR创建或者打开事件
            call(owner, repo, "", pr_id, "create")

        elif request.IsPRUpdateEvent:  # PR更新事件
            pass

        elif request.IsCommentEvent:  # 评论事件
            pass

        else:
            return BadRequestResponse(msg="Invalid Event")

        return OkResponse()
