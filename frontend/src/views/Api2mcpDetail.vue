<template>
  <div class="api2mcp-detail">
    <!-- Step Navigation -->
    <div class="step-nav">
      <el-steps :active="currentStep" align-center finish-status="success">
        <el-step title="Basic Info" />
        <el-step title="Request" />
        <el-step title="Params" />
        <el-step title="Response" />
        <el-step title="Examples" />
        <el-step title="Preview" />
      </el-steps>
    </div>

    <!-- Step Content -->
    <div class="step-content">
      <!-- Step 1: Basic Info -->
      <div v-show="currentStep === 0" class="step-panel">
        <el-card>
          <template #header>
            <span>Basic Information</span>
          </template>
          <el-form :model="formData" label-width="120px">
            <el-form-item label="Tool Name" required>
            <el-input v-model="formData.tool_name" placeholder="English identifier, e.g. search_projects" />
            <div class="form-tip">Used as MCP tool name, only letters, numbers, and underscores allowed</div>
          </el-form-item>
          <el-form-item label="Version">
            <el-select v-model="formData.version" style="width: 150px">
              <el-option label="v1" value="v1" />
              <el-option label="v2" value="v2" />
              <el-option label="v3" value="v3" />
              <el-option label="v4" value="v4" />
              <el-option label="v5" value="v5" />
              <el-option label="v6" value="v6" />
              <el-option label="v7" value="v7" />
              <el-option label="v8" value="v8" />
              <el-option label="v9" value="v9" />
              <el-option label="v10" value="v10" />
            </el-select>
            <div class="form-tip">Tool version. Tool name + version must be unique</div>
          </el-form-item>
            <el-form-item label="Description">
              <el-input
                v-model="formData.tool_description"
                type="textarea"
                :rows="3"
                placeholder="LLM-facing description explaining tool purpose and usage"
              />
              <div class="form-tip">Clear descriptions help agents understand when to call this tool</div>
            </el-form-item>
            <el-form-item label="Category">
              <el-select v-model="formData.category" placeholder="Select category" style="width: 100%">
                <el-option label="Project Management" value="Project Management" />
                <el-option label="User Management" value="User Management" />
                <el-option label="Data Analysis" value="Data Analysis" />
                <el-option label="System Config" value="System Config" />
                <el-option label="Other" value="Other" />
              </el-select>
            </el-form-item>
            <el-form-item label="Tags">
              <el-select v-model="formData.tags" multiple placeholder="Select tags" style="width: 100%">
                <el-option label="High Value" value="high-value" />
                <el-option label="Frequent" value="frequent" />
                <el-option label="Internal" value="internal" />
                <el-option label="External" value="external" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>
      </div>

      <!-- Step 2: Request Definition -->
      <div v-show="currentStep === 1" class="step-panel">
        <el-card>
          <template #header>
            <span>Request Configuration</span>
          </template>
          <el-form :model="formData" label-width="120px">
            <el-form-item label="Method" required>
              <el-select v-model="formData.method" style="width: 100%">
                <el-option label="GET" value="GET" />
                <el-option label="POST" value="POST" />
                <el-option label="PUT" value="PUT" />
                <el-option label="PATCH" value="PATCH" />
                <el-option label="DELETE" value="DELETE" />
              </el-select>
            </el-form-item>
            <el-form-item label="Base URL" required>
              <el-input v-model="formData.base_url" placeholder="https://api.example.com" />
            </el-form-item>
            <el-form-item label="Path" required>
              <el-input v-model="formData.path" placeholder="/api/v1/projects/search" />
              <div class="form-tip">Supports path parameters, e.g. /api/v1/projects/{id}</div>
            </el-form-item>
            <el-form-item label="Content-Type">
              <el-select v-model="formData.content_type" style="width: 100%">
                <el-option label="application/json" value="application/json" />
                <el-option label="application/x-www-form-urlencoded" value="application/x-www-form-urlencoded" />
                <el-option label="multipart/form-data" value="multipart/form-data" />
              </el-select>
            </el-form-item>
            <el-form-item label="Auth Config">
              <el-select v-model="formData.auth_config_id" placeholder="Select auth config" style="width: 100%">
                <el-option label="No Auth" value="" />
                <el-option v-for="auth in store.authConfigs" :key="auth.id" :label="auth.name" :value="auth.id" />
              </el-select>
              <div class="form-tip">
                Supports env vars like <code v-text="'{{{{API_KEY}}}'"></code>, configure in environment variables
              </div>
            </el-form-item>
            <el-form-item label="Timeout">
              <el-input-number v-model="formData.timeout_ms" :min="1000" :max="120000" :step="1000" />
              <span style="margin-left: 8px">ms</span>
            </el-form-item>
            <el-form-item label="Cache TTL">
              <el-input-number v-model="formData.cache_ttl" :min="0" :max="3600" :step="60" />
              <span style="margin-left: 8px">seconds (0 = no cache)</span>
            </el-form-item>
          </el-form>
        </el-card>
      </div>

      <!-- Step 3: Parameter Definition -->
      <div v-show="currentStep === 2" class="step-panel">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Parameter Definition (supports nested structure)</span>
              <el-button size="small" @click="showParamDialog()">Add Parameter</el-button>
            </div>
          </template>
          <div v-if="parameters.length > 0" class="param-tree">
            <el-tree
              :data="parameters"
              :props="{ label: 'param_name', children: 'children' }"
              default-expand-all
            >
              <template #default="{ data }">
                <div class="param-node">
                  <span class="param-name">{{ data.param_name }}</span>
                  <el-tag size="small" type="info">{{ data.param_location }}</el-tag>
                  <el-tag size="small">{{ data.param_type }}</el-tag>
                  <el-tag v-if="data.required" size="small" type="danger">Required</el-tag>
                  <el-tag v-if="data.semantic_tag" size="small" type="warning">
                    {{ getSemanticLabel(data.semantic_tag) }}
                  </el-tag>
                  <div class="param-actions">
                    <el-button size="small" text @click="showParamDialog(data)">Edit</el-button>
                    <el-button size="small" text type="primary" @click="addChildParam(data)">Add Child</el-button>
                    <el-button size="small" text type="danger" @click="deleteParam(data)">Delete</el-button>
                  </div>
                </div>
              </template>
            </el-tree>
          </div>
          <div v-else class="empty-tip">
            No parameters defined. Click "Add Parameter" to start
          </div>
        </el-card>

        <!-- Parameter Edit Dialog -->
        <el-dialog v-model="paramDialogVisible" :title="editingParam ? 'Edit Parameter' : 'Add Parameter'" width="600px">
          <el-form :model="paramForm" label-width="100px">
            <el-form-item label="Name" required>
              <el-input v-model="paramForm.param_name" placeholder="e.g. keyword, budget_min" />
            </el-form-item>
            <el-form-item label="Location" required>
              <el-select v-model="paramForm.param_location" style="width: 100%">
                <el-option label="Query" value="query" />
                <el-option label="Path" value="path" />
                <el-option label="Body" value="body" />
                <el-option label="Header" value="header" />
              </el-select>
            </el-form-item>
            <el-form-item label="Type" required>
              <el-select v-model="paramForm.param_type" style="width: 100%">
                <el-option label="String" value="string" />
                <el-option label="Integer" value="integer" />
                <el-option label="Number" value="number" />
                <el-option label="Boolean" value="boolean" />
                <el-option label="Array" value="array" />
                <el-option label="Object" value="object" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="paramForm.param_type === 'array'" label="Item Type">
              <el-select v-model="paramForm.item_type" style="width: 100%">
                <el-option label="String" value="string" />
                <el-option label="Integer" value="integer" />
                <el-option label="Number" value="number" />
                <el-option label="Object" value="object" />
              </el-select>
            </el-form-item>
            <el-form-item label="Semantic Tag">
              <el-select v-model="paramForm.semantic_tag" placeholder="Select semantic tag (optional)" clearable style="width: 100%">
                <el-option v-for="tag in store.semanticTags" :key="tag.value" :label="tag.label" :value="tag.value" />
              </el-select>
              <div class="form-tip">Semantic tags help LLM understand parameter intent, e.g. "multi-field fuzzy match", "date range start"</div>
            </el-form-item>
            <el-form-item label="Description">
              <el-input v-model="paramForm.description" type="textarea" :rows="2" placeholder="Business meaning of parameter" />
            </el-form-item>
            <el-form-item label="Unit">
              <el-input v-model="paramForm.unit" placeholder="e.g. million, yuan, percent" />
            </el-form-item>
            <el-form-item label="Default">
              <el-input v-model="paramForm.default_value" placeholder="Default value" />
            </el-form-item>
            <el-form-item label="Example">
              <el-input v-model="paramForm.example_value" placeholder="Example value" />
            </el-form-item>
            <el-form-item label="Required">
              <el-switch v-model="paramForm.required" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="paramDialogVisible = false">Cancel</el-button>
            <el-button type="primary" @click="saveParam">Save</el-button>
          </template>
        </el-dialog>
      </div>

      <!-- Step 4: Response Mapping -->
      <div v-show="currentStep === 3" class="step-panel">
        <el-card>
          <template #header>
            <span>Response Field Mapping</span>
          </template>
          <el-form label-width="120px">
            <el-form-item label="Output Template">
              <el-input
                v-model="formData.output_template"
                type="textarea"
                :rows="4"
                placeholder="JMESPath expression, e.g. data.items[*].{name: name, id: id}"
              />
              <div class="form-tip">Used to extract and transform API response data</div>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card style="margin-top: 16px">
          <template #header>
            <div class="card-header">
              <span>Exposed Fields</span>
              <el-button size="small" @click="showFieldDialog()">Add Field</el-button>
            </div>
          </template>
          <div v-if="Object.keys(formData.output_fields).length > 0">
            <el-table :data="outputFieldsTable" size="small">
              <el-table-column prop="field" label="Field" />
              <el-table-column prop="type" label="Type" width="100">
                <template #default="{ row }">
                  <el-select v-model="row.type" size="small">
                    <el-option label="string" value="string" />
                    <el-option label="number" value="number" />
                    <el-option label="boolean" value="boolean" />
                    <el-option label="array" value="array" />
                    <el-option label="object" value="object" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="Description" />
              <el-table-column label="Actions" width="100">
                <template #default="{ row }">
                  <el-button size="small" text type="danger" @click="removeField(row.field)">Delete</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div v-else class="empty-tip">
            No exposed fields configured. Click "Add Field" to define response fields for agent
          </div>
        </el-card>

        <!-- Field Edit Dialog -->
        <el-dialog v-model="fieldDialogVisible" title="Add Response Field" width="500px">
          <el-form :model="fieldForm" label-width="100px">
            <el-form-item label="Field Name" required>
              <el-input v-model="fieldForm.field" placeholder="e.g. id, name, revenue" />
            </el-form-item>
            <el-form-item label="Type" required>
              <el-select v-model="fieldForm.type" style="width: 100%">
                <el-option label="String" value="string" />
                <el-option label="Number" value="number" />
                <el-option label="Boolean" value="boolean" />
                <el-option label="Array" value="array" />
                <el-option label="Object" value="object" />
              </el-select>
            </el-form-item>
            <el-form-item label="Description">
              <el-input v-model="fieldForm.description" type="textarea" :rows="2" placeholder="Business meaning, e.g. project revenue, unit: yuan" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="fieldDialogVisible = false">Cancel</el-button>
            <el-button type="primary" @click="addField">Add</el-button>
          </template>
        </el-dialog>
      </div>

      <!-- Step 5: Usage Example -->
      <div v-show="currentStep === 4" class="step-panel">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Usage Examples (Few-shot Injection)</span>
              <el-button size="small" @click="addExample()">Add Example</el-button>
            </div>
          </template>
          <div class="examples-tip">
            Adding 2-3 examples significantly improves LLM's first-call success rate
          </div>
          <div v-if="formData.usage_examples?.examples?.length > 0" class="examples-list">
            <div v-for="(example, idx) in formData.usage_examples.examples" :key="idx" class="example-item">
              <div class="example-header">
                <span>Example {{ (idx as number) + 1 }}</span>
                <el-button size="small" text type="danger" @click="removeExample(idx as number)">Delete</el-button>
              </div>
              <el-form label-width="100px">
                <el-form-item label="User Question">
                  <el-input v-model="example.question" placeholder="User's possible question" />
                </el-form-item>
                <el-form-item label="Call Parameters">
                  <el-input
                    v-model="example.paramsText"
                    type="textarea"
                    :rows="3"
                    placeholder='{"keyword": "artificial intelligence", "budget_min": 1000000}'
                    @blur="parseParams(example)"
                  />
                </el-form-item>
              </el-form>
            </div>
          </div>
          <div v-else class="empty-tip">
            No examples yet. Click "Add Example" to create
          </div>
        </el-card>
      </div>

      <!-- Step 6: Preview and Publish -->
      <div v-show="currentStep === 5" class="step-panel">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>MCP Tool Preview</span>
              <el-button size="small" type="primary" @click="refreshPreview">Refresh Preview</el-button>
            </div>
          </template>
          <div v-if="mcpPreview" class="mcp-preview">
            <div class="preview-section">
              <h4>Tool Name</h4>
              <code>{{ formData.tool_name }}@{{ formData.version }}</code>
            </div>
            <div class="preview-section">
              <h4>Description</h4>
              <div class="description-preview">{{ mcpPreview.description }}</div>
            </div>
            <div class="preview-section">
              <h4>Input Schema</h4>
              <pre class="json-preview">{{ JSON.stringify(mcpPreview.inputSchema, null, 2) }}</pre>
            </div>
            <div v-if="mcpPreview.outputSchema" class="preview-section">
              <h4>Output Schema</h4>
              <pre class="json-preview">{{ JSON.stringify(mcpPreview.outputSchema, null, 2) }}</pre>
            </div>
          </div>
          <div v-else class="empty-tip">
            Click "Refresh Preview" to view MCP definition
          </div>
        </el-card>

        <el-card style="margin-top: 16px">
          <template #header>
            <div class="card-header">
              <span>MCP Service Endpoints</span>
              <el-button size="small" @click="copyMcpUrl(mcpBaseUrl)">Copy Root Endpoint</el-button>
            </div>
          </template>

          <!-- Root Endpoint (shared by all protocols) -->
          <div class="mcp-urls">
            <div class="url-section url-section-primary">
              <div class="url-label">
                <span class="label-icon">🌐</span>
                <span>Root Endpoint (exposes all active tools)</span>
              </div>
              <div class="url-value">
                <code>{{ mcpBaseUrl }}</code>
                <el-button size="small" text @click="copyMcpUrl(mcpBaseUrl)">Copy</el-button>
              </div>
              <div class="url-desc">MCP clients connect to this address to discover and call all tools</div>
            </div>
          </div>

          <!-- Single Tool Isolated Endpoint -->
          <div class="url-section">
            <div class="url-label">
              <span class="label-icon"></span>
              <span>Single Tool Endpoint</span>
            </div>
            <div class="url-value">
              <code>{{ mcpToolUrl }}</code>
              <el-button size="small" text @click="copyMcpUrl(mcpToolUrl)">Copy</el-button>
            </div>
            <div class="url-desc">Exposes only current tool, format: /mcpapi/{tool_name}/{version}</div>
          </div>

          <!-- Transport Protocol Display -->
          <div class="transport-modes-section">
            <div class="section-label">Supported Transport Protocols</div>
            <div class="transport-tags">
              <el-tag
                v-for="mode in (formData.transport_modes || ['streamable_http'])"
                :key="mode"
                type="primary"
                size="large"
              >
                {{ mode === 'streamable_http' ? 'streamablehttp' : mode }}
              </el-tag>
            </div>
          </div>

          <div class="mcp-usage">
            <h4>Usage Instructions</h4>
            <ul>
              <li><strong>Root Endpoint</strong>: Use root endpoint <code>{{ mcpBaseUrl }}</code> to expose all active tools</li>
              <li><strong>Single Tool Endpoint</strong>: Use single tool endpoint <code>{{ mcpToolUrl }}</code> to expose only current tool</li>
              <li><strong>Supported Methods</strong>: <code>initialize</code>, <code>tools/list</code>, <code>tools/call</code>, <code>ping</code></li>
            </ul>
          </div>
        </el-card>

        <el-card style="margin-top: 16px">
          <template #header>
            <span>Publish Configuration</span>
          </template>
          <el-form label-width="120px">
            <el-form-item label="Status">
              <el-switch
                v-model="formData.status"
                active-value="active"
                inactive-value="inactive"
              />
              <span style="margin-left: 12px">{{ formData.status === 'active' ? 'Active' : 'Inactive' }}</span>
            </el-form-item>
          </el-form>
        </el-card>
      </div>
    </div>

    <!-- Bottom Action Bar -->
    <div class="bottom-actions">
      <el-button @click="$emit('close')">Cancel</el-button>
      <el-button v-if="currentStep > 0" @click="prevStep">Previous</el-button>
      <el-button v-if="currentStep < 5" type="primary" @click="nextStep">Next</el-button>
      <el-button v-if="currentStep === 5" type="primary" @click="saveProject(true)" :loading="saving">
        {{ isEdit ? 'Save Changes' : 'Create Tool' }}
      </el-button>
      <el-button v-if="currentStep === 5 && isEdit" type="success" @click="registerToMcp" :loading="registering">
        Register to MCP
      </el-button>
      <el-button 
        v-if="currentStep < 5" 
        type="primary" 
        @click="saveProject()" 
        :loading="saving"
      >
        Save
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAPIProjectStore, type Api2mcpParameter } from '@/stores/apiProject'

