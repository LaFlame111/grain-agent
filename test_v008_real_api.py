import httpx
import json
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.wms_client import WMSClient

def test_real_api_integration():
    print("=" * 60)
    print("V008 WMS Real API Integration Test")
    print("=" * 60)
    
    client = WMSClient()
    house_code = "91620702MADKWU312X01001"
    
    # 0. Connected Silos List
    print("\n[0/4] Testing Connected Silos List...")
    try:
        silos = client.get_connected_silos()
        if silos:
            print(f"SUCCESS! Found {len(silos)} connected silos")
            print(f"  First Silo: {silos[0].get('house_name')} ({silos[0].get('house_code')})")
        else:
            print("WARNING: No silos returned")
    except Exception as e:
        print(f"FAILED: {e}")

    # 1. Warehouse Info
    print(f"\n[1/4] Testing Warehouse Info (House: {house_code})...")
    try:
        info = client.get_warehouse_info(house_code)
        print(f"SUCCESS! Name: {info.house_name}, Depot: {info.depot_name}")
        if hasattr(info, 'grain_nature') and info.grain_nature:
            print(f"  Nature: {info.grain_nature}, Variety: {info.variety}")
    except Exception as e:
        print(f"FAILED: {e}")

    # 2. Grain Temperature
    print(f"\n[2/4] Testing Grain Temperature (2026-01-01 to 2026-01-05)...")
    try:
        st = datetime(2026, 1, 1)
        et = datetime(2026, 1, 5, 23, 59, 59)
        temps = client.get_grain_temperature(house_code, st, et)
        if temps:
            print(f"SUCCESS! Got {len(temps)} records")
            last = temps[-1]
            print(f"  Last Check: {last.check_time}, Avg: {last.avg_temp}C")
        else:
            print("WARNING: No data returned from API")
    except Exception as e:
        print(f"FAILED: {e}")

    # 3. Gas Concentration
    gas_house_code = "91620702MADKWU312X01012"
    print(f"\n[3/4] Testing Gas Concentration (2026-01-01 to 2026-01-05)...")
    try:
        st = datetime(2026, 1, 1)
        et = datetime(2026, 1, 5, 23, 59, 59)
        gases = client.get_gas_concentration(gas_house_code, st, et)
        if gases:
            print(f"SUCCESS! Got {len(gases)} records")
            last = gases[-1]
            print(f"  Last Check: {last.check_time}, O2: {last.avg_o2}%, PH3: {last.avg_ph3}")
        else:
            print("WARNING: No gas data returned")
    except Exception as e:
        print(f"FAILED: {e}")

    print("\n" + "=" * 60)
    print("Test Completed")
    print("=" * 60)

if __name__ == "__main__":
    test_real_api_integration()
