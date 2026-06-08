import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd() + '/..', '')
  
  // 从环境变量获取端口配置，如果没有则使用默认值
  const frontendPort = parseInt(env.API2MCP_PORT_FRONTEND || '34075')
  const backendPort = parseInt(env.API2MCP_PORT_BACKEND || '34085')
  
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      port: frontendPort,
      proxy: {
        // 服务端 API 代理
        '/serverapi': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true
        },
        // MCP 服务代理
        '/mcpapi': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true
        },
      },
      // 支持 Vue Router history 模式
      historyApiFallback: {
        index: '/frontrouter'
      }
    }
  }
})
