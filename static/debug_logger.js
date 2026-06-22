/**
 * TLD 前端调试日志工具
 * 
 * 在关键点记录日志并批量提交到后端
 * 使用方式:
 *   debugLogger.info("搜索单词", { word: "hello" })
 *   debugLogger.warn("点击无反应", { element: "pattern-word" })
 *   debugLogger.error("htmx 请求失败", { url: "/api/lookup", error: "..." })
 */

const debugLogger = (function() {
    const LOG_BUFFER = [];
    const BUFFER_INTERVAL = 5000; // 每5秒批量提交一次
    const MAX_BUFFER_SIZE = 50; // 缓冲区最大日志数
    let timer = null;
    
    // 是否启用日志（可通过控制台 debugLogger.setEnabled(false) 关闭）
    let enabled = true;
    
    /**
     * 添加一条日志
     */
    function addLog(level, message, meta = {}) {
        if (!enabled) return;
        
        const entry = {
            timestamp: new Date().toISOString(),
            level: level,
            message: message,
            url: window.location.href,
            meta: meta
        };
        
        // 同时输出到浏览器控制台
        const consoleMsg = `[${level.toUpperCase()}] ${message}` + 
                          (Object.keys(meta).length ? ' ' + JSON.stringify(meta) : '');
        if (level === 'error') {
            console.error(consoleMsg);
        } else if (level === 'warn') {
            console.warn(consoleMsg);
        } else {
            console.log(consoleMsg);
        }
        
        // 加入缓冲区
        LOG_BUFFER.push(entry);
        
        // 超过缓冲区大小时立即提交
        if (LOG_BUFFER.length >= MAX_BUFFER_SIZE) {
            flushLogs();
        }
        
        // 确保定时器启动
        ensureTimer();
    }
    
    /**
     * 确保批量提交定时器运行
     */
    function ensureTimer() {
        if (timer) return;
        timer = setInterval(flushLogs, BUFFER_INTERVAL);
    }
    
    /**
     * 批量提交日志到后端
     */
    function flushLogs() {
        if (LOG_BUFFER.length === 0) {
            clearInterval(timer);
            timer = null;
            return;
        }
        
        const entries = LOG_BUFFER.splice(0, LOG_BUFFER.length);
        
        fetch('/api/debug/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(entries)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok') {
                console.log(`[DEBUG] 已提交 ${data.received} 条日志到服务器`);
            }
        })
        .catch(error => {
            console.warn('[DEBUG] 日志提交失败:', error);
            // 提交失败的数据重新加入缓冲区
            LOG_BUFFER.unshift(...entries);
        });
    }
    
    /**
     * 公开 API
     */
    return {
        info: function(message, meta) { addLog('info', message, meta); },
        warn: function(message, meta) { addLog('warn', message, meta); },
        error: function(message, meta) { addLog('error', message, meta); },
        
        /**
         * 手动提交所有缓冲的日志
         */
        flush: flushLogs,
        
        /**
         * 获取当前缓冲区内容
         */
        getBuffer: function() { return [...LOG_BUFFER]; },
        
        /**
         * 启用/禁用日志
         */
        setEnabled: function(state) { enabled = state; },
        isEnabled: function() { return enabled; }
    };
})();

// 将 debugLogger 挂载到 window 对象，方便控制台调用
window.debugLogger = debugLogger;

// ==================== 自动监听 htmx 事件 ====================
// 注意：这段代码必须在 DOM 准备好后执行（document.body 存在）
(function() {
    function registerEventListeners() {
        // 如果 body 还不存在，等待后再试
        if (!document.body) {
            setTimeout(registerEventListeners, 50);
            return;
        }
        
        // htmx 请求开始前
        document.body.addEventListener('htmx:beforeRequest', function(evt) {
            debugLogger.info('htmx 请求开始', {
                url: evt.detail.requestConfig.url,
                target: evt.detail.elt.id
            });
        });
        
        // htmx 请求成功后
        document.body.addEventListener('htmx:afterRequest', function(evt) {
            debugLogger.info('htmx 请求完成', {
                url: evt.detail.requestConfig.url,
                status: evt.detail.xhr.status,
                target: evt.detail.elt.id
            });
        });
        
        // htmx 请求失败
        document.body.addEventListener('htmx:sendFailed', function(evt) {
            debugLogger.error('htmx 请求失败', {
                url: evt.detail.requestConfig?.url || 'unknown',
                reason: evt.detail.reason || 'network error'
            });
        });
        
        // htmx 验证失败
        document.body.addEventListener('htmx:validation:failed', function(evt) {
            debugLogger.warn('htmx 验证失败', {
                element: evt.detail.elt.textContent?.substring(0, 50) || 'unknown'
            });
        });
        
        // htmx 目标错误（这就是你遇到的那个错误！）
        document.body.addEventListener('htmx:targetError', function(evt) {
            debugLogger.error('htmx 目标错误', {
                reason: evt.detail.reason || 'target not found',
                target: evt.detail.target?.id || 'unknown'
            });
        });
        
        // htmx 历史推送后
        document.body.addEventListener('htmx:pushedIntoHistory', function(evt) {
            debugLogger.info('URL 已推送到历史', {
                url: evt.detail.newUrl || window.location.href
            });
        });
        
        // 监听 popstate 事件（浏览器前进后退）
        window.addEventListener('popstate', function() {
            debugLogger.info('popstate 事件触发', {
                url: window.location.href
            });
        });
        
        debugLogger.info('HTMX 事件监听器已注册');
    }
    
    // 延迟注册，等待 DOM 准备
    setTimeout(registerEventListeners, 0);
})();