"""
智能API解析服务 - 使用LLM解析API文档
"""
import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from openai import AsyncOpenAI, APIError
from ...config import settings

logger = logging.getLogger(__name__)


class ParseResult(BaseModel):
    """API解析结果"""
    mcp_name: str
    method: str = "GET"
    api_fullurl: str
    tool_description: str = ""
    parameters: List[Dict[str, Any]] = []
    output_fields: Dict[str, Dict[str, str]] = {}
    output_template: Optional[str] = None


class SmartApiParser:
    """智能API解析器"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=f"{settings.LLM_API_URL}/v1"
        )
        self.model_name = settings.LLM_MODEL_NAME
    
    async def parse_api_text(self, text: str) -> ParseResult:
        """
        使用LLM解析API文档文本
        
        Args:
            text: API文档文本，可以是自然语言描述、Swagger JSON或URL模式
        
        Returns:
            ParseResult: 解析后的API配置
        
        Raises:
            ValueError: 当输入为空或无法解析出有效API配置时
        """
        if not text.strip():
            raise ValueError("Input text cannot be empty")
        
        # 先尝试本地解析（快速路径）
        local_result = self._local_parse(text)
        if local_result.mcp_name and local_result.api_fullurl:
            logger.debug("Local parse succeeded")
            return local_result
        
        # 本地解析结果不完整，尝试 LLM 解析
        if settings.LLM_API_KEY:
            try:
                logger.debug("Local parse incomplete, using LLM")
                llm_result = await self._llm_parse(text)
                # 校验 LLM 解析结果的有效性
                if llm_result.mcp_name and llm_result.api_fullurl:
                    return llm_result
                logger.warning("LLM parse returned incomplete result, falling back to local")
            except Exception as e:
                logger.warning(f"LLM parse failed: {e}, falling back to local")
        
        # 降级：返回本地解析结果（即使不完整）
        if local_result.api_fullurl:
            if not local_result.mcp_name:
                local_result.mcp_name = "api_tool"
            return local_result
        
        raise ValueError(
            "Unable to parse API configuration from input. "
            "Please provide a valid URL (e.g., GET https://api.example.com/users) "
            "or Swagger/OpenAPI JSON."
        )
    
    def _local_parse(self, text: str) -> ParseResult:
        """
        本地解析API文本（不调用LLM）
        
        支持的格式：
        1. GET https://api.example.com/users/search?keyword=xxx
        2. POST https://api.example.com/projects/create with body params: name, description
        3. https://api.example.com/users/search?keyword=xxx (裸 URL，默认 GET)
        4. Swagger/OpenAPI JSON snippet
        """
        result = ParseResult(
            mcp_name="",
            method="GET",
            api_fullurl="",
            tool_description="",
            parameters=[],
            output_fields={},
            output_template=None
        )
        
        # 1. 提取URL和方法
        import re
        
        # 优先匹配 "METHOD URL" 格式
        url_pattern = r"(GET|POST|PUT|PATCH|DELETE)\s+https?://[\w.-]+(?:/[\w./-{}]*)*"
        url_match = re.search(url_pattern, text, re.IGNORECASE)
        if url_match:
            result.method = url_match.group(1).upper()
            full_url = url_match.group(0).replace(result.method + ' ', '').strip()
            
            # 从URL中提取完整的API地址（包含查询参数）
            full_url_pattern = rf"{re.escape(full_url)}(?:\?[^\s]*)?"
            full_url_match = re.search(full_url_pattern, text)
            if full_url_match:
                result.api_fullurl = full_url_match.group(0)
            else:
                result.api_fullurl = full_url
        else:
            # 回退：匹配裸 URL（无 HTTP 方法前缀，默认 GET）
            bare_url_pattern = r"https?://[\w.-]+(?::\d+)?(?:/[\w./%-{}]*)*(?:\?[^\s,]*)?"
            bare_url_match = re.search(bare_url_pattern, text)
            if bare_url_match:
                result.api_fullurl = bare_url_match.group(0)
        
        # 从URL生成mcp_name（只使用路径部分，去掉查询参数和端口号）
        if result.api_fullurl:
            path_url = result.api_fullurl.replace('https://', '').replace('http://', '')
            # 去掉端口号部分
            if ':' in path_url.split('/')[0]:
                path_url = '/'.join([path_url.split('/')[0].split(':')[0].split('@')[-1]] + path_url.split('/')[1:])
            if '?' in path_url:
                path_url = path_url.split('?')[0]
            url_parts = path_url.split('/')
            path_parts = [p for p in url_parts[1:] if p and not p.startswith('{')]
            result.mcp_name = '_'.join(path_parts) if path_parts else 'api_tool'
        
        # 2. 从URL提取路径参数
        if result.api_fullurl:
            path_params = re.findall(r'{(\w+)}', result.api_fullurl)
            for name in path_params:
                result.parameters.append({
                    "param_name": name,
                    "param_type": "string",
                    "param_location": "path",
                    "required": True,
                    "description": ""
                })
        
        # 3. 提取查询参数（从URL的query部分）
        if result.api_fullurl and '?' in result.api_fullurl:
            query_string = result.api_fullurl.split('?')[1]
            # 使用正确的方式提取查询参数名（只取=前面的部分）
            query_parts = query_string.split('&')
            for part in query_parts:
                if '=' in part:
                    name = part.split('=')[0]
                    # 尝试从值推断类型
                    value = part.split('=')[1] if len(part.split('=')) > 1 else ''
                    p_type = self._infer_type(value)
                    if name and not any(p['param_name'] == name for p in result.parameters):
                        result.parameters.append({
                            "param_name": name,
                            "param_type": p_type,
                            "param_location": "query",
                            "required": False,
                            "description": ""
                        })
        
        # 4. 尝试解析JSON（支持Swagger/OpenAPI和普通API响应）
        try:
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = text[json_start:json_end]
                api_json = json.loads(json_str)
                
                # 判断是Swagger格式还是普通API响应
                if 'paths' in api_json:
                    # Swagger/OpenAPI格式
                    self._parse_swagger(api_json, result)
                else:
                    # 普通API响应格式，提取输出字段
                    self._parse_api_response(api_json, result)
        except Exception as e:
            logger.debug(f"JSON parse failed: {e}")
            pass
        
        # 5. 如果没有提取到参数，尝试自然语言提取
        if not result.parameters:
            # 匹配 "param: name(type, required)" 格式
            param_pattern = r'(\w+)\s*\(\s*(string|integer|number|boolean|array|object)\s*(?:,\s*required)?'
            matches = re.findall(param_pattern, text, re.IGNORECASE)
            for name, p_type in matches:
                result.parameters.append({
                    "param_name": name,
                    "param_type": p_type.lower(),
                    "param_location": "query" if result.method == "GET" else "body",
                    "required": True,
                    "description": ""
                })
        
        # 6. 生成默认描述
        if not result.tool_description:
            result.tool_description = f"{result.method} {result.api_fullurl}"
        
        return result
    
    def _infer_type(self, value: str) -> str:
        """从字符串值推断类型"""
        if not value:
            return "string"
        
        # 尝试解析为整数
        try:
            int(value)
            return "integer"
        except ValueError:
            pass
        
        # 尝试解析为浮点数
        try:
            float(value)
            return "number"
        except ValueError:
            pass
        
        # 检查布尔值
        lower_value = value.lower()
        if lower_value in ('true', 'false'):
            return "boolean"
        
        # 默认返回字符串
        return "string"
    
    def _parse_api_response(self, response: dict, result: ParseResult):
        """从普通API响应JSON中提取输出字段和 JMESPath 输出模板"""
        # 常见的列表数据路径键名模式
        list_keys = ['list', 'items', 'records', 'rows', 'data', 'results', 'entries', 'content']
        
        # 策略1：在 data 下寻找列表字段（最常见的分页响应结构）
        data = response.get('data')
        list_path = None
        list_sample = None
        
        if isinstance(data, dict):
            for key in list_keys:
                candidate = data.get(key)
                if isinstance(candidate, list) and len(candidate) > 0 and isinstance(candidate[0], dict):
                    list_path = f"data.{key}"
                    list_sample = candidate[0]
                    break
        
        # 策略2：直接在顶层寻找列表字段
        if list_sample is None:
            for key in list_keys:
                candidate = response.get(key)
                if isinstance(candidate, list) and len(candidate) > 0 and isinstance(candidate[0], dict):
                    list_path = key
                    list_sample = candidate[0]
                    break
        
        # 策略3：顶层 data 本身就是列表
        if list_sample is None and isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            list_path = "data"
            list_sample = data[0]
        
        # 如果找到了列表结构，生成 JMESPath 模板
        if list_sample is not None and list_path is not None:
            fields = list(list_sample.keys())
            field_mapping = ", ".join(f"{f}: {f}" for f in fields)
            result.output_template = f"{list_path}[*].{{{field_mapping}}}"
            
            # 从列表元素提取 output_fields
            for key, value in list_sample.items():
                result.output_fields[key] = {
                    "type": self._infer_value_type(value),
                    "description": ""
                }
        else:
            # 没有找到列表结构，回退到平铺字段提取
            sample = data if isinstance(data, dict) else response
            if isinstance(sample, dict):
                for key, value in sample.items():
                    field_type = self._infer_value_type(value)
                    result.output_fields[key] = {
                        "type": field_type,
                        "description": ""
                    }
            
            # 也从顶层提取未覆盖的字段
            for key, value in response.items():
                if key not in result.output_fields:
                    field_type = self._infer_value_type(value)
                    result.output_fields[key] = {
                        "type": field_type,
                        "description": ""
                    }
    
    def _infer_value_type(self, value) -> str:
        """从实际值推断类型"""
        if isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "string"
    
    def _parse_swagger(self, swagger: dict, result: ParseResult):
        """解析Swagger/OpenAPI规范"""
        paths = swagger.get('paths', {})
        if not paths:
            return
        
        first_path = list(paths.keys())[0]
        methods = paths[first_path]
        
        # 获取第一个可用的方法
        method_keys = ['get', 'post', 'put', 'patch', 'delete']
        for method in method_keys:
            if method in methods:
                operation = methods[method]
                result.method = method.upper()
                
                # 构建完整URL
                base_url = swagger.get('servers', [{}])[0].get('url', '')
                result.api_fullurl = base_url + first_path
                
                # 获取描述
                result.tool_description = operation.get('summary', '') or operation.get('description', '')
                result.mcp_name = operation.get('operationId', result.mcp_name)
                
                # 提取参数
                parameters = operation.get('parameters', [])
                for param in parameters:
                    result.parameters.append({
                        "param_name": param.get('name', ''),
                        "param_type": param.get('schema', {}).get('type', 'string'),
                        "param_location": param.get('in', 'query'),
                        "required": param.get('required', False),
                        "description": param.get('description', '')
                    })
                
                # 提取响应字段
                responses = operation.get('responses', {}).get('200', {}).get('content', {}).get('application/json', {}).get('schema', {})
                if responses.get('properties'):
                    for field, props in responses['properties'].items():
                        result.output_fields[field] = {
                            "type": props.get('type', 'string'),
                            "description": props.get('description', '')
                        }
                break
    
    async def _llm_parse(self, text: str) -> ParseResult:
        """使用LLM解析API文档"""
        system_prompt = """
