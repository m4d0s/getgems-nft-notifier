import subprocess
import os
import platform
import ipaddress
import random
import asyncio
import json
import sqlite3
from database import get_logger

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
ipv6_mask = config['ipv6']
logger = get_logger()
ipv6_count = 1024

def get_from_list():
    return ipv6_list[random.randint(0, len(ipv6_list) - 1)]

def is_local_address(ipv6_address):
    # Проверяем link-local адреса
    if ipv6_address.startswith('fe80::'):
        return True
    # Проверяем loopback адрес
    if ipv6_address == '::1':
        return True
    # Проверяем unique local адреса (ULA)
    if ipv6_address.startswith('fd') or ipv6_address.startswith('fc'):
        return True
    return False

#db
def get_free_proxy(version='ipv4'):
    if ipv6_mask and not is_local_address(ipv6_mask):
        version = 'ipv6'
    with sqlite3.connect(config['db_path']) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM proxy WHERE used = 0 and version = '{version}' ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
        if not row:
            cur.execute(f"SELECT * FROM {version} WHERE version = '{version}' ORDER BY RANDOM() LIMIT 1")
            row = cur.fetchone()
        else:
            set_proxy_used(row[0])
        return row[0] if row else None

def set_proxy_used(link, used=1):
    with sqlite3.connect(config['db_path']) as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE proxy SET used = {used} WHERE link = '{link}'")
        conn.commit()
        
def insert_or_delete_proxy(link, delete=False, version='ipv6'):
    with sqlite3.connect(config['db_path']) as conn:
        cur = conn.cursor()
        if delete:
            cur.execute(f"DELETE FROM proxy WHERE link = '{link}'")
        else:
            cur.execute(f"INSERT INTO proxy (link, used, version) VALUES ({link}, 0, '{version}')")
        conn.commit()


#prepare
async def generate_ipv6(mask):
    network = ipaddress.IPv6Network(mask)
    network_address = int(network.network_address)
    num_addresses = network.num_addresses
    random_offset = random.randint(0, num_addresses - 1)
    random_ipv6_address = str(ipaddress.IPv6Address(network_address + random_offset))
    await manage_ipv6_address(random_ipv6_address)
    return str(random_ipv6_address)

async def manage_ipv6_address(ip_addr, interface = 'ens3', only_del = False):
    current_platform = platform.system()
    succeed = False
    
    def execute_command(command):
        try:
            subprocess.run(command, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            logger.info(f"Command failed: {e}")
    
    if current_platform == 'Linux':
        # Linux команды
        if only_del:
            execute_command(f"sudo ip -6 addr del {ip_addr} dev {interface} || true")
        execute_command(f"sudo ip -6 addr add {ip_addr} dev {interface}")
        succeed = True
    
    elif current_platform == 'Windows':
        # Windows команды
        if only_del:
            execute_command(f"netsh interface ipv6 delete address \"{interface}\" {ip_addr}")
        execute_command(f"netsh interface ipv6 add address \"{interface}\" {ip_addr}")
        succeed = True
    else:
        logger.info(f"Unsupported platform: {current_platform}")
    
    if succeed:
        insert_or_delete_proxy(ip_addr)
        await asyncio.sleep(2)

def ensure_sysctl_config(file_path, configs):
    if platform.system() != 'Linux':
        return

    try:
        # Read the existing configuration file
        already = {}
        with open(file_path, 'r') as file:
            existing_lines = file.readlines()
            for line in existing_lines:
                # Skip comments and empty lines
                stripped_line = line.strip()
                if stripped_line.startswith('#') or not stripped_line:
                    continue
                
                # Safely split lines by '=', handling cases with comments
                if '=' in stripped_line:
                    key, value = stripped_line.split('=', 1)
                    already[key.strip()] = value.split('#', 1)[0].strip()  # Split off any comments after '#'

        # Update or add missing configurations
        modified = False
        for key, value in configs.items():
            if key not in already or already[key] != value:
                already[key] = value
                modified = True

        # If modifications were made, write back to the file
        if modified:
            with open(file_path, 'w') as file:
                for key, value in already.items():
                    config_line = f"{key} = {value}\n"
                    file.write(config_line)
                    logger.info(f"Updating or adding configuration: {config_line.strip()}")

            # Apply the new configurations
            os.system("sysctl -p")
            logger.info("Configuration applied successfully.")
        else:
            logger.info("No configuration changes needed.")
    
    except IOError as e:
        logger.error(f"Error reading or writing the file: {e}")

def clear_ipv6_interface(interface='ens3', mask=128):
    try:
        # Получаем список всех IPv6 адресов с маской /128 на интерфейсе
        result = subprocess.run(
            f"ip -6 addr show dev {interface} | grep '/{mask}' | awk '{{print $2}}'",
            shell=True, capture_output=True, text=True
        )
        ipv6_addresses = result.stdout.strip().split('\n')
        
        for ip in ipv6_addresses:
            if ip:
                logger.debug(f"Удаляю IPv6 адрес: {ip} с интерфейса {interface}")
                subprocess.run(f"sudo ip -6 addr del {ip} dev {interface}", shell=True)
                insert_or_delete_proxy(ip, delete=True)
        logger.info('Удаление IPv6 адресов завершено.')
    
    except Exception as e:
        logger.info(f"Произошла ошибка: {e}")


async def prepare():
    global ipv6_list
    # Конфигурации для добавления
    sysctl_configs = {
        "net.ipv6.conf.ens3.proxy_ndp": "1",
        "net.ipv6.conf.all.proxy_ndp": "1",
        "net.ipv6.conf.default.forwarding": "1",
        "net.ipv6.conf.all.forwarding": "1",
        "net.ipv6.neigh.default.gc_thresh3": "102400",
        "net.ipv6.route.max_size": "409600",
    }

    # Путь к файлу sysctl.conf
    sysctl_conf_file = '/etc/sysctl.conf'

    # Обеспечить наличие конфигураций
    ensure_sysctl_config(sysctl_conf_file, sysctl_configs)
    clear_ipv6_interface()
    if ipv6_mask:
        tasks = [asyncio.create_task(generate_ipv6(ipv6_mask)) for _ in range(ipv6_count)]
        while any(not t.done() for t in tasks):
            logger.info(f'Addresses added: {len([t.done() for t in tasks])}/{ipv6_count}')
            await asyncio.sleep(1)
    logger.info('IPv6 addresses added successfully.')
