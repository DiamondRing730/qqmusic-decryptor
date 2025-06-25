import os
import re
import requests
from mutagen.flac import FLAC, Picture
import shutil

input_dir = r"E:\edge\raw"
output_dir = r"E:\edge\done"

headers = {
    "Referer": "https://y.qq.com/",
    "User-Agent": "Mozilla/5.0"
}

def extract_song_info(filename):
    base = os.path.splitext(filename)[0]
    if ' - ' in base:
        parts = base.split(' - ', 1)
        artist = parts[0].strip()
        title = parts[1].strip()
        return artist, title
    else:
        return "", base.strip()

def search_song(query):
    url = f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?format=json&p=1&n=1&w={query}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        song = data['data']['song']['list'][0]
        cover_url, cover_size = get_best_cover_url(song['albummid'])
        return {
            'title': song['songname'],
            'artist': song['singer'][0]['name'],
            'album': song['albumname'],
            'albummid': song['albummid'],
            'songmid': song['songmid'],
            'track': song.get('index_album', 0),
            'cover_url': cover_url,
            'cover_size': cover_size
        }
    except Exception as e:
        print(f"[❌] 获取元信息失败: {query}，原因: {e}")
        return None

def get_best_cover_url(albummid):
    sizes = ["1500", "800", "500", "300"]
    for size in sizes:
        url = f"https://y.qq.com/music/photo_new/T002R{size}x{size}M000{albummid}.jpg"
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200 and len(resp.content) > 10 * 1024:
                return url, size
        except:
            continue
    return "", "0"

def get_album_tracks(albummid):
    url = f"https://c.y.qq.com/v8/fcg-bin/fcg_v8_album_info_cp.fcg?albummid={albummid}&format=json"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        tracks = data['data']['list']
        return tracks
    except Exception as e:
        print(f"[❌] 获取专辑曲目失败: {albummid}，原因: {e}")
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
    try:
        audio = FLAC(file_path)
        audio['title'] = metadata['title']
        audio['artist'] = metadata['artist']
        audio['album'] = metadata['album']
        audio['tracknumber'] = str(metadata['track'])
        audio['comment'] = "Processed by 𝗣𝗔𝗡"

        cover_data = requests.get(metadata['cover_url'], timeout=10).content
        image = Picture()
        image.data = cover_data
        image.type = 3
        image.mime = "image/jpeg"

        audio.clear_pictures()
        audio.add_picture(image)
        audio.save()

        print(f"[✅] 已处理：{os.path.basename(file_path)} (Track {metadata['track']})")
        print(f"    ↳ 封面分辨率：{metadata.get('cover_size')}x{metadata.get('cover_size')}")
        print(f"    ↳ 签名：Processed by 𝗣𝗔𝗡")
    except Exception as e:
        print(f"[❌] 写入标签失败: {file_path}，原因: {e}")

def process_all_flac():
    os.makedirs(output_dir, exist_ok=True)
    for fname in os.listdir(input_dir):
        if fname.lower().endswith('.flac'):
            input_path = os.path.join(input_dir, fname)
            artist, title = extract_song_info(fname)
            query = f"{artist} {title}".strip()
            metadata = search_song(query)
            if metadata:
                tracks = get_album_tracks(metadata['albummid'])
                track_number = find_track_number(tracks, metadata['songmid'], metadata['title'])
                if track_number > 0:
                    metadata['track'] = track_number
                else:
                    metadata['track'] = metadata.get('track', 1)
                write_tags(input_path, metadata)
                output_path = os.path.join(output_dir, fname)
                shutil.copy2(input_path, output_path)
                os.remove(input_path)
            else:
                print(f"[跳过] 无法获取元信息：{fname}")

if __name__ == "__main__":
    process_all_flac()
