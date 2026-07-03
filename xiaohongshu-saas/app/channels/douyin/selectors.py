"""Douyin creator web UI selectors (placeholder).

These are starting-point guesses. Verify against the live DOM before relying on
them — the douyin creator UI changes frequently.
"""


class Selectors:
    PUBLISH_TAB = "text=发布视频"
    FILE_INPUT = "input[type=file][accept^='video'], input[type=file][accept^='image']"
    UPLOAD_PROGRESS_DONE = "text=上传完成, .upload-progress-done"

    TITLE_INPUT = "input[placeholder^='添加标题']"
    BODY_EDITOR = "div[contenteditable='true']"
    TOPIC_INPUT = "input[placeholder^='添加话题']"

    SUBMIT_BUTTON = "button:has-text('发布'), button:has-text('立即发布')"
    SUCCESS_TOAST = "text=发布成功, .success-toast, text=已发布"