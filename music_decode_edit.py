import os
import sys
import time
import argparse
import shutil
import requests
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import EasyMP3
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4, MP4Cover
from mutagen.wave import WAVE
from mutagen.oggvorbis import OggVorbis
from mutagen.aac import AAC

from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------- 相对路径支持 --------------------
# 获取exe所在目录
if getattr(sys, 'frozen', False):
    # 运行在打包后的exe中
    application_path = os.path.dirname(sys.executable)
else:
    # 运行在Python脚本中
    application_path = os.path.dirname(os.path.abspath(__file__))

# 设置相对路径
default_driver_path = os.path.join(application_path, "msedgedriver.exe")

# 保持你原来的输入输出路径
default_source_dir = r"E:\music\VipSongsDownload"
default_raw_dir = r"E:\edge\raw"
default_done_dir = r"E:\edge\done"

# ---------------- 参数解析 ----------------
parser = argparse.ArgumentParser(description="自动解密 QQ 音乐加密文件并补全标签")
parser.add_argument("--source", default=default_source_dir, help="源目录 (存放加密文件：.mflac/.mmp4/.mgg)")
parser.add_argument("--raw", default=default_raw_dir, help="解密输出目录")
parser.add_argument("--done", default=default_done_dir, help="最终处理目录")
parser.add_argument("--driver", default=default_driver_path, help="EdgeDriver 路径")
parser.add_argument("--threads", type=int, default=5, help="并行处理线程数")
args = parser.parse_args()

input_dir = args.source
raw_dir = args.raw
done_dir = args.done
edge_driver_path = args.driver
max_workers = args.threads

# ---------------- 全局缓存 ----------------
album_cache = {}  # 专辑信息缓存: albummid -> tracks
cover_cache = {}  # 封面URL缓存: albummid -> (url, size)
metadata_cache = {}  # 元数据缓存: query -> metadata


