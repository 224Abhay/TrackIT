import datetime
import json
import os
import subprocess
from itertools import chain
from urllib import request
import winreg
import psutil
from subprocess import CREATE_NO_WINDOW

MAIN_DIR = "C:/ProgramData/TrackIt"
CONFIG_FILE = os.path.join(MAIN_DIR, "config.json")
AVAILABLE_METHODS_FILE = os.path.join(MAIN_DIR, "available_methods.json")


class HardwareInfo:
    @staticmethod
    def get_memory_details():
        try:
            command = (
                "Get-CimInstance Win32_PhysicalMemory | "
                "ForEach-Object {\"$($_.Capacity),$($_.Manufacturer),$($_.Speed)\"}"
            )

            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW).strip()

            if not output:
                return [{"size": "Unknown", "manufacturer": "Unknown", "speed": "Unknown"}]

            ram_details = [
                {
                    "size": f"{int(capacity) / (1024**3):.2f} GB",
                    "manufacturer": manufacturer if manufacturer else "Unknown",
                    "speed": f"{speed} MHz" if speed.isdigit() else "Unknown"
                }
                for line in output.split("\n") if (parts := line.split(",")) and len(parts) == 3
                for capacity, manufacturer, speed in [parts]
            ]

            return ram_details

        except subprocess.CalledProcessError:
            return [{"size": "Unknown", "manufacturer": "Unknown", "speed": "Unknown"}]

    @staticmethod
    def get_storage_details():
        disks = {}
        try:
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks[partition.device] = {
                        "total": f"{usage.total / (1024**3):.2f} GB",
                        "free": f"{usage.free / (1024**3):.2f} GB"
                    }
                except PermissionError:
                    continue
        except Exception:
            return {"Unknown": {"total": "Unknown", "free": "Unknown"}}

        return disks

    @staticmethod
    def get_serial_number():
        try:
            command = 'Get-CimInstance Win32_BIOS | Select-Object -ExpandProperty SerialNumber'
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW).strip()

            return output if output else "Unknown"

        except subprocess.CalledProcessError:
            return "Unknown"

    @staticmethod
    def get_motherboard_details():
        try:
            command = (
                'Get-CimInstance Win32_BaseBoard | '
                'ForEach-Object {"$($_.Manufacturer),$($_.Product)"}'
            )

            output = subprocess.check_output(
                ["powershell", "-Command", command], 
                text=True, 
                creationflags=CREATE_NO_WINDOW
            ).strip()

            if not output:
                return {"manufacturer": "Unknown", "product": "Unknown"}

            # Split output by comma
            manufacturer, product = output.split(",", 1)

            return {
                "manufacturer": manufacturer.strip() if manufacturer else "Unknown",
                "product": product.strip() if product else "Unknown"
            }

        except subprocess.CalledProcessError:
            return {"manufacturer": "Unknown", "product": "Unknown"}

    @staticmethod    
    def get_monitor_details():
        try:
            command = "Get-WmiObject Win32_DesktopMonitor | Where-Object {$_.Availability -eq 3} | Select-Object Name, ScreenWidth, ScreenHeight | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return [{"name": mon["Name"], "width": mon["ScreenWidth"], "height": mon["ScreenHeight"]} for mon in data]
        except Exception:
            return []

    @staticmethod
    def get_cpu_details():
        try:
            command = "Get-WmiObject Win32_Processor | Select-Object Name, NumberOfCores, MaxClockSpeed | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return [{
                "name": cpu["Name"].strip(),
                "cores": cpu["NumberOfCores"],
                "speed": f"{cpu['MaxClockSpeed']} MHz",
                "usage": f"{psutil.cpu_percent(interval=1)}%"
            } for cpu in data]
        except Exception:
            return [{"name": "Unknown", "cores": 0, "speed": "Unknown", "usage": "Unknown"}]

    @staticmethod
    def get_gpu_details():
        
        def get_total_system_ram():
            """Get total physical RAM in GB."""
            try:
                command = "Get-WmiObject Win32_OperatingSystem | Select-Object TotalVisibleMemorySize | ConvertTo-Json"
                output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
                data = json.loads(output)
                total_mem_kb = data["TotalVisibleMemorySize"]  # in KB
                return round(int(total_mem_kb) / (1024**2), 2)  # Convert to GB
            except Exception:
                return 0
        
        gpu_list = []
        
        # Step 1: Get all GPUs from WMI
        try:
            command = "Get-WmiObject Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            wmi_data = json.loads(output)
            if isinstance(wmi_data, dict):
                wmi_data = [wmi_data]
        except Exception:
            wmi_data = [{"Name": "Unknown", "AdapterRAM": 0}]
        
        # Step 2: Get NVIDIA-specific data from nvidia-smi
        nvidia_data = {}
        try:
            output = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", text=True, shell=True, creationflags=CREATE_NO_WINDOW)
            for line in output.strip().splitlines():
                name, memory = line.split(", ")
                memory_gb = f"{round(int(memory.split()[0]) / 1024, 2)} GB"
                nvidia_data[name] = memory_gb
        except (subprocess.CalledProcessError, FileNotFoundError):
            nvidia_data = {}

        # Step 3: Combine data with shared memory heuristic
        total_ram = get_total_system_ram()
        shared_mem_limit = min(8, total_ram / 2)  # Cap at 8 GB or 50% of total RAM, per Intel defaults
        
        for gpu in wmi_data:
            name = gpu.get("Name", "Unknown")
            ram_bytes = gpu.get("AdapterRAM", 0)
            
            if name in nvidia_data:
                ram = nvidia_data[name]  # Use nvidia-smi for NVIDIA GPUs
            elif "Intel" in name or "UHD" in name or "Integrated" in name:
                ram = f"Shared ({shared_mem_limit:.2f} GB)"  # Use capped shared memory
            else:
                ram = f"{round(int(ram_bytes) / (1024**3), 2)} GB" if ram_bytes else "Unknown"
            
            gpu_list.append({"name": name, "ram": ram})
        
        return gpu_list

    @staticmethod
    def get_peripheral_devices():
        try:
            command = "Get-WmiObject Win32_PnPEntity | Where-Object {$_.Service -ne $null} | Select-Object Name, DeviceID | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return [{"name": device["Name"], "id": device["DeviceID"]} for device in data]
        except Exception:
            return []

    available_methods = {
        "memory": get_memory_details,
        "storage": get_storage_details,
        "serial_number": get_serial_number,
        "motherboard": get_motherboard_details,
        "monitor": get_monitor_details,
        "cpu": get_cpu_details,
        "gpu": get_gpu_details,
        "peripheral_devices": get_peripheral_devices
    }

