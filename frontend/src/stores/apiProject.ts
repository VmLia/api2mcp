import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Api2mcpTool {
  id: string
  mcp_name: string
  version: string
  tool_description: string | null
  category: string | null
  tags: string[]
  method: string
  api_fullurl: string
  content_type: string
  mcp_fullurl: string | null
  output_fields: Record<string, { type: string; description?: string }>
  output_template: string | null
  usage_examples: { examples?: Array<{ question: string; params: Record<string, any> }> }
  cache_ttl: number
  timeout_ms: number
  status: string
  auth_config_id: string | null
  created_at: string | null
  updated_at: string | null
  parameters?: Api2mcpParameter[]
}

export interface Api2mcpParameter {
  id: string
  baseinfo_id: string
  parent_id: string | null
  param_name: string
  param_location: 'query' | 'path' | 'body' | 'header'
  param_type: 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'object'
  item_type: string | null
  required: boolean
  description: string | null
  default_value: string | null
  example_value: string | null
  unit: string | null
  semantic_tag: string | null
  sort_order: number
  children?: Api2mcpParameter[]
}

export interface Api2mcpAuthConfig {
  id: string
  name: string
  auth_type: string
  config: Record<string, any>
  created_at: string | null
}

export interface SemanticTag {
  value: string
  label: string
}

// 状态管理相关接口
export interface ServerInfo {
  server_id: string
  name: string
  status: string
  last_heartbeat: string
  total_requests: number
  successful_requests: number
  failed_requests: number
  avg_latency_ms: number
}

export interface RequestInfo {
  request_id: string
  mcp_name: string
  tool_version: string
  status: string
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  latency_ms: number | null
  input_params: Record<string, any> | null
  output_result: Record<string, any> | null
}

export interface CallStats {
  total_calls: number
  success_calls: number
  failed_calls: number
  avg_latency_ms: number
  success_rate: number
}

export interface HourlyStats {
  hour: string
  total_calls: number
  success_calls: number
  failed_calls: number
  avg_latency_ms: number
}

