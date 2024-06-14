import requests
import hashlib
import time
from ruamel.yaml import YAML


# 使用ruamel.yaml加载配置文件config.yml
def load_config():
    yaml = YAML()
    yaml.preserve_quotes = True
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.load(config_file)
    return config


def save_config(config):
    yaml = YAML()
    yaml.preserve_quotes = True
    with open("config.yml", "w", encoding="utf-8") as config_file:
        yaml.dump(config, config_file)


def get_row_ids(config):
    return config.get("domain_row_ids", [])


def set_row_ids(row_ids):
    config = load_config()
    # 仅在 config 中存在 domain_row_ids 字段时才更新它
    if "domain_row_ids" in config:
        config["domain_row_ids"] = row_ids
        save_config(config)


# 获取sess_key
def login(session, config):
    url = f"{config['server_address']}/Action/login"
    headers = {"Content-Type": "application/json;charset=UTF-8"}
    passwd_md5 = hashlib.md5(config["password"].encode()).hexdigest()
    payload = {"username": config["username"], "passwd": passwd_md5}

    response = session.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        cookie = response.cookies.get("sess_key")
        if cookie:
            return cookie
        else:
            print("未找到 sess_key")
            return None
    else:
        print("登录失败:", response.status_code)
        return None


def get_domains(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text.splitlines()
    else:
        print("获取域名失败:", response.status_code)
        return []


def add_domains(session, sess_key, config, domains):
    url = f"{config['server_address']}/Action/call"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Cookie": f"sess_key={sess_key}",
    }

    # 从 config.yml 读取之前添加的域名的 RowId
    row_ids = get_row_ids(config)

    # 确保 row_ids 是一个列表
    if row_ids is None:
        row_ids = []

    # 如果文件内容为空或没有需要删除的域名，则跳过删除域名步骤
    if row_ids:
        # 删除之前添加的域名
        row_ids_str = ",".join(str(id_) for id_ in row_ids)  # 转换为字符串
        payload = {
            "func_name": "stream_domain",
            "action": "del",
            "param": {"id": row_ids_str},
        }
        # print("删除请求参数:", payload)  # 打印删除请求参数
        response = session.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print("删除之前添加的域名成功")
            # 清空 row_ids 列表
            row_ids = []
        else:
            print("删除域名失败:", response.status_code)
            return  # 如果删除失败，停止执行后续步骤

    # 添加域名
    domain_batches = [domains[i : i + 1000] for i in range(0, len(domains), 1000)]
    for i, batch in enumerate(domain_batches):
        payload = {
            "func_name": "stream_domain",
            "action": "add",
            "param": {
                "interface": config["domain_interface"],
                "src_addr": config["domain_src_addr"],
                "domain": ",".join(batch),
                "comment": config["domain_comment"] + f"-{i+1}",
                "week": "1234567",
                "time": "00:00-23:59",
                "enabled": "yes",
            },
        }
        response = session.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
            row_id = result.get("RowId", "")
            print(
                f"添加域名成功，comment: {payload['param']['comment']}, RowId: {row_id}"
            )
            row_ids.append(row_id)

    # 更新 config.yml 中的 row_ids
    set_row_ids(row_ids)

    # 间隔5秒
    time.sleep(5)


if __name__ == "__main__":
    # 读取配置信息
    config = load_config()

    with requests.Session() as session:
        # 登录获取sess_key
        sess_key = login(session, config)
        if sess_key:
            print("登录成功，sess_key:", sess_key)

            # 获取域名列表
            domains = get_domains(config["domain_list_url"])
            if domains:
                print(f"获取到域名数量: {len(domains)}")

                # 添加域名
                add_domains(session, sess_key, config, domains)
                print("域名添加完成")
            else:
                print("未获取到域名")
