export type SpeakerId = 'bob' | 'alice' | 'charlie' | 'user';

export interface BlackboardData {
  title: string;
  bullets: string[];
  diagramType: 'free_body' | 'trajectory' | 'energy_graph' | 'flowchart' | 'formula_box' | 'atoms' | 'circuit' | string;
  diagramNote: string;
}

export interface DialogueTurn {
  speaker: SpeakerId;
  speakerName: string;
  text: string;
  emotion?: 'thinking' | 'mistake_realization' | 'hinting' | 'explaining' | 'pointing_board' | 'celebrating' | 'confused';
  gesture?: 'raise_hand' | 'lean_forward' | 'point_chalkboard' | 'nod' | 'confused_tilt' | 'idle';
}

export interface ClassroomResponse {
  blackboard: BlackboardData;
  dialogue: DialogueTurn[];
  takeawaySummary: string;
}

export interface ParticipantConfig {
  id: SpeakerId;
  name: string;
  role: string;
  position: [number, number, number];
  rotation: [number, number, number];
  color: string;
  accentColor: string;
  avatarIcon: string;
  tag: string;
}

export type CameraViewMode = 'desk_pov' | 'free_orbit' | 'blackboard_focus' | 'classmate_focus';

export interface ScreenCoord {
  x: number;
  y: number;
  visible: boolean;
}
