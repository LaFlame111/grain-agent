"""
将粮仓 Excel 原始数据转换为 WMS API 兼容的 JSON 格式。

输入：驻马店直属库15号仓原始数据自改10排5区4层.xlsx
输出：data/grain_data_wms_format.json

Excel 结构：
  第1行：传感器位置描述（"1排1区1层" / "1，2,2" 等格式）
  第2行：列名（仓房号、测温时间、布点号0~199、汇总列）
  第3行起：数据，每行 200 个传感器值

WMS GrainTempData 格式：
  house_code, house_name, record_time, max_temp, min_temp, avg_temp,
  indoor_temp, indoor_humidity, outdoor_temp, outdoor_humidity,
  temp_values  -> "value,layer,row,col|..." 竖线分隔
"""

import re
import json
import sys
from pathlib import Path
from datetime import datetime

# ── 路径配置 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_PATH = BASE_DIR / "驻马店直属库15号仓原始数据自改10排5区4层.xlsx"
OUTPUT_PATH = BASE_DIR / "data" / "grain_data_wms_format.json"

# 该仓的标识（前端/Agent 可用 "15" 或 "ZMD15" 查询）
HOUSE_CODE = "ZMD_ZMDZSZK_015"
HOUSE_NAME = "15号仓"

# 数据列索引（0-based）
COL_SILO = 0  # 仓房号
COL_TIME = 1  # 测温时间
COL_SENSOR_START = 2  # 布点号0
COL_SENSOR_COUNT = 200  # 布点号0~199
COL_MAX = 202  # 所有层最高温度
COL_MIN = 203  # 所有层最低温度
COL_AVG = 204  # 所有层平均温度


def parse_position(text: str):
    """
    解析传感器位置文本，返回 (row排, col区, layer层)。
    支持格式：
      "1排1区1层"  ->  (1, 1, 1)
      "1，2,2"     ->  (1, 2, 2)   （中文逗号/ASCII逗号混用）
      "10,5,4"    ->  (10, 5, 4)
    """
    if not text or not isinstance(text, str):
        return None

    # 方式一：完整中文格式 "N排N区N层"
    m = re.match(r"(\d+)\s*排\s*(\d+)\s*区\s*(\d+)\s*层", text.strip())
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    # 方式二：数字逗号格式（中英文逗号均可）"R，C,L" 或 "R,C,L"
    normalized = text.strip().replace("，", ",").replace(" ", "")
    m = re.match(r"^(\d+),(\d+),(\d+)$", normalized)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    return None


def build_sensor_map(header_row1):
    """
    从第1行 header 构建 {列索引: (row, col, layer)} 映射。
    """
    sensor_map = {}
    for idx, cell in enumerate(header_row1):
        if idx < COL_SENSOR_START:
            continue
        if idx >= COL_SENSOR_START + COL_SENSOR_COUNT:
            break
        pos = parse_position(str(cell) if cell else "")
        if pos:
            sensor_map[idx] = pos  # (排, 区, 层)
    return sensor_map


def row_to_wms(data_row, sensor_map):
    """
    将一行 Excel 数据转为 GrainTempData 字典。
    """
    # 时间
    ts = data_row[COL_TIME]
    if isinstance(ts, datetime):
        record_time = ts.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(ts, str):
        record_time = ts
    else:
        return None  # 无效行

    # 汇总温度
    def safe_float(v):
        try:
            return round(float(v), 2) if v is not None else None
        except (TypeError, ValueError):
            return None

    max_temp = safe_float(data_row[COL_MAX])
    min_temp = safe_float(data_row[COL_MIN])
    avg_temp = safe_float(data_row[COL_AVG])

    # 200 个传感器值 -> temp_values 字符串
    segments = []
    for col_idx, (r, c, layer) in sensor_map.items():
        val = safe_float(data_row[col_idx])
        if val is not None:
            segments.append(f"{val},{layer},{r},{c}")

    if not segments:
        return None

    temp_values = "|".join(segments)

    # 如果 max/min/avg 为空，从传感器数据计算
    vals: list[float] = [
        v
        for i in range(COL_SENSOR_START, COL_SENSOR_START + COL_SENSOR_COUNT)
        if (v := safe_float(data_row[i])) is not None
    ]
    if vals:
        if max_temp is None:
            max_temp = round(max(vals), 2)
        if min_temp is None:
            min_temp = round(min(vals), 2)
        if avg_temp is None:
            avg_temp = round(sum(vals) / len(vals), 2)

    return {
        "house_code": HOUSE_CODE,
        "house_name": HOUSE_NAME,
        "record_time": record_time,
        "max_temp": max_temp,
        "min_temp": min_temp,
        "avg_temp": avg_temp,
        "indoor_temp": None,
        "indoor_humidity": None,
        "outdoor_temp": None,
        "outdoor_humidity": None,
        "temp_values": temp_values,
    }


def main():
    try:
        import openpyxl
    except ImportError:
        print("请先安装 openpyxl：pip install openpyxl")
        sys.exit(1)

    if not EXCEL_PATH.exists():
        print(f"找不到 Excel 文件：{EXCEL_PATH}")
        sys.exit(1)

    print(f"读取 Excel：{EXCEL_PATH.name}")
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    ws = wb["温度值"]

    all_rows = list(ws.iter_rows(values_only=True))
    print(f"总行数（含标题）：{len(all_rows)}")

    header_row1 = all_rows[0]  # 第1行：传感器位置
    # header_row2 = all_rows[1] # 第2行：列名（不需要）
    data_rows = all_rows[2:]  # 第3行起：数据

    sensor_map = build_sensor_map(header_row1)
    print(f"解析到传感器数量：{len(sensor_map)}")

    records = []
    skipped = 0
    for row in data_rows:
        if not row or row[COL_TIME] is None:
            skipped += 1
            continue
        rec = row_to_wms(row, sensor_map)
        if rec:
            records.append(rec)
        else:
            skipped += 1

    print(f"有效记录数：{len(records)}，跳过：{skipped}")
    print(f"时间范围：{records[0]['record_time']} ~ {records[-1]['record_time']}")

    # 写出 JSON
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 如果已存在，合并（保留其他仓的数据）
    existing = []
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        # 移除旧的同仓数据
        existing = [r for r in existing if r.get("house_code") != HOUSE_CODE]
        print(f"已有 JSON 中保留其他仓数据：{len(existing)} 条")

    final = existing + records
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 已写出 {len(records)} 条记录到：{OUTPUT_PATH}")
    print(f"  house_code = {HOUSE_CODE}")
    print(f"  house_name = {HOUSE_NAME}")
    print(f'  前端/Agent 查询关键词："15号仓" 或 "15"')


if __name__ == "__main__":
    main()
