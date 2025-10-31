#!-*- utf-8 -*-

import json
import logging

from django.http import JsonResponse
from common.base_response import BadRequestResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

EventTypeSet = ["merge_request", "note"]
ActionSet = ["open", "reopen", "update"]


def permission_check_decorator(func):
    """
    检查请求是否是符合规则
    """

    def wrapper(request, *args, **kwargs):

        data = json.loads(request.body)

        event_type, action = data.get("event_type"), data.get("merge_request", {}).get("action")

        logging.info(f"Event_type: {event_type}, action: {action}")

        if not event_type or not action:
            return BadRequestResponse()

        if event_type not in EventTypeSet or action not in ActionSet:
            return BadRequestResponse()

        request.JSON = data

        # 非法请求
        request.InvalidRequest = True if (not event_type or not action) else False
        # PR创建或者打开事件
        request.IsPRCreatOROpenEvent = True if (event_type == "merge_request" and action in ["open", "reopen"]) else False
        # PR更新事件
        request.IsPRUpdateEvent = True if (event_type == "merge_request" and action == "update") else False
        # 评论事件
        request.IsCommentEvent = True if (event_type == "note" and action == "open") else False

        return func(request, *args, **kwargs)

    return wrapper
