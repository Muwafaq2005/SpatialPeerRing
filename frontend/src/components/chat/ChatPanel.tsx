import React, { useState } from 'react';
import { DialogueMessage } from '@/types/peerring';

interface ChatPanelProps {
  messages: DialogueMessage[];
  onSendMessage: (content: string) => boolean;
  isConnected: boolean;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ messages, onSendMessage, isConnected }) => {
  const [input, setInput] = useState('');
  const [showThinkBlocks, setShowThinkBlocks] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (onSendMessage(input)) {
      setInput('');
    }
  };

  const getAgentBadgeColor = (agentId?: string) => {
    switch (agentId) {
      case 'bob-tutor':
        return '#3b82f6';
      case 'alice-arithmetic':
        return '#ec4899';
      case 'charlie-conceptual':
        return '#8b5cf6';
      default:
        return '#10b981';
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'rgba(15, 23, 42, 0.95)',
        borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
        padding: '16px',
        color: '#f8fafc',
        boxSizing: 'border-box',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#f1f5f9' }}>Dialogue & Deliberation</h3>
        <button
          onClick={() => setShowThinkBlocks((prev) => !prev)}
          style={{
            background: showThinkBlocks ? 'rgba(79, 70, 229, 0.3)' : 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            color: '#c7d2fe',
            fontSize: '11px',
            padding: '4px 8px',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          {showThinkBlocks ? 'Hide Pólya <think>' : 'Show Pólya <think>'}
        </button>
      </div>

      {/* Message History Transcript */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          paddingRight: '4px',
        }}
      >
        {messages.length === 0 ? (
          <div style={{ color: '#64748b', textAlign: 'center', marginTop: '40px', fontSize: '13px' }}>
            No messages yet. Ask a question to begin the peer learning session!
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '88%',
                background: msg.role === 'user' ? '#1e293b' : 'rgba(30, 41, 59, 0.8)',
                border: `1px solid ${msg.role === 'user' ? '#334155' : getAgentBadgeColor(msg.agent_id)}`,
                borderRadius: '12px',
                padding: '10px 14px',
                fontSize: '13px',
                lineHeight: '1.5',
              }}
            >
              {/* Sender Badge */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '11px' }}>
                <span style={{ fontWeight: 700, color: getAgentBadgeColor(msg.agent_id) }}>
                  {msg.role === 'user' ? 'Student (You)' : msg.agent_id || 'Agent'}
                </span>
                <span style={{ color: '#64748b' }}>
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>

              {/* Pólya <think> Deliberation block */}
              {showThinkBlocks && msg.think_block && (
                <div
                  style={{
                    background: 'rgba(0, 0, 0, 0.4)',
                    borderLeft: '3px solid #818cf8',
                    padding: '6px 10px',
                    borderRadius: '4px',
                    margin: '6px 0',
                    fontSize: '11px',
                    color: '#a5b4fc',
                    fontFamily: 'monospace',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {msg.think_block}
                </div>
              )}

              {/* Message Content */}
              <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

              {/* Governance Flags Badges */}
              {msg.governance_flags && Object.keys(msg.governance_flags).length > 0 && (
                <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                  {Object.entries(msg.governance_flags).map(([key, passed]) => (
                    <span
                      key={key}
                      style={{
                        fontSize: '9px',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: passed ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                        color: passed ? '#6ee7b7' : '#fca5a5',
                        border: `1px solid ${passed ? '#10b981' : '#ef4444'}`,
                      }}
                    >
                      {key.toUpperCase()}: {passed ? 'PASS' : 'FAIL'}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isConnected ? 'Ask Bob, Alice, or Charlie a question...' : 'Connecting to backend...'}
          disabled={!isConnected}
          style={{
            flex: 1,
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '8px',
            padding: '10px 14px',
            color: '#f8fafc',
            fontSize: '13px',
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={!isConnected || !input.trim()}
          style={{
            background: isConnected && input.trim() ? '#4f46e5' : '#334155',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            padding: '10px 18px',
            fontWeight: 600,
            fontSize: '13px',
            cursor: isConnected && input.trim() ? 'pointer' : 'not-allowed',
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
};
