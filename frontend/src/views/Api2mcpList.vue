<template>
  <div class="api2mcp-page">
    <div class="header-bar">
      <h2>API2MCP Tool Management</h2>
      <div class="header-actions">
        <el-button @click="goToStatus">
          <el-icon><Monitor /></el-icon>
          Server Status
        </el-button>
        <el-input
          v-model="searchQuery"
          placeholder="Search tools"
          style="width: 220px; margin-right: 10px"
          clearable
        />
        <el-button type="primary" @click="showFormCreateDialog()">
          <el-icon><Plus /></el-icon>
          表单创建New Tool
        </el-button>
        <el-button type="success" @click="showSmartCreateDialog()">
          <el-icon><Cpu /></el-icon>
          智能解析创建New Tool
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="categoryFilter" placeholder="Select category" style="width: 150px; margin-right: 10px">
        <el-option label="All" value="" />
        <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
      </el-select>
      <el-radio-group v-model="statusFilter">
        <el-radio-button label="">All</el-radio-button>
        <el-radio-button label="active">Active</el-radio-button>
        <el-radio-button label="inactive">Inactive</el-radio-button>
      </el-radio-group>
    </div>

    <div class="project-table" v-loading="store.isLoading">
      <el-table :data="filteredProjects" stripe>
        <el-table-column prop="mcp_name" label="MCP Name" width="180">
          <template #default="{ row }">
            <div class="tool-name-cell">
              <el-icon><Setting /></el-icon>
              <span>{{ row.mcp_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="tool_description" label="Description" width="250" />
        <el-table-column prop="category" label="Category" width="100">
          <template #default="{ row }">
            <el-tag size="small" v-if="row.category">{{ row.category }}</el-tag>
            <span v-else class="no-category">-</span>
          </template>
        </el-table-column>
        <el-table-column label="Original API" width="250">
          <template #default="{ row }">
            <el-tag
              :type="row.method === 'GET' ? 'success' : row.method === 'POST' ? 'primary' : 'warning'"
              size="small"
              style="margin-right: 8px"
            >
              {{ row.method }}
            </el-tag>
            <code class="url-code">{{ row.api_fullurl }}</code>
          </template>
        </el-table-column>
        <el-table-column label="Transport Protocol" width="200">
          <template #default="{ row }">
            <div class="transport-tags">
              <el-tag
                v-for="mode in (row.transport_modes || ['streamable_http'])"
                :key="mode"
                type="primary"
                size="small"
              >
                {{ mode === 'streamable_http' ? 'streamablehttp' : mode }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="MCP Endpoint" width="350">
          <template #default="{ row }">
            <div class="mcp-url-cell">
              <div class="url-wrapper">
                <code class="url-code">{{ getMcpToolUrl(row) }}</code>
              </div>
              <el-button
                size="small"
                text
                @click="copyToClipboard(getMcpToolUrl(row))"
                style="flex-shrink: 0"
              >
                <el-icon><Files /></el-icon>
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.status === 'active' ? 'success' : 'info'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? 'Active' : 'Inactive' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="300">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showEditDialog(row.id)">
              Edit
            </el-button>
            <el-button size="small" @click="showMcpConfig(row)">
              <el-icon><View /></el-icon>
              View Config
            </el-button>
            <el-button size="small" type="danger" text @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="filteredProjects.length === 0 && !store.isLoading" class="empty-tip">
        No API2MCP tools found. Click "New Tool" to create one
      </div>
    </div>

    <!-- Smart Parse Dialog -->
    <div v-if="showSmartDialog" class="smart-parse-overlay" @click.self="showSmartDialog = false">
      <div class="smart-parse-modal">
        <div class="modal-header">
          <span class="modal-title">🧠 Smart API Parser</span>
          <button class="modal-close" @click="showSmartDialog = false">×</button>
        </div>
        
        <div class="modal-body">
          <div class="parse-input-section">
            <label class="input-label">Paste URL and Response Example</label>
            <textarea
              v-model="smartParseInput"
              rows="12"
              :placeholder="placeholderText"
              class="parse-textarea"
            />
            <button 
              class="parse-button"
              @click="parseApiSmart"
              :disabled="smartParsing"
            >
              {{ smartParsing ? '⏳ Parsing...' : '🔍 Parse API' }}
            </button>
          </div>
          
          <div v-if="smartParseResult" class="parse-result-section">
            <div class="result-header">
              <span>Parse Result</span>
              <button class="apply-button" @click="applySmartResult">
                ✓ Apply to Form
              </button>
            </div>
            
            <div class="result-content">
              <div class="result-row">
                <span class="result-label">MCP Name:</span>
                <code>{{ smartParseResult.mcp_name }}</code>
              </div>
              <div class="result-row">
                <span class="result-label">Method:</span>
                <code>{{ smartParseResult.method }}</code>
              </div>
              <div class="result-row">
                <span class="result-label">API URL:</span>
                <code class="url-code">{{ smartParseResult.api_fullurl }}</code>
              </div>
              
              <div v-if="smartParseResult.parameters && smartParseResult.parameters.length > 0" class="result-section">
                <h4>Parameters ({{ smartParseResult.parameters.length }})</h4>
                <table class="result-table">
                  <thead>
                    <tr><th>Name</th><th>Location</th><th>Type</th><th>Required</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="param in smartParseResult.parameters" :key="param.param_name">
                      <td>{{ param.param_name }}</td>
                      <td>{{ param.param_location }}</td>
                      <td>{{ param.param_type }}</td>
                      <td>{{ param.required ? 'Yes' : 'No' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              
              <div v-if="smartParseResult.output_fields && Object.keys(smartParseResult.output_fields).length > 0" class="result-section">
                <h4>Output Fields</h4>
                <table class="result-table">
                  <thead>
                    <tr><th>Field</th><th>Type</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(config, field) in smartParseResult.output_fields" :key="field">
                      <td>{{ field }}</td>
                      <td>{{ config.type || 'string' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              
              <div v-if="smartParseResult.output_template" class="result-section">
                <h4>Output Template (JMESPath)</h4>
                <code class="jmespath-code">{{ smartParseResult.output_template }}</code>
              </div>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="cancel-button" @click="showSmartDialog = false">Cancel</button>
          <button v-if="smartParseResult" class="confirm-button" @click="applySmartResult">
            Apply to Form
          </button>
        </div>
      </div>
    </div>

    <!-- Add/Edit Dialog -->
    <el-dialog 
      v-model="showDetailDialog" 
      :title="editingId ? 'Edit Tool' : 'New Tool'" 
      width="900px"
      :close-on-click-modal="false"
    >
      <Api2mcpDetail 
        :edit-id="editingId" 
        @close="closeDetailDialog"
        @saved="onProjectSaved"
      />
    </el-dialog>

    <!-- MCP Config Detail Dialog -->
    <el-dialog v-model="showConfigDialog" title="MCP Server Configuration" width="900px">
      <div v-if="currentProject" class="mcp-config">
        <el-tabs v-model="configTab">
          <el-tab-pane label="Overview" name="overview">
            <div class="config-grid">
              <div class="config-card">
                <div class="config-card-header">
                  <el-icon class="config-icon"><InfoFilled /></el-icon>
                  <h4>Original API Info</h4>
                </div>
                <div class="config-item">
                  <span class="label">Method</span>
                  <el-tag :type="currentProject.method === 'GET' ? 'success' : 'primary'">
                    {{ currentProject.method }}
                  </el-tag>
                </div>
                <div class="config-item">
                  <span class="label">API URL</span>
                  <code class="url-value">{{ currentProject.api_fullurl }}</code>
                </div>
              </div>

              <div class="config-card">
                <div class="config-card-header">
                  <el-icon class="config-icon"><Monitor /></el-icon>
                  <h4>MCP Tool Info</h4>
                </div>
                <div class="config-item">
                  <span class="label">Tool Name</span>
                  <code class="url-value">{{ currentProject.mcp_name }}@{{ currentProject.version || 'v1' }}</code>
                </div>
                <div class="config-item">
                  <span class="label">MCP Root Endpoint</span>
                  <div class="copyable-url">
                    <code>{{ mcpBaseUrl }}</code>
                    <el-button size="mini" @click="copyToClipboard(mcpBaseUrl)">
                      <el-icon><Files /></el-icon>
                    </el-button>
                  </div>
                  <div class="form-tip" style="margin-top:4px;color:#909399;font-size:12px;">
                    Exposes all active tools
                  </div>
                </div>
              </div>

              <div class="config-card">
                <div class="config-card-header">
                  <el-icon class="config-icon"><More /></el-icon>
                  <h4>Transport Protocols & Endpoints</h4>
                </div>
                <div class="config-item">
                  <span class="label">Supported Protocols</span>
                  <div class="transport-tags">
                    <el-tag
                      v-for="mode in (currentProject.transport_modes || ['streamable_http'])"
                      :key="mode"
                      type="primary"
                      size="large"
                    >
                      {{ mode === 'streamable_http' ? 'streamablehttp' : mode }}
                    </el-tag>
                  </div>
                </div>
                <div class="config-item">
                  <span class="label">Single Tool Endpoint</span>
                  <div class="copyable-url">
                    <code>{{ getMcpToolUrl(currentProject) }}</code>
                    <el-button size="mini" @click="copyToClipboard(getMcpToolUrl(currentProject))">
                      <el-icon><Files /></el-icon>
                    </el-button>
                  </div>
                </div>
              </div>

              <div class="config-card full-width">
                <div class="config-card-header">
                  <el-icon class="config-icon"><Document /></el-icon>
                  <h4>Tool Description</h4>
                </div>
                <p class="description-text">{{ currentProject.tool_description || 'No description' }}</p>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="JSON Definition" name="json">
            <div class="json-container">
              <pre class="json-preview">{{ JSON.stringify(mcpDefinition, null, 2) }}</pre>
            </div>
          </el-tab-pane>

          <el-tab-pane label="Parameter Details" name="params">
            <div class="params-container">
              <el-table :data="inputParams" size="small" border>
                <el-table-column prop="name" label="Name" />
                <el-table-column prop="location" label="Location">
                  <template #default="{ row }">
                    <el-tag size="small" type="info">{{ row.location }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="type" label="Type" />
                <el-table-column prop="description" label="Description" />
                <el-table-column prop="required" label="Required">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.required ? 'danger' : 'info'">
                      {{ row.required ? 'Yes' : 'No' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="default_value" label="Default" />
                <el-table-column prop="example_value" label="Example" />
              </el-table>
            </div>
          </el-tab-pane>

          <el-tab-pane label="CherryStudio Config" name="cherrystudio">
            <div class="cherrystudio-config">
              <p class="config-tip">Copy the following config to CherryStudio's MCP Server configuration:</p>
              <div class="config-block">
                <div class="config-block-header">
                  <span>MCP Server Configuration</span>
                  <el-button size="mini" @click="copyToClipboard(cherryStudioConfig)">
                    <el-icon><Files /></el-icon>
                    Copy All
                  </el-button>
                </div>
                <pre class="config-content">{{ cherryStudioConfig }}</pre>
              </div>
              <div class="config-tips">
                <h5>Configuration Notes:</h5>
                <ul>
                  <li>Paste the above config to CherryStudio's "MCP Server Management" page</li>
                  <li>URL: <code>{{ mcpBaseUrl }}</code> (root endpoint, exposes all tools)</li>
                  <li>Transport Protocol: Streamable HTTP</li>
                </ul>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="showConfigDialog = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Setting, Delete, View, Files, InfoFilled, Monitor, More, Document, Cpu } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAPIToolStore } from '@/stores/apiProject'
import Api2mcpDetail from './Api2mcpDetail.vue'

const router = useRouter()
const store = useAPIToolStore()

const searchQuery = ref('')
const statusFilter = ref('')
const categoryFilter = ref('')
const showConfigDialog = ref(false)
const showDetailDialog = ref(false)
const editingId = ref<string | null>(null)
const configTab = ref('overview')
const mcpDefinition = ref<any>(null)
const currentProject = ref<any>(null)

// 智能解析相关变量定义（必须在使用它们的计算属性和函数之前）
const showSmartDialog = ref(false)
const smartParseInput = ref('')
const smartParsing = ref(false)
const smartParseResult = ref<any>(null)
const placeholderText = `Example:

http://192.100.45.45:35800/openapi/api/projects/search?keyword=test&page=1&page_size=2
{
  "code": 200,
  "data": {
    "list": [...],
    "total": 100
  }
}`

// MCP base URL is dynamically fetched from backend, not hardcoded
const mcpBaseUrl = computed(() => store.mcpBaseUrl)

const categories = computed(() => {
  const cats = new Set(store.api2mcpTools.map(t => t.category).filter(Boolean))
  return Array.from(cats)
})

const filteredProjects = computed(() => {
  let list = store.api2mcpTools
  if (statusFilter.value) {
    list = list.filter(t => t.status === statusFilter.value)
  }
  if (categoryFilter.value) {
    list = list.filter(t => t.category === categoryFilter.value)
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(t =>
      t.mcp_name.toLowerCase().includes(q) ||
      (t.tool_description || '').toLowerCase().includes(q)
    )
  }
  return list
})

const inputParams = computed(() => {
  if (!currentProject.value?.parameters) return []
  return currentProject.value.parameters.map((param: any) => ({
    name: param.param_name,
    location: param.param_location,
    type: param.param_type,
    description: param.description,
    required: param.required,
    default_value: param.default_value,
    example_value: param.example_value,
  }))
})

const cherryStudioConfig = computed(() => {
  if (!currentProject.value) return ''
  const mcpName = currentProject.value.mcp_name
  const version = currentProject.value.version || 'v1'
  return JSON.stringify({
    name: `${mcpName}@${version}`,
    type: "streamableHttp",
    description: currentProject.value.tool_description || "",
    baseUrl: mcpBaseUrl.value,
  }, null, 2)
})

/**
 * Get tool's MCP endpoint URL
 * Format: http://ip:port/mcpapi/{mcp_name}/{version}
 */
const getMcpToolUrl = (row: any): string => {
  const base = mcpBaseUrl.value
  const mcpName = row.mcp_name
  const version = row.version || 'v1'
  return `${base}/${mcpName}/${version}`
}

// 表单创建 - 传统方式填写表单
const showFormCreateDialog = () => {
  editingId.value = null
  showDetailDialog.value = true
}

// 智能解析创建 - 通过URL和响应示例自动解析
const showSmartCreateDialog = () => {
  showSmartDialog.value = true
  smartParseInput.value = ''
  smartParseResult.value = null
}

const showEditDialog = (id: string) => {
  editingId.value = id
  showDetailDialog.value = true
}

const closeDetailDialog = () => {
  showDetailDialog.value = false
  editingId.value = null
}

const onProjectSaved = () => {
  // Refresh tool list
  store.loadApi2mcpTools()
  closeDetailDialog()
}

const parseApiSmart = async () => {
  if (!smartParseInput.value.trim()) {
    ElMessage.warning('Please enter URL and response example')
    return
  }
  
  smartParsing.value = true
  smartParseResult.value = null
  
  try {
    const response = await fetch('/serverapi/parse', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text: smartParseInput.value }),
    })
    
    if (!response.ok) {
      throw new Error('Parse failed')
    }
    
    const data = await response.json()
    if (data.success) {
      smartParseResult.value = data.data
    } else {
      ElMessage.error(data.message || 'Parse failed')
    }
  } catch (error) {
    console.warn('Backend parse failed, using local fallback:', error)
    smartParseResult.value = parseApiTextLocal(smartParseInput.value)
  } finally {
    smartParsing.value = false
  }
}

const parseApiTextLocal = (text: string): any => {
  const result: any = {
    mcp_name: '',
    method: 'GET',
    api_fullurl: '',
    tool_description: '',
    parameters: [],
    output_fields: {},
    output_template: null,
  }
  
  // 提取URL
  const urlPattern = /https?:\/\/[\w.-]+(?:\/[\w./-{}]*)(?:\?[^\s]*)?/
  const urlMatch = text.match(urlPattern)
  if (urlMatch) {
    result.api_fullurl = urlMatch[0]
    
    // 从URL生成mcp_name
    const pathUrl = result.api_fullurl.replace(/^https?:\/\//, '').split('?')[0]
    const urlParts = pathUrl.split('/')
    const pathParts = urlParts.slice(1).filter((p: string) => p && !p.startsWith('{'))
    result.mcp_name = pathParts.length > 0 ? pathParts.join('_') : 'api_tool'
    
    // 提取查询参数
    if (result.api_fullurl.includes('?')) {
      const queryString = result.api_fullurl.split('?')[1]
      const queryParams = queryString.split('&').map((p: string) => p.split('=')[0])
      queryParams.forEach((name: string) => {
        if (name && !result.parameters.find((p: any) => p.param_name === name)) {
          result.parameters.push({
            param_name: name,
            param_type: 'string',
            param_location: 'query',
            required: false,
            description: '',
          })
        }
      })
    }
  }
  
  // 尝试解析JSON响应来提取输出字段和生成 JMESPath 模板
  try {
    const jsonStart = text.indexOf('{')
    const jsonEnd = text.lastIndexOf('}') + 1
    if (jsonStart !== -1 && jsonEnd > jsonStart) {
      const jsonStr = text.substring(jsonStart, jsonEnd)
      const responseData = JSON.parse(jsonStr)
      
      // 常见的列表数据路径键名
      const listKeys = ['list', 'items', 'records', 'rows', 'data', 'results', 'entries', 'content']
      const inferType = (value: any): string => {
        if (typeof value === 'number') return Number.isInteger(value) ? 'integer' : 'number'
        if (typeof value === 'boolean') return 'boolean'
        if (Array.isArray(value)) return 'array'
        if (typeof value === 'object' && value !== null) return 'object'
        return 'string'
      }
      
      // 在 data 下寻找列表字段
      let listPath: string | null = null
      let listSample: any = null
      const data = responseData.data
      
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        for (const key of listKeys) {
          const candidate = data[key]
          if (Array.isArray(candidate) && candidate.length > 0 && typeof candidate[0] === 'object') {
            listPath = `data.${key}`
            listSample = candidate[0]
            break
          }
        }
      }
      
      // 直接在顶层寻找列表字段
      if (!listSample) {
        for (const key of listKeys) {
          const candidate = responseData[key]
          if (Array.isArray(candidate) && candidate.length > 0 && typeof candidate[0] === 'object') {
            listPath = key
            listSample = candidate[0]
            break
          }
        }
      }
      
      // 顶层 data 本身就是列表
      if (!listSample && Array.isArray(data) && data.length > 0 && typeof data[0] === 'object') {
        listPath = 'data'
        listSample = data[0]
      }
      
      if (listSample && listPath) {
        // 生成 JMESPath 输出模板
        const fields = Object.keys(listSample)
        const fieldMapping = fields.map(f => `${f}: ${f}`).join(', ')
        result.output_template = `${listPath}[*].{${fieldMapping}}`
        
        // 从列表元素提取 output_fields
        fields.forEach(key => {
          result.output_fields[key] = {
            type: inferType(listSample[key]),
            description: '',
          }
        })
      } else {
        // 没有找到列表结构，回退到平铺字段提取
        const sample = (data && typeof data === 'object' && !Array.isArray(data)) ? data : responseData
        if (typeof sample === 'object' && !Array.isArray(sample)) {
          Object.keys(sample).forEach(key => {
            result.output_fields[key] = {
              type: inferType(sample[key]),
              description: '',
            }
          })
        }
        // 也从顶层提取未覆盖的字段
        Object.keys(responseData).forEach(key => {
          if (!result.output_fields[key]) {
            result.output_fields[key] = {
              type: inferType(responseData[key]),
              description: '',
            }
          }
        })
      }
    }
  } catch {
    // 不是有效的JSON，忽略
  }
  
  result.tool_description = `API endpoint ${result.method} ${result.api_fullurl}`
  return result
}

const applySmartResult = () => {
  if (!smartParseResult.value) return
  
  showSmartDialog.value = false
  
  // 使用解析结果预填充表单
  editingId.value = null
  showDetailDialog.value = true
  
  // 将解析结果存储到store或直接传递
  store.setParseResult(smartParseResult.value)
  ElMessage.success('Smart parse result applied')
}

const showMcpConfig = async (project: any) => {
  currentProject.value = project
  mcpDefinition.value = await store.getMcpDefinition(project.id)
  // Load parameter data
  await store.loadApi2mcpParameters(project.id)
  // Merge parameters into currentProject
  if (currentProject.value) {
    currentProject.value = {
      ...currentProject.value,
      parameters: store.api2mcpParameters
    }
  }
  showConfigDialog.value = true
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('Copied to clipboard')
  } catch (e) {
    ElMessage.error('Copy failed')
  }
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(`Are you sure you want to delete tool "${row.mcp_name}"?`, 'Confirm Delete', { type: 'warning' })
    await store.deleteApi2mcpTool(row.id)
    ElMessage.success('Deleted successfully')
    // Refresh list
    store.loadApi2mcpTools()
  } catch {
    // cancelled
  }
}

const toggleStatus = async (row: any) => {
  try {
    const newStatus = row.status === 'active' ? 'inactive' : 'active'
    await store.updateApi2mcpTool(row.id, { status: newStatus })
    ElMessage.success(`Tool "${row.mcp_name}" has been ${newStatus === 'active' ? 'activated' : 'deactivated'}`)
  } catch (e: any) {
    ElMessage.error(e.message || 'Operation failed')
  }
}

const goToStatus = () => {
  router.push('/frontrouter/status')
}

onMounted(() => {
  store.loadApi2mcpTools()
  store.loadServerInfo()
})
</script>

<style scoped>
.api2mcp-page {
  padding: 20px;
}
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.header-bar h2 {
  margin: 0;
}
.filter-bar {
  margin-bottom: 16px;
}
.project-table {
  background: white;
  border-radius: 8px;
  padding: 16px;
}
.tool-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mcp-url-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.url-wrapper {
  word-break: break-all;
  max-width: 300px;
}
.url-code {
  font-size: 12px;
  color: #606266;
  word-break: break-all;
  white-space: pre-wrap;
}
.no-category {
  color: #909399;
  font-size: 12px;
}
.empty-tip {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}
.transport-tags {
  display: flex;
  gap: 4px;
}

/* MCP Config Dialog */
.mcp-config {
  max-height: 700px;
  overflow-y: auto;
}
.config-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.config-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}
.config-card.full-width {
  grid-column: 1 / -1;
}
.config-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e9ecef;
}
.config-icon {
  color: #409eff;
}
.config-card-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.config-item {
  margin-bottom: 12px;
}
.config-item:last-child {
  margin-bottom: 0;
}
.config-item .label {
  display: block;
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}
.url-value {
  font-size: 12px;
  color: #409eff;
  word-break: break-all;
}
.copyable-url {
  display: flex;
  align-items: center;
  gap: 8px;
}
.copyable-url code {
  flex: 1;
  font-size: 12px;
  color: #409eff;
  word-break: break-all;
}
.mcp-url-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.description-text {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  margin: 0;
}

/* JSON Preview */
.json-container {
  max-height: 500px;
  overflow-y: auto;
}
.json-preview {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  max-height: 500px;
  overflow-y: auto;
}

/* Params Container */
.params-container {
  max-height: 500px;
  overflow-y: auto;
}

/* CherryStudio Config */
.cherrystudio-config {
  padding: 16px;
}
.config-tip {
  font-size: 13px;
  color: #606266;
  margin-bottom: 16px;
}
.config-block {
  background: #f8f9fa;
  border-radius: 8px;
  overflow: hidden;
}
.config-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #e9ecef;
  font-weight: 600;
  font-size: 13px;
}
.config-content {
  padding: 16px;
  background: #1e1e1e;
  color: #d4d4d4;
  font-size: 12px;
  max-height: 300px;
  overflow-y: auto;
}
.config-tips {
  margin-top: 16px;
  padding: 16px;
  background: #fff3cd;
  border-radius: 8px;
}
.config-tips h5 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #856404;
}
.config-tips ul {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: #856404;
}
.config-tips code {
  background: rgba(0,0,0,0.1);
  padding: 2px 4px;
  border-radius: 4px;
}

/* Smart Parse Dialog Styles */
.smart-parse-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.smart-parse-modal {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.modal-close {
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.modal-close:hover {
  color: #666;
}

.modal-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

.parse-input-section {
  margin-bottom: 20px;
}

.input-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #303133;
}

.parse-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  font-family: monospace;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
  line-height: 1.5;
}

.parse-textarea:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.parse-button {
  width: 100%;
  padding: 12px;
  margin-top: 12px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.3s;
}

.parse-button:hover:not(:disabled) {
  background: #66b1ff;
}

.parse-button:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.parse-result-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-weight: 600;
  color: #303133;
}

.apply-button {
  background: #67c23a;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
}

.apply-button:hover {
  background: #85ce61;
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-row {
  display: flex;
  gap: 12px;
  font-size: 14px;
}

.result-label {
  color: #909399;
  min-width: 80px;
}

.result-row code {
  background: #f5f7fa;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  word-break: break-all;
}

.url-code {
  flex: 1;
}

.result-section {
  margin-top: 16px;
}

.result-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #606266;
}

.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.result-table th,
.result-table td {
  border: 1px solid #ebeef5;
  padding: 8px 12px;
  text-align: left;
}

.result-table th {
  background: #f5f7fa;
  font-weight: 600;
  color: #606266;
}

.cancel-button {
  padding: 8px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: white;
  color: #606266;
  cursor: pointer;
  font-size: 14px;
}

.cancel-button:hover {
  background: #f5f7fa;
}

.confirm-button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  background: #67c23a;
  color: white;
  cursor: pointer;
  font-size: 14px;
}

.confirm-button:hover {
  background: #85ce61;
}

.jmespath-code {
  display: block;
  padding: 10px 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  font-size: 13px;
  font-family: 'Monaco', 'Menlo', monospace;
  word-break: break-all;
  white-space: pre-wrap;
}
</style>
