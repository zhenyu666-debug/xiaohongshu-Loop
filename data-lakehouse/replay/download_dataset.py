"""
下载阿里云天池淘宝用户行为数据集
使用方法:
    python download_dataset.py --cookie "your-tianchi-cookie" --output data/raw/

注意：需要先在天池官网登录后获取 Cookie。
Cookie 可通过浏览器开发者工具 -> Network -> 找到任意请求的 Header 中的 Cookie 值获取。
"""

import argparse
import os
import sys
import time
import requests
from pathlib import Path

TIANCHI_API = "https://tianchi.aliyun.com/dataset/api/dataset/file/detail"
TIANCHI_PAGE = "https://tianchi.aliyun.com/dataset/649"


def get_download_url(cookie: str) -> str:
    """从天池 API 获取下载链接"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie,
        "Referer": TIANCHI_PAGE,
    }
    try:
        resp = requests.get(TIANCHI_PAGE, headers=headers, timeout=30)
        resp.raise_for_status()
        # 从页面中提取下载 token 或 API
        # 具体实现取决于天池的实际接口，可能需要逆向
        print("已获取页面，请手动访问以下地址下载数据集：")
        print(f"  {TIANCHI_PAGE}")
        print("登录后点击下载按钮。")
        return None
    except Exception as e:
        print(f"获取下载链接失败: {e}")
        return None


def download_with_progress(url: str, output_path: Path, cookie: str):
    """带进度条的文件下载"""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": cookie,
        "Referer": TIANCHI_PAGE,
    }
    response = requests.get(url, headers=headers, stream=True, timeout=300)
    response.raise_for_status()
    total_size = int(response.headers.get("Content-Length", 0))
    downloaded = 0
    chunk_size = 1024 * 1024  # 1MB

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = downloaded * 100 / total_size
                    print(f"\r下载进度: {pct:.1f}% ({downloaded//1024//1024}MB/{total_size//1024//1024}MB)", end="")
                else:
                    print(f"\r已下载: {downloaded//1024//1024}MB", end="")

    print(f"\n下载完成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="下载天池淘宝用户行为数据集")
    parser.add_argument("--cookie", help="天池登录 Cookie")
    parser.add_argument("--output", default="data/raw/UserBehavior.csv", help="输出文件路径")
    parser.add_argument("--url", help="直接提供下载 URL（绕过 Cookie）")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.url:
        print(f"使用提供的 URL 下载...")
        download_with_progress(args.url, output, args.cookie or "")
        return

    if args.cookie:
        url = get_download_url(args.cookie)
        if url:
            download_with_progress(url, output, args.cookie)
    else:
        print("请选择以下方式之一下载数据集：")
        print()
        print("方式 1：手动下载（推荐）")
        print(f"  1. 访问 {TIANCHI_PAGE}")
        print("  2. 登录后下载 UserBehavior.csv.zip")
        print("  3. 解压得到 UserBehavior.csv")
        print(f"  4. 放入 {output.parent}")
        print()
        print("方式 2：提供 Cookie 自动下载")
        print("  python download_dataset.py --cookie 'your-cookie' --output data/raw/")
        print()
        print("方式 3：使用 GitHub 镜像")
        print("  https://github.com/zq2599/blog_download_files/tree/master/files")


if __name__ == "__main__":
    main()
