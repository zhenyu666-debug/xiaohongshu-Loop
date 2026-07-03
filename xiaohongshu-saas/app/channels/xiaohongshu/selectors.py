"""Xiaohongshu web UI selectors.

Keep all DOM selectors here so they can be tweaked in one place if the
Xiaohongshu creator web UI changes.
"""
from __future__ import annotations


class Selectors:
    PUBLISH_TAB = "text=上传图文"
    FILE_INPUT = "input[type=file][accept^='image']"
    VIDEO_FILE_INPUT = "input[type=file][accept^='video']"
    UPLOAD_PROGRESS_DONE = ".upload-progress[aria-valuenow='100'], .upload-done, text=上传完成"

    TITLE_INPUT = "input[placeholder^='填写标题']"
    BODY_EDITOR = "div[contenteditable='true']"
    TOPIC_INPUT = "input[placeholder^='输入话题']"

    SUBMIT_BUTTON = "button:has-text('发布'), button:has-text('立即发布')"
    SUCCESS_TOAST = "text=发布成功, .success-toast, text=已发布"