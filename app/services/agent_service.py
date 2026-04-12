# -*- coding: utf-8 -*-
"""
Agent 服务 - 基于 LLM Function Calling 的智能对话

V006: 使用真实 LLM + Function Calling
"""

from typing import Dict, Any, List, Tuple
from app.services.tools import GrainTools
from app.services.tool_definitions import TOOL_DEFINITIONS
from app.services.rag_service import get_rag_service
import json, time


class AgentService:
    """粮情分析 Agent (Function Calling 版)"""

    def __init__(self):
        self.tools = GrainTools()
        self.conversation_history = []

        # 工具函数映射
        self.tool_map = {
            "inspection": self.tools.inspection,
            "extraction": self.tools.extraction,
            "analysis": self.tools.analysis,
            "comparison_time": self.tools.comparison_time,
            "comparison_silo": self.tools.comparison_silo,
            "llm_reasoning": self.tools.llm_reasoning,
            "visualization": self.tools.visualization,
            "report": self.tools.report,

            # C: WMS 标准数据接口
            "get_connected_silos": self.tools.get_connected_silos,
            "get_warehouse_info": self.tools.get_warehouse_info,
            "get_grain_temperature": self.tools.get_grain_temperature,
            "get_gas_concentration": self.tools.get_gas_concentration,

            # V008: 新增工具
            "three_temp_chart": self.tools.three_temp_chart,
            "two_humidity_chart": self.tools.two_humidity_chart,
            "short_term_prediction": self.tools.short_term_prediction,
            "llm_temperature_prediction": self.tools.llm_temperature_prediction,

            # RAG: 知识检索
            "knowledge_search": self._knowledge_search,
        }

    def _knowledge_search(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """知识检索：使用 RAGFlow 后端"""
        return get_rag_service().search(query=query, top_k=top_k)

    def chat(self, query: str) -> Dict[str, Any]:
        """
        处理用户查询

        Args:
            query: 用户的自然语言查询

        Returns:
            Agent 响应，包含回答、工具调用记录等
        """
        # 构造 System Prompt
        system_prompt = (
            "你是一个专业的粮情分析智能助手。你可以使用工具来获取粮库数据、进行分析和对比。\n"
            "重要规则：\n"
            "1. 当用户查询连接的仓房列表、接入清单时，必须调用 'get_connected_silos' 工具。\n"
            "2. 当用户提到的仓房名称（如 'Q1', 'P1'）不是完整的 20 位以上编码时，"
            "你应该优先参考之前获取的仓房清单，或者调用 'get_connected_silos' 来确认对应的 house_code。\n"
            "3. 当用户查询中指定了时间范围（如'2015年4月'、'2015年1月-2015年12月'等）时，必须：\n"
            "   - 解析时间范围并转换为标准格式（YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD）\n"
            "   - 将解析后的时间范围传递给相应的工具函数（如 report、get_grain_temperature 等）\n"
            "\n"
            "4. 关于文件路径：\n"
            "   - 当你生成报告或图表时，工具会返回一个本地绝对路径（如 G:\\...\\artifacts\\...）。\n"
            "   - 禁止在 answer 中直接展示这个原始绝对路径。\n"
            "   - 你应该在回答中告诉用户文件已生成，我会通过 UI 自动提供下载链接。\n"
            "\n"
            "5. [最高优先级] 关于知识检索：\n"
            "   - 当用户的问题涉及以下任何一类时，你必须先调用 'knowledge_search' 工具，禁止直接凭自身知识回答：\n"
            "     a) 储粮标准、国家标准、行业标准（如 GB/T、LS/T 相关内容）\n"
            "     b) 操作规程、操作规范、操作流程（如通风规程、熏蒸操作、入库流程等）\n"
            "     c) 安全阈值、安全标准（如温度阈值、湿度阈值、气体浓度限值等）\n"
            "     d) 条件判断（如什么条件下启动通风、什么情况下需要熏蒸等）\n"
            "     e) 最佳实践、储藏建议、技术要求\n"
            "   - 关键词识别：当问题中出现 标准/规程/规范/阈值/条件/要求/规定/安全/通风/熏蒸/储藏/储存/保管/防治 等词语时，必须调用 knowledge_search。\n"
            "   - 调用时将用户问题原文作为 query 参数传入。\n"
            "   - 回答必须基于检索到的知识库内容，并注明引用来源（如标准编号）。\n"
            "   - 如果知识库没有检索到相关内容，再用自身知识补充，但必须注明：以下内容非来自知识库。\n"
            "\n"
            "6. 关于粮温预测：\n"
            "   - 默认使用最近14天数据即可，适合日常短期预测。\n"
            "   - 仅当用户明确关心长期趋势或季节性变化时，才将参考时间段扩展到1-3个月。\n"
            "\n"
            "7. 解读预测结果时的注意事项（重要）：\n"
            "   - 若预测结果的 environmental_context 中包含 'seasonal_transition' 字段，\n"
            "     说明当前处于季节转折期（秋冬或冬春交接），统计模型的外推方向存在反转风险。\n"
            "     此时你**必须**在回答中提醒用户：预测数字仅为数学外推，季节转折期粮温走势\n"
            "     可能与预测方向相反，建议加强现场巡检频次，以实测数据为准。\n"
            "   - 若 data_quality.note 包含'数据极少'或'物理下界截断'等关键词，\n"
            "     同样需要在回答中明确告知用户该预测的局限性，不可直接引用数字而不加说明。\n"
            "\n"
            "回答时请保持专业、简洁。最终输出包含 'answer' 和 'reasoning'。"
        )

        # 维护对话上下文
        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史记录 (限制最近 10 轮以防超长)
        for hist in self.conversation_history[-10:]:
            messages.append({"role": "user", "content": hist["query"]})
            # 简化历史响应，只保留答案部分
            messages.append({"role": "assistant", "content": hist["response"].get("answer", "")})

        messages.append({"role": "user", "content": query})

        # 调用 LLM (带 Function Calling)
        llm_result = self.tools.llm_service.chat_with_tools(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_map=self.tool_map
        )

        # 提取结果
        answer = llm_result.response
        reasoning = llm_result.reasoning
        tool_calls = llm_result.tool_calls
        raw_results = llm_result.tool_outputs

        # 简单的意图推断 (基于调用的第一个工具)
        intent = "general"
        if tool_calls:
            intent = tool_calls[0]["tool"]

        # 构建响应
        response = {
            "query": query,
            "intent": intent,
            "answer": answer,
            "reasoning": reasoning,
            "tool_calls": tool_calls,
            "raw_results": raw_results
        }

        # 记录对话历史
        self.conversation_history.append({
            "query": query,
            "intent": intent,
            "response": response
        })

        return response
