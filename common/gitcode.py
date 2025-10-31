#!-*- utf-8 -*-
import logging

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

SUC_CODE = [200, 201, 204]


class GitcodeApp:

    def __init__(self,
                 owner: str,
                 repo: str,
                 access_token: str
                 ):
        self.owner = owner
        self.repo = repo
        self.token = access_token

        self.base_url = "https://api.gitcode.com/api/v5"

    def get_pr_all_comments(self, pr_id: int, direction: str = "desc"):
        """
        https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-pulls-number-comments
        获取 pr 所有评论
        :param pr_id:
        :param direction:asc 升序, desc 降序
        :return: 评论json
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_id}/comments"

        page = 1
        params = {
            "per_page": 10,
            "access_token": self.token,
            "direction": direction,
            "comment_type": "pr_comment"
        }

        result = []
        while True:
            params.update(page=page)
            response = requests.get(url, params=params)
            result.extend(response.json())

            total_page = response.headers.get("total_page")

            if not total_page or int(total_page) <= page:
                break
            page += 1

        return result

    def create_comment(self, pr_id: int, body: str) -> bool:
        """
        https://docs.gitcode.com/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-comments
        创建一个评论
        :param pr_id:
        :param body: 评论内容
        :return:
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_id}/comments?access_token={self.token}"
        response = requests.post(url, json=dict(body=body))

        if response.status_code not in SUC_CODE:
            logging.info(f"create pr comment failed, {response.text}")
            return False

        return True

    def delete_comment(self, comment_id: str) -> bool:
        """
        https://docs.gitcode.com/docs/apis/delete-api-v-5-repos-owner-repo-pulls-comments-id
        删除一个评论
        :param comment_id: 评论id
        :return:
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/comments/{comment_id}?access_token={self.token}"
        response = requests.delete(url)

        if response.status_code not in SUC_CODE:
            logging.info(f"delete comment: {comment_id} failed: {response.text}")
            return False

        return True

    def edit_comment(self, comment_id: str, body: str) -> bool:
        """
        https://docs.gitcode.com/docs/apis/patch-api-v-5-repos-owner-repo-pulls-comments-id
        编辑一个评论
        :param comment_id: 评论id
        :param body: 需要更新的评论内容
        :return:
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/comments/{comment_id}?access_token={self.token}"
        response = requests.patch(url, json=body)

        if response.status_code not in SUC_CODE:
            logging.info(f"edit comment: {comment_id} failed, {response.text}")
            return False

        return True

    def get_pr_labels(self, pr_id: int) -> list[str]:
        """
        https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-pulls-number-labels
        获取pr所有标签
        :param pr_id:
        :return: 标签列表
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_id}/labels?access_token={self.token}"
        response = requests.get(url)
        if response.status_code not in SUC_CODE:
            logging.info(f"Get Pr Labels failed: {response.text}")
        labels = [x.get("name") for x in response.json()]
        return labels

    def del_pr_labels(self, pr_id: int, labels: str) -> bool:
        """
        https://docs.gitcode.com/docs/apis/delete-api-v-5-repos-owner-repo-pulls-number-labels-name
        删除pr标签
        :param pr_id:
        :param labels: 标签，多个标签用,分割，eg: "bug,feature"
        :return:
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_id}/labels/{labels}?access_token={self.token}"
        response = requests.delete(url)

        if response.status_code not in SUC_CODE:
            logging.info(f"delete repo: {self.repo}, pr: {pr_id}, labels: {labels} failed: {response.text}")
            return False

        return True

    def add_pr_labels(self, pr_id: int, labels: list[str]) -> bool:
        """
        https://docs.gitcode.com/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-labels
        新增pr标签
        :param pr_id:
        :param labels: 标签，多个标签用,分割，eg: "bug,feature"
        :return: 标签列表
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_id}/labels?access_token={self.token}"
        response = requests.post(url, json=labels)

        if response.status_code not in SUC_CODE:
            logging.info(f"add repo: {self.repo}, pr: {pr_id} label failed: {response.text}")
            return False

        return True

    def get_pr_detail(self, pr_id: int):
        """
        https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-pulls-number
        获取pr详情
        :params pr_id:
        :return: pr详情
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_id}?access_token={self.token}"
        response = requests.get(url)

        if response.status_code not in SUC_CODE:
            logging.info(f"Get repo: {self.repo}, pr: {pr_id} detail failed: {response.text}")
            return

        return response.json()


if __name__ == '__main__':
    app = GitcodeApp(owner="ascend",
                     repo="MindIE-LLM",
                     access_token=""
                     )
    app.get_pr_all_comments(10475)
