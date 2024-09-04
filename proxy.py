import subprocess
import os
import platform
import ipaddress
import random
import asyncio
import json
from database import get_logger

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
ipv6_mask = config['ipv6']
logger = get_logger()
ipv6_list, ipv6_count = [], 1024

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
        await asyncio.sleep(2)

def ensure_sysctl_config(file_path, configs):
    """ Убедитесь, что все конфигурационные строки присутствуют в файле sysctl """
    try:
        # Чтение существующего файла конфигурации
        with open(file_path, 'r') as file:
            existing_lines = file.read()
        
        # Открываем файл в режиме добавления
        with open(file_path, 'a') as file:
            for key, value in configs.items():
                # Формируем строку конфигурации
                config_line = f"{key} = {value}\n"
                # Проверяем наличие строки в файле
                if config_line not in existing_lines:
                    logger.info(f"Adding missing configuration: {config_line.strip()}")
                    file.write(config_line)
                    
        # Применение изменений
        os.system("sysctl -p")
        logger.info("Configuration applied successfully.")
    
    except IOError as e:
        logger.info(f"Error reading or writing the file: {e}")

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
                logger.info(f"Удаляю IPv6 адрес: {ip} с интерфейса {interface}")
                subprocess.run(f"sudo ip -6 addr del {ip} dev {interface}", shell=True)
    
    except Exception as e:
        logger.info(f"Произошла ошибка: {e}")


async def prepare():
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
    tasks = [asyncio.create_task(generate_ipv6(ipv6_mask)) for _ in range(ipv6_count)]
    while any(not t.done for t in tasks):
        logger.info(f'Addresses added: {len([t.done for t in tasks])}/{ipv6_count}')
        await asyncio.sleep(1)
