"""
爱快路由器国内IP地址分组生成工具
合并 IPv4 / IPv6 / 省份IP 生成
数据来源优化：加入 APNIC 权威数据，多源合并，CIDR 自动聚合
"""

import os
import ipaddress
from datetime import datetime

import requests

# ==================== 配置 ====================
IPV4_SOURCES = [
    ("apnic", "https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest"),
    ("cidr", "https://cdn.jsdelivr.net/gh/Loyalsoldier/geoip@release/text/cn.txt"),
    ("cidr", "https://metowolf.github.io/iplist/data/special/china.txt"),
]

IPV6_SOURCES = [
    ("apnic", "https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest"),
    ("range", "https://raw.githubusercontent.com/mayaxcn/china-ip-list/refs/heads/master/chn_ip_v6.txt"),
    ("cidr", "https://cdn.jsdelivr.net/gh/Loyalsoldier/geoip@release/text/cn.txt"),
]

IPV4_OUTPUT = "ikuai_cn_ipv4group.txt"
IPV6_OUTPUT = "ikuai_cn_ipv6group.txt"
PROVINCE_OUTPUT = "ikuai_cn_province_ipgroup.txt"

IPV4_START_ID = 60
IPV6_START_ID = 70
PROVINCE_START_ID = 80

MAX_IP_PER_GROUP = 1000

PROVINCE_BASE_URL = "https://raw.githubusercontent.com/metowolf/iplist/master/data/country/CN/"
PROVINCE_MAPPING = {
    "AH": "安徽", "BJ": "北京", "CQ": "重庆", "FJ": "福建",
    "GD": "广东", "GS": "甘肃", "GX": "广西", "GZ": "贵州",
    "HA": "河南", "HB": "湖北", "HE": "河北", "HI": "海南",
    "HL": "黑龙江", "HN": "湖南", "JL": "吉林", "JS": "江苏",
    "JX": "江西", "LN": "辽宁", "NM": "内蒙古", "NX": "宁夏",
    "QH": "青海", "SC": "四川", "SD": "山东", "SH": "上海",
    "SN": "陕西", "SX": "山西", "TJ": "天津", "XJ": "新疆",
    "XZ": "西藏", "YN": "云南", "ZJ": "浙江",
}
# =============================================


def fetch_text(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  [!] {url} - {e}")
        return None


def parse_apnic_ipv4(text):
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) >= 7 and parts[1] == "CN" and parts[2] == "ipv4":
            results.append(f"{parts[3]}/{parts[4]}")
    return results


def parse_apnic_ipv6(text):
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) >= 7 and parts[1] == "CN" and parts[2] == "ipv6":
            results.append(f"{parts[3]}/{parts[4]}".lower())
    return results


def parse_cidr_text(text, version=4):
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            net = ipaddress.ip_network(line, strict=False)
            if net.version == version:
                results.append(str(net))
        except ValueError:
            pass
    return results


def parse_range_text(text, version=6):
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            start = ipaddress.ip_address(parts[0])
            end = ipaddress.ip_address(parts[1])
            if start.version != version or end.version != version:
                continue
            for net in ipaddress.summarize_address_range(start, end):
                results.append(str(net))
        except (ValueError, TypeError):
            pass
    return results


def merge_cidrs(cidrs):
    networks = []
    for c in set(cidrs):
        try:
            networks.append(ipaddress.ip_network(c, strict=False))
        except ValueError:
            pass
    merged = list(ipaddress.collapse_addresses(networks))
    merged.sort()
    return [str(n) for n in merged]


def split_chunks(lst, size):
    return [lst[i:i+size] for i in range(0, len(lst), size)]


def generate_records(cidrs, start_id, base_name):
    records = []
    cid = start_id
    for idx, chunk in enumerate(split_chunks(cidrs, MAX_IP_PER_GROUP), 1):
        gname = f"{base_name}-{idx}"
        comment = ", ".join(chunk)
        addr_pool = ",".join(chunk)
        records.append(f"id={cid} comment={comment} group_name={gname} addr_pool={addr_pool}")
        cid += 1
    return records


def save_file(records, path, start_id):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(records))
    print(f"\n  [OK] {path}")
    print(f"       记录数: {len(records)}, ID: {start_id}~{start_id+len(records)-1}")
    total = sum(len(r.split("comment=")[1].split(", ")) for r in records)
    print(f"       总地址段: {total}")


def process_ipv4():
    print("=" * 60)
    print("收集国内 IPv4 地址段...")
    all_cidrs = []
    for ptype, url in IPV4_SOURCES:
        text = fetch_text(url)
        if not text:
            continue
        if ptype == "apnic":
            parsed = parse_apnic_ipv4(text)
        else:
            parsed = parse_cidr_text(text, version=4)
        print(f"  [+] {url}")
        print(f"      解析到 {len(parsed)} 条")
        all_cidrs.extend(parsed)

    if not all_cidrs:
        print("  [!] 未获取到 IPv4 数据")
        return

    merged = merge_cidrs(all_cidrs)
    print(f"  [+] 汇总: {len(all_cidrs)} 条 -> 去重合并后 {len(merged)} 条")

    records = generate_records(merged, IPV4_START_ID, "国内IPv4")
    save_file(records, IPV4_OUTPUT, IPV4_START_ID)


def process_ipv6():
    print("=" * 60)
    print("收集国内 IPv6 地址段...")
    all_cidrs = []
    for ptype, url in IPV6_SOURCES:
        text = fetch_text(url)
        if not text:
            continue
        if ptype == "apnic":
            parsed = parse_apnic_ipv6(text)
        elif ptype == "range":
            parsed = parse_range_text(text, version=6)
        else:
            parsed = parse_cidr_text(text, version=6)
        print(f"  [+] {url}")
        print(f"      解析到 {len(parsed)} 条")
        all_cidrs.extend(parsed)

    if not all_cidrs:
        print("  [!] 未获取到 IPv6 数据")
        return

    merged = merge_cidrs(all_cidrs)
    print(f"  [+] 汇总: {len(all_cidrs)} 条 -> 去重合并后 {len(merged)} 条")

    records = generate_records(merged, IPV6_START_ID, "国内IPv6")
    save_file(records, IPV6_OUTPUT, IPV6_START_ID)


def process_provinces():
    print("=" * 60)
    print("生成省份 IP 分组...")
    records = []
    cid = PROVINCE_START_ID
    for code in sorted(PROVINCE_MAPPING):
        name = PROVINCE_MAPPING[code]
        url = f"{PROVINCE_BASE_URL}CN-{code}.txt"
        text = fetch_text(url)
        if not text:
            print(f"  [!] 跳过 {name}")
            continue
        cidrs = parse_cidr_text(text)
        if not cidrs:
            print(f"  [!] {name} 无有效数据")
            continue
        merged = merge_cidrs(cidrs)
        chunks = split_chunks(merged, MAX_IP_PER_GROUP)
        nc = len(chunks)
        for i, chunk in enumerate(chunks, 1):
            gname = f"{name}IP" + (f"({i})" if nc > 1 else "")
            comment = ", ".join(chunk)
            addr_pool = ",".join(chunk)
            records.append(f"id={cid} comment={comment} group_name={gname} addr_pool={addr_pool}")
            cid += 1
        print(f"  [+] {name}: {len(merged)} 条 ({nc} 个分组)")

    if records:
        save_file(records, PROVINCE_OUTPUT, PROVINCE_START_ID)


def main():
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    process_ipv4()
    process_ipv6()
    process_provinces()
    print("\n" + "=" * 60)
    print("全部完成!")


if __name__ == "__main__":
    main()
