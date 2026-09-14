'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import { useWebSocket } from '@/hooks/useWebSocket';
import { PolicyHUD } from '@/components/hud/PolicyHUD';
import { Blackboard } from '@/components/blackboard/Blackboard';
import { ChatPanel } from '@/components/chat/ChatPanel';

// Dynamic client-side loading for R3F 3D Canvas
const StudyPod = dynamic(
  () => import('@/components/spatial/StudyPod').then((mod) => mod.StudyPod),
  { ssr: false }
);

export default function PeerRingPage() {
  const [sessionId] = useState<string>('demo-session-001');
  const [evalResult, setEvalResult] = useState<any>(null);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);

  const {
    isConnected,
    messages,
    activeSpeaker,
    blackboardPatch,
    policyState,
    turnCount,
    sendMessage,
    clearBlackboard,
  } = useWebSocket(sessionId);

  const triggerEvaluation = async () => {
    setIsEvaluating(true);
    try {
      const res = await fetch('http://localhost:8000/api/v1/test/run-prism-suite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, mastery_before: 0.2 }),
      });
      const data = await res.json();
      setEvalResult(data);
    } catch (err) {
      console.error('Evaluation API error:', err);
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', background: '#090d16' }}>
      {/* Top Bar Header */}
      <header
        style={{
          height: '56px',
          background: 'rgba(15, 23, 42, 0.95)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0 20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #6366f1, #a855f7)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: '14px',
            }}
          >
            P
          </div>
          <span style={{ fontWeight: 700, fontSize: '16px', letterSpacing: '0.5px' }}>SPATIAL PEERRING</span>
          <span
            style={{
              background: 'rgba(99, 102, 241, 0.2)',
              border: '1px solid #6366f1',
              color: '#a5b4fc',
              fontSize: '10px',
              padding: '2px 8px',
              borderRadius: '10px',
              fontWeight: 600,
            }}
          >
            BUILD → OBSERVE → IMPROVE → PROVE
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={triggerEvaluation}
            disabled={isEvaluating}
            style={{
              background: 'linear-gradient(135deg, #10b981, #059669)',
              border: 'none',
              color: '#ffffff',
              padding: '6px 14px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: isEvaluating ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
            }}
          >
            {isEvaluating ? 'Running 7-Pillar Suite...' : '📊 Run PRISM Evaluation & Trust Pack'}
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left Side: 3D Spatial Scene + HUD + Blackboard */}
        <div style={{ flex: '1 1 65%', display: 'flex', flexDirection: 'column', padding: '16px', gap: '16px' }}>
          {/* Policy & Observability HUD */}
          <PolicyHUD
            sessionId={sessionId}
            isConnected={isConnected}
            activeSpeaker={activeSpeaker}
            turnCount={turnCount}
            policy={policyState}
          />

          {/* 3D Study Pod Workspace */}
          <div style={{ flex: 1, position: 'relative', minHeight: '320px' }}>
            <StudyPod activeSpeaker={activeSpeaker} />
          </div>

          {/* Dynamic KaTeX Blackboard */}
          <Blackboard patch={blackboardPatch} onClear={clearBlackboard} />
        </div>

        {/* Right Side: Chat & Pólya Deliberation Transcript */}
        <div style={{ flex: '1 1 35%', minWidth: '340px', maxWidth: '480px' }}>
          <ChatPanel messages={messages} onSendMessage={sendMessage} isConnected={isConnected} />
        </div>
      </div>

      {/* Trust Pack & Evaluation Modal Overlay */}
      {evalResult && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.8)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '16px',
              padding: '24px',
              maxWidth: '680px',
              width: '90%',
              maxHeight: '85vh',
              overflowY: 'auto',
              color: '#f8fafc',
              boxShadow: '0 20px 50px rgba(0,0,0,0.8)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ margin: 0, fontSize: '18px', color: '#10b981' }}>
                🏆 7-Pillar Evaluation Report & Trust Pack
              </h2>
              <button
                onClick={() => setEvalResult(null)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '20px', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div style={{ background: '#1e293b', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px' }}>
              <div style={{ fontSize: '13px', color: '#94a3b8' }}>Overall Score</div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: '#38bdf8' }}>
                {(evalResult.overall_score * 100).toFixed(1)}% / 100%
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                PRISM Trace Reference: {evalResult.prism_session_id}
              </div>
            </div>

            <h4 style={{ margin: '12px 0 8px 0', fontSize: '14px', color: '#c7d2fe' }}>7 Quality Pillars Score Breakdown</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
              {evalResult.pillars &&
                Object.entries(evalResult.pillars).map(([key, data]: [string, any]) => (
                  <div key={key} style={{ background: '#0f172a', border: '1px solid #334155', padding: '8px 12px', borderRadius: '6px' }}>
                    <div style={{ color: '#94a3b8', textTransform: 'capitalize' }}>{data.name}</div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: '#f1f5f9' }}>
                      {(data.score * 100).toFixed(0)}%
                    </div>
                  </div>
                ))}
            </div>

            <h4 style={{ margin: '16px 0 8px 0', fontSize: '14px', color: '#c7d2fe' }}>Trust Pack Evidence Summary</h4>
            <pre
              style={{
                background: '#020617',
                border: '1px solid #1e293b',
                padding: '12px',
                borderRadius: '8px',
                fontSize: '11px',
                color: '#34d399',
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
              }}
            >
              {evalResult.trust_pack?.human_summary}
            </pre>

            <button
              onClick={() => setEvalResult(null)}
              style={{
                width: '100%',
                marginTop: '16px',
                background: '#4f46e5',
                color: '#fff',
                border: 'none',
                padding: '10px',
                borderRadius: '8px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Close Evaluation Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
