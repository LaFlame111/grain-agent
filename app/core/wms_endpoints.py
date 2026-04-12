"""
WMS 外部接口链接配置文件

此文件用于管理与 WMS (粮库业务管理系统) 通信的所有 API 端点。
考虑到未来可能对接不同的 WMS 系统版本或环境，请统一在此处修改链接。
"""

# WMS 系统基础访问链接 (Base URL)
# 生产环境建议通过环境变量配置，此处为当前真实 API 的默认值
WMS_BASE_URL = "http://121.40.162.1:8017"

# 0. 接入仓房列表查询接口
# 功能：获取当前所有接入智能体的粮仓清单（编码、长名、短名）
WMS_ENDPOINT_WAREHOUSE_LIST = f"{WMS_BASE_URL}/api/wms/warehouse/list"

# 1. 仓房基本信息查询接口
# 功能：根据 house_code 获取仓房物理结构、容量、维度等信息
# 参数说明：house_code (必需)
WMS_ENDPOINT_WAREHOUSE_INFO = f"{WMS_BASE_URL}/api/wms/warehouse/info"

# 2. 粮温数据查询接口
# 功能：获取指定仓房在特定时间段内的粮情温度数据
# 参数说明：house_code (必需), start_time (可选), end_time (可选)
WMS_ENDPOINT_GRAIN_TEMPERATURE = f"{WMS_BASE_URL}/api/wms/grain/temperature"

# 3. 气体浓度查询接口
# 功能：获取指定仓房的气体检测数据 (O2, PH3, CO2, N2 等)
# 参数说明：house_code (必需), start_time (可选), end_time (可选)
WMS_ENDPOINT_GAS_CONCENTRATION = f"{WMS_BASE_URL}/api/wms/gas/concentration"

# 接口超时时间配置 (单位：秒)
WMS_API_TIMEOUT = 5.0
