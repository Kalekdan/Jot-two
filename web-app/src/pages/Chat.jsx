import { useEffect, useRef, useState, useCallback } from 'react'
import './Chat.css'

const USER_ID = 'web-user-' + Math.random().toString(36).slice(2, 8)

function getWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  return `${proto}://${host}/ws/chat/${USER_ID}`
}

export default function Chat() {
  const [messages, setMessages] = useState([
    { role: 'system', text: 'Connected to Jot-two. Start chatting below.' },
  ])
  const [input, setInput] = useState('')
  const [connected, setConnected] = useState(false)
  const [connecting, setConnecting] = useState(true)
  const wsRef = useRef(null)
  const bottomRef = useRef(null)
  const reconnectTimer = useRef(null)

  const addMessage = useCallback((role, text) => {
    setMessages((prev) => [...prev, { role, text, id: Date.now() + Math.random() }])
  }, [])

  const connect = useCallback(() => {
    setConnecting(true)
    const ws = new WebSocket(getWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setConnecting(false)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'message') {
          addMessage('assistant', data.text)
        } else if (data.type === 'error') {
          addMessage('error', data.text)
        }
      } catch {
        addMessage('assistant', event.data)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      setConnecting(false)
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      setConnected(false)
      setConnecting(false)
    }
  }, [addMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function sendMessage(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    addMessage('user', text)
    wsRef.current.send(text)
    setInput('')
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h1 className="page-title">Chat</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'connected' : connecting ? 'connecting' : 'disconnected'}`} />
          <span className="status-text">
            {connected ? 'Connected' : connecting ? 'Connecting…' : 'Reconnecting…'}
          </span>
        </div>
      </div>

      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, i) => (
            <div key={msg.id ?? i} className={`message message-${msg.role}`}>
              {msg.role === 'user' && <div className="message-label">You</div>}
              {msg.role === 'assistant' && <div className="message-label">Jot-two</div>}
              <div className="message-bubble">
                <p className="message-text">{msg.text}</p>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form className="input-row" onSubmit={sendMessage}>
          <input
            className="chat-input"
            type="text"
            placeholder={connected ? 'Type a message…' : 'Connecting…'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!connected}
            autoFocus
          />
          <button
            type="submit"
            className="send-btn"
            disabled={!connected || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
