/**
 * WebSocket 服务用于实时转录
 */
export class TranscriptionWebSocket {
  constructor(config, callbacks) {
    this.config = config
    this.callbacks = callbacks
    this.ws = null
    this.mediaRecorder = null
    this.audioStream = null
    this.isPaused = false
    this._flushTimer = null
  }

  /**
   * 连接到服务器 WebSocket
   */
  async connect() {
    return new Promise((resolve, reject) => {
      // 构造当前站点的 WS 地址（HTTPS -> WSS，HTTP -> WS）
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      let wsUrl = `${wsProtocol}://${window.location.host}/ws/transcribe`
      // 防呆：若外层代理或历史代码导致出现 "wsss"，在此强制修正
      if (wsUrl.startsWith('wsss://')) {
        wsUrl = 'wss://' + wsUrl.slice('wsss://'.length)
      }

      this.ws = new WebSocket(wsUrl)
      try { this.ws.binaryType = 'arraybuffer' } catch (_) {}

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        // 发送配置
        const cfg = {
          ...this.config,
          api_key: (this.config.api_key || '').trim().replace(/\s+/g, '')
        }
        this.ws.send(JSON.stringify({ config: cfg }))
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.type === 'connected') {
            console.log('Transcription session ready:', data.session_id)
            this.callbacks.onConnected?.(data)
            resolve(data)
          } else if (data.type === 'error') {
            const msg = `${data.error_code ?? ''} ${data.error_message ?? ''}`.trim() || '后端报错'
            this.callbacks.onError?.(new Error(msg))
          } else if (data.type === 'transcription') {
            this.callbacks.onTranscription?.(data)
          } else if (data.type === 'session_completed') {
            this.callbacks.onSessionCompleted?.(data)
          } else if (data.error) {
            console.error('Server error:', data.error)
            this.callbacks.onError?.(data.error)
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      this.ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        const err = new Error('WebSocket 连接失败，请检查后端是否运行以及网络/代理设置')
        this.callbacks.onError?.(err)
        reject(err)
      }

      this.ws.onclose = (e) => {
        console.log('WebSocket closed', e?.code, e?.reason)
        this.callbacks.onDisconnected?.()
      }
    })
  }

  /**
   * 开始录音并流式发送音频
   */
  async startRecording() {
    try {
      // 若已有音频流（例如从暂停恢复），则复用；否则请求权限
      if (!this.audioStream) {
        this.audioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true,
          },
        })
      } else {
        // 重新启用被暂停的轨道
        this.audioStream.getTracks().forEach((t) => (t.enabled = true))
      }

      // 创建 MediaRecorder（带 MIME 类型回退，以兼容不同浏览器；iOS 优先 mp4）
      const mimeType = this.getSupportedMimeType()
      try {
        const options = mimeType
          ? { mimeType: mimeType, audioBitsPerSecond: 128000 }
          : { audioBitsPerSecond: 128000 }
        this.mediaRecorder = new MediaRecorder(this.audioStream, options)
      } catch (e) {
        // 再次回退：不带任何 options
        try {
          this.mediaRecorder = new MediaRecorder(this.audioStream)
        } catch (e2) {
          this.callbacks.onError?.(e2)
          return false
        }
      }

      // 当有音频数据可用时，发送到服务器
      this.mediaRecorder.ondataavailable = async (event) => {
        try {
          if (event.data && event.data.size > 0 && this.ws?.readyState === WebSocket.OPEN) {
            // 移动端兼容：统一转 ArrayBuffer 再发送
            const buf = await event.data.arrayBuffer()
            this.ws.send(buf)
            this._lastChunkAt = Date.now()
          }
        } catch (e) {
          console.error('Send audio chunk failed:', e)
          this.callbacks.onError?.(e)
        }
      }

      // 开始录音（每 100ms 发送一次数据）
      this.mediaRecorder.start(100)

      console.log('Recording started')
      this.isPaused = false
      // Safari 兼容：某些移动端忽略 timeslice，只有在 requestData 或 stop 时才触发 dataavailable
      try {
        if (typeof this.mediaRecorder.requestData === 'function') {
          clearInterval(this._flushTimer)
          this._flushTimer = setInterval(() => {
            if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
              this.mediaRecorder.requestData()
            }
          }, 250)
        }
      } catch (_) {}
      // Watchdog：若 2s 内无任何音频块，自动切至 PCM 回退
      this._lastChunkAt = Date.now()
      clearTimeout(this._fallbackTimer)
      this._fallbackTimer = setTimeout(() => {
        const idle = Date.now() - (this._lastChunkAt || 0)
        if (idle >= 1800) {
          console.warn('No audio chunks detected, switching to PCM fallback...')
          this.switchToPcmFallback().catch((e) => console.error(e))
        }
      }, 2000)
      return true
    } catch (error) {
      console.error('Error starting recording:', error)
      this.callbacks.onError?.(error)
      return false
    }
  }

  /**
   * 停止录音
   */
  stopRecording() {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop()
    }
    if (this._flushTimer) {
      clearInterval(this._flushTimer)
      this._flushTimer = null
    }

    if (this.audioStream) {
      this.audioStream.getTracks().forEach((track) => track.stop())
      this.audioStream = null
    }

    // 发送停止命令
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ command: 'stop' }))
    }

    console.log('Recording stopped')
  }

  /**
   * 暂停录音（保持会话与音频流，停止送帧）
   */
  pause() {
    try {
      if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
        this.mediaRecorder.stop()
      }
      if (this._flushTimer) {
        clearInterval(this._flushTimer)
        this._flushTimer = null
      }
      // 关闭数据上送但保留轨道用于恢复
      if (this.audioStream) {
        this.audioStream.getTracks().forEach((t) => (t.enabled = false))
      }
      this.isPaused = true
      console.log('Recording paused')
    } catch (e) {
      console.error('Pause failed', e)
    }
  }

  /**
   * 恢复录音（复用音频流，重新创建 MediaRecorder）
   */
  async resume() {
    if (this.isPaused) {
      return await this.startRecording()
    }
    return false
  }

  /**
   * 强制完成当前转录
   */
  finalize() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ command: 'finalize' }))
    }
  }

  /**
   * 关闭连接
   */
  close() {
    this.stopRecording()

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * 获取支持的音频 MIME 类型
   */
  getSupportedMimeType() {
    // iOS Safari 优先支持 mp4，其次 webm/ogg
    const ua = navigator.userAgent || ''
    const prefersMp4 = /iPhone|iPad|iPod|Safari/i.test(ua)
    const types = prefersMp4
      ? ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
      : ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']

    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        console.log('Using MIME type:', type)
        return type
      }
    }

    return ''
  }

  /**
   * PCM 回退（WebAudio -> 16k 单声道 s16le）
   */
  async switchToPcmFallback() {
    try {
      // 停止 MediaRecorder 路径
      if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
        this.mediaRecorder.stop()
      }
      if (this._flushTimer) {
        clearInterval(this._flushTimer)
        this._flushTimer = null
      }
      // 确保音频流存在（若不存在则重新申请）
      if (!this.audioStream) {
        this.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      }
      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 44100 })
      const source = ctx.createMediaStreamSource(this.audioStream)
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      source.connect(processor)
      processor.connect(ctx.destination)

      // 请求后端切换 Soniox 配置为 PCM 格式
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({
          command: 'set_format',
          audio_format: 'pcm_s16le',
          sample_rate: 16000,
          num_channels: 1
        }))
      }

      const targetRate = 16000
      const convertAndSend = (inputBuffer) => {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
        const input = inputBuffer.getChannelData(0) // Float32
        const srcRate = ctx.sampleRate
        // 线性重采样到 16k
        const ratio = srcRate / targetRate
        const outLength = Math.floor(input.length / ratio)
        const out = new Int16Array(outLength)
        for (let i = 0; i < outLength; i++) {
          const s = input[Math.floor(i * ratio)] || 0
          const v = Math.max(-1, Math.min(1, s))
          out[i] = v < 0 ? v * 0x8000 : v * 0x7FFF
        }
        this.ws.send(out.buffer)
      }

      processor.onaudioprocess = (e) => convertAndSend(e.inputBuffer)

      console.log('Switched to PCM fallback streaming (s16le/16k mono)')
    } catch (e) {
      console.error('PCM fallback failed:', e)
      this.callbacks.onError?.(e)
    }
  }
}