export const useAPIToolStore = defineStore('apiTool', () => {
  const api2mcpTools = ref<Api2mcpTool[]>([])
  const currentApi2mcpTool = ref<Api2mcpTool | null>(null)
  const api2mcpParameters = ref<Api2mcpParameter[]>([])
  const authConfigs = ref<Api2mcpAuthConfig[]>([])
  const semanticTags = ref<SemanticTag[]>([])
  const mcpBaseUrl = ref<string>('')
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  
  // 智能解析结果存储
  const parseResult = ref<any>(null)

  // 状态管理相关数据
  const serverStatus = ref<{ instance_id: string; servers: ServerInfo[] } | null>(null)
  const toolStats = ref<Record<string, CallStats>>({})
  const recentRequests = ref<RequestInfo[]>([])
  
  // 设置智能解析结果
  function setParseResult(result: any) {
    parseResult.value = result
  }
  
  // 获取智能解析结果
  function getParseResult() {
    const result = parseResult.value
    parseResult.value = null // 一次性消费
    return result
  }

  async function loadServerInfo() {
    try {
      const response = await fetch('/serverapi/apimng/server-info')
      const data = await response.json()
      mcpBaseUrl.value = data.mcp_base_url || ''
    } catch (e) {
      console.error('Failed to load MCP server configuration', e)
    }
  }

  async function loadApi2mcpTools(params?: { category?: string; status?: string; search?: string }) {
    isLoading.value = true
    error.value = null
    try {
      const query = new URLSearchParams()
      if (params?.category) query.append('category', params.category)
      if (params?.status) query.append('status', params.status)
      if (params?.search) query.append('search', params.search)
      const response = await fetch(`/serverapi/apimng/baseinfos?${query.toString()}`)
      const result = await response.json()
      api2mcpTools.value = result.baseinfos || []
    } catch (e) {
      error.value = 'Failed to load tool list'
      console.error(e)
    } finally {
      isLoading.value = false
    }
  }

  async function loadApi2mcpTool(toolId: string) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}`)
      if (!response.ok) throw new Error('Tool not found')
      currentApi2mcpTool.value = await response.json()
      return currentApi2mcpTool.value
    } catch (e: any) {
      error.value = e.message || 'Failed to load tool details'
      console.error(e)
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function createApi2mcpTool(data: Partial<Api2mcpTool>) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch('/serverapi/apimng/baseinfos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Creation failed')
      await loadApi2mcpTools()
      return result.baseinfo_id
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function updateApi2mcpTool(toolId: string, data: Partial<Api2mcpTool>) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!response.ok) {
        const result = await response.json()
        throw new Error(result.detail || 'Update failed')
      }
      await loadApi2mcpTools()
      return { status: 'ok' }
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function deleteApi2mcpTool(toolId: string) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}`, { method: 'DELETE' })
      if (!response.ok) {
        const result = await response.json()
        throw new Error(result.detail || 'Deletion failed')
      }
      await loadApi2mcpTools()
      return { status: 'ok' }
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function loadApi2mcpParameters(toolId: string) {
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}/parameters`)
      const result = await response.json()
      api2mcpParameters.value = result.parameters || []
      return api2mcpParameters.value
    } catch (e) {
      console.error(e)
      return []
    }
  }

  async function createApi2mcpParameter(toolId: string, data: Partial<Api2mcpParameter>) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}/parameters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Creation failed')
      await loadApi2mcpParameters(toolId)
      return result.parameter_id
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function updateApi2mcpParameter(toolId: string, paramId: string, data: Partial<Api2mcpParameter>) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}/parameters/${paramId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!response.ok) {
        const result = await response.json()
        throw new Error(result.detail || 'Update failed')
      }
      await loadApi2mcpParameters(toolId)
      return { status: 'ok' }
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function deleteApi2mcpParameter(toolId: string, paramId: string) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}/parameters/${paramId}`, {
        method: 'DELETE'
      })
      if (!response.ok) {
        const result = await response.json()
        throw new Error(result.detail || 'Deletion failed')
      }
      await loadApi2mcpParameters(toolId)
      return { status: 'ok' }
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function loadAuthConfigs() {
    try {
      const response = await fetch('/serverapi/apimng/auth-configs')
      const result = await response.json()
      authConfigs.value = result.configs || []
      return authConfigs.value
    } catch (e) {
      console.error(e)
      return []
    }
  }

  async function getMcpDefinition(toolId: string) {
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}/mcp-definition`)
      if (!response.ok) throw new Error('Failed to get MCP definition')
      return await response.json()
    } catch (e) {
      console.error(e)
      return null
    }
  }

  async function registerToMcp(toolId: string) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/serverapi/apimng/baseinfos/${toolId}/register-mcp`, {
        method: 'POST'
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Registration failed')
      return result
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function loadSemanticTags() {
    try {
      const response = await fetch('/serverapi/apimng/semantic-tags')
      const result = await response.json()
      semanticTags.value = result.tags || []
      return semanticTags.value
    } catch (e) {
      console.error(e)
      return []
    }
  }

  // ── 状态管理相关 API ──

  /**
   * 获取服务状态信息
   */
  async function loadServerStatus() {
    try {
      const response = await fetch('/server/status')
      if (!response.ok) throw new Error('Failed to load server status')
      serverStatus.value = await response.json()
      return serverStatus.value
    } catch (e) {
      console.error('Failed to load server status', e)
      return null
    }
  }

  /**
   * 获取工具调用统计
   */
  async function loadToolStats(toolName: string, version: string = 'v1') {
    try {
      const response = await fetch(`/mcpapi/stats/${toolName}?version=${version}`)
      if (!response.ok) throw new Error('Failed to load tool stats')
      const stats = await response.json()
      toolStats.value[`${toolName}@${version}`] = stats
      return stats
    } catch (e) {
      console.error('Failed to load tool stats', e)
      return null
    }
  }

  /**
   * 获取工具历史调用统计
   */
  async function loadToolStatsHistory(toolName: string, version: string = 'v1', hours: number = 24) {
    try {
      const response = await fetch(`/mcpapi/stats/${toolName}/history?version=${version}&hours=${hours}`)
      if (!response.ok) throw new Error('Failed to load tool stats history')
      return await response.json()
    } catch (e) {
      console.error('Failed to load tool stats history', e)
      return null
    }
  }

  /**
   * 获取请求状态信息
   */
  async function loadRequestStatus(requestId: string) {
    try {
      const response = await fetch(`/mcpapi/requests/${requestId}`)
      if (!response.ok) throw new Error('Request not found')
      return await response.json()
    } catch (e) {
      console.error('Failed to load request status', e)
      return null
    }
  }

  /**
   * 获取工具最近请求列表
   */
  async function loadRecentRequests(toolName: string, version: string = 'v1', limit: number = 100) {
    try {
      const response = await fetch(`/mcpapi/requests/${toolName}/${version}?limit=${limit}`)
      if (!response.ok) throw new Error('Failed to load recent requests')
      const result = await response.json()
      recentRequests.value = result.requests || []
      return recentRequests.value
    } catch (e) {
      console.error('Failed to load recent requests', e)
      return []
    }
  }

  /**
   * 测试工具调用
   */
  async function testToolCall(toolName: string, args: Record<string, any>) {
    try {
      const response = await fetch(`/mcpapi/tools/${toolName}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args)
      })
      if (!response.ok) {
        const result = await response.json()
        throw new Error(result.detail || 'Test failed')
      }
      return await response.json()
    } catch (e: any) {
      console.error('Tool test failed', e)
      throw e
    }
  }

  return {
    api2mcpTools,
    currentApi2mcpTool,
    api2mcpParameters,
    authConfigs,
    semanticTags,
    mcpBaseUrl,
    isLoading,
    error,

    // 状态管理相关
    serverStatus,
    toolStats,
    recentRequests,

    loadServerInfo,
    loadApi2mcpTools,
    loadApi2mcpTool,
    createApi2mcpTool,
    updateApi2mcpTool,
    deleteApi2mcpTool,

    loadApi2mcpParameters,
    createApi2mcpParameter,
    updateApi2mcpParameter,
    deleteApi2mcpParameter,

    loadAuthConfigs,
    getMcpDefinition,
    registerToMcp,
    loadSemanticTags,

    // 状态管理 API
    loadServerStatus,
    loadToolStats,
    loadToolStatsHistory,
    loadRequestStatus,
    loadRecentRequests,
    testToolCall,
    
    // 智能解析
    setParseResult,
    getParseResult
  }
})