const props = defineProps<{
  editId: string | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const store = useAPIProjectStore()

// Use editId from props instead of route params
const isEdit = computed(() => !!props.editId)
const projectId = computed(() => props.editId)

const currentStep = ref(0)
const saving = ref(false)
const registering = ref(false)
const mcpPreview = ref<any>(null)
const parameters = ref<Api2mcpParameter[]>([])

// Parameter Dialog
const paramDialogVisible = ref(false)
const editingParam = ref<Api2mcpParameter | null>(null)
const editingParentId = ref<string | null>(null)
const paramForm = ref<any>({
  param_name: '',
  param_location: 'query',
  param_type: 'string',
  item_type: null,
  required: false,
  description: '',
  default_value: '',
  example_value: '',
  unit: '',
  semantic_tag: '',
})

// Field Dialog
const fieldDialogVisible = ref(false)
const fieldForm = ref({
  field: '',
  type: 'string',
  description: '',
})

// Form Data
const formData = ref<any>({
  tool_name: '',
  version: 'v1',
  tool_description: '',
  category: '',
  tags: [],
  method: 'GET',
  base_url: '',
  path: '/',
  content_type: 'application/json',
  auth_config_id: null,
  timeout_ms: 30000,
  cache_ttl: 0,
  output_fields: {},
  output_template: '',
  usage_examples: { examples: [] },
  status: 'active',
  transport_modes: ['streamable_http'],
})

const outputFieldsTable = computed(() => {
  return Object.entries(formData.value.output_fields).map(([field, config]: [string, any]) => ({
    field,
    type: config.type || 'string',
    description: config.description || '',
  }))
})

// MCP URL computed properties
const mcpBaseUrl = computed(() => {
  const base = import.meta.env.VITE_API_URL || window.location.origin
  return `${base}/mcpapi`
})

const mcpToolUrl = computed(() => {
  const base = import.meta.env.VITE_API_URL || window.location.origin
  const toolName = formData.value.tool_name || 'your_tool_name'
  const version = formData.value.version || 'v1'
  return `${base}/mcpapi/${toolName}/${version}`
})

// Copy URL to clipboard
const copyMcpUrl = async (url: string) => {
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('Copied to clipboard')
  } catch {
    ElMessage.error('Copy failed, please copy manually')
  }
}

