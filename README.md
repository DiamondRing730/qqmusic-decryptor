# QQ音乐解密工具 🎵

这是一个用于批量解密 `.mflac` 文件、补全元数据并打上封面的自动化脚本。

## 功能介绍

- 使用 Selenium 自动访问 Unlock Music 网站，上传并下载 `.flac`
- 使用 QQ 音乐接口自动补全标签（歌手/专辑/封面/曲序）
- 分两段脚本运行，搭配 PyCharm 使用最佳

## 如何使用

1. 下载项目
2. 安装依赖：`pip install -r requirements.txt`
3. 运行解密脚本：`python music_decode_web.py`
4. 运行标签补全脚本：`python music_edit.py`
