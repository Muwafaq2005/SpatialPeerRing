import React from 'react';
import { PolicyState } from '@/types/peerring';

interface PolicyHUDProps {
  sessionId: string;
  isConnected: boolean;
  activeSpeaker: string;
  turnCount: number;
  policy: PolicyState;
}

export const PolicyHUD: React.FC<PolicyHUDProps> = ({
  sessionId,
  isConnected,
  activeSpeaker,
  turnCount,
  policy,
}) => {
  const getSpeakerLabel = (id: string) => {
    switch (id) {
      case 'bob-tutor':
        return 'Bob (Socratic Tutor)';
      case 'alice-arithmetic':
        return 'Alice (Arithmetic Peer)';
      case 'charlie-conceptual':
        return 'Charlie (Conceptual Peer)';
      case 'user':
        return 'Student (You)';
      default:
        return 'Idle';
    }
  };

  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.9)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '12px',
        padding: '14px 18px',
        color: '#f8fafc',
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '12px',
        fontSize: '13px',
      }}
    >
      {/* Connection & Session */}
      <div>
        <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Session Status
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: isConnected ? '#10b981' : '#ef4444',
              boxShadow: isConnected ? '0 0 8px #10b981' : 'none',
            }}
          />
          <span style={{ fontWeight: 600 }}>{isConnected ? 'ONLINE' : 'CONNECTING...'}</span>
          <span style={{ color: '#64748b', fontSize: '11px' }}>({sessionId.slice(0, 8)})</span>
        </div>
      </div>

      {/* Active Speaker */}
      <div>
        <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Active Speaker
        </div>
        <div style={{ fontWeight: 600, color: '#38bdf8', marginTop: '4px' }}>
          {getSpeakerLabel(activeSpeaker)}
        </div>
      </div>

      {/* Assistance Level Ladder */}
      <div>
        <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Assistance Level (L{policy.assistance_level}/6)
        </div>
        <div style={{ fontWeight: 600, color: '#a78bfa', marginTop: '4px' }}>
          {policy.assistance_level_name || `Level ${policy.assistance_level}`}
        </div>
      </div>

      {/* Struggle Score Meter */}
      <div>
        <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Struggle Meter: {(policy.struggle_score * 100).toFixed(0)}%
        </div>
        <div style={{ background: '#334155', height: '6px', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
          <div
            style={{
              width: `${Math.min(100, Math.max(0, policy.struggle_score * 100))}%`,
              height: '100%',
              background: policy.struggle_score > 0.6 ? '#ef4444' : policy.struggle_score > 0.3 ? '#f59e0b' : '#10b981',
              transition: 'width 0.4s ease',
            }}
          />
        </div>
      </div>

      {/* Turn Counter & Recovery */}
      <div>
        <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Turn / Recovery State
        </div>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginTop: '4px' }}>
          Turn #{turnCount} | <span style={{ color: '#34d399' }}>{policy.recovery_state.toUpperCase()}</span>
        </div>
      </div>
    </div>
  );
};
