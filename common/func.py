#!-*- utf-8 -*-

import re
import yaml
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")


def has_chinese_regex(string: str) -> bool:
    """
    字符串是否包含中文
    :params string:
    :return:
    """
    pattern = re.compile(r'[\u4e00-\u9fa5]')
    if pattern.search(string):
        return True

    return False


def load_yaml(path):
    """
    加载yaml文件
    :params path: yaml路径
    :return:
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def exec_cmd(cmd: list[str]) -> tuple[int, str]:
    """
    执行shell脚本
    :params cmd: 执行命令列表
    :return: tuple(状态码, 脚本执行标准输出), 状态码0: 执行成功, 1: 执行异常
    """
    try:
        result = subprocess.run(cmd,
                                capture_output=True,
                                text=True,
                                )
    except Exception as err:
        logging.error(err)
        return 1, ""

    code, out, err = result.returncode, result.stdout, result.stderr
    if code != 0:
        logging.info(f"some err happened, please check: {err}")
        return 1, ""

    return 0, out
