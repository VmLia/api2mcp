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
    
    // 构建优化
    build: {
      // 目标浏览器
      target: 'es2015',
      // 启用 CSS 代码分割
      cssCodeSplit: true,
      // 启用资源内联（小于 4KB 的资源内联）
      assetsInlineLimit: 4096,
      // 启用 rollup 分块
      rollupOptions: {
        output: {
          // 手动分包策略
          manualChunks: {
            // Vue 核心
            'vue-vendor': ['vue', 'vue-router', 'pinia'],
            // Element Plus
            'element-plus': ['element-plus'],
          }
        }
      },
      // 启用 sourcemap（生产环境可关闭）
      sourcemap: mode === 'development',
      // 启用 CSS minify
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: mode === 'production',
          drop_debugger: mode === 'production'
        }
      }
    },
    
    // 开发服务器配置
    server: {
      port: frontendPort,
      // 启用热模块替换
      hmr: {
        overlay: true
      },
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
        // Prometheus 指标代理
        '/metrics': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true
        },
        // 系统状态代理
        '/server': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true
        },
      },
      // 支持 Vue Router history 模式
      historyApiFallback: {
        index: '/frontrouter'
      }
    },
    
    // 依赖优化
    optimizeDeps: {
      include: [
        'vue',
        'vue-router',
        'pinia',
        'element-plus',
        '@element-plus/icons-vue'
      ]
    },
    
    // CSS 配置
    css: {
      // 启用 CSS source map
      sourceMap: mode === 'development',
      // CSS 预处理器配置
      preprocessorOptions: {}
    }
  }
})