const getSemanticLabel = (tag: string) => {
  const found = store.semanticTags.find(t => t.value === tag)
  return found ? found.label : tag
}

const showParamDialog = (param?: Api2mcpParameter) => {
  editingParam.value = param || null
  editingParentId.value = param?.parent_id || null
  if (param) {
    paramForm.value = { ...param }
  } else {
    paramForm.value = {
      param_name: '',
      param_location: 'query',
      param_type: 'string',
      item_type: null,
      required: false,
      description: '',
      default_value: '',
      example_value: '',
      unit: '',
      semantic_tag: '',
    }
  }
  paramDialogVisible.value = true
}

const addChildParam = (parent: Api2mcpParameter) => {
  editingParam.value = null
  editingParentId.value = parent.id
  paramForm.value = {
    param_name: '',
    param_location: parent.param_location,
    param_type: 'string',
    item_type: null,
    required: false,
    description: '',
    default_value: '',
    example_value: '',
    unit: '',
    semantic_tag: '',
  }
  paramDialogVisible.value = true
}

const saveParam = async () => {
  if (!formData.value.tool_name) {
    ElMessage.warning('Please fill in tool name first')
    return
  }

  // If creating new project, save first to get ID
  if (!isEdit.value && !projectId.value) {
    try {
      const newId = await store.createApi2mcpProject({
        ...formData.value,
        output_fields: {},
        usage_examples: {},
      })
      // Update project ID (via internal variable not route)
      ;(formData.value as any).id = newId
      formData.value = { ...formData.value, id: newId }
      ElMessage.success('Project saved, please continue adding parameters')
    } catch (error) {
      ElMessage.error('Failed to save project, please try again later')
      return
    }
  }

  const data = {
    ...paramForm.value,
    parent_id: editingParentId.value,
  }

  const currentProjectId = projectId.value || (formData.value as any).id
  if (!currentProjectId) {
    ElMessage.error('Project ID does not exist')
    return
  }

  if (editingParam.value) {
    await store.updateApi2mcpParameter(currentProjectId, editingParam.value.id, data)
  } else {
    await store.createApi2mcpParameter(currentProjectId, data)
  }

  paramDialogVisible.value = false
  await loadParameters(currentProjectId)
}

