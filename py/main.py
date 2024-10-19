import re
import requests
import logging
from collections import OrderedDict
from datetime import datetime
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("function.log", "w", encoding="utf-8"), logging.StreamHandler()])

def parse_template(template_file):
    template_channels = OrderedDict()
    current_category = None

    with open(template_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    template_channels[current_category] = []
                elif current_category:
                    channel_name = line.split(",")[0].strip()
                    template_channels[current_category].append(channel_name)

    return template_channels

def fetch_channels(url):
    channels = OrderedDict()

    try:
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.split("\n")
        current_category = None
        is_m3u = any("#EXTINF" in line for line in lines[:15])
        source_type = "m3u" if is_m3u else "txt"
        logging.info(f"url: {url} 获取成功，判断为{source_type}格式")

        if is_m3u:
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r'group-title="(.*?)",(.*)', line)
                    if match:
                        current_category = match.group(1).strip()
                        channel_name = match.group(2).strip()
                        if current_category not in channels:
                            channels[current_category] = []
                elif line and not line.startswith("#"):
                    channel_url = line.strip()
                    if current_category and channel_name:
                        channels[current_category].append((channel_name, channel_url))
        else:
            for line in lines:
                line = line.strip()
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    channels[current_category] = []
                elif current_category:
                    match = re.match(r"^(.*?),(.*?)$", line)
                    if match:
                        channel_name = match.group(1).strip()
                        channel_url = match.group(2).strip()
                        channels[current_category].append((channel_name, channel_url))
                    elif line:
                        channels[current_category].append((line, ''))
        if channels:
            categories = ", ".join(channels.keys())
            logging.info(f"url: {url} 爬取成功✅，包含频道分类: {categories}")
    except requests.RequestException as e:
        logging.error(f"url: {url} 爬取失败❌, Error: {e}")

    return channels

def match_channels(template_channels, all_channels):
    matched_channels = OrderedDict()

    for category, channel_list in template_channels.items():
        matched_channels[category] = OrderedDict()
        for channel_name in channel_list:
            for online_category, online_channel_list in all_channels.items():
                for online_channel_name, online_channel_url in online_channel_list:
                    if channel_name == online_channel_name:
                        matched_channels[category].setdefault(channel_name, []).append(online_channel_url)

    return matched_channels

def filter_source_urls(template_file):
    template_channels = parse_template(template_file)
    source_urls = config.source_urls

    all_channels = OrderedDict()
    for url in source_urls:
        fetched_channels = fetch_channels(url)
        for category, channel_list in fetched_channels.items():
            if category in all_channels:
                all_channels[category].extend(channel_list)
            else:
                all_channels[category] = channel_list

    matched_channels = match_channels(template_channels, all_channels)

    return matched_channels, template_channels

# 假设config是从某个地方导入的，这里我们简单模拟一下  
config = {  
    'announcements': [  
        {'channel': 'Channel1', 'entries': [{'name': 'Live1', 'url': 'http://example.com/stream1', 'logo': 'logo1.png'}]},  
        # 更多频道和公告  
    ],  
    'epg_urls': ['http://epg1.com', 'http://epg2.com'],  
    'ip_version_priority': 'ipv4',  # 假设我们默认优先ipv4  
    'url_blacklist': ['blacklist.com']  # 黑名单示例  
}  
  
# 检查是否为IPv6地址的函数  
def is_ipv6(url):  
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None  
  
# 检查是否为包含域名的IPv4地址的函数  
def is_valid_ipv4_with_domain(url):  
    # 这里使用简单的正则表达式来检查URL是否包含域名（不是IP地址）  
    # 并且是一个HTTP请求且端口号可选（默认80）  
    return re.match(r'^http:\/\/(?P<domain>[a-zA-Z0-9-]+\.[a-zA-Z]{2,})(?::\d+)?\/?', url) is not None  
  
def updateChannelUrlsM3U(channels, template_channels):  
    written_urls = set()  
  
    current_date = datetime.now().strftime("%Y-%m-%d")  
    for group in config.announcements:  
        for announcement in group['entries']:  
            if announcement['name'] is None:  
                announcement['name'] = current_date  
  
    with open("lv/live.m3u", "w", encoding="utf-8") as f_m3u:  
        f_m3u.write(f"""#EXTM3U x-tvg-url={",".join(f'"{epg_url}"' for epg_url in config.epg_urls)}\n""")  
  
        with open("lv/live.txt", "w", encoding="utf-8") as f_txt:  
            for group in config.announcements:  
                f_txt.write(f"{group['channel']},#genre#\n")  
                for announcement in group['entries']:  
                    # 假设公告中的URL总是有效的，这里直接写入  
                    f_m3u.write(f"""#EXTINF:-1 tvg-id="1" tvg-name="{announcement['name']}" tvg-logo="{announcement['logo']}" group-title="{group['channel']}",{announcement['name']}\n""")  
                    f_m3u.write(f"{announcement['url']}\n")  
                    f_txt.write(f"{announcement['name']},{announcement['url']}\n")  
  
            for category, channel_list in template_channels.items():  
                f_txt.write(f"{category},#genre#\n")  
                if category in channels:  
                    for channel_name in channel_list:  
                        if channel_name in channels[category]:  
                            # 过滤和排序URL，只保留有效的IPv4且包含域名的URL  
                            valid_urls = [url for url in channels[category][channel_name] if is_valid_ipv4_with_domain(url)]  
                            filtered_urls = []  
                            for url in valid_urls:  
                                if url and url not in written_urls and not any(blacklist in url for blacklist in config.url_blacklist):  
                                    filtered_urls.append(url)  
                                    written_urls.add(url)  
  
                            total_urls = len(filtered_urls)  
                            for index, url in enumerate(filtered_urls, start=1):  
                                url_suffix = f"$涛哥直播•域名" if total_urls == 1 else f"$涛哥直播•域名『线路{index}』"  
                                if '$' in url:  
                                    base_url = url.split('$', 1)[0]  
                                else:  
                                    base_url = url  
  
                                new_url = f"{base_url}{url_suffix}"  
  
                                f_m3u.write(f"#EXTINF:-1 tvg-id=\"{index}\" tvg-name=\"{channel_name}\" tvg-logo=\"https://gitee.com/yuanzl77/TVBox-logo/raw/main/png/{channel_name}.png\" group-title=\"{category}\",{channel_name}\n")  
                                f_m3u.write(new_url + "\n")  
                                f_txt.write(f"{channel_name},{new_url}\n")  
  
            f_txt.write("\n")  
  
# 假设这个函数从模板文件中读取并返回频道和模板频道信息  
def filter_source_urls(template_file):  
    # 这里应该有一些代码来读取和处理template_file  
    # 但为了示例，我们直接返回一些模拟数据  
    channels = {  
        'Sports': {  
            'ESPN': ['http://example.com/espn1', 'http://example.com/espn2'],  
            'Fox Sports': ['http://foxsports.com/live1']  
        },  
        'News': {  
            'CNN': ['http://cnn.com/live'],  
            'BBC': ['http://bbc.co.uk/live']  
        }  
    }  
    template_channels = {  
        'Sports': ['ESPN', 'Fox Sports'],  
        'News': ['CNN', 'BBC']  
    }  
    return channels, template_channels  
  
if __name__ == "__main__":  
    template_file = "demo.txt"  
    channels, template_channels = filter_source_urls(template_file)  
    updateChannelUrlsM3U(channels, template_channels)