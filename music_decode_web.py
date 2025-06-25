import os
import time
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 配置参数
input_dir = r"E:\music\VipSongsDownload"  # 源目录
output_dir = r"E:\edge\raw"  # 下载目录
edge_driver_path = r"E:\edge\msedgedriver.exe"  # 驱动路径


def setup_browser():
    """配置浏览器选项"""
    edge_options = EdgeOptions()
    prefs = {
        "download.default_directory": output_dir,
        "download.prompt_for_download": False,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    edge_options.add_experimental_option("prefs", prefs)

    service = EdgeService(executable_path=edge_driver_path)
    driver = webdriver.Edge(service=service, options=edge_options)
    return driver, WebDriverWait(driver, 30)


def wait_for_decryption(driver, wait, file_count):
    """等待所有文件解密完成"""
    print(f"🔍 正在监测解密进度(0/{file_count})", end="", flush=True)
    decrypted = 0

    while decrypted < file_count:
        # 检测解密结果表格行数
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
    """等待所有文件下载完成"""
    print(f"⏬ 正在监测下载进度(0/{file_count})", end="", flush=True)
    downloaded = set()
    start_time = time.time()

    while len(downloaded) < file_count:
        # 获取已完成的文件（排除临时文件）
        current_files = {
            f for f in os.listdir(output_dir)
            if not (f.endswith('.crdownload') or f.endswith('.tmp'))
               and os.path.getsize(os.path.join(output_dir, f)) > 1024  # 文件需大于1KB
        }
        new_files = current_files - downloaded

        if new_files:
            downloaded.update(new_files)
            print(f"\r⏬ 正在监测下载进度({len(downloaded)}/{file_count})", end="", flush=True)

        # 超时检查（最长等待5分钟）
        if time.time() - start_time > 300:
            print(f"\n⚠️ 下载超时（完成 {len(downloaded)}/{file_count}）")
            return False

        time.sleep(2)

    print("\n✅ 所有文件下载完成！")
    return True


def main():
    # 初始化浏览器
    driver, wait = setup_browser()

    try:
        # 访问网站
        driver.get("https://unlock-music.lmb520.cn/")
        print("🌐 网站加载中...")

        # 获取待处理文件
        mflac_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.mflac')]
        if not mflac_files:
            print("❌ 未找到.mflac文件")
            return

        file_count = len(mflac_files)
        print(f"📂 发现 {file_count} 个待处理文件")

        # 上传文件
        upload_box = wait.until(
            EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
        )
        upload_box.send_keys("\n".join(os.path.join(input_dir, f) for f in mflac_files))
        print(f"⬆️ 已上传 {file_count} 个文件")

        # 等待解密完成
        if not wait_for_decryption(driver, wait, file_count):
            print("❌ 解密过程异常")
            return

        # 点击下载全部
        try:
            download_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[.//span[contains(text(),"下载全部")]]'))
            )
            download_btn.click()
            print("💾 已触发批量下载")
        except Exception as e:
            print(f"❌ 下载按钮点击失败: {e}")
            return

        # 等待下载完成
        if not wait_for_downloads(file_count):
            print("⚠️ 下载未全部完成")

        # 删除源文件
        success_count = 0
        for f in mflac_files:
            try:
                os.remove(os.path.join(input_dir, f))
                success_count += 1
            except Exception as e:
                print(f"⚠️ 删除失败 {f}: {e}")

        print(f"🧹 已清理 {success_count}/{file_count} 个源文件")

    finally:
        driver.quit()
        print("🚫 浏览器已关闭")


if __name__ == "__main__":
    main()