const deleteParam = async (param: Api2mcpParameter) => {
  const currentProjectId = projectId.value || (formData.value as any).id
  if (!currentProjectId) return
  await store.deleteApi2mcpParameter(currentProjectId, param.id)
  await loadParameters(currentProjectId)
}

const loadParameters = async (currentProjectId: string) => {
  const params = await store.loadApi2mcpParameters(currentProjectId)
  parameters.value = params || []
}

const showFieldDialog = () => {
  fieldForm.value = { field: '', type: 'string', description: '' }
  fieldDialogVisible.value = true
}

const addField = () => {
  if (!fieldForm.value.field) {
    ElMessage.warning('Please fill in field name')
    return
  }
  formData.value.output_fields[fieldForm.value.field] = {
    type: fieldForm.value.type,
    description: fieldForm.value.description,
  }
  fieldDialogVisible.value = false
}

const removeField = (field: string) => {
  delete formData.value.output_fields[field]
}

const addExample = () => {
  if (!formData.value.usage_examples.examples) {
    formData.value.usage_examples.examples = []
  }
  formData.value.usage_examples.examples.push({
    question: '',
    params: {},
    paramsText: '',
  })
}

const removeExample = (index: number) => {
  formData.value.usage_examples.examples.splice(index, 1)
}

const parseParams = (example: any) => {
  try {
    example.params = JSON.parse(example.paramsText || '{}')
  } catch {
    example.params = {}
  }
}

