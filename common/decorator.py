#!-*- utf-8 -*-

import json
from django.http import JsonResponse
from common.base_response import BadRequestResponse

HookNameSet = ['merge_request_hooks', 'note_hooks']
ActionSet = ['open', 'comment', 'update']


def permission_check_decorator(func):
    """
    检查请求是否是符合规则
    """

    def wrapper(request, *args, **kwargs):

        data = json.loads(request.body)

        hook_name, action = data.get('hook_name'), data.get('action')

        if not hook_name or not action:
            return BadRequestResponse()

        if hook_name not in HookNameSet or action not in ActionSet:
            return BadRequestResponse()

        request.JSON = data

        # 非法请求
        request.InvalidRequest = True if (not hook_name or not action or not pr_url) else False
        # PR创建或者打开事件
        request.IsPRCreatOROpenEvent = True if (hook_name == 'merge_request_hooks' and action == 'open') else False
        # PR更新事件
        request.IsPRUpdateEvent = True if (hook_name == 'merge_request_hooks' and action == 'update') else False
        # 评论事件
        request.IsCommentEvent = True if (hook_name == 'note_hooks' and action == 'comment') else False

        return func(request, *args, **kwargs)

    return wrapper
