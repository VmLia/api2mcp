import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Api2mcpTool {
  id: string
  tool_name: string
  version: string
  tool_description: string | null
  category: string | null
  tags: string[]
  method: string
  base_url: string
  path: string
  content_type: string
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
  tool_id: string
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

export const useAPIToolStore = defineStore('apiTool', () => {
  const api2mcpTools = ref<Api2mcpTool[]>([])
  const currentApi2mcpTool = ref<Api2mcpTool | null>(null)
  const api2mcpParameters = ref<Api2mcpParameter[]>([])
  const authConfigs = ref<Api2mcpAuthConfig[]>([])
  const semanticTags = ref<SemanticTag[]>([])
  const mcpBaseUrl = ref<string>('')
  const isLoading = ref(false)
  const error = ref<string | null>(null)

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
      const response = await fetch(`/serverapi/apimng/tools?${query.toString()}`)
      const result = await response.json()
      api2mcpTools.value = result.tools || []
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}`)
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
      const response = await fetch('/serverapi/apimng/tools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Creation failed')
      await loadApi2mcpTools()
      return result.tool_id
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}`, {
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}`, { method: 'DELETE' })
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}/parameters`)
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}/parameters`, {
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}/parameters/${paramId}`, {
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}/parameters/${paramId}`, {
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}/mcp-definition`)
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
      const response = await fetch(`/serverapi/apimng/tools/${toolId}/register-mcp`, {
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

  return {
    api2mcpTools,
    currentApi2mcpTool,
    api2mcpParameters,
    authConfigs,
    semanticTags,
    mcpBaseUrl,
    isLoading,
    error,
    
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
    loadSemanticTags
  }
})