const refreshPreview = async () => {
  const currentProjectId = projectId.value || (formData.value as any).id
  if (!currentProjectId) return
  mcpPreview.value = await store.getMcpDefinition(currentProjectId)
}

const registerToMcp = async () => {
  const currentProjectId = projectId.value || (formData.value as any).id
  if (!currentProjectId) {
    ElMessage.error('Project ID does not exist')
    return
  }
  registering.value = true
  try {
    await store.registerToMcp(currentProjectId)
    ElMessage.success('Registered to MCP successfully')
  } catch (e: any) {
    ElMessage.error(e.message || 'Registration failed')
  } finally {
    registering.value = false
  }
}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

const nextStep = async () => {
  if (currentStep.value >= 5) return
  
  // If creating new project without ID, save first
  if (!isEdit.value && !projectId.value && !(formData.value as any).id) {
    if (!formData.value.tool_name) {
      ElMessage.warning('Please fill in tool name first')
      return
    }
    
    try {
      const newId = await store.createApi2mcpProject({
        ...formData.value,
        output_fields: {},
        usage_examples: {},
      })
      // Update project ID (via internal variable)
      formData.value = { ...formData.value, id: newId }
      ElMessage.success('Project saved')
    } catch (error) {
      ElMessage.error('Failed to save project, please try again later')
      return
    }
  }
  
  // If editing mode, save current step data
  const currentProjectId = projectId.value || (formData.value as any).id
  if (currentProjectId) {
    try {
      await store.updateApi2mcpProject(currentProjectId, formData.value)
    } catch (error) {
      console.error('Failed to save step data:', error)
    }
  }
  
  currentStep.value++
}