class SoftwareInfo:
    @staticmethod
    def get_os_install_date(time_format):
        try:
            windows_path = r"C:\Windows"
            creation_time = os.path.getctime(windows_path)
            return datetime.fromtimestamp(creation_time).strftime(time_format)
        except Exception:
            return "Unknown"

    @staticmethod
    def get_installed_software():
        """Retrieve a unique list of installed software from Windows registry."""
        registry_paths = {
            winreg.HKEY_LOCAL_MACHINE: [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ],
            winreg.HKEY_CURRENT_USER: [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
            ],
        }

        software_list = []
        seen_software = []

        def process_registry_keys(hive, keys):
            temp_list = []

            for uninstall_key in keys:
                try:
                    with winreg.OpenKey(hive, uninstall_key) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    
                                    subkey_values = {
                                        winreg.EnumValue(subkey, j)[0]: str(winreg.EnumValue(subkey, j)[1])
                                        for j in range(winreg.QueryInfoKey(subkey)[1] )
                                    }
                                    
                                    name = subkey_values.get("DisplayName")
                                    if not name:
                                        continue
                                    
                                    version = subkey_values.get("DisplayVersion", "Unknown")
                                    software_key = (name, version)
                                    
                                    # if software_key in seen_software:
                                    #     continue
                                    seen_software.append(name)
                                    
                                    temp_list.append(subkey_values)
                            except OSError:
                                continue
                except PermissionError:
                    continue
            return temp_list

        software_list = list(chain.from_iterable(process_registry_keys(hive, keys) for hive, keys in registry_paths.items()))

        return software_list

    @staticmethod
    def get_running_processes():
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'username', 'status', 'cpu_percent', 'memory_info']):
            try:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "exe": proc.info.get('exe', 'N/A'),  # Executable path
                    "username": proc.info.get('username', 'N/A'),  # User running the process
                    "status": proc.info.get('status', 'N/A'),  # Process status
                    "cpu_percent": proc.info.get('cpu_percent', 0),  # CPU usage
                    "memory": proc.info['memory_info'].rss // (1024 * 1024)  # Memory usage in MB
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return processes

    @staticmethod
    def get_windows_update_status():
        try:
            command = "Get-WmiObject -Class Win32_QuickFixEngineering | Select-Object -Last 1 | Select-Object InstalledOn | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            return {"last_update": data['InstalledOn']['DateTime']} if data else {"last_update": "Unknown"}
        except Exception:
            return {"last_update": "Unknown"}

    @staticmethod
    def get_installed_drivers():
        """Fetch detailed information about installed drivers."""
        try:
            command = """
            Get-WmiObject Win32_PnPSignedDriver | 
            Select-Object DeviceName, DriverVersion, Manufacturer, DriverDate, DeviceClass, DriverProviderName, InfName, HardwareID, IsSigned, DigitalSigner, OEMINF | 
            ConvertTo-Json -Depth 2
            """
            output = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True)

            # If PowerShell output is empty, return an error
            if not output.stdout.strip():
                return {"error": "No driver information found."}

            data = json.loads(output.stdout)

            # Ensure data is a list
            if isinstance(data, dict):
                data = [data]

            # Format and return driver info
            drivers = []
            for drv in data:
                if drv:  # Check if the dictionary is not None
                    drivers.append({
                        "name": drv.get("DeviceName", "Unknown"),
                        "version": drv.get("DriverVersion", "Unknown"),
                        "manufacturer": drv.get("Manufacturer", "Unknown"),
                        "release_date": drv.get("DriverDate", "Unknown"),
                        "device_class": drv.get("DeviceClass", "Unknown"),
                        "provider": drv.get("DriverProviderName", "Unknown"),
                        "inf_name": drv.get("InfName", "Unknown"),
                        "hardware_id": drv.get("HardwareID", ["Unknown"])[0] if drv.get("HardwareID") else "Unknown",
                        "is_signed": drv.get("IsSigned", False),
                        "digital_signer": drv.get("DigitalSigner", "Unknown"),
                        "oem_inf": drv.get("OEMINF", "Unknown")
                    })

            return drivers if drivers else {"error": "No driver information found."}

        except Exception as e:
            return {"error": str(e)}

    available_methods = {
        "installed_software": get_installed_software,
        "running_processes": get_running_processes,
        "windows_update_status": get_windows_update_status,
        "installed_drivers": get_installed_drivers
    }

