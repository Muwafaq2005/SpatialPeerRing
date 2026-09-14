import { useEffect, useRef, useState, useCallback } from 'react';
import { DialogueMessage, AgentResponseEvent, PolicyState, WebSocketEvent } from '@/types/peerring';

export function useWebSocket(sessionId: string, serverUrl = 'ws://localhost:8000/api/v1/ws') {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<DialogueMessage[]>([]);
  const [activeSpeaker, setActiveSpeaker] = useState<string>('idle');
  const [blackboardPatch, setBlackboardPatch] = useState<string>('');
  const [policyState, setPolicyState] = useState<PolicyState>({
    assistance_level: 1,
    assistance_level_name: 'Independent',
    struggle_score: 0.0,
    recovery_state: 'normal',
  });
  const [turnCount, setTurnCount] = useState<number>(0);
  const [lastError, setLastError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!sessionId) return;
    const wsUrl = `${serverUrl}/${sessionId}`;

    try {
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        setIsConnected(true);
        setLastError(null);
        console.log(`[PeerRing WS] Connected to session ${sessionId}`);
      };

      socket.onmessage = (event) => {
        try {
          const data: WebSocketEvent = JSON.parse(event.data);

          if (data.type === 'AGENT_RESPONSE') {
            const agentEvent = data as AgentResponseEvent;

            // Update dialogue messages
            setMessages((prev) => [
              ...prev,
              {
                id: `msg-${Date.now()}`,
                role: 'agent',
                agent_id: agentEvent.agent_id,
                content: agentEvent.content,
                timestamp: agentEvent.timestamp,
                think_block: agentEvent.think_block,
                blackboard_patch: agentEvent.blackboard_patch,
                governance_flags: agentEvent.governance_flags,
              },
            ]);

            // Update spatial state & speaker
            setActiveSpeaker(agentEvent.active_speaker || agentEvent.agent_id);

            // Update KaTeX Blackboard patch if emitted
            if (agentEvent.blackboard_patch) {
              setBlackboardPatch(agentEvent.blackboard_patch);
            }

            // Update Policy HUD state
            if (agentEvent.policy_state) {
              setPolicyState(agentEvent.policy_state);
            }

            if (agentEvent.turn_count !== undefined) {
              setTurnCount(agentEvent.turn_count);
            }
          } else if (data.type === 'STATE_SYNC') {
            setPolicyState(data.policy);
            setTurnCount(data.turn_count);
          } else if (data.type === 'error') {
            setLastError(data.message);
          }
        } catch (e) {
          console.error('[PeerRing WS] Malformed event payload:', e);
        }
      };

      socket.onerror = (error) => {
        console.warn('[PeerRing WS] Error:', error);
      };

      socket.onclose = () => {
        setIsConnected(false);
        socketRef.current = null;
        console.log('[PeerRing WS] Disconnected. Reconnecting in 3s...');
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };
    } catch (err) {
      console.error('[PeerRing WS] Connection init error:', err);
    }
  }, [sessionId, serverUrl]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim() || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        return false;
      }

      const userMsg: DialogueMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setActiveSpeaker('user');

      const payload = {
        type: 'USER_MESSAGE',
        session_id: sessionId,
        content,
        timestamp: new Date().toISOString(),
      };

      socketRef.current.send(JSON.stringify(payload));
      return true;
    },
    [sessionId]
  );

  return {
    isConnected,
    messages,
    activeSpeaker,
    blackboardPatch,
    policyState,
    turnCount,
    lastError,
    sendMessage,
    clearBlackboard: () => setBlackboardPatch(''),
  };
}
