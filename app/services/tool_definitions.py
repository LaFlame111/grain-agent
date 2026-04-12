"""
Grain Agent 工具定义 (JSON Schema)
用于 LLM Function Calling
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "inspection",
            "description": "粮库巡检：检查指定粮库的所有仓，识别异常点位（如温度过高）。如果不指定粮库ID，默认检查所有。",
            "parameters": {
                "type": "object",
                "properties": {
                    "warehouse_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "粮库ID列表，例如 ['1', '2']。留空则检查所有。"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analysis",
            "description": "智能分析：对指定仓号进行深入的粮情分析，识别风险（如热点、霉变风险）并给出评分。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {
                        "type": "string",
                        "description": "仓号，例如 '1'。"
                    }
                },
                "required": ["silo_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extraction",
            "description": "数据提取：从 WMS 接口获取指定仓在一段时间内的粮温/气体等原始数据与统计摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {"type": "string", "description": "仓号/仓房编码，例如 '1'。"},
                    "time_range_hours": {"type": "integer", "description": "时间范围（小时），默认24。", "default": 24}
                },
                "required": ["silo_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comparison_time",
            "description": "同仓对比：对比同一个仓在不同时间段的粮情（如温度变化趋势）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {
                        "type": "string",
                        "description": "仓号，例如 '1'。"
                    },
                    "time_windows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "hours_ago": {"type": "integer", "description": "几小时前的数据"}
                            }
                        },
                        "description": "要对比的时间点列表。例如 [{'hours_ago': 24}, {'hours_ago': 168}] 表示对比24小时前和一周前。"
                    }
                },
                "required": ["silo_id", "time_windows"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comparison_silo",
            "description": "仓间对比：对比多个仓在同一时间段的粮情（如找出温度最高的仓）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的仓号列表，例如 ['1', '2', '3']。"
                    },
                    "time_range_hours": {
                        "type": "integer",
                        "description": "时间范围（小时），默认24。",
                        "default": 24
                    }
                },
                "required": ["silo_ids"]
            }
        }
    },

    # === C: WMS 标准数据接口（对齐 interface_schema.md）===
    {
        "type": "function",
        "function": {
            "name": "get_connected_silos",
            "description": "获取当前所有接入智能体的粮仓清单（编码、长名、短名）。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_warehouse_info",
            "description": "根据仓房编码查询仓房详细信息（结构/容量/尺寸等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_code": {"type": "string", "description": "仓房编码"}
                },
                "required": ["house_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_grain_temperature",
            "description": "查询指定仓房在一段时间内的粮温/温湿度数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_code": {"type": "string", "description": "仓房编码"},
                    "start_time": {"type": "string", "description": "开始时间，例如 '2024-01-01 00:00:00'"},
                    "end_time": {"type": "string", "description": "结束时间，例如 '2024-01-01 23:59:59'"},
                },
                "required": ["house_code", "start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gas_concentration",
            "description": "查询指定仓房在一段时间内的气体浓度数据（O2/PH3/CO2/N2 等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_code": {"type": "string", "description": "仓房编码"},
                    "start_time": {"type": "string", "description": "开始时间，例如 '2024-01-01 00:00:00'"},
                    "end_time": {"type": "string", "description": "结束时间，例如 '2024-01-01 23:59:59'"},
                },
                "required": ["house_code", "start_time", "end_time"],
            },
        },
    },

    # === B: T6/T7/T8（全部通过 tools 被 LLM 调度）===
    {
        "type": "function",
        "function": {
            "name": "llm_reasoning",
            "description": "融合推理：基于上下文（T1-T5 或 WMS 数据接口结果）生成风险结论与建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用户问题/要生成建议的目标"},
                    "context": {"type": "object", "description": "上下文数据（任意 JSON 对象）"},
                    "prompt_template": {"type": "string", "description": "可选：额外指令/模板"},
                },
                "required": ["query", "context"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visualization",
            "description": "可视化：生成指定仓的粮情图表（line/heatmap/3d）。返回图片路径。\n重要：如果用户查询中指定了时间范围（如'2015年4月'），必须解析并传递 start_time 和 end_time 参数。\n时间范围解析规则：\n- '2015年4月' -> start_time='2015-04-01 00:00:00', end_time='2015-04-30 23:59:59'\n- '2015年1月-2015年12月' -> start_time='2015-01-01 00:00:00', end_time='2015-12-31 23:59:59'\n- '2015年' -> start_time='2015-01-01 00:00:00', end_time='2015-12-31 23:59:59'",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {"type": "string", "description": "仓号"},
                    "chart_type": {"type": "string", "description": "图表类型：line/heatmap/3d", "default": "line"},
                    "time_range_hours": {"type": "integer", "description": "时间范围（小时），默认24小时。如果用户查询中指定了时间范围，应使用 start_time 和 end_time 参数。"},
                    "start_time": {"type": "string", "description": "开始时间，格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'。如果用户查询中指定了时间范围（如'2015年4月'），必须解析并传递此参数。例如：'2015-04-01 00:00:00' 或 '2015-04-01'。"},
                    "end_time": {"type": "string", "description": "结束时间，格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'。如果用户查询中指定了时间范围（如'2015年4月'），必须解析并传递此参数。例如：'2015-04-30 23:59:59' 或 '2015-04-30'。"},
                },
                "required": ["silo_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report",
            "description": "报告：生成粮情分析报告（daily/weekly/alert），返回 docx 路径。\n重要：如果用户查询中指定了时间范围（如'2015年4月'、'2015年1月-2015年12月'等），必须解析并传递 start_time 和 end_time 参数。\n时间范围解析规则：\n- '2015年4月' -> start_time='2015-04-01 00:00:00', end_time='2015-04-30 23:59:59'\n- '2015年1月-2015年12月' -> start_time='2015-01-01 00:00:00', end_time='2015-12-31 23:59:59'\n- '2015年' -> start_time='2015-01-01 00:00:00', end_time='2015-12-31 23:59:59'",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_ids": {"type": "array", "items": {"type": "string"}, "description": "仓号列表"},
                    "report_type": {"type": "string", "description": "报告类型 daily/weekly/alert", "default": "daily"},
                    "start_time": {"type": "string", "description": "开始时间，格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'。如果用户查询中指定了时间范围（如'2015年4月'），必须解析并传递此参数。例如：'2015-04-01 00:00:00' 或 '2015-04-01'。"},
                    "end_time": {"type": "string", "description": "结束时间，格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'。如果用户查询中指定了时间范围（如'2015年4月'），必须解析并传递此参数。例如：'2015-04-30 23:59:59' 或 '2015-04-30'。"},
                },
                "required": ["silo_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "three_temp_chart",
            "description": "三温图：生成包含气温、仓温、粮温三条曲线的可视化图表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {"type": "string", "description": "仓号"},
                    "start_time": {"type": "string", "description": "开始时间"},
                    "end_time": {"type": "string", "description": "结束时间"},
                },
                "required": ["silo_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "two_humidity_chart",
            "description": "两湿图：生成包含气湿、仓湿两条曲线的可视化图表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {"type": "string", "description": "仓号"},
                    "start_time": {"type": "string", "description": "开始时间"},
                    "end_time": {"type": "string", "description": "结束时间"},
                },
                "required": ["silo_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "short_term_prediction",
            "description": "趋势预测：基于参考时间段内的历史数据预测未来 3-7 天的粮情变化趋势。参考时间段默认为最近14天，适合日常短期预测。当用户明确询问较长期的趋势变化或季节性分析时，可将参考时间段设为1-3个月。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {"type": "string", "description": "仓号"},
                    "prediction_days": {
                        "type": "integer",
                        "description": "预测天数（3-7天）",
                        "default": 3,
                    },
                    "start_time": {
                        "type": "string",
                        "description": "参考开始时间（可选）",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "参考结束时间（可选）",
                    },
                    "include_spatial": {
                        "type": "boolean",
                        "description": "是否包含空间热点分析（各传感器点位独立预测）。默认 false。启用后会返回 spatial_analysis 字段，包含热点位置、各点位预测温度和升温速率异常点。当用户询问'哪个点位温度最高'、'热点位置'、'传感器分布'等空间相关问题时应设为 true。",
                        "default": False,
                    },
                },
                "required": ["silo_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "llm_temperature_prediction",
            "description": "LLM辅助温度预测：将历史粮温数据提交给大语言模型进行智能分析，生成未来3-7天的逐日温度预测、趋势判断、风险评估和储粮建议，并输出包含历史数据与预测曲线的可视化图表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "silo_id": {"type": "string", "description": "仓号"},
                    "prediction_days": {"type": "integer", "description": "预测天数（3-7天），默认5天。", "default": 5},
                    "start_time": {"type": "string", "description": "历史参考数据的开始时间（可选）"},
                    "end_time": {"type": "string", "description": "历史参考数据的结束时间（可选）"},
                },
                "required": ["silo_id"],
            },
        },
    },

    # === RAG: 知识检索 ===
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": "粮储知识检索：从粮储知识库（基于 GB/T 29890 等国家标准编译的结构化知识页面，涵盖温度阈值、水分标准、通风/熏蒸 SOP、害虫防治等）中检索相关信息。当用户询问储粮标准、操作规范、安全阈值、最佳实践等专业知识时，应调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询文本"},
                    "top_k": {"type": "integer", "description": "返回片段数量，默认3", "default": 3}
                },
                "required": ["query"]
            }
        }
    },
]
