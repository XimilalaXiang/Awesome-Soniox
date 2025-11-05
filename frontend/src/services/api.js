import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

/**
 * 获取所有会话（支持分页和搜索）
 */
export async function getSessions(params = {}) {
  const response = await api.get('/sessions', { params })
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
 * 更新会话标题
 */
export async function updateSessionTitle(sessionId, title) {
  const response = await api.put(`/sessions/${sessionId}/title`, null, {
    params: { title }
  })
  return response.data
}

/**
 * 导出会话
 */
export function exportSession(sessionId, format = 'txt') {
  window.location.href = `/api/sessions/${sessionId}/export?format=${format}`
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
