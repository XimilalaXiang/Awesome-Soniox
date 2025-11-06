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
  }

  /**
   * 连接到服务器 WebSocket
   */
  async connect() {
    return new Promise((resolve, reject) => {
      // 构造相对当前站点的 WS 地址，避免跨端口/HTTPS 混合内容问题
      const isHttps = window.location.protocol === 'https:'
      const origin = window.location.origin
      const wsOrigin = origin.replace(/^http/, isHttps ? 'wss' : 'ws')
      const wsUrl = `${wsOrigin}/ws/transcribe`

      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        // 发送配置
        this.ws.send(JSON.stringify({ config: this.config }))
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.type === 'connected') {
            console.log('Transcription session ready:', data.session_id)
            this.callbacks.onConnected?.(data)
            resolve(data)
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
      // 请求麦克风权限
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      // 创建 MediaRecorder
      const mimeType = this.getSupportedMimeType()
      this.mediaRecorder = new MediaRecorder(this.audioStream, {
        mimeType: mimeType,
        audioBitsPerSecond: 128000,
      })

      // 当有音频数据可用时，发送到服务器
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(event.data)
        }
      }

      // 开始录音（每 100ms 发送一次数据）
      this.mediaRecorder.start(100)

      console.log('Recording started')
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
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ]

    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        console.log('Using MIME type:', type)
        return type
      }
    }

    return ''
  }
}
