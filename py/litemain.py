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


import re  
from collections import OrderedDict  
from datetime import datetime  
  
def is_ipv6(url):  
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None  
  
def updateChannelUrlsM3U(channels, template_channels):  
    written_urls = set()  
  
    current_date = datetime.now().strftime("%Y-%m-%d")  
    for group in litecon.announcements:  
        for announcement in group['entries']:  
            if announcement['name'] is None:  
                announcement['name'] = current_date  
  
    with open("lv/litelive.m3u", "w", encoding="utf-8") as f_m3u:  
        f_m3u.write(f'#EXTM3U x-tvg-url="{",".join(f"\"{epg_url}\"" for epg_url in litecon.epg_urls)}"\n') 
  
        with open("lv/litelive.txt", "w", encoding="utf-8") as f_txt:  
            for group in litecon.announcements:  
                f_txt.write(f"{group['channel']},#genre#\n")  
                for announcement in group['entries']:  
                    f_m3u.write(f"#EXTINF:-1 tvg-id=\"1\" tvg-name=\"{announcement['name']}\" tvg-logo=\"{announcement['logo']}\" group-title=\"{group['channel']}\",{announcement['name']}\n")  
                    f_m3u.write(f"{announcement['url']}\n")  
                    f_txt.write(f"{announcement['name']},{announcement['url']}\n")  
                    written_urls.add(announcement['url'])  
  
            for category, channel_list in template_channels.items():  
                f_txt.write(f"{category},#genre#\n")  
                if category in channels:  
                    for channel_name in channel_list:  
                        if channel_name in channels[category]:  
                            # 去重逻辑  
                            unique_urls = list(OrderedDict.fromkeys([url for _, url in channels[category][channel_name]]))  
  
                            # 分离IPv6和IPv4地址  
                            ipv6_urls = [url for url in unique_urls if is_ipv6(url)]  
                            ipv4_urls = [url for url in unique_urls if not is_ipv6(url)]  
  
                            # 根据需求选择优先级  
                            if litecon.ip_version_priority == "ipv6":  
                                # 优先IPv6，如果没有IPv6则不保留IPv4  
                                sorted_urls = ipv6_urls or []  
                            else:  
                                # 优先非IPv6（即IPv4），如果没有IPv4则不保留IPv6（但此逻辑已在此场景下不适用，因为默认就是先处理IPv4）  
                                # 但由于需求只要求在没有IPv6时保留IPv4，所以这里我们不需要改变ipv4_urls的处理  
                                sorted_urls = ipv4_urls  # 实际上这个分支在ipv6优先的情况下不会被用到  
                                # 但为了清晰，我们仍保留此逻辑以展示如何区分  
  
                            # 由于ipv6优先，且我们已知当ipv6存在时不考虑ipv4，所以直接使用ipv6_urls  
                            # 并过滤掉已经在written_urls中的URL，以及黑名单中的URL  
                            filtered_urls = [url for url in ipv6_urls if url not in written_urls and not any(blacklist in url for blacklist in litecon.url_blacklist)]  
  
                            # 如果没有IPv6地址，则考虑IPv4地址（但根据需求，这部分在ipv6优先时不会执行）  
                            # 如果需要，可以在ipv6不存在时添加以下逻辑：  
                            # if not filtered_urls and ipv4_urls:  
                            #     filtered_urls = [url for url in ipv4_urls if url not in written_urls and not any(blacklist in url for blacklist in litecon.url_blacklist)]  
  
                            # 但由于需求明确只要求IPv6，所以上述IPv4的备用逻辑被注释掉  
  
                            for url in filtered_urls:  
                                # 在这里可以添加将筛选后的URL写入文件的逻辑，  
                                # 但根据原始代码逻辑，这部分已经在外部循环中通过announcement处理完成。  
                                # 如果需要在此处额外处理，请取消以下注释并调整以适应您的需求：  
                                # f_m3u.write(f"#EXTINF: 相关信息\n{url}\n")  
                                # 注意：这里需要您根据实际情况填写"#EXTINF: 相关信息"部分  

                            index = 1
                            for url in filtered_urls:
                                url_suffix = f"$轩蓓直播•IPV6" if len(filtered_urls) == 1 else f"$轩蓓直播•IPV6『线路{index}』"
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