class NetworkInfo:
    @staticmethod
    def get_network_adapters():

        def parse_adapter_status(status_code):
            """Convert NetConnectionStatus code to readable status."""
            status_mapping = {
                0: "Disconnected",
                1: "Connecting",
                2: "Connected",
                3: "Disconnecting",
                4: "Hardware not present",
                5: "Hardware disabled",
                6: "Hardware malfunction",
                7: "Media disconnected",
                8: "Authenticating",
                9: "Authentication succeeded",
                10: "Authentication failed",
            }
            return status_mapping.get(status_code, "Unknown")

        """Fetch all network adapters (active + inactive) with details."""
        try:
            command = """
            Get-CimInstance Win32_NetworkAdapter | 
            Select-Object Name, MACAddress, NetConnectionStatus, AdapterType, Speed | 
            ConvertTo-Json -Depth 2
            """

            output = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True)

            # If PowerShell output is empty, return an error
            if not output.stdout.strip():
                return {"error": "No network adapters found."}

            data = json.loads(output.stdout)

            # Ensure data is a list
            if isinstance(data, dict):
                data = [data]

            # Process adapter information
            adapters = []
            for adapter in data:
                adapters.append({
                    "name": adapter.get("Name", "Unknown"),
                    "mac_address": adapter.get("MACAddress", "N/A"),
                    "status": parse_adapter_status(adapter.get("NetConnectionStatus")),
                    "type": adapter.get("AdapterType", "Unknown"),
                    "speed_mbps": adapter.get("Speed", 0) // 1_000_000 if adapter.get("Speed") else "Unknown"
                })

            return adapters if adapters else {"error": "No network adapters found."}

        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def get_public_ip():
        try:
            response = request.get("https://api.ipify.org?format=json")
            return response.json()["ip"]
        except Exception:
            return "Unknown"
        
    @staticmethod
    def get_wifi_ssid():
        try:
            output = subprocess.check_output("netsh wlan show interfaces", text=True, creationflags=CREATE_NO_WINDOW)
            for line in output.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    return line.split(":")[1].strip()
            return "Not connected to Wi-Fi"
        except Exception:
            return "Unknown"

    @staticmethod
    def get_vpn_status():
        try:
            command = "Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object {$_.Description -like '*VPN*'} | Select-Object Description | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            return "VPN Active" if data else "No VPN Detected"
        except Exception:
            return "Unknown"

    available_methods = {
        "network_adapters": get_network_adapters,
        "public_ip": get_public_ip,
        "wifi_ssid": get_wifi_ssid,
        "vpn_status": get_vpn_status
    }

