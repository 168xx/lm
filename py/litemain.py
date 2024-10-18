import re
import requests
import logging
from collections import OrderedDict
from datetime import datetime
import litecon

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

def parse_corrections(correction_file):
    corrections = {}

    with open(correction_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(",")
                unified_name = parts[0].strip()
                for alias in parts[1:]:
                    corrections[alias.strip()] = unified_name

    return corrections

def fetch_channels(url, corrections):
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
                        channel_name = corrections.get(channel_name, channel_name)
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
                        channel_name = corrections.get(channel_name, channel_name)
                        channels[current_category].append((channel_name, channel_url))
                    elif line:
                        channel_name = line.strip()
                        channel_name = corrections.get(channel_name, channel_name)
                        channels[current_category].append((channel_name, ''))
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
                        if channel_name not in matched_channels[category]:
                            matched_channels[category][channel_name] = []
                        if online_channel_url not in [url for _, url in matched_channels[category][channel_name]]:
                            matched_channels[category][channel_name].append((online_channel_name, online_channel_url))

    return matched_channels

def filter_source_urls(template_file, correction_file):
    template_channels = parse_template(template_file)
    corrections = parse_corrections(correction_file)
    source_urls = litecon.source_urls

    all_channels = OrderedDict()
    for url in source_urls:
        fetched_channels = fetch_channels(url, corrections)
        for category, channel_list in fetched_channels.items():
            if category in all_channels:
                all_channels[category].extend(channel_list)
            else:
                all_channels[category] = channel_list

    matched_channels = match_channels(template_channels, all_channels)

    return matched_channels, template_channels

def is_ipv6(url):  
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None  
  
def is_pure_ipv4(url):  
    # 检查是否匹配IPv4地址格式（忽略URL的其他部分）  
    # 假设IPv4地址在URL中是直接跟在协议后面的，并且可能用方括号括起来（尽管不常见）  
    ipv4_pattern = re.compile(r'(?<=http:\/\/|https:\/\/)(?:\[([0-9]{1,3}(?:\.[0-9]{1,3}){3})\]|([0-9]{1,3}(?:\.[0-9]{1,3}){3}))')  
    match = ipv4_pattern.search(url)  
    if match:  
        # 提取匹配的IPv4地址，看是否整个URL仅包含这个地址  
        ip_match = match.group(1) or match.group(2)  
        # 简化处理：如果URL中仅包含这个IPv4地址（或加上端口），则认为它是纯IPv4地址  
        # 注意：这个检查很粗略，因为它没有处理URL路径、查询参数等  
        return re.fullmatch(rf'^{re.escape(url.split("://")[0])}://(?:\[{ip_match}\]|{ip_match})(?::\d+)?/?$', url) is not None  
    return False  
  
def has_domain(url):  
    # 简单的检查：如果URL不包含纯IPv4地址格式，并且包含'.'，则可能包含域名  
    return not is_pure_ipv4(url) and '.' in url  
  
def updateChannelUrlsM3U(channels, template_channels):  
    written_urls = set()  
  
    current_date = datetime.now().strftime("%Y-%m-%d")  
    for group in litecon.announcements:  
        for announcement in group['entries']:  
            if announcement['name'] is None:  
                announcement['name'] = current_date  
  
    with open("lv/litelive.m3u", "w", encoding="utf-8") as f_m3u:  
        f_m3u.write(f"""#EXTM3U x-tvg-url={",".join(f'"{epg_url}"' for epg_url in litecon.epg_urls)}\n""")  
  
        with open("lv/litelive.txt", "w", encoding="utf-8") as f_txt:  
            for group in litecon.announcements:  
                f_txt.write(f"{group['channel']},#genre#\n")  
                for announcement in group['entries']:  
                    # 这里我们仍然写入所有公告的URL，但后续我们会修改对channels的处理  
                    f_m3u.write(f"""#EXTINF:-1 tvg-id="1" tvg-name="{announcement['name']}" tvg-logo="{announcement['logo']}" group-title="{group['channel']}",{announcement['name']}\n""")  
                    f_m3u.write(f"{announcement['url']}\n")  
                    f_txt.write(f"{announcement['name']},{announcement['url']}\n")  
  
            for category, channel_list in template_channels.items():  
                f_txt.write(f"{category},#genre#\n")  
                if category in channels:  
                    for channel_name in channel_list:  
                        if channel_name in channels[category]:  
                            # 去重逻辑  
                            unique_urls = list(OrderedDict.fromkeys([url for _, url in channels[category][channel_name]]))  
                            # 只保留有域名的IPv4地址或IPv6地址（如果配置优先）  
                            filtered_urls = [  
                                url for url in unique_urls  
                                if (has_domain(url) and not is_ipv6(url)) or (litecon.ip_version_priority == "ipv6" and is_ipv6(url))  
                            ]  
                            # 确保没有重复写入  
                            filtered_urls = [url for url in filtered_urls if url not in written_urls and not any(blacklist in url for blacklist in litecon.url_blacklist)]  
                            written_urls.update(filtered_urls)  # 更新已写入的URL集合  

                            # 保证数字连续
                            index = 1
                            for url in filtered_urls:
                                url_suffix = f"$雷蒙影视•IPV4" if len(filtered_urls) == 1 else f"$雷蒙影视•IPV4『线路{index}』"
                                if '$' in url:
                                    base_url = url.split('$', 1)[0]
                                else:
                                    base_url = url

                                new_url = f"{base_url}{url_suffix}"

                                if base_url not in written_urls:
                                    f_m3u.write(f"#EXTINF:-1 tvg-id=\"{index}\" tvg-name=\"{channel_name}\" tvg-logo=\"https://gitee.com/n3rddd/tvlogos/raw/main/logo/{channel_name}.png\" group-title=\"{category}\",{channel_name}\n")
                                    f_m3u.write(new_url + "\n")
                                    f_txt.write(f"{channel_name},{new_url}\n")
                                    written_urls.add(base_url)
                                    index += 1

            f_txt.write("\n")

if __name__ == "__main__":
    template_file = "litedemo.txt"
    correction_file = "correction.txt"
    channels, template_channels = filter_source_urls(template_file, correction_file)
    updateChannelUrlsM3U(channels, template_channels)
