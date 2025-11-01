#!-*- utf-8 -*-

import logging
import re
from multiprocessing import Process

from django.conf import settings

from common.gitcode import GitcodeApp
from common.func import has_chinese_regex, load_yaml, exec_cmd
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
        title = pr_detail.get("title", "")
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
                # 添加静态检查 item
                if condition == "code-modified" and name == "static-check":
                    _dict = self.check_programing_language(branch)

                    if not _dict:
                        continue

                    _lg, _er = "/".join(_dict.keys()), "/".join(_dict.values())
                    line = self.format_checklist_item(category, claim, explain)
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
                    line = self.format_checklist_item(category, claim, explain)
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

    def load_remote_yaml(self, path: str) -> dict:
        """
        加载 remote path路径下yaml文件
        :param path: 仓库相对路径
        :return:
        """
        # 切换到master分支， 并加载master分支sig信息, 再恢复环境
        cmd = [f"{self.root_dir}/tools/git_checkout.sh", self.repo, "master", self.repo_dir]
        _, _ = exec_cmd(cmd)

        remote_sig_info = load_yaml(f"{self.repo_dir}/{path}")

        cmd = [f"{self.root_dir}/tools/git_checkout.sh", self.repo, f"tmp_pr_{self.pr_id}", self.repo_dir]
        _, _ = exec_cmd(cmd)

        return remote_sig_info

    def maintainer_changed_sigs(self, diff_files: list[str]) -> dict:
        """
        查找sig maintainer 有变化的sig; 修改 sig 的 maintainers需要 @SIG原所有 maintainers
        :param diff_files: 有变动的文件名称列表
        :return: key: sig-name, value: remote sig maintainers
        """
        sigs = {}
        for line in diff_files:
            status, file = re.split(r"\s+", line)
            if status != "M":
                continue

            if file.startswith("sig/") and file.endswith("/sig-info.yaml"):
                sig_name = file.split("/")[1]
                sig_info = load_yaml(f"{self.repo_dir}/{file}")
                maintainers = sig_info.get("maintainers", [])
                maintainer_ids = [x.get("gitee_id") for x in maintainers]  # todo

                remote_sig_info = self.load_remote_yaml(file)
                remote_maintainers = remote_sig_info.get("maintainers", [])
                remote_maintainer_ids = [x.get("gitee_id") for x in remote_maintainers]  # todo

                if set(maintainer_ids) != set(remote_maintainer_ids):
                    owners = [f"@{x}" for x in remote_maintainer_ids]
                    sigs[sig_name] = owners

        return sigs

    def sig_info_changed(self, diff_files: list[str]) -> dict:
        """
        检查有变化的 SIG, 并需要 @SIG原所有 maintainers
        :param diff_files: 有变动的文件名称列表
        :return: key: sig-name, value: remote sig maintainers
        :return:
        """
        sigs = {}
        for line in diff_files:
            status, file = re.split(r"\s+", line)
            if status not in ["A", "M"] or file == "sig/sigs.yaml" or not file.startswith("sig/"):
                continue

            sig_name = file.split("/")[1]

            if sig_name == "sig-template":
                continue

            remote_sig_info = self.load_remote_yaml(f"sig/{sig_name}/sig-info.yaml")

            remote_maintainers = remote_sig_info.get("maintainers", [])
            remote_maintainer_ids = [x.get("gitee_id") for x in remote_maintainers]  # todo

            owners = [f"@{x}" for x in remote_maintainer_ids]
            sigs[sig_name] = owners

        return sigs

    @staticmethod
    def is_repo_add(diff_files: list[str]) -> bool:
        """
        检查是否有 repo.yaml 变动
        :param diff_files: 有变动的文件名称列表
        :return:
        """
        for line in diff_files:
            status, file = re.split(r"\s+", line)

            if status == "A" and file.startswith("sig") and file.endswith(".yaml") and len(file.split("/")) == 5 \
                    and file.split("/")[2] in ["openeuler", "src-openeuler"]:
                return True

        return False

    @staticmethod
    def sig_recycle_changed(diff_files: list[str]) -> bool:
        """
        检测src-openeuler是否有文件被删除或者移除到 sig-recycle
        :param diff_files: 有变动的文件名称列表
        :return:
        """

        delete_set, add_to_recycle_set, add_to_other_set = set(), set(), set()
        for line in diff_files:
            status, file = re.split(r"\s+", line, maxsplit=1)

            # 更换路径, eg: R100 sig/A/test.yaml sig/B/test.yaml
            if status == "R100":
                file_tuple = re.split(r"\s+", file)
                if len(file_tuple) != 2:
                    continue
                route_lst = file_tuple[1].split("/")
                if len(route_lst) > 2 and route_lst[0] == "sig" and route_lst[1] == "sig-recycle" \
                        and route_lst[2] == "src-openeuler":
                    return True

            if file.startswith("sig/") and file.endswith(".yaml"):
                if status == "D":  # 删除
                    route_lst = file.split("/")
                    if len(route_lst) > 2 and route_lst[2] == "src-openeuler":
                        delete_set.add(route_lst[-1])
                elif status == "A":  # 新增
                    route_lst = file.split("/")
                    if len(route_lst) <= 2 or route_lst[2] != "src-openeuler":
                        continue
                    if route_lst[1] == "sig-recycle":
                        add_to_recycle_set.add(route_lst[-1])
                    else:
                        add_to_other_set.add(route_lst[-1])

        return bool(delete_set - add_to_other_set) or bool(add_to_recycle_set)

    def repo_sig_change(self, item: dict):
        """
        检查 repo.yaml 是否转移sig
        :param item: yaml.load -> config.review_checklist_**.yaml .customization. community: repo-ownership-check
        :return:
        """
        res = []
        # todo
        return res

    def committer_change(self,
                         diff_files: list,
                         category: str,
                         claim: str,
                         explain: str,
                         author: str) -> list:
        """
        committer 有变更
        :param diff_files: 有变动的文件名称列表
        :param category: checklist 类别
        :param claim: item.claim
        :param explain: item.explain
        :param author: pr 作者
        :return:
        """

        def _deal_with_commit(repo_inf: list, res_map: dict):
            """
            处理后的 res_map key: git id, value: repos
            """
            for item in repo_inf:
                _repos, _committers = item.get("repo", []), item.get("committers", [])
                [res_map.setdefault(x.get("gitee_id"), []).extend(_repos) for x in _committers]

        changed_committer_ids = set()
        for line in diff_files:
            status, file = re.split(r"\s+", line)
            committer_map, remote_committer_map = dict(), dict()
            if status != "M" and file.startswith("sig/") and file.endswith("/sig-info.yaml"):
                repo_info: list = load_yaml(file).get("repositories", [])
                remote_repo_info: list = self.load_remote_yaml(file).get("repositories", [])

                _deal_with_commit(repo_info, committer_map)
                _deal_with_commit(remote_repo_info, remote_committer_map)

                for committer, repos in committer_map.items():
                    remote_repos = remote_committer_map.get(committer, [])
                    if sorted(repos) != sorted(remote_repos):
                        changed_committer_ids.add(committer)

                for remote_committer, remote_repos in remote_committer_map.items():
                    repos = committer_map.get(remote_committer, [])
                    if sorted(repos) != sorted(remote_repos):
                        changed_committer_ids.add(remote_committer)

        changed_committer_ids.remove(author) if author in changed_committer_ids else None

        return [self.format_checklist_item(category, claim, explain).format(committer=x) for x in changed_committer_ids]

    def community_review(self, checklist: dict, author: str) -> str:
        """
        定制化checklist, 仅针对 openeuler/community 仓
        :param author: pr作者 gitcode id
        :param checklist:  yaml.load -> config.review_checklist_**.yaml .customization部分
        :return:
        """
        res = []

        cmd = [f"{self.root_dir}/tools/git_diff.sh", self.repo, "master", self.repo_dir, "--name-status", ""]
        _, diff_files = exec_cmd(cmd)

        lines = diff_files.splitlines()
        maintainer_changed_sigs = self.maintainer_changed_sigs(lines)
        sig_info_changed_sigs = self.sig_info_changed(lines)
        is_repo_add = self.is_repo_add(lines)
        is_recycle_sig_changed = self.sig_recycle_changed(lines)

        category = self.category.get("customization")
        for repo, items in checklist.items():  # 实际只有community仓
            if self.repo != repo:
                continue

            for item in items:

                condition, name = item.get("condition"), item.get("name")
                claim, explain = item.get("claim"), item.get("explain")
                # 新增or删除 sig maintainer
                if condition == "maintainer-change" and maintainer_changed_sigs:
                    if name == "maintainer-add-explain":
                        res.append(self.format_checklist_item(category, claim, explain))
                    elif name == "maintainer-change-lgtm":
                        for _sig, _maintainers in maintainer_changed_sigs.items():
                            res.append(self.format_checklist_item(category, claim, explain).format(sig=_sig,
                                                                                                   owners=_maintainers))
                # sig 有变动
                elif condition == "sig-update" and sig_info_changed_sigs:
                    for _sig, _maintainers in sig_info_changed_sigs.items():
                        if _sig in maintainer_changed_sigs.keys() or _sig == "sig-template":
                            continue
                        res.append(self.format_checklist_item(category, claim, explain).format(sig=_sig,
                                                                                               owners=_maintainers))
                # repo.yaml 新增或者变动
                elif condition == "repo-introduce" and is_repo_add:
                    res.append(self.format_checklist_item(category, claim, explain))
                elif condition == "sanity_check":
                    pass  # todo
                elif condition == "repo-ownership-change":
                    self.repo_sig_change(item)  # todo
                elif condition == "new-branch-add":
                    pass  # todo
                elif condition == "new-members-add":
                    pass  # todo
                # 文件被删除或移除至 sig-recycle
                elif condition == "repo-blacklist-change" and is_recycle_sig_changed:
                    res.append(self.format_checklist_item(category, claim, explain))
                elif condition == "sig-info-change":
                    pass  # 应该和sig-update有重合
                elif condition == "committer-change":
                    res.extend(self.committer_change(lines, category,  claim, explain, author))

        return "".join(res)

    def generate_checklist(self, pr_detail: dict) -> str:
        """
        生成 review checklist列表
        :params pr_detail: pr详情, json
        :return: review comment内容
        """
        branch = pr_detail.get("base", {}).get("label")
        author = pr_detail.get("user", {}).get("login")

        if not pr_detail.get("mergeable"):
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
        # 定制化检查
        review += self.community_review(checklist.get("customization", {}), author)

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
            body = comment.get("body", "")
            if key in body and not flag:
                flag = True
                continue
            elif key in body and flag:
                comment_id = comment.get("id")
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
            exec_cmd([f"{self.root_dir}/tools/clean_up.sh", self.repo_dir])
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