你是一个专业的API文档解析助手。请将用户提供的API文档转换为结构化的数据格式。

输入格式：
- 自然语言描述
- Swagger/OpenAPI JSON
- URL模式
- API文档片段

输出格式（必须是有效的JSON）：
{
  "mcp_name": "工具名称（英文标识符）",
  "method": "HTTP方法（GET/POST/PUT/PATCH/DELETE）",
  "api_fullurl": "完整的API端点URL",
  "tool_description": "工具描述，用于LLM理解",
  "parameters": [
    {
      "param_name": "参数名",
      "param_type": "参数类型（string/integer/number/boolean/array/object）",
      "param_location": "参数位置（query/path/body/header）",
      "required": true/false,
      "description": "参数描述"
    }
  ],
  "output_fields": {
    "字段名": {
      "type": "字段类型",
      "description": "字段描述"
    }
  }
}

规则：
1. mcp_name必须是小写字母和下划线组成的标识符
2. 路径参数（如 /users/{id}）必须标记为 required: true
3. GET方法的参数默认位置是query，POST方法默认是body
4. 如果无法确定某个字段，使用合理的默认值
5. 只输出JSON，不要输出其他解释性文字
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            # 清理可能的markdown代码块标记
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            data = json.loads(content)
            return ParseResult(**data)
        
        except APIError as e:
            logger.error(f"LLM API error: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise ValueError(f"LLM returned invalid JSON response")
        except Exception as e:
            logger.error(f"LLM parse failed: {e}")
            raise
