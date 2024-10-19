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

def is_ipv6(url):  
    # 检查URL是否以IPv6地址格式开头  
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None  
  
def has_domain(url):  
    # 简化检查，假设如果URL在'//'之后包含'.'，则它可能包含域名  
    # 注意：这不是一个完美的检查，但它应该足够用于大多数情况  
    return bool(re.search(r'//[^/]*\.', url))  
  
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
                    # 这里我们假设announcements中的URL都是有效的，并且可能包含域名  
                    # 因此我们直接写入，不进行额外的IPv4/IPv6检查  
                    f_m3u.write(f"""#EXTINF:-1 tvg-id="1" tvg-name="{announcement['name']}" tvg-logo="{announcement['logo']}" group-title="{group['channel']}",{announcement['name']}\n""")  
                    f_m3u.write(f"{announcement['url']}\n")  
                    f_txt.write(f"{announcement['name']},{announcement['url']}\n")  
  
            for category, channel_list in template_channels.items():  
                f_txt.write(f"{category},#genre#\n")  
                if category in channels:  
                    for channel_name in channel_list:  
                        if channel_name in channels[category]:  
                            # 只保留带域名的IPv4地址  
                            filtered_urls = []  
                            for url in channels[category][channel_name]:  
                                if url and not is_ipv6(url) and has_domain(url) and url not in written_urls and not any(blacklist in url for blacklist in config.url_blacklist):  
                                    filtered_urls.append(url)  
                                    written_urls.add(url)  
  
                            total_urls = len(filtered_urls)  
                            for index, url in enumerate(filtered_urls, start=1):  
                                # 由于我们只保留带域名的IPv4，所以不需要区分IPv4和IPv6的后缀  
                                url_suffix = f"$涛哥直播『线路{index}』"  
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
    # 确保filter_source_urls函数正确地从template_file中读取并返回channels和template_channels  
    channels, template_channels = filter_source_urls(template_file)  
    updateChannelUrlsM3U(channels, template_channels)
