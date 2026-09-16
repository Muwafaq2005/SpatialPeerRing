import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_BACKEND_URL } from '../services/api';

export interface BlackboardPatch {
  title?: string;
  bullets?: string[];
  diagramType?: string;
  diagramNote?: string;
}

export interface PolicyState {
  assistance_level: number;
  assistance_level_name: string;
  struggle_score: number;
  recovery_state: string;
}

export interface AgentResponsePayload {
  session_id: string;
  agent_id: string;
  active_speaker: 'bob' | 'alice' | 'charlie' | string;
  content: string;
  think_block?: string;
  blackboard_patch?: BlackboardPatch;
  policy_state?: PolicyState;
  governance_flags?: Record<string, boolean>;
  timestamp: string;
}

export interface UsePeerRingSocketReturn {
  isConnected: boolean;
  isProcessing: boolean;
  isTurnLocked: boolean;
  sessionId: string;
  lastAgentResponse: AgentResponsePayload | null;
  governanceRejection: { message: string; failed_judges: string[] } | null;
  error: string | null;
  sendMessage: (content: string) => boolean;
  reconnect: () => void;
}

export function usePeerRingSocket(initialSessionId: string = 'default-pod-session'): UsePeerRingSocketReturn {
  const [sessionId] = useState<string>(initialSessionId);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [isTurnLocked, setIsTurnLocked] = useState<boolean>(false);
  const [lastAgentResponse, setLastAgentResponse] = useState<AgentResponsePayload | null>(null);
  const [governanceRejection, setGovernanceRejection] = useState<{ message: string; failed_judges: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const connectSocket = useCallback(() => {
    try {
      if (socketRef.current) {
        socketRef.current.close();
      }

      const wsUrl = `${WS_BACKEND_URL}/api/v1/ws/${sessionId}`;
      console.log(`[PeerRing WS] Connecting to ${wsUrl}...`);
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        console.log('[PeerRing WS] Connected');
        setIsConnected(true);
        setError(null);

        // Keepalive ping every 25s
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'PING', timestamp: new Date().toISOString() }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          switch (data.type) {
            case 'CONNECTION_ESTABLISHED':
              console.log('[PeerRing WS] Connection established:', data);
              break;

            case 'PROCESSING':
              setIsProcessing(true);
              setIsTurnLocked(false);
              setGovernanceRejection(null);
              break;

            case 'AGENT_RESPONSE':
              setIsProcessing(false);
              setIsTurnLocked(false);
              setLastAgentResponse(data as AgentResponsePayload);
              break;

            case 'TURN_LOCKED':
              setIsProcessing(false);
              setIsTurnLocked(true);
              console.warn('[PeerRing WS] Turn locked:', data.message);
              break;

            case 'GOVERNANCE_REJECTION':
              setIsProcessing(false);
              setIsTurnLocked(false);
              setGovernanceRejection({
                message: data.message,
                failed_judges: data.failed_judges || [],
              });
              break;

            case 'ERROR':
              setIsProcessing(false);
              setError(data.message || 'WebSocket Error');
              break;

            case 'PONG':
              // Heartbeat acknowledgement
              break;

            default:
              console.log('[PeerRing WS] Received message:', data);
          }
        } catch (e) {
          console.error('[PeerRing WS] Failed to parse message:', e);
        }
      };

      ws.onerror = (evt) => {
        console.warn('[PeerRing WS] Socket encountered error:', evt);
        setError('Connection to backend lost or unavailable');
      };

      ws.onclose = () => {
        console.log('[PeerRing WS] Disconnected');
        setIsConnected(false);
        setIsProcessing(false);
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
      };
    } catch (err: unknown) {
      console.error('[PeerRing WS] Setup error:', err);
      setError('Could not initialize WebSocket connection');
    }
  }, [sessionId]);

  useEffect(() => {
    connectSocket();
    return () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connectSocket]);

  const sendMessage = useCallback((content: string): boolean => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      console.warn('[PeerRing WS] Socket not open, cannot send message');
      return false;
    }

    setGovernanceRejection(null);
    setError(null);
    setIsProcessing(true);

    socketRef.current.send(
      JSON.stringify({
        type: 'USER_MESSAGE',
        content,
        metadata: { client: 'react-frontend-2.0' },
      })
    );
    return true;
  }, []);

  return {
    isConnected,
    isProcessing,
    isTurnLocked,
    sessionId,
    lastAgentResponse,
    governanceRejection,
    error,
    sendMessage,
    reconnect: connectSocket,
  };
}