const saveProject = async (closeAfterSave: boolean = false) => {
  if (!formData.value.tool_name) {
    ElMessage.warning('Please fill in tool name')
    return
  }
  if (!formData.value.base_url) {
    ElMessage.warning('Please fill in Base URL')
    return
  }

  saving.value = true
  try {
    const currentProjectId = projectId.value || (formData.value as any).id
    if (isEdit.value && currentProjectId) {
      await store.updateApi2mcpProject(currentProjectId, formData.value)
      ElMessage.success('Saved successfully')
    } else {
      await store.createApi2mcpProject(formData.value)
      ElMessage.success('Created successfully')
    }
    if (closeAfterSave) {
      emit('saved')
    }
  } catch (e: any) {
    ElMessage.error(e.message || 'Operation failed')
  } finally {
    saving.value = false
  }
}

const loadData = async () => {
  await Promise.all([
    store.loadSemanticTags(),
    store.loadAuthConfigs(),
  ])

  if (isEdit.value && projectId.value) {
    const project = await store.loadApi2mcpProject(projectId.value)
    if (project) {
      formData.value = { ...project }
      await loadParameters(projectId.value)
      await refreshPreview()
    }
  }
}

const resetForm = () => {
  currentStep.value = 0
  mcpPreview.value = null
  parameters.value = []
  formData.value = {
    tool_name: '',
    version: 'v1',
    tool_description: '',
    category: '',
    tags: [],
    method: 'GET',
    base_url: '',
    path: '/',
    content_type: 'application/json',
    auth_config_id: null,
    timeout_ms: 30000,
    cache_ttl: 0,
    output_fields: {},
    output_template: '',
    usage_examples: { examples: [] },
    status: 'active',
    transport_modes: ['streamable_http'],
  }
}

