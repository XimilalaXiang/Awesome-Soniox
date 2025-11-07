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

      // 创建 MediaRecorder（带 MIME 类型回退，以兼容不同浏览器）
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
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(event.data)
        }
      }

      // 开始录音（每 100ms 发送一次数据）
      this.mediaRecorder.start(100)

      console.log('Recording started')
      this.isPaused = false
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
   * 暂停录音（保持会话与音频流，停止送帧）
   */
  pause() {
    try {
      if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
        this.mediaRecorder.stop()
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
