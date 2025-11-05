import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

/**
 * 获取所有会话
 */
export async function getSessions() {
  const response = await api.get('/sessions')
  return response.data
}

/**
 * 获取特定会话详情
 */
export async function getSession(sessionId) {
  const response = await api.get(`/sessions/${sessionId}`)
  return response.data
}

/**
 * 删除会话
 */
export async function deleteSession(sessionId) {
  const response = await api.delete(`/sessions/${sessionId}`)
  return response.data
}

/**
 * 总结会话内容（流式）
 */
export async function* summarizeSession(sessionId, openaiConfig, prompt) {
  const response = await fetch('/api/summarize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      openai_config: openaiConfig,
      prompt: prompt || '请总结以下会议内容的要点：',
    }),
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value, { stream: true })
    yield chunk
  }
}

/**
 * 提问关于会话内容（流式）
 */
export async function* askQuestion(sessionId, question, openaiConfig) {
  const response = await fetch('/api/question', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      question: question,
      openai_config: openaiConfig,
    }),
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value, { stream: true })
    yield chunk
  }
}

export default api
