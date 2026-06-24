<template>
  <div class="server-status-page">
    <div class="header-bar">
      <h2>MCP Server Status</h2>
      <el-button type="primary" @click="refreshStatus">
        <el-icon><Refresh /></el-icon>
        Refresh
      </el-button>
    </div>

    <!-- 服务实例概览 -->
    <el-card class="status-card">
      <template #header>
        <div class="card-header">
          <span>Service Instances</span>
          <el-tag :type="isHealthy ? 'success' : 'danger'" size="large">
            {{ isHealthy ? 'Healthy' : 'Degraded' }}
          </el-tag>
        </div>
      </template>

      <div v-if="store.serverStatus" class="servers-grid">
        <div v-for="server in store.serverStatus.servers" :key="server.server_id" class="server-item">
          <div class="server-header">
            <el-icon class="server-icon"><Monitor /></el-icon>
            <span class="server-name">{{ server.name }}</span>
            <el-tag :type="server.status === 'running' ? 'success' : 'danger'" size="small">
              {{ server.status }}
            </el-tag>
          </div>

          <div class="server-stats">
            <div class="stat-item">
              <span class="stat-label">Total Requests</span>
              <span class="stat-value">{{ server.total_requests }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Successful</span>
              <span class="stat-value success">{{ server.successful_requests }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Failed</span>
              <span class="stat-value danger">{{ server.failed_requests }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Avg Latency</span>
              <span class="stat-value">{{ server.avg_latency_ms.toFixed(2) }} ms</span>
            </div>
          </div>

          <div class="server-footer">
            <span class="heartbeat-time">Last heartbeat: {{ formatTime(server.last_heartbeat) }}</span>
          </div>
        </div>
      </div>

      <div v-else class="empty-tip">
        No server status data available
      </div>
    </el-card>

    <!-- 工具调用统计 -->
    <el-card class="stats-card">
      <template #header>
        <div class="card-header">
          <span>Tool Call Statistics</span>
          <el-select v-model="selectedTool" placeholder="Select tool" style="width: 200px" @change="loadToolStats">
            <el-option v-for="tool in store.api2mcpTools" :key="tool.id" :label="tool.mcp_name" :value="tool.mcp_name" />
          </el-select>
        </div>
      </template>

      <div v-if="currentStats" class="stats-content">
        <div class="stats-overview">
          <div class="overview-item">
            <div class="overview-value">{{ currentStats.total_calls }}</div>
            <div class="overview-label">Total Calls</div>
          </div>
          <div class="overview-item">
            <div class="overview-value success">{{ currentStats.success_calls }}</div>
            <div class="overview-label">Successful</div>
          </div>
          <div class="overview-item">
            <div class="overview-value danger">{{ currentStats.failed_calls }}</div>
            <div class="overview-label">Failed</div>
          </div>
          <div class="overview-item">
            <div class="overview-value">{{ currentStats.avg_latency_ms.toFixed(2) }} ms</div>
            <div class="overview-label">Avg Latency</div>
          </div>
          <div class="overview-item">
            <div class="overview-value">{{ currentStats.success_rate.toFixed(1) }}%</div>
            <div class="overview-label">Success Rate</div>
          </div>
        </div>

        <!-- 历史统计图表 -->
        <div v-if="statsHistory" class="stats-history">
          <h4>Hourly Statistics (Last 24 Hours)</h4>
          <el-table :data="statsHistory.history" size="small" border>
            <el-table-column prop="hour" label="Hour" width="120" />
            <el-table-column prop="total_calls" label="Total" width="80" />
            <el-table-column prop="success_calls" label="Success" width="80">
              <template #default="{ row }">
                <span class="success-text">{{ row.success_calls }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="failed_calls" label="Failed" width="80">
              <template #default="{ row }">
                <span class="danger-text">{{ row.failed_calls }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="avg_latency_ms" label="Avg Latency">
              <template #default="{ row }">
                {{ row.avg_latency_ms.toFixed(2) }} ms
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div v-else class="empty-tip">
        Select a tool to view statistics
      </div>
    </el-card>

    <!-- 最近请求列表 -->
    <el-card class="requests-card">
      <template #header>
        <div class="card-header">
          <span>Recent Requests</span>
          <el-button size="small" @click="loadRequests">Load More</el-button>
        </div>
      </template>

      <div v-if="store.recentRequests.length > 0" class="requests-list">
        <el-table :data="store.recentRequests" size="small" border>
          <el-table-column prop="request_id" label="Request ID" width="200">
            <template #default="{ row }">
              <el-button size="small" text @click="showRequestDetail(row.request_id)">
                {{ row.request_id }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="mcp_name" label="Tool" width="150" />
          <el-table-column prop="tool_version" label="Version" width="80" />
          <el-table-column prop="status" label="Status" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="latency_ms" label="Latency" width="100">
            <template #default="{ row }">
              {{ row.latency_ms ? `${row.latency_ms} ms` : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="Created" width="180">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="error_message" label="Error">
            <template #default="{ row }">
              <span v-if="row.error_message" class="error-text">{{ row.error_message }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-else class="empty-tip">
        No recent requests data
      </div>
    </el-card>

    <!-- 请求详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="Request Details" width="600px">
      <div v-if="requestDetail" class="request-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Request ID">{{ requestDetail.request_id }}</el-descriptions-item>
          <el-descriptions-item label="Status">
            <el-tag :type="getStatusType(requestDetail.status)">{{ requestDetail.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Tool">{{ requestDetail.mcp_name }}</el-descriptions-item>
          <el-descriptions-item label="Version">{{ requestDetail.tool_version }}</el-descriptions-item>
          <el-descriptions-item label="Created">{{ formatTime(requestDetail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="Completed">{{ requestDetail.completed_at ? formatTime(requestDetail.completed_at) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="Latency">{{ requestDetail.latency_ms ? `${requestDetail.latency_ms} ms` : '-' }}</el-descriptions-item>
          <el-descriptions-item label="Error">{{ requestDetail.error_message || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="requestDetail.input_params" class="detail-section">
          <h4>Input Parameters</h4>
          <pre class="json-preview">{{ JSON.stringify(requestDetail.input_params, null, 2) }}</pre>
        </div>

        <div v-if="requestDetail.output_result" class="detail-section">
          <h4>Output Result</h4>
          <pre class="json-preview">{{ JSON.stringify(requestDetail.output_result, null, 2) }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, Monitor } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAPIToolStore } from '@/stores/apiProject'

const store = useAPIToolStore()

const selectedTool = ref('')
const currentStats = ref<any>(null)
const statsHistory = ref<any>(null)
const showDetailDialog = ref(false)
const requestDetail = ref<any>(null)

const isHealthy = computed(() => {
  if (!store.serverStatus?.servers) return false
  return store.serverStatus.servers.every(s => s.status === 'running')
})

const getStatusType = (status: string) => {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'processing': return 'warning'
    default: return 'info'
  }
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString()
}

const refreshStatus = async () => {
  await store.loadServerStatus()
  ElMessage.success('Status refreshed')
}

const loadToolStats = async () => {
  if (!selectedTool.value) return
  currentStats.value = await store.loadToolStats(selectedTool.value, 'v1')
  statsHistory.value = await store.loadToolStatsHistory(selectedTool.value, 'v1', 24)
}

const loadRequests = async () => {
  if (!selectedTool.value) {
    ElMessage.warning('Please select a tool first')
    return
  }
  await store.loadRecentRequests(selectedTool.value, 'v1', 100)
}

const showRequestDetail = async (requestId: string) => {
  requestDetail.value = await store.loadRequestStatus(requestId)
  if (requestDetail.value) {
    showDetailDialog.value = true
  }
}

onMounted(async () => {
  await store.loadApi2mcpTools()
  await store.loadServerStatus()
})
</script>

<style scoped>
.server-status-page {
  padding: 20px;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-bar h2 {
  margin: 0;
}

.status-card, .stats-card, .requests-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.servers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.server-item {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}

.server-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.server-icon {
  color: #409eff;
  font-size: 20px;
}

.server-name {
  font-weight: 600;
  flex: 1;
}

.server-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
}

.stat-label {
  color: #606266;
  font-size: 12px;
}

.stat-value {
  font-weight: 600;
  font-size: 14px;
}

.stat-value.success {
  color: #67c23a;
}

.stat-value.danger {
  color: #f56c6c;
}

.server-footer {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid #e9ecef;
}

.heartbeat-time {
  color: #909399;
  font-size: 12px;
}

.stats-overview {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.overview-item {
  text-align: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.overview-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.overview-value.success {
  color: #67c23a;
}

.overview-value.danger {
  color: #f56c6c;
}

.overview-label {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}

.stats-history {
  margin-top: 20px;
}

.stats-history h4 {
  margin-bottom: 12px;
}

.success-text {
  color: #67c23a;
}

.danger-text {
  color: #f56c6c;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}

.empty-tip {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}

.request-detail {
  max-height: 600px;
  overflow-y: auto;
}

.detail-section {
  margin-top: 16px;
}

.detail-section h4 {
  margin-bottom: 8px;
}

.json-preview {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
}
</style>