# ---------------- 版本检测函数 ----------------
def get_edge_version():
    """获取已安装的Edge浏览器版本"""
    try:
        result = subprocess.run(['reg', 'query',
                                 'HKEY_CURRENT_USER\\Software\\Microsoft\\Edge\\BLBeacon',
                                 '/v', 'version'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', result.stdout)
            if version_match:
                return version_match.group(1)
    except Exception:
        pass
    return "未知"


def get_driver_version(driver_path):
    """获取EdgeDriver版本"""
    try:
        if os.path.exists(driver_path):
            result = subprocess.run([driver_path, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', result.stdout)
                if version_match:
                    return version_match.group(1)
    except Exception:
        pass
    return "未知"


def check_driver_compatibility():
    """检查dist文件夹中的Driver版本，提供明确提示"""
    edge_version = get_edge_version()

    # 检查dist文件夹中是否有driver文件
    driver_exists = os.path.exists(edge_driver_path)

    if not driver_exists:
        print("\n❌ 未找到EdgeDriver文件")
        print("=" * 50)
        print(f"当前Edge浏览器版本: {edge_version}")
        print(f"需要下载的Driver版本: 与Edge版本匹配")
        print("\n📥 请执行以下操作:")
        print("1. 访问: https://developer.microsoft.com/zh-cn/microsoft-edge/tools/webdriver/")
        print("2. 下载与您Edge版本匹配的EdgeDriver")
        print(f"3. 将下载的msedgedriver.exe放在: {os.path.dirname(edge_driver_path)}")
        print("=" * 50)
        return False

    # 获取driver版本
    driver_version = get_driver_version(edge_driver_path)

    print(f"🔍 版本检查:")
    print(f"   - Edge浏览器版本: {edge_version}")
    print(f"   - 当前Driver版本: {driver_version}")

    if edge_version == "未知" or driver_version == "未知":
        print("⚠️ 无法完成版本检查，请手动确认驱动兼容性")
        return True

    # 提取主版本号进行比较
    edge_major = edge_version.split('.')[0]
    driver_major = driver_version.split('.')[0]

    if edge_major != driver_major:
        print("\n❌ Driver版本不匹配！")
        print("=" * 50)
        print(f"当前Edge版本: {edge_version}")
        print(f"当前Driver版本: {driver_version}")
        print(f"主版本号不匹配: Edge v{edge_major} ≠ Driver v{driver_major}")
        print("\n📥 请执行以下操作:")
        print("1. 访问: https://developer.microsoft.com/zh-cn/microsoft-edge/tools/webdriver/")
        print("2. 下载与您Edge版本匹配的EdgeDriver")
        print(f"3. 替换文件: {os.path.basename(edge_driver_path)}")
        print("=" * 50)
        return False

    print("✅ 版本兼容性检查通过")
    return True


# ---------------- 第一段：解密下载 ----------------
def setup_browser():
    if not check_driver_compatibility():
        print("\n💡 请按照上述提示操作后重新运行程序")
        exit(1)

    edge_options = EdgeOptions()
    prefs = {
        "download.default_directory": raw_dir,
        "download.prompt_for_download": False,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    edge_options.add_experimental_option("prefs", prefs)

    try:
        service = EdgeService(executable_path=edge_driver_path)
        driver = webdriver.Edge(service=service, options=edge_options)
        return driver, WebDriverWait(driver, 30)

    except Exception as e:
        print(f"❌ 浏览器启动失败: {e}")
        print("\n🔧 可能的原因:")
        print("1. Driver版本与Edge浏览器不匹配")
        print("2. Driver文件损坏")
        print("3. 请重新下载正确的Driver版本")
        exit(1)


def wait_for_decryption(driver, wait, file_count):
    print(f"🔍 正在监测解密进度(0/{file_count})", end="", flush=True)
    decrypted = 0
    while decrypted < file_count:
        rows = driver.find_elements(By.CSS_SELECTOR, '.el-table__body-wrapper tbody tr')
        current = len(rows)
        if current > decrypted:
            decrypted = current
            print(f"\r🔍 正在监测解密进度({decrypted}/{file_count})", end="", flush=True)
        if decrypted >= file_count:
            print("\n✅ 所有文件解密完成！")
            return True
        time.sleep(1)
    return False


def wait_for_downloads(file_count):
    print(f"⏬ 正在监测下载进度(0/{file_count})", end="", flush=True)
    downloaded = set()
    start_time = time.time()
    while len(downloaded) < file_count:
        current_files = {
            f for f in os.listdir(raw_dir)
            if not (f.endswith('.crdownload') or f.endswith('.tmp'))
               and os.path.getsize(os.path.join(raw_dir, f)) > 1024
        }
        new_files = current_files - downloaded
        if new_files:
            downloaded.update(new_files)
            print(f"\r⏬ 正在监测下载进度({len(downloaded)}/{file_count})", end="", flush=True)
        if time.time() - start_time > 300:
            print(f"\n⚠️ 下载超时（完成 {len(downloaded)}/{file_count}）")
            return False
        time.sleep(2)
    print("\n✅ 所有文件下载完成！")
    return True


def main():
    # 检查目录是否存在，如果不存在则创建
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)

    print(f"📁 输入目录: {input_dir}")
    print(f"📁 解密输出: {raw_dir}")
    print(f"📁 完成目录: {done_dir}")
    print("-" * 50)

    driver, wait = setup_browser()
    try:
        driver.get("https://unlock-music.lmb520.cn/")
        print("🌐 网站加载中...")

        enc_files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.mflac', '.mmp4', '.mgg'))]
        if not enc_files:
            print("❌ 未找到加密文件（.mflac/.mmp4/.mgg）")
            return

        file_count = len(enc_files)
        print(f"📂 发现 {file_count} 个待处理文件")

        upload_box = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="file"]')))
        upload_box.send_keys("\n".join(os.path.join(input_dir, f) for f in enc_files))
        print(f"⬆️ 已上传 {file_count} 个文件")

        if not wait_for_decryption(driver, wait, file_count):
            print("❌ 解密过程异常")
            return

        try:
            download_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[.//span[contains(text(),"下载全部")]]'))
            )
            download_btn.click()
            print("💾 已触发批量下载")
        except Exception as e:
            print(f"❌ 下载按钮点击失败: {e}")
            return

        if not wait_for_downloads(file_count):
            print("⚠️ 下载未全部完成")

        for f in enc_files:
            try:
                os.remove(os.path.join(input_dir, f))
            except Exception as e:
                print(f"⚠️ 删除失败 {f}: {e}")

    finally:
        driver.quit()
        print("🚫 浏览器已关闭")

    process_all_music()


# ---------------- 第二段：标签补全 ----------------
headers = {
    "Referer": "https://y.qq.com/",
    "User-Agent": "Mozilla/5.0"
}


def extract_song_info(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    try:
        if ext == '.flac':
            audio = FLAC(file_path)
            title = audio.get('title', [''])[0]
            artist = audio.get('artist', [''])[0]

        elif ext == '.mp3':
            audio = EasyMP3(file_path)
            title = audio.get('title', [''])[0]
            artist = audio.get('artist', [''])[0]

        elif ext in ['.m4a', '.mp4']:
            audio = MP4(file_path)
            title = audio.get("\xa9nam", [''])[0] if "\xa9nam" in audio else ''
            artist = audio.get("\xa9ART", [''])[0] if "\xa9ART" in audio else ''

        elif ext == '.ogg':
            audio = OggVorbis(file_path)
            title = audio.get('title', [''])[0]
            artist = audio.get('artist', [''])[0]

        else:
            return extract_from_filename(filename)

        if title and artist:
            return artist.strip(), title.strip()
        else:
            return extract_from_filename(filename)

    except Exception as e:
        print(f"⚠️ 读取文件标签失败 {filename}: {e}")
        return extract_from_filename(filename)


def extract_from_filename(filename):
    base = os.path.splitext(filename)[0]
    if ' - ' in base:
        parts = base.split(' - ', 1)
        return parts[0].strip(), parts[1].strip()
    return "", base.strip()


def search_song(query):
    # 检查缓存
    if query in metadata_cache:
        return metadata_cache[query]

    url = f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?format=json&p=1&n=1&w={query}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()

        if not data.get('data') or not data['data'].get('song') or not data['data']['song'].get('list') or len(
                data['data']['song']['list']) == 0:
            print(f"⚠️ 未找到歌曲: {query}")
            return None

        song = data['data']['song']['list'][0]
        cover_url, cover_size = get_best_cover_url(song['albummid'])

        metadata = {
            'title': song['songname'],
            'artist': song['singer'][0]['name'],
            'album': song['albumname'],
            'albummid': song['albummid'],
            'songmid': song['songmid'],
            'track': song.get('index_album', 0),
            'cover_url': cover_url,
            'cover_size': cover_size
        }

        # 存入缓存
        metadata_cache[query] = metadata
        return metadata

    except Exception as e:
        print(f"❌ 搜索歌曲时出错 {query}: {e}")
        return None


def get_best_cover_url(albummid):
    # 检查缓存
    if albummid in cover_cache:
        return cover_cache[albummid]

    sizes = ["1500", "800", "500", "300"]
    for size in sizes:
        url = f"https://y.qq.com/music/photo_new/T002R{size}x{size}M000{albummid}.jpg"
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200 and len(resp.content) > 10 * 1024:
                cover_cache[albummid] = (url, size)
                return url, size
        except:
            continue

    cover_cache[albummid] = ("", "0")
    return "", "0"


def get_album_tracks(albummid):
    # 检查缓存
    if albummid in album_cache:
        return album_cache[albummid]

    url = f"https://c.y.qq.com/v8/fcg-bin/fcg_v8_album_info_cp.fcg?albummid={albummid}&format=json"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        tracks = resp.json()['data']['list']
        album_cache[albummid] = tracks
        return tracks
    except:
        album_cache[albummid] = []
        return []


def find_track_number(tracks, songmid, title):
    for idx, track in enumerate(tracks, 1):
        if track['songmid'] == songmid:
            return idx
    for idx, track in enumerate(tracks, 1):
        if track['name'] == title:
            return idx
    return 0


def write_tags(file_path, metadata):
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == '.flac':
            audio = FLAC(file_path)
        elif ext == '.mp3':
            audio = EasyMP3(file_path)
        elif ext in ['.m4a', '.mp4']:
            audio = MP4(file_path)
        elif ext == '.wav':
            return False, "WAV 格式不支持标签写入"
        elif ext == '.aac':
            return False, "AAC 标签支持有限"
        elif ext == '.ogg':
            audio = OggVorbis(file_path)
        else:
            return False, f"不支持的文件类型: {ext}"

        if ext in ['.mp3', '.flac', '.ogg']:
            audio['title'] = metadata['title']
            audio['artist'] = metadata['artist']
            audio['album'] = metadata['album']
            audio['tracknumber'] = str(metadata['track'])
            audio['comment'] = "Processed by 𝗣𝗔𝗡"
        elif ext in ['.m4a', '.mp4']:
            audio["\xa9nam"] = metadata['title']
            audio["\xa9ART"] = metadata['artist']
            audio["\xa9alb"] = metadata['album']
            audio["trkn"] = [(metadata['track'], 0)]
            audio["desc"] = "Processed by 𝗣𝗔𝗡"

        if metadata['cover_url']:
            cover_data = requests.get(metadata['cover_url'], timeout=10).content
            if ext == '.flac':
                image = Picture()
                image.data = cover_data
                image.type = 3
                image.mime = "image/jpeg"
                audio.clear_pictures()
                audio.add_picture(image)
            elif ext == '.mp3':
                id3 = ID3(file_path)
                id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data))
                id3.save()
            elif ext in ['.m4a', '.mp4']:
                audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()
        return True, None
    except Exception as e:
        return False, f"写入标签失败: {e}"


def process_single_file(fname):
    """处理单个文件的函数，用于并行处理"""
    input_path = os.path.join(raw_dir, fname)

    try:
        artist, title = extract_song_info(input_path)
        query = f"{artist} {title}".strip()

        if not query or query.strip() == "":
            query = os.path.splitext(fname)[0]

        metadata = search_song(query)
        if not metadata:
            return fname, False, "获取元信息失败"

        tracks = get_album_tracks(metadata['albummid'])
        track_number = find_track_number(tracks, metadata['songmid'], metadata['title'])
        metadata['track'] = track_number if track_number > 0 else metadata.get('track', 1)

        ok, err = write_tags(input_path, metadata)
        if ok:
            shutil.move(input_path, os.path.join(done_dir, fname))
            return fname, True, metadata
        else:
            return fname, False, err

    except Exception as e:
        return fname, False, f"处理异常: {e}"


def process_all_music():
    os.makedirs(done_dir, exist_ok=True)
    success_count, fail_count = 0, 0
    failures = []

    files = [f for f in os.listdir(raw_dir) if
             f.lower().endswith(('.flac', '.mp3', '.m4a', '.mp4', '.wav', '.ogg', '.aac'))]
    total_files = len(files)

    if total_files == 0:
        print("❌ 没有找到可处理的音频文件")
        return

    print(f"🎵 开始处理 {total_files} 个文件，使用 {max_workers} 个线程...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_file, fname): fname for fname in files}

        for i, future in enumerate(as_completed(futures), 1):
            fname = futures[future]
            try:
                result = future.result()
                fname, success, data = result

                if success and isinstance(data, dict):
                    success_count += 1
                    print(f"[✅] ({i}/{total_files}) 已处理：{fname} (Track {data['track']})")
                    if data.get('cover_size') != "0":
                        print(f"    ↳ 封面分辨率：{data.get('cover_size')}x{data.get('cover_size')}")
                    print("    ↳ 签名：Processed by 𝗣𝗔𝗡")
                else:
                    fail_count += 1
                    failures.append((fname, data))
                    print(f"[❌] ({i}/{total_files}) 处理失败：{fname} - {data}")

            except Exception as e:
                fail_count += 1
                failures.append((fname, str(e)))
                print(f"[❌] ({i}/{total_files}) 处理异常：{fname} - {e}")

    end_time = time.time()
    total_time = end_time - start_time

    print("\n🎵 处理完成")
    print(f"⏱️ 总耗时: {total_time:.2f}秒")
    print(f"📊 平均每个文件: {total_time / total_files:.2f}秒")
    print(f"✅ 成功: {success_count} 个")
    print(f"❌ 失败: {fail_count} 个")

    if failures:
        print("---- 失败详情 ----")
        for fname, reason in failures:
            print(f"  - {fname} ：{reason}")


if __name__ == "__main__":
    try:
        main()
        print(f"\n🎉 全部完成！结果已保存到：{done_dir}")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
    finally:
        # 让界面停留，等待用户按键
        print("\n" + "=" * 50)
        print("程序执行完成，按任意键退出...")
        input()  # 等待用户按键