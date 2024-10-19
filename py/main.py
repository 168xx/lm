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

import re  
import datetime  
# 假设 config 和其他必要的配置已经定义  
  
def is_ipv6(url):  
    # 保留原函数，用于可能的IPv6检测  
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None  
  
def is_ipv4_domain(url):  
    # 检查URL是否不是IPv6，并且不包含直接的IPv4地址（仅域名形式）  
    if is_ipv6(url):  
        return False  
    # 简单的检查，确保URL不包含直接的IPv4地址（这里假设路径中不包含IP）  
    # 这是一个非常简化的检查，实际中可能需要更复杂的逻辑来确定URL是否仅包含域名  
    ipv4_pattern = re.compile(r'\d{1,3}(\.\d{1,3}){3}')  # 简单的IPv4地址模式  
    if ipv4_pattern.search(url.split('//', 1)[-1].split('/', 1)[0]):  # 忽略协议部分和路径部分  
        # 进一步检查是否直接是一个IP地址（这里我们假设不是，因为我们想要域名形式）  
        # 但由于我们仅通过格式检查，这里简单返回False（因为我们不期望它匹配直接的IPv4）  
        return False  
    # 如果URL不包含直接的IPv4或IPv6地址，我们假设它是域名形式（这里是一个简化的假设）  
    return True  
  
def updateChannelUrlsM3U(channels, template_channels):  
    written_urls = set()  
  
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")  
    for group in config.announcements:  
        for announcement in group['entries']:  
            if announcement['name'] is None:  
                announcement['name'] = current_date  
  
    with open("lv/live.m3u", "w", encoding="utf-8") as f_m3u:  
        f_m3u.write(f"#EXTM3U x-tvg-url={','.join(f'\"{epg_url}\"' for epg_url in config.epg_urls)}\n")  
  
        with open("lv/live.txt", "w", encoding="utf-8") as f_txt:  
            for group in config.announcements:  
                f_txt.write(f"{group['channel']},#genre#\n")  
                for announcement in group['entries']:  
                    f_m3u.write(f"#EXTINF:-1 tvg-id=\"1\" tvg-name=\"{announcement['name']}\" tvg-logo=\"{announcement['logo']}\" group-title=\"{group['channel']}\",{announcement['name']}\n")  
                    f_m3u.write(f"{announcement['url']}\n")  
                    f_txt.write(f"{announcement['name']},{announcement['url']}\n")  
  
            for category, channel_list in template_channels.items():  
                f_txt.write(f"{category},#genre#\n")  
                if category in channels:  
                    for channel_name in channel_list:  
                        if channel_name in channels[category]:  
                            # 只保留域名形式的IPv4地址  
                            filtered_urls = []  
                            for url in channels[category][channel_name]:  
                                if url and url not in written_urls and is_ipv4_domain(url) and not any(blacklist in url for blacklist in config.url_blacklist):  
                                    filtered_urls.append(url)  
                                    written_urls.add(url)  
                            # 这里不再需要排序，因为我们已经筛选出了需要的URL  
                            for url in filtered_urls:  
                                # 可以在这里添加处理每个有效URL的逻辑，如果需要的话  
                                pass

                            total_urls = len(filtered_urls)
                            for index, url in enumerate(filtered_urls, start=1):
                                if is_ipv6(url):
                                    url_suffix = f"$涛哥直播•IPV6" if total_urls == 1 else f"$涛哥直播•IPV6『线路{index}』"
                                else:
                                    url_suffix = f"$涛哥直播•IPV4" if total_urls == 1 else f"$涛哥直播•IPV4『线路{index}』"
                                if '$' in url:
                                    base_url = url.split('$', 1)[0]
                                else:
                                    base_url = url

                                new_url = f"{base_url}{url_suffix}"

                                f_m3u.write(f"#EXTINF:-1 tvg-id=\"{index}\" tvg-name=\"{channel_name}\" tvg-logo=\"https://gitee.com/yuanzl77/TVBox-logo/raw/main/png/{channel_name}.png\" group-title=\"{category}\",{channel_name}\n")
                                f_m3u.write(new_url + "\n")
                                f_txt.write(f"{channel_name},{new_url}\n")

            f_txt.write("\n")

if __name__ == "__main__":
    template_file = "demo.txt"
    channels, template_channels = filter_source_urls(template_file)
    updateChannelUrlsM3U(channels, template_channels)
