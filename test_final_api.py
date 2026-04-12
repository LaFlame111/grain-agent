import httpx
import json

def test_final_api():
    url = "http://121.40.162.1:8017/api/wms/grain/temperature"
    house_code = "91620702MADKWU312X01012" # Q1
    params = {
        "house_code": house_code,
        "start_time": "2025-01-01 00:00:00",
        "end_time": "2026-12-31 23:59:59"
    }
    print(f"Testing API with: {house_code}")
    response = httpx.get(url, params=params, timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Is list? {isinstance(data, list)}")
    if isinstance(data, list):
        print(f"Count: {len(data)}")
        for i, item in enumerate(data):
            print(f"Item {i}: {item.get('check_time')}")
    else:
        print(f"Response: {data}")

if __name__ == "__main__":
    test_final_api()
