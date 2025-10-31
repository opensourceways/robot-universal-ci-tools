#!-*- utf-8 -*-

import logging
import re
from multiprocessing import Process

from django.conf import settings

from common.gitcode import GitcodeApp
from common.func import has_chinese_regex, load_yaml, exec_cmd, clean_up
from common.config import CheckListHeader_ZH, Category_ZH, CheckListHeader_EN, Category_EN, FAILURE_COMMENT, \
    PR_CONFLICT_COMMENT, REVIEW_STATUS, WaitConFirmLabel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")


class PRHandlerService:

    def __init__(self,
                 owner: str,
                 repo: str,
                 access_token: str,
                 pr_id: int
                 ):
        self.owner = owner
        self.repo = repo
        self.token = access_token
        self.pr_id = pr_id

        self.is_cn = True  # 是否是中文评论
        self.checklist_header = CheckListHeader_ZH  # checklist 表头
        self.category = Category_ZH  # checklist 分类
        self.root_dir = settings.BASE_DIR  # 项目根目录
        self.config_path = f"{self.root_dir}/config/reviewer_checklist_zh.yaml"  # 配置文件路径
        self.line_id = 0  # checklist item id
        self.repo_dir = f"{self.root_dir}/data/{self.owner}_{self.repo}_{self.pr_id}"  # 代码下载目录

        self.gitcode_app = GitcodeApp(owner, repo, access_token)

    def choose_language(self, pr_detail):
        """
        根据PR详情选择 checklist 语言
        :params pr_detail: pr 详情
        :return
        """
        title = pr_detail.get("tile", "")
        body = pr_detail.get("body", "")
        if not has_chinese_regex(title) and not has_chinese_regex(body):
            self.is_cn = False
            self.checklist_header = CheckListHeader_EN
            self.category = Category_EN
            self.config_path = f"{self.root_dir}/config/reviewer_checklist_en.yaml"

    def check_programing_language(self, branch) -> dict:
        """
        检测编程语言类别
        :return: dict, key: 编程语言,  value: 编程语言规范
        """
        result = {}
        cmd = [f"{self.root_dir}/tools/git_diff.sh", self.repo, branch, self.repo_dir, "--name-only"]
        code, output = exec_cmd(cmd)

        if code != 0:
            logging.error(f"{self.owner}/{self.repo}/{self.pr_id}: get git diff files failed")
            return result

        for item in output.splitlines():
            if item.endswith(".py"):
                result.update({"Python": "pylint-3"})
            elif item.endswith(".go"):
                result.update({"GO": "golint"})
            elif item.endswith(".c") or item.endswith(".cpp") or item.endswith(".h"):
                result.update({"C/C++": "pclint"})

        return result

    def has_add_file(self, branch: str) -> bool:
        """
        检查本次pr是否新增文件
        :param branch:
        :return:
        """
        cmd = [f"{self.root_dir}/tools/git_diff.sh", self.repo, branch, self.repo_dir, "--name-only --diff-filter=A"]
        code, output = exec_cmd(cmd)
        if code != 0:
            logging.error(f"{self.owner}/{self.repo}/{self.pr_id}: get git add files failed")
            return False
        return bool(output.splitlines())

    def has_modify_spec_file(self,
                             branch: str,
                             keyword: str
                             ) -> bool:
        """
        检查是否对 .spec 文件做修改: 对文件中license、version的字段做更改
        :param branch:
        :param keyword:
        :return:
        """
        cmd = [f"{self.root_dir}/tools/git_diff.sh", self.repo, branch, self.repo_dir, "--name-only --diff-filter=M"]
        code, output = exec_cmd(cmd)
        if code != 0:
            logging.error(f"{self.owner}/{self.repo}/{self.pr_id}: get git add files failed")
            return False

        for file_name in output.splitlines():
            if file_name.endswith(".spec"):
                cmd = [f"{self.root_dir}/tools/git_diff.sh", self.repo, branch, self.repo_dir, "", file_name]

                code, diffs = exec_cmd(cmd)
                if code != 0:
                    logging.error(f"{self.owner}/{self.repo}/{self.pr_id}: get files {file_name} diff failed")
                    return False

                diff_lines = [x for x in diffs.splitlines() if re.match(f"^[+-]{keyword}", x)]
                if len(diff_lines) != 2:
                    break

                cur_value, old_value = "", ""
                for diff_line in diff_lines:
                    if diff_line.startswith(f"+{keyword}:"):
                        cur_value = diff_line.split(":")[1].strip()
                    elif diff_line.startswith(f"-{keyword}:"):
                        old_value = diff_line.split(":")[1].strip()

                if cur_value != old_value:
                    return True
        return False

    def format_checklist_item(self,
                              category: str,
                              claim: str,
                              explain: str,
                              value: str = REVIEW_STATUS["ongoing"],
                              ):
        """
        格式化 checklist item
        :param category: 审视类别
        :param claim: 审视要求
        :param explain: 审视要求说明
        :param value: 审视结果, 固定选项, REVIEW_STATUS.values()
        :return:
        """
        item_template = "|{}|{}|{}|{}|{}|\n"
        res = item_template.format(self.line_id, category, claim, explain, value)
        self.line_id += 1
        return res

    def basic_review(self,
                     checklist: dict,
                     branch: str,
                     ) -> str:
        """
        基础检查项
        :param checklist: yaml.load -> config.review_checklist_**.yaml .basic部分
        :param branch: 合入分支
        :return: checklist 内容
        """
        if not checklist:
            return ""

        res = []
        for review_type, items in checklist.items():
            category = self.category.get(review_type)
            for item in items:
                condition, name = item.get("condition"), item.get("name")
                claim, explain = item.get("claim"), item.get("explain")

                line = self.format_checklist_item(category, claim, explain)
                # 添加静态检查 item
                if condition == "code-modified" and name == "static-check":
                    _dict = self.check_programing_language(branch)

                    if not _dict:
                        continue

                    _lg, _er = "/".join(_dict.keys()), "/".join(_dict.values())
                    res.append(line.format(lang=_lg, checker=_er))
                # 是否有新增文件
                elif condition == "new-file-add" and not self.has_add_file(branch):
                    continue
                elif condition == "license-change" and not self.has_modify_spec_file(branch, "License"):
                    continue
                elif condition == "version-change" and branch == "master" and not \
                        self.has_modify_spec_file(branch, "Version"):
                    continue
                else:
                    res.append(line)

        return "".join(res)

    def src_openeuler_review(self,
                             checklist: dict,
                             branch: str
                             ) -> str:
        """

        :param checklist: yaml.load -> config.review_checklist_**.yaml .src-openeuler部分
        :param branch: 合入分支
        :return: checklist 内容
        """
        res = []
        for review_type, items in checklist.items():
            category = self.category.get(review_type)

            for item in items:
                claim, explain, name = item.get("claim"), item.get("explain"), item.get("name")

                if name == "PR-latest-version" and branch == "master":
                    continue

                line = self.format_checklist_item(category, claim, explain)
                res.append(line)

        return "".join(res)

    def community_review(self, checklist: dict) -> str:
        """
        定制化checklist, 仅针对 openeuler/community 仓
        :param checklist:  yaml.load -> config.review_checklist_**.yaml .customization部分
        :return:
        """
        res = []
        for repo, items in checklist.items():
            if self.repo != repo:
                continue
            # todo
            for item in items:
                pass

        return "".join(res)

    def generate_checklist(self, pr_detail: dict) -> str:
        """
        生成 review checklist列表
        :params pr_detail: pr详情, json
        :return: review comment内容
        """
        branch = pr_detail.get("base", {}).get("label")
        if pr_detail.get("mergeable"):
            return PR_CONFLICT_COMMENT.format(owner=pr_detail.get("user", {}).get("login"))

        # review header
        review = self.checklist_header.format(go=REVIEW_STATUS['go'],
                                              nogo=REVIEW_STATUS['nogo'],
                                              na=REVIEW_STATUS['na'],
                                              question=REVIEW_STATUS['question'],
                                              ongoing=REVIEW_STATUS['ongoing'])

        checklist = load_yaml(self.config_path)
        # 常规检查，对应checklist basic部分
        review += self.basic_review(checklist.get("basic"), branch)
        # src-openeuler的检查，对应checklist src-openeuler部分
        if self.owner == "src-openeuler":
            review += self.src_openeuler_review(checklist.get("src-openeuler", {}), branch)

        review += self.community_review(checklist.get("customization", {}))

        return review

    def delete_old_checklist(self):
        """
        获取所有历史checklist, 并删除
        :return:
        """
        comments = self.gitcode_app.get_pr_all_comments(self.pr_id)
        key = self.checklist_header[3:47]
        flag = False
        for comment in comments:
            if key in comment and not flag:
                flag = True
                continue
            elif key in comment and flag:
                comment_id = ""
                self.gitcode_app.delete_comment(comment_id)

    def add_wait_confirm_label(self, comment: str):
        """
        给 pr 添加 "wait_confirm" 标签
        :params comment: 评论列表内容
        :return:
        """
        if "等所有人" in comment or "approved by all members" in comment:
            labels = self.gitcode_app.get_pr_labels(self.pr_id)
            if WaitConFirmLabel not in labels:
                self.gitcode_app.add_pr_labels(self.pr_id, WaitConFirmLabel)

    def run(self, action: str) -> bool:
        """
        :params action: edit 编辑列表; create 创建列表
        :return:
        """
        pr_detail: dict = self.gitcode_app.get_pr_detail(self.pr_id)

        if not pr_detail:
            return False

        self.choose_language(pr_detail)

        if action == "edit":
            pass
        elif action == "create":
            branch = pr_detail.get("base", {}).get("label")
            if not branch:
                logging.error("Get pr target branch failed, exit")
                return False

            cmd = [f"{self.root_dir}/tools/prepare_env.sh", self.owner, self.repo, self.pr_id, branch, self.repo_dir]

            code, _ = exec_cmd(cmd)
            if code != 0:
                self.gitcode_app.create_comment(self.pr_id, FAILURE_COMMENT)
                return False

            # 生成评论内容
            comment = self.generate_checklist(pr_detail)

            # 评论 checklist
            if not self.gitcode_app.create_comment(self.pr_id, comment):
                return False

            # 删除旧的 checklist
            self.delete_old_checklist()

            # 更新 wait_confirm 标签
            self.add_wait_confirm_label(comment)

            # 清除环境
            clean_up(self.repo_dir)
            logging.info("push review list success")

            return True


def call(owner: str,
         repo: str,
         access_token: str,
         pr_id: int,
         action: str
         ) -> bool:
    """
    """
    service = PRHandlerService(owner=owner,
                               repo=repo,
                               access_token=access_token,
                               pr_id=pr_id
                               )
    if settings.DEBUG:
        return service.run(action)
    else:
        p = Process(target=service.run, args=(action,))
        p.start()
