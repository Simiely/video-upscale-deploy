# -*- coding: utf-8 -*-
"""领域异常：让 UI 能区分“查版本失败 / 下载失败 / 解压失败”，而不是一律字符串。"""


class VEHelperError(Exception):
    """所有可预期错误的基类。"""


class ReleaseError(VEHelperError):
    pass


class DownloadError(VEHelperError):
    pass


class InstallError(VEHelperError):
    pass
