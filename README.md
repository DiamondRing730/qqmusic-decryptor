# QQ音乐解密工具 🎵

本项目提供一套基于 Python 的自动化脚本，用于批量解密 QQ 音乐加密音频文件（`.mflac`），并自动补全歌曲的元信息（包括歌手、专辑、封面、曲目顺序等），最终输出带完整标签的 FLAC 音频文件。

---
最新版是dist，解密和标签补全合并了，并添加driver版本检测机制

## 📦 功能介绍

- 自动上传并解密 `.mflac` 文件，生成标准 `.flac`
- 自动调用 QQ 音乐接口补全歌曲标签和专辑封面
- 支持批量处理，保留文件顺序和元信息完整性
- 分为两步脚本，分别负责解密和标签写入，便于流程管理
---
## ⚙️ 环境依赖与准备
### 1. Python 环境
- 推荐使用 Python 3.7 及以上版本  
- 安装必备依赖库：
```bash
pip install selenium mutagen requests
````
### 2. 浏览器与驱动
* 安装 **Microsoft Edge 浏览器**（建议最新稳定版）
* 下载对应版本的 **Edge WebDriver (msedgedriver)**：
  [https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/)
* 解压 `msedgedriver.exe`，放置到合适目录（如 `E:\edge\`）
* 确保代码中配置了正确的驱动路径，例如：
```python
edge_driver_path = r"E:\edge\msedgedriver.exe"
```
---
## 📁 默认路径说明

| 类型        | 路径                          | 说明                 |
| --------- | --------------------------- | ------------------ |
| QQ音乐下载目录  | `E:\music\VipSongsDownload` | `.mflac` 文件所在目录    |
| 解码输出目录    | `E:\edge\raw`               | 解密后 `.flac` 文件保存目录 |
| 标签写入后保存目录 | `E:\edge\done`              | 补全标签、封面后的最终文件保存目录  |
---
## 🛠 使用步骤
1. 将你从 QQ 音乐下载的 `.mflac` 文件放入 `E:\music\VipSongsDownload`
2. 运行 `music_decode_web.py` 脚本，程序会自动上传并解密，生成的 `.flac` 文件保存到 `E:\edge\raw`
3. 运行 `music_edit.py` 脚本，自动查询并写入歌曲元信息与封面，生成的文件保存到 `E:\edge\done`
---
## 🔧 自定义路径
代码中路径是写死的绝对路径，若你的文件目录不同，请修改脚本中的路径变量，例如：
```python
input_dir = r"E:\music\VipSongsDownload"
output_dir = r"E:\edge\raw"
final_dir = r"E:\edge\done"
```
你也可以改造代码，使用配置文件、环境变量或命令行参数传递路径以增强灵活性。
---
## ⚠️ 注意事项

* 确保 Edge 浏览器版本与下载的 WebDriver 版本对应，否则 Selenium 启动会失败
* 网络环境需可访问 `https://unlock-music.lmb520.cn/` 和 QQ 音乐相关接口
* 运行脚本前请关闭可能占用目标文件夹的程序，避免文件被锁定
* 处理大量文件时，建议耐心等待解密和下载完成，避免中途终止
---
## 📖 项目结构（示例）

```
qqmusic-decryptor/
│
├─ music_decode_web.py       # 解密及批量下载脚本
├─ music_edit.py             # 元数据补全脚本
├─ README.md                 # 本文件
└─ config.json (可选)       # 路径配置文件（如果使用）
```
## 🙋‍♂️ 联系与反馈

如遇问题欢迎通过 GitHub 提交 Issue，或联系项目维护者：

* GitHub: [DiamondRing730](https://github.com/DiamondRing730)
---