// Watch editId change and reload data
watch(() => props.editId, () => {
  resetForm()
  if (props.editId) {
    loadData()
  }
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.api2mcp-detail {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
}
.step-nav {
  margin-bottom: 24px;
}
.step-content {
  min-height: 500px;
}
.step-panel {
  animation: fadeIn 0.3s;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.param-tree {
  max-height: 400px;
  overflow-y: auto;
}
.param-node {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.param-name {
  font-weight: 600;
  min-width: 100px;
}
.param-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.empty-tip {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}
.examples-tip {
  background: #f0f9ff;
  border: 1px solid #b3d8fd;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 16px;
  color: #0066cc;
  font-size: 13px;
}
.examples-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.example-item {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
}
.example-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.mcp-preview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.preview-section h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #606266;
}
.preview-section code {
  background: #f5f7fa;
  padding: 4px 8px;
  border-radius: 4px;
}
.description-preview {
  background: #f9f9f9;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}
.json-preview {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  max-height: 300px;
  overflow-y: auto;
}
.bottom-actions {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* MCP URL Styles */
.mcp-urls {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.url-section {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px 16px;
}

.url-section-primary {
  background: #f0f9eb;
  border-color: #67c23a;
}

.url-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.label-icon {
  font-size: 16px;
}

.url-value {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.url-value code {
  flex: 1;
  background: #f5f7fa;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
  word-break: break-all;
  font-family: 'Monaco', 'Menlo', monospace;
}

.url-desc {
  font-size: 12px;
  color: #909399;
  padding-left: 24px;
}

.transport-modes-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.transport-tags {
  display: flex;
  gap: 8px;
}

.mcp-usage {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #d9d9d9;
}

.mcp-usage h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #303133;
}

.mcp-usage ul {
  margin: 0;
  padding-left: 20px;
}

.mcp-usage li {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  line-height: 1.6;
}

.mcp-usage li:last-child {
  margin-bottom: 0;
}

.mcp-usage code {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
</style>