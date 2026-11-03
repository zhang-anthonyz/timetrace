"""Turn process metadata into a friendly application name."""

from __future__ import annotations

import re
from pathlib import Path

from .win32 import file_description

KNOWN_NAMES: dict[str, str] = {
    "timetrace.exe": "时迹",
    "timeflow.exe": "时迹",
    "explorer.exe": "文件资源管理器",
    "notepad.exe": "记事本",
    "calc.exe": "计算器",
    "mspaint.exe": "画图",
    "cmd.exe": "命令提示符",
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell",
    "windowsterminal.exe": "Windows Terminal",
    "applicationframehost.exe": "Windows 应用",
    "lockapp.exe": "锁屏",
    "logonui.exe": "登录界面",
    "searchhost.exe": "Windows 搜索",
    "shellexperiencehost.exe": "Windows 界面",
    "startmenuexperiencehost.exe": "开始菜单",
    "wechat.exe": "微信",
    "weixin.exe": "微信",
    "qq.exe": "QQ",
    "dingtalk.exe": "钉钉",
    "feishu.exe": "飞书",
    "lark.exe": "飞书",
    "wps.exe": "WPS Office",
    "winword.exe": "Word",
    "excel.exe": "Excel",
    "powerpnt.exe": "PowerPoint",
    "outlook.exe": "Outlook",
    "onenote.exe": "OneNote",
    "teams.exe": "Microsoft Teams",
    "ms-teams.exe": "Microsoft Teams",
    "code.exe": "Visual Studio Code",
    "devenv.exe": "Visual Studio",
    "idea64.exe": "IntelliJ IDEA",
    "idea.exe": "IntelliJ IDEA",
    "pycharm64.exe": "PyCharm",
    "pycharm.exe": "PyCharm",
    "webstorm64.exe": "WebStorm",
    "goland64.exe": "GoLand",
    "clion64.exe": "CLion",
    "sublime_text.exe": "Sublime Text",
    "notepad++.exe": "Notepad++",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
    "spotify.exe": "Spotify",
    "steam.exe": "Steam",
    "steamwebhelper.exe": "Steam",
    "discord.exe": "Discord",
    "telegram.exe": "Telegram",
    "slack.exe": "Slack",
    "zoom.exe": "Zoom",
    "vlc.exe": "VLC",
    "mpc-hc64.exe": "MPC-HC",
    "photoshop.exe": "Adobe Photoshop",
    "illustrator.exe": "Adobe Illustrator",
    "acrobat.exe": "Adobe Acrobat",
    "acrord32.exe": "Adobe Reader",
    "python.exe": "Python",
    "pythonw.exe": "Python",
    "java.exe": "Java",
    "javaw.exe": "Java",
    "git-bash.exe": "Git Bash",
    "mintty.exe": "Git Bash",
}


def process_stem(process_name: str) -> str:
    stem = Path(process_name).stem
    stem = re.sub(r"[-_]+", " ", stem).strip()
    return stem or process_name or "未知应用"


def friendly_name(process_name: str, exe_path: str = "") -> str:
    key = (process_name or "").lower()
    if key in KNOWN_NAMES:
        return KNOWN_NAMES[key]

    description = file_description(exe_path) if exe_path else ""
    description = _clean(description)
    if description and _is_useful(description):
        return description

    stem = process_stem(process_name)
    if stem.islower():
        return stem.title()
    return stem


def _clean(text: str) -> str:
    text = text.replace("®", "").replace("™", "").replace("©", "")
    return re.sub(r"\s+", " ", text).strip()


def _is_useful(text: str) -> bool:
    lowered = text.lower()
    if not text or len(text) > 80:
        return False
    if text.startswith("@"):
        return False
    if "windows operating system" in lowered:
        return False
    if lowered in {"application", "setup", "installer", "launcher"}:
        return False
    return True