class SecurityInfo:
    @staticmethod
    def get_antivirus_details():
        try:
            command = "Get-WmiObject -Namespace 'root\\SecurityCenter2' -Class AntiVirusProduct | Select-Object displayName | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return [av["displayName"] for av in data] if data else ["No AV detected"]
        except Exception:
            return ["Unknown"]
        
    @staticmethod
    def get_firewall_details():
        try:
            command = "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {profile["Name"]: profile["Enabled"] for profile in data}
        except Exception:
            return {"Unknown": False}

    available_methods = {
        "antivirus": get_antivirus_details,
        "firewall": get_firewall_details
    }

class UserInfo:
    @staticmethod
    def get_current_user():
        """Fetch the currently logged-in user in the most efficient way."""
        users = psutil.users()
        return users[0].name if users else "Unknown"

    @staticmethod
    def get_login_history():
        try:
            command = "Get-WinEvent -LogName 'Security' -MaxEvents 10 | Where-Object {$_.Id -eq 4624} | Select-Object TimeCreated | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return [event["TimeCreated"] for event in data]
        except Exception:
            return []
    
    @staticmethod
    def get_bitlocker_status():
        try:
            command = "Get-BitLockerVolume | Select-Object MountPoint, ProtectionStatus | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", command], text=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {vol["MountPoint"]: "Encrypted" if vol["ProtectionStatus"] == 1 else "Not Encrypted" for vol in data}
        except Exception:
            return {"Unknown": "Unknown"}

    avaiable_methods = {
        "current_user": get_current_user,
        "login_history": get_login_history,
        "bitlocker_status": get_bitlocker_status
    }

class OtherInfo:
    @staticmethod
    def get_cpu_usage():
        return {"cpu_usage_percent": psutil.cpu_percent(interval=1)}

    @staticmethod
    def get_asset_tag():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)["asset_tag"]
        except FileNotFoundError:
            return "Not Assigned"

    @staticmethod
    def get_last_boot_time(date_format, time_format):
        """Fetch the system's last boot time in an optimized way."""
        return datetime.fromtimestamp(psutil.boot_time()).strftime(f"{date_format} {time_format}")


    @staticmethod
    def get_battery_status():
        """Fetch the battery status efficiently."""
        if not (battery := psutil.sensors_battery()):
            return {"status": "No battery detected"}

        return {
            "percent": battery.percent,
            "power_plugged": battery.power_plugged,
            "secsleft": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else "Unlimited"
        }

    @staticmethod
    def get_windows_product_key():
        """Fetch the Windows product key efficiently."""
        try:
            command = (
                'Get-CimInstance -Query "SELECT OA3xOriginalProductKey FROM SoftwareLicensingService" | '
                'Select-Object -ExpandProperty OA3xOriginalProductKey'
            )

            output = subprocess.check_output(
                ["powershell", "-Command", command], 
                text=True, 
                creationflags=CREATE_NO_WINDOW
            ).strip()

            return output if output else "Unknown"

        except subprocess.CalledProcessError:
            return "Unknown"

    available_methods = {
        "cpu_usage": get_cpu_usage,
        "asset_tag": get_asset_tag,
        "last_boot_time": get_last_boot_time,
        "battery_status": get_battery_status,
        "windows_product_key": get_windows_product_key
    }

class UnusedInfo:
    @staticmethod
    def get_tpm_status():
        try:
            command = (
                "$tpm = Get-Tpm; "
                "if ($tpm) { "
                "  [PSCustomObject]@{ TpmPresent = $tpm.TpmPresent; TpmReady = $tpm.TpmReady } "
                "} | ConvertTo-Json -Compress"
            )
            
            output = subprocess.run(
                ["powershell", "-Command", command], 
                capture_output=True, text=True
            )
            
            if output.returncode == 0 and output.stdout.strip():
                data = json.loads(output.stdout)
                return {
                    "present": bool(data.get("TpmPresent", False)),
                    "ready": bool(data.get("TpmReady", False))
                }
            else:
                return {"present": False, "ready": False}
        
        except Exception as e:
            return {"present": False, "ready": False}

    @staticmethod
    def get_usb_history():
        usb_list = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\USBSTOR") as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)
                    usb_list.append(subkey_name)
        except Exception:
            return ["Unknown"]
        return usb_list

available_methods = {
    **HardwareInfo.available_methods,
    **SoftwareInfo.available_methods,
    **NetworkInfo.available_methods,
    **SecurityInfo.available_methods,
    **OtherInfo.available_methods,
}

if not os.path.exists(AVAILABLE_METHODS_FILE):
    with open(AVAILABLE_METHODS_FILE, "w") as f:
        json.dump(list(available_methods.keys()), f, indent=4)

def get_info(*args):
    info = {}

    if "all" in args:
        args = list(available_methods.keys())

    for arg in args:
        if arg in available_methods:
            info[arg] = available_methods[arg]()
        else:
            info[arg] = "Invalid option"

    return info


