<template>
  <div class="api2mcp-page">
    <div class="header-bar">
      <h2>API2MCP Tool Management</h2>
      <div class="header-actions">
        <el-input
          v-model="searchQuery"
          placeholder="Search tools"
          style="width: 220px; margin-right: 10px"
          clearable
        />
        <el-button type="primary" @click="showCreateDialog()">
          <el-icon><Plus /></el-icon>
          New Tool
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
        <el-table-column prop="tool_name" label="Tool Name" width="180">
          <template #default="{ row }">
            <div class="tool-name-cell">
              <el-icon><Setting /></el-icon>
              <span>{{ row.tool_name }}</span>
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
            <code class="url-code">{{ row.base_url + row.path }}</code>
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
                  <code class="url-value">{{ currentProject.base_url + currentProject.path }}</code>
                </div>
              </div>

              <div class="config-card">
                <div class="config-card-header">
                  <el-icon class="config-icon"><Monitor /></el-icon>
                  <h4>MCP Tool Info</h4>
                </div>
                <div class="config-item">
                  <span class="label">Tool Name</span>
                  <code class="url-value">{{ currentProject.tool_name }}@{{ currentProject.version || 'v1' }}</code>
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
import { Plus, Setting, Delete, View, Files, InfoFilled, Monitor, More, Document } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAPIToolStore } from '@/stores/apiProject'
import Api2mcpDetail from './Api2mcpDetail.vue'

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
      t.tool_name.toLowerCase().includes(q) ||
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
  const toolName = currentProject.value.tool_name
  const version = currentProject.value.version || 'v1'
  return JSON.stringify({
    name: `${toolName}@${version}`,
    type: "streamableHttp",
    description: currentProject.value.tool_description || "",
    baseUrl: mcpBaseUrl.value,
  }, null, 2)
})

/**
 * Get tool's MCP endpoint URL
 * Format: http://ip:port/mcpapi/{tool_name}/{version}
 */
const getMcpToolUrl = (row: any): string => {
  const base = mcpBaseUrl.value
  const toolName = row.tool_name
  const version = row.version || 'v1'
  return `${base}/${toolName}/${version}`
}

const showCreateDialog = () => {
  editingId.value = null
  showDetailDialog.value = true
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
    await ElMessageBox.confirm(`Are you sure you want to delete tool "${row.tool_name}"?`, 'Confirm Delete', { type: 'warning' })
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
    ElMessage.success(`Tool "${row.tool_name}" has been ${newStatus === 'active' ? 'activated' : 'deactivated'}`)
  } catch (e: any) {
    ElMessage.error(e.message || 'Operation failed')
  }
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
</style>
