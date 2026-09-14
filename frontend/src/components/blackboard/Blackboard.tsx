import React, { useEffect, useRef } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface BlackboardProps {
  patch: string;
  onClear?: () => void;
}

export const Blackboard: React.FC<BlackboardProps> = ({ patch, onClear }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    if (!patch || !patch.trim()) {
      containerRef.current.innerHTML = '<span style="color: #64748b; font-style: italic;">[ Blackboard Ready - Waiting for mathematical patch... ]</span>';
      return;
    }

    try {
      // Clean or extract KaTeX math content
      let rawLatex = patch.trim();

      // Render into container safely
      katex.render(rawLatex, containerRef.current, {
        displayMode: true,
        throwOnError: false,
      });
    } catch (err) {
      console.warn('[KaTeX Render Warning]:', err);
      if (containerRef.current) {
        containerRef.current.innerText = patch; // Safe raw text fallback
      }
    }
  }, [patch]);

  return (
    <div
      style={{
        background: '#022c22',
        border: '3px solid #1e293b',
        borderRadius: '12px',
        padding: '16px 20px',
        color: '#f8fafc',
        fontFamily: "'Courier New', monospace",
        boxShadow: 'inset 0 0 20px rgba(0,0,0,0.6), 0 8px 16px rgba(0,0,0,0.4)',
        minHeight: '140px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        position: 'relative',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <span style={{ fontSize: '12px', letterSpacing: '1px', textTransform: 'uppercase', color: '#34d399', fontWeight: 700 }}>
          ❖ Dynamic Mathematical Blackboard
        </span>
        {patch && onClear && (
          <button
            onClick={onClear}
            style={{
              background: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#fca5a5',
              padding: '2px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              cursor: 'pointer',
            }}
          >
            Clear
          </button>
        )}
      </div>

      <div
        ref={containerRef}
        style={{
          fontSize: '18px',
          overflowX: 'auto',
          padding: '10px 0',
          textAlign: 'center',
        }}
      />
    </div>
  );
};
