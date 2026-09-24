"""课程内容：21 个课程单元，按主题区域分模块组织。

内容结构见 REQUIREMENTS.md §4.1.2。
"""

from .zone_container import UNITS as CONTAINER_UNITS
from .zone_file import UNITS as FILE_UNITS
from .zone_incident import UNITS as INCIDENT_UNITS
from .zone_network import UNITS as NETWORK_UNITS
from .zone_shell import UNITS as SHELL_UNITS
from .zone_system import UNITS as SYSTEM_UNITS

# 区域顺序必须与 main.py 的 ZONE_ORDER 一致
UNITS = [
    *FILE_UNITS,
    *SYSTEM_UNITS,
    *NETWORK_UNITS,
    *SHELL_UNITS,
    *CONTAINER_UNITS,
    *INCIDENT_UNITS,
]

__all__ = ["UNITS"]
