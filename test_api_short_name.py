import httpx
from app.core.wms_endpoints import WMS_ENDPOINT_GRAIN_TEMPERATURE

def test_short_name():
    house_code = "P1" # 尝试使用短名称
    params = {
        "house_code": house_code,
        "start_time": "2026-01-01 00:00:00",
        "end_time": "2026-01-05 23:59:59"
    }
    print(f"Testing API with short name: {house_code}")
    try:
        response = httpx.get(WMS_ENDPOINT_GRAIN_TEMPERATURE, params=params, timeout=10)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Data length: {len(data)}")
        if data:
            print(f"First item keys: {list(data[0].keys())}")
        else:
            print("Response is empty list.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_short_name()
