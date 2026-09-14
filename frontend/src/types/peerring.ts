export type AgentId = 'bob-tutor' | 'alice-arithmetic' | 'charlie-conceptual' | 'user' | string;

export interface PolicyState {
  assistance_level: number;
  assistance_level_name: string;
  struggle_score: number;
  recovery_state: 'normal' | 'scaffold' | 'prerequisite_repair' | 'micro_teaching' | string;
}

export interface DialogueMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  agent_id?: string;
  content: string;
  timestamp: string;
  think_block?: string;
  blackboard_patch?: string;
  governance_flags?: Record<string, boolean>;
}

export interface AgentResponseEvent {
  type: 'AGENT_RESPONSE';
  session_id: string;
  agent_id: string;
  active_speaker: string;
  content: string;
  think_block?: string;
  blackboard_patch?: string;
  governance_flags: Record<string, boolean>;
  policy_state: PolicyState;
  turn_count: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface StateSyncEvent {
  type: 'STATE_SYNC';
  session_id: string;
  turn_count: number;
  policy: PolicyState;
  messages_count: number;
  timestamp: string;
}

export interface ErrorEvent {
  type: 'error';
  message: string;
}

export type WebSocketEvent = AgentResponseEvent | StateSyncEvent | ErrorEvent;

export interface AvatarState {
  id: string;
  name: string;
  role: string;
  color: string;
  accentColor: string;
  position: [number, number, number];
  status: 'idle' | 'thinking' | 'speaking';
}
