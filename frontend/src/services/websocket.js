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
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.hostname}:${window.location.port || 8000}/ws/transcribe`

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

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.callbacks.onError?.(error)
        reject(error)
      }

      this.ws.onclose = () => {
        console.log('WebSocket closed')
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
