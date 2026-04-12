import json
import logging
from typing import Dict, Any, Optional, List

from pydantic import BaseModel
import time

from app.models.schemas import AnalysisResult, LLMStructuredResponse
from app.core.config import settings

try:
    # 通义千问（qwen-max）兼容 OpenAI SDK，通过 compatible-mode 接入
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - 可选依赖
    OpenAI = None  # type: ignore


logger = logging.getLogger(__name__)


class LLMResult:
    """LLM 结果封装"""

    def __init__(self, response: str, reasoning: str, tool_calls: Optional[List[Dict]] = None, tool_outputs: Optional[Dict[str, Any]] = None):
        self.response = response
        self.reasoning = reasoning
        self.tool_calls = tool_calls or []
        self.tool_outputs = tool_outputs or {}


class LLMService:
    """V006: 接入真实云端大模型（如 qwen-max），带本地 Mock 兜底"""

    def __init__(self):
        # 可选的云端 LLM 客户端
        self._client: Optional["OpenAI"] = None

        if OpenAI is None:
            logger.error("OpenAI package not installed. Please run 'pip install openai'.")
        
        if not settings.DASHSCOPE_API_KEY:
            logger.warning("DASHSCOPE_API_KEY is empty. LLM features will be disabled (using mock).")

        if OpenAI is not None and settings.DASHSCOPE_API_KEY:
            try:
                logger.info(f"Initializing LLM client with model: {settings.LLM_MODEL}")
                self._client = OpenAI(
                    api_key=settings.DASHSCOPE_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                )
                logger.info("LLM client initialized successfully.")
            except Exception as e:  # pragma: no cover - 初始化失败时回退
                logger.warning(
                    "Failed to initialize OpenAI/DashScope client, fallback to mock LLM. Error: %s",
                    e,
                )
                self._client = None

    def reason_with_context(self, context: Dict[str, Any], prompt_template: Optional[str] = None) -> Dict[str, Any]:
        """
        V006: 纯推理接口，根据上下文生成结论
        """
        if self._client is None:
            return {
                "conclusion": "Mock Conclusion: Based on the data, everything looks fine.",
                "risk_level": "low",
                "recommendations": ["Keep monitoring"],
                "evidence": ["Mock evidence"]
            }
            
        # Construct prompt
        system_prompt = "你是一个专业的粮情分析专家。请根据提供的上下文数据，进行风险评估并给出建议。请以JSON格式返回，包含 conclusion, risk_level, recommendations, evidence 字段。"
        user_prompt = f"上下文数据:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        if prompt_template:
            user_prompt += f"\n额外指令: {prompt_template}"
            
        try:
            response = self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                # response_format={"type": "json_object"}, # Uncomment if model supports it
                temperature=0.3,
                timeout=30.0,  # 30秒超时
            )
            content = response.choices[0].message.content
            # Parse JSON
            try:
                # Try to find JSON block if wrapped in markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                return json.loads(content)
            except:
                return {
                    "conclusion": content,
                    "risk_level": "unknown",
                    "recommendations": [],
                    "evidence": []
                }
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            return {
                "conclusion": f"Error during reasoning: {str(e)}",
                "risk_level": "unknown",
                "recommendations": [],
                "evidence": []
            }

    def analyze(self, query: str, context: Optional[Dict[str, Any]] = None) -> LLMResult:
        """基于分析/巡检/对比结果生成储藏建议。

        优先调用真实云端大模型（qwen-max 等），在以下情况回退到本地 Mock：
        - 未配置 DASHSCOPE_API_KEY
        - openai SDK 未安装
        - 调用云端接口失败或返回异常
        """

        # 没有可用的云端客户端时，直接走本地逻辑
        if self._client is None:
            return self._analyze_mock(query, context)

        try:
            return self._analyze_with_llm(query, context)
        except Exception as e:  # pragma: no cover - 远端失败时兜底
            logger.warning("Cloud LLM analyze failed, fallback to mock: %s", e)
            return self._analyze_mock(query, context)

    def chat_with_tools(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict]] = None, 
        tool_map: Optional[Dict[str, Any]] = None
    ) -> LLMResult:
        """
        支持 Function Calling 的对话接口
        
        Args:
            messages: 对话历史
            tools: 工具定义列表 (JSON Schema)
            tool_map: 工具函数映射 {name: function}
        """
        def get_msg_field(msg, field):
            if isinstance(msg, dict):
                return msg.get(field)
            return getattr(msg, field, None)

        if self._client is None:
            # Fallback to mock if no client
            last_user_msg = next((get_msg_field(m, "content") for m in reversed(messages) if get_msg_field(m, "role") == "user"), "")
            return self._analyze_mock(str(last_user_msg))

        executed_tool_calls: List[Dict[str, Any]] = []
        executed_tool_outputs: Dict[str, Any] = {}

        try:
            # 允许多轮工具调用（最多 3 轮），以支持"获取数据→分析→可视化/报告"等链路
            max_rounds = 3
            round_idx = 0

            while True:
                round_idx += 1
                
                try:
                    response = self._client.chat.completions.create(  # type: ignore
                        model=settings.LLM_MODEL,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto" if tools else None,
                        temperature=0.3,
                        timeout=30.0,  # 30秒超时
                    )
                except Exception as e:
                    raise
                
                response_message = response.choices[0].message
                tool_calls = response_message.tool_calls
                
                # If no tool calls, return the response
                if not tool_calls:
                    content = response_message.content or ""
                    answer, reasoning = self._parse_answer_and_reasoning(content)
                    return LLMResult(
                        response=answer,
                        reasoning=reasoning,
                        tool_calls=executed_tool_calls,
                        tool_outputs=executed_tool_outputs,
                    )
                
                # Handle tool calls
                messages.append(response_message) 
                
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse tool arguments: {tool_call.function.arguments}")
                        function_args = {}
                    
                    executed_tool_calls.append({"tool": function_name, "params": function_args})
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
                    
                    if tool_map and function_name in tool_map:
                        tool_function = tool_map[function_name]
                        try:
                            function_response = tool_function(**function_args)
                            content_str = json.dumps(function_response, ensure_ascii=False)
                            executed_tool_outputs[function_name] = function_response
                        except Exception as e:
                            content_str = json.dumps({"error": str(e)}, ensure_ascii=False)
                            executed_tool_outputs[function_name] = {"error": str(e)}
                    else:
                        content_str = json.dumps({"error": "tool_not_found"}, ensure_ascii=False)
                        executed_tool_outputs[function_name] = {"error": "tool_not_found"}
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": content_str,
                    })
                
                # 超出轮次限制则直接让模型给最终回答（不再允许 tools）
                if round_idx >= max_rounds:
                    final_resp = self._client.chat.completions.create(  # type: ignore
                        model=settings.LLM_MODEL,
                        messages=messages,
                        temperature=0.3,
                        timeout=30.0,  # 30秒超时
                    )
                    content = final_resp.choices[0].message.content or ""
                    answer, reasoning = self._parse_answer_and_reasoning(content)
                    return LLMResult(
                        response=answer, 
                        reasoning=reasoning,
                        tool_calls=executed_tool_calls,
                        tool_outputs=executed_tool_outputs,
                    )
            
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            # Fallback to mock on error
            last_user_msg = next((get_msg_field(m, "content") for m in reversed(messages) if get_msg_field(m, "role") == "user"), "")
            return self._analyze_mock(str(last_user_msg))

    # === 云端 LLM 实现 ===

    def _analyze_with_llm(self, query: str, context: Optional[Dict[str, Any]]) -> LLMResult:
        """调用云端大模型（OpenAI 兼容接口）生成回答。"""

        assert self._client is not None  # 为类型检查器提供保证

        messages = self._build_messages(query, context)

        completion = self._client.chat.completions.create(  # type: ignore[call-arg]
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=0.3,
            timeout=30.0,  # 30秒超时
        )

        content = completion.choices[0].message.content or ""
        answer, reasoning = self._parse_answer_and_reasoning(content)
        return LLMResult(response=answer, reasoning=reasoning)

    def _build_messages(self, query: str, context: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
        """构造对话消息，包含 System Prompt 和上下文。"""

        system_prompt = (
            "你是一个严谨的粮情分析智能体，擅长根据传感器数据、分析结果和对比结果，" 
            "判断粮仓是否存在温度、湿度等风险并给出操作建议。\n"
            "- 必须严格基于提供的上下文数据进行分析，不要编造数据或凭空假设。\n"
            "- 如果信息不足以得出结论，要明确说明'不足以判断'，并说明还需要哪些数据。\n"
            "- **必须给出推理依据**：在 reasoning 字段中详细说明分析过程、判断依据、风险评估的逻辑链条，不能省略。\n"
            "- 语言风格：专业但易懂，用简洁的中文给出结论和可执行建议。\n"
            "- 输出格式：只输出 JSON，不要添加任何多余文字或 Markdown。"
            "形如：{\"answer\": \"...\", \"reasoning\": \"...\"}"
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        if context:
            context_text = self._format_context(context)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "以下是与本次查询相关的结构化数据（JSON）：\n" f"{context_text}"
                    ),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": (
                    "用户问题：\n"
                    f"{query}\n\n"
                    "请基于上述数据，先给出结论和具体操作建议，再详细说明推理依据和分析过程。"
                    "**必须**在 reasoning 字段中提供完整的推理思路，包括："
                    "1) 如何从数据中得出风险判断；"
                    "2) 判断依据的具体数值和标准；"
                    "3) 建议的逻辑链条。"
                    "直接以 JSON 形式返回结果，键名为 'answer' 和 'reasoning'。"
                ),
            }
        )

        return messages

    def _format_context(self, context: Dict[str, Any]) -> str:
        """将上下文转换为适合大模型阅读的 JSON 文本。"""

        def normalize(value: Any) -> Any:
            if isinstance(value, BaseModel):
                return value.model_dump()
            if isinstance(value, dict):
                return {k: normalize(v) for k, v in value.items()}
            if isinstance(value, list):
                return [normalize(v) for v in value]
            return value

        safe_context = normalize(context)

        try:
            return json.dumps(safe_context, ensure_ascii=False, indent=2)
        except TypeError:
            # 最保险的降级：退回到字符串表示
            return str(safe_context)

    def _parse_answer_and_reasoning(self, content: str) -> tuple[str, str]:
        """从模型返回的文本中解析出 answer 和 reasoning。"""

        text = content.strip()

        # 优先从回答中提取 JSON 片段（模型常见输出：先自然语言，再 ```json ... ```）
        extracted = text
        if "```json" in extracted:
            try:
                extracted = extracted.split("```json", 1)[1].split("```", 1)[0].strip()
            except Exception:
                extracted = text
        elif "```" in extracted:
            # 兼容 ``` ... ``` 包裹（但不一定标注 json）
            try:
                extracted = extracted.split("```", 1)[1].split("```", 1)[0].strip()
            except Exception:
                extracted = text
        else:
            # 兼容“正文 + JSON 对象”的情况：尽量截取第一个 { ... } 作为候选
            l = extracted.find("{")
            r = extracted.rfind("}")
            if l != -1 and r != -1 and r > l:
                extracted = extracted[l : r + 1].strip()

        # 兼容 ```json ... ``` 代码块输出
        if text.startswith("```"):
            # 去掉开头的 ```xxx
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            # 尝试解析 JSON
            data = json.loads(extracted)
            
            # 使用 Pydantic 进行校验
            try:
                validated_data = LLMStructuredResponse(**data)
                return (validated_data.answer, validated_data.reasoning)
            except Exception as e:
                logger.warning(f"LLM output validation failed: {e}. Fallback to loose parsing.")
                # 降级：宽松解析
                answer = str(data.get("answer", "")).strip()
                reasoning = str(data.get("reasoning", "")).strip()
                if answer or reasoning:
                    return (answer or reasoning, reasoning)
                    
        except Exception:
            # 如果不是合法 JSON，则整体作为 answer 返回
            pass

        return text, ""

    # === 本地 Mock 实现（作为兜底） ===

    def _analyze_mock(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> LLMResult:
        """原有的基于规则的 Mock 逻辑，作为云端失败时的兜底。"""

        # 如果有分析结果上下文，生成更智能的建议
        if context and "analysis_result" in context:
            analysis: AnalysisResult = context["analysis_result"]
            return self._generate_storage_advice(query, analysis)

        # 如果有巡检结果
        if context and "inspection_result" in context:
            inspection = context["inspection_result"]
            return self._generate_inspection_summary(query, inspection)

        # 如果有对比结果
        if context and "comparison_result" in context:
            comparison = context["comparison_result"]
            return self._generate_comparison_summary(query, comparison)

        # 默认 Mock 响应
        return LLMResult(
            response=(
                f"收到您的查询：{query}\n\n"
                "这是一个模拟回答。在真实环境中，这里会调用大语言模型生成智能回答。"
            ),
            reasoning="Mock LLM 推理过程",
        )

    def _generate_storage_advice(self, query: str, analysis: AnalysisResult) -> LLMResult:
        """根据分析结果生成储藏建议"""
        
        silo_id = analysis.silo_id
        score = analysis.score
        findings = analysis.findings
        
        # 构建响应
        response_parts = []
        response_parts.append(f"📊 {silo_id}号仓粮情分析报告\n")
        response_parts.append(f"综合评分: {score:.1f}/100\n")
        
        # 根据评分判断风险等级
        if score >= 90:
            risk_level = "低风险 ✓"
            status_emoji = "🟢"
        elif score >= 70:
            risk_level = "中等风险 ⚠️"
            status_emoji = "🟡"
        else:
            risk_level = "高风险 ⚠️⚠️"
            status_emoji = "🔴"
        
        response_parts.append(f"风险等级: {status_emoji} {risk_level}\n")
        response_parts.append("\n📋 主要发现:")
        for finding in findings:
            response_parts.append(f"  {finding}")
        
        # 生成建议
        response_parts.append("\n💡 储藏建议:")
        recommendations = self._generate_recommendations(score, findings)
        for rec in recommendations:
            response_parts.append(f"  {rec}")
        
        # 构建推理过程
        reasoning_parts = []
        reasoning_parts.append("分析依据:")
        reasoning_parts.append(f"1. 综合评分 {score:.1f}/100 基于以下因素:")
        reasoning_parts.append("   - 温度是否超过安全阈值（25°C）")
        reasoning_parts.append("   - 是否存在热点（局部高温）")
        reasoning_parts.append("   - 温度分布均匀性（标准差）")
        reasoning_parts.append("   - 湿度水平")
        reasoning_parts.append(f"2. 检测到 {len([f for f in findings if '热点' in f or '🔥' in f])} 个潜在问题")
        reasoning_parts.append("3. 建议基于粮食储藏国家标准和最佳实践")
        
        return LLMResult(
            response="\n".join(response_parts),
            reasoning="\n".join(reasoning_parts)
        )
    
    def _generate_recommendations(self, score: float, findings: List[str]) -> List[str]:
        """根据评分和发现生成具体建议"""
        recommendations = []
        
        findings_text = " ".join(findings)
        
        # 检查热点问题
        if "热点" in findings_text or "🔥" in findings_text or "危险" in findings_text:
            recommendations.append("🌡️ 立即启动通风系统，降低仓内温度")
            recommendations.append("🔄 对热点区域进行重点监控，每2小时检查一次")
            recommendations.append("📍 考虑对热点区域进行翻仓处理")
        
        # 检查温度偏高
        if "偏高" in findings_text or "警告" in findings_text:
            recommendations.append("🌬️ 增加通风频次，建议夜间通风降温")
            recommendations.append("📊 加密温度监测频率，从每小时改为每30分钟")
        
        # 检查温度不均匀
        if "不均匀" in findings_text:
            recommendations.append("🔀 检查通风系统是否正常，确保气流均匀分布")
            recommendations.append("🔍 排查是否存在局部粮堆密实或通风死角")
        
        # 检查湿度问题
        if "湿度" in findings_text and "偏高" in findings_text:
            recommendations.append("💨 加强除湿措施，可使用除湿机或干燥通风")
            recommendations.append("🦠 注意防霉，定期检查粮食表面状况")
        
        # 如果评分很高，给予正面建议
        if score >= 90:
            recommendations.append("✅ 当前储藏状况良好，继续保持现有管理措施")
            recommendations.append("📅 建议每日例行巡检，确保粮情稳定")
        
        # 如果没有具体建议，给出通用建议
        if not recommendations:
            recommendations.append("📋 继续按照标准流程进行日常监测")
            recommendations.append("🔔 如发现异常变化，及时采取应对措施")
        
        return recommendations
    
    def _generate_inspection_summary(self, query: str, inspection: Dict[str, Any]) -> LLMResult:
        """生成巡检总结"""
        total = inspection.get("total_silos", 0)
        abnormal = inspection.get("abnormal_silos", 0)
        issues = inspection.get("issues", [])
        
        response_parts = []
        response_parts.append(f"📋 全库巡检报告\n")
        response_parts.append(f"检查仓数: {total}")
        response_parts.append(f"异常仓数: {abnormal}\n")
        
        if issues:
            response_parts.append("⚠️ 发现以下问题:")
            for issue in issues:
                severity_emoji = "🔴" if issue["severity"] == "danger" else "🟡"
                response_parts.append(f"  {severity_emoji} {issue['silo_id']}: {issue['issue']}")
        else:
            response_parts.append("✅ 所有粮仓状况正常")
        
        return LLMResult(
            response="\n".join(response_parts),
            reasoning=f"基于对{total}个仓的巡检数据分析"
        )
    
    def _generate_comparison_summary(self, query: str, comparison: Dict[str, Any]) -> LLMResult:
        """生成对比总结"""
        summary = comparison.get("summary", "")
        
        response_parts = []
        response_parts.append(f"📊 对比分析结果\n")
        response_parts.append(summary)
        
        return LLMResult(
            response="\n".join(response_parts),
            reasoning="基于多个数据源的对比分析"
        )

