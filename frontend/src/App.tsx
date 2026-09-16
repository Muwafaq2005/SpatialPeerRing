/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Classroom3D } from './classroom/Classroom3D';
import { SpeechBubble } from './components/SpeechBubble';
import { ClassroomUI } from './components/ClassroomUI';
import { BlackboardData, CameraViewMode, DialogueTurn, ScreenCoord, SpeakerId } from './types';
import { playBellChime, playChalkSound, speakTurn } from './classroom/audioEffects';
import { usePeerRingSocket, AgentResponsePayload } from './hooks/usePeerRingSocket';

const INITIAL_BLACKBOARD: BlackboardData = {
  title: 'Blackboard Ready',
  bullets: [
    'Select a topic or submit a doubt to begin.',
  ],
  diagramType: 'flowchart',
  diagramNote: 'Ready for lesson...',
};

export default function App() {
  const [currentTopic, setCurrentTopic] = useState<string | null>(null);
  const [blackboardData, setBlackboardData] = useState<BlackboardData>(INITIAL_BLACKBOARD);
  const [cameraMode, setCameraMode] = useState<CameraViewMode>('desk_pov');

  // PeerRing FastAPI WebSocket Hook
  const {
    isConnected: isWsConnected,
    isProcessing: isWsProcessing,
    isTurnLocked,
    lastAgentResponse,
    governanceRejection,
    sendMessage: sendWsMessage,
  } = usePeerRingSocket();

  // Screen coordinates of each participant projected from 3D scene
  const [screenCoords, setScreenCoords] = useState<Record<SpeakerId, ScreenCoord>>({
    bob: { x: 0, y: 0, visible: false },
    alice: { x: 0, y: 0, visible: false },
    charlie: { x: 0, y: 0, visible: false },
    user: { x: 0, y: 0, visible: false },
  });

  // Active messages displayed in chat bubbles (null initially - no response until student queries)
  const [activeBubbles, setActiveBubbles] = useState<
    Record<SpeakerId, { text: string; emotion?: string; timestamp: number } | null>
  >({
    bob: null,
    alice: null,
    charlie: null,
    user: null,
  });

  const [activeSpeaker, setActiveSpeaker] = useState<SpeakerId | null>(null);
  const [activeGesture, setActiveGesture] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Audio toggles
  const [ttsEnabled, setTtsEnabled] = useState<boolean>(false);
  const [sfxEnabled, setSfxEnabled] = useState<boolean>(true);

  // Student study notebook & history
  const [notebookNotes, setNotebookNotes] = useState<
    { timestamp: string; topic: string; summary: string; board: BlackboardData }[]
  >([]);

  const [dialogueHistory, setDialogueHistory] = useState<DialogueTurn[]>([]);

  const timeoutsRef = useRef<NodeJS.Timeout[]>([]);

  // Clear all pending turn timers
  const clearTimeouts = () => {
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];
  };

  useEffect(() => {
    return () => clearTimeouts();
  }, []);

  const handleCoordinatesUpdate = useCallback((coords: Record<SpeakerId, ScreenCoord>) => {
    setScreenCoords(coords);
  }, []);

  // Handle incoming agent responses from WebSocket
  useEffect(() => {
    if (!lastAgentResponse) return;

    const speakerId: SpeakerId =
      (lastAgentResponse.active_speaker?.toLowerCase() as SpeakerId) || 'bob';

    setActiveSpeaker(speakerId);
    setActiveGesture(speakerId === 'bob' ? 'point_chalkboard' : 'lean_forward');

    setActiveBubbles((prev) => ({
      ...prev,
      [speakerId]: {
        text: lastAgentResponse.content,
        emotion: 'explaining',
        timestamp: Date.now(),
      },
    }));

    setDialogueHistory((prev) => [
      ...prev,
      {
        speaker: speakerId,
        speakerName: speakerId === 'bob' ? 'Bob (AI Tutor)' : speakerId === 'alice' ? 'Alice (Peer)' : 'Charlie (Peer)',
        text: lastAgentResponse.content,
      },
    ]);

    if (sfxEnabled) {
      playBellChime(speakerId === 'bob' ? 523 : speakerId === 'alice' ? 659 : 493);
    }
    if (ttsEnabled) {
      speakTurn(lastAgentResponse.content, speakerId, true);
    }

    if (lastAgentResponse.blackboard_patch) {
      const patch = lastAgentResponse.blackboard_patch;
      if (sfxEnabled) playChalkSound();
      setBlackboardData((prev) => ({
        ...prev,
        title: patch.title || prev.title,
        bullets: patch.bullets || prev.bullets,
        diagramType: (patch.diagramType as BlackboardData['diagramType']) || prev.diagramType,
        diagramNote: patch.diagramNote || prev.diagramNote,
      }));

      setNotebookNotes((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          topic: currentTopic,
          summary: `FastAPI Agent Turn: ${lastAgentResponse.agent_id}`,
          board: {
            title: patch.title || blackboardData.title,
            bullets: patch.bullets || blackboardData.bullets,
            diagramType: (patch.diagramType as BlackboardData['diagramType']) || blackboardData.diagramType,
            diagramNote: patch.diagramNote || blackboardData.diagramNote,
          },
        },
      ]);
    }

    setIsLoading(false);
  }, [lastAgentResponse]);

  // Handle student query / doubt submission
  const handleSubmitQuery = async (query: string) => {
    clearTimeouts();
    setIsLoading(true);
    if (sfxEnabled) playBellChime(440);

    // 1. Show User's Speech Bubble at User's desk POV immediately
    setActiveBubbles((prev) => ({
      ...prev,
      user: {
        text: query,
        emotion: 'questioning',
        timestamp: Date.now(),
      },
    }));
    setActiveSpeaker('user');
    setActiveGesture('idle');
    setDialogueHistory((prev) => [
      ...prev,
      { speaker: 'user', speakerName: 'You (Student)', text: query },
    ]);

    console.log(`[PeerRing UI] Submitting student query to Groq AI Agents: "${query}"`);

    try {
      const res = await fetch('/api/classroom/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: currentTopic,
          userQuery: query,
          history: dialogueHistory.slice(-6),
        }),
      });

      if (!res.ok) {
        throw new Error(`Groq AI request failed: ${res.status} ${res.statusText}`);
      }

      const data = await res.json();
      console.log('[PeerRing UI] Groq AI Agents Response Received:', data);

      const turns: DialogueTurn[] = data.dialogue || [];
      if (turns.length === 0) {
        console.warn('[PeerRing UI] No dialogue turns returned by Groq AI, using default response.');
      }

      let delay = 800; // brief pause after student asks doubt

      turns.forEach((turn, idx) => {
        const timeout = setTimeout(() => {
          const speakerId = (turn.speaker?.toLowerCase() as SpeakerId) || 'bob';
          setActiveSpeaker(speakerId);
          setActiveGesture(turn.gesture || 'idle');
          setActiveBubbles((prev) => ({
            ...prev,
            [speakerId]: {
              text: turn.text,
              emotion: turn.emotion,
              timestamp: Date.now(),
            },
          }));
          setDialogueHistory((prev) => [...prev, turn]);

          if (sfxEnabled) {
            playBellChime(speakerId === 'bob' ? 523 : speakerId === 'alice' ? 659 : 493);
          }
          if (ttsEnabled) {
            speakTurn(turn.text, speakerId, true);
          }

          // If Bob is speaking (or final turn), update the blackboard
          if ((turn.speaker === 'bob' || idx === turns.length - 1) && data.blackboard) {
            if (sfxEnabled) playChalkSound();
            setBlackboardData(data.blackboard);

            setNotebookNotes((prev) => [
              ...prev,
              {
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                topic: currentTopic || 'General Study Session',
                summary: data.takeawaySummary || 'Core concept clarified through peer analysis.',
                board: data.blackboard,
              },
            ]);
          }
        }, delay);

        timeoutsRef.current.push(timeout);
        delay += Math.max(3500, turn.text.length * 50);
      });
    } catch (err) {
      console.error('[PeerRing UI] Groq AI Submission Error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTopicChange = (newTopic: string) => {
    setCurrentTopic(newTopic);
    clearTimeouts();

    const newBoard: BlackboardData = {
      title: `${newTopic}: Foundations`,
      bullets: [
        `Subject Overview: ${newTopic}`,
        'Core Principles & Foundational Equations',
        'Identify common assumptions & boundary conditions',
        'Collaborative Problem Solving with Bob, Alice & Charlie',
      ],
      diagramType: 'flowchart',
      diagramNote: 'Observation -> Model -> Law',
    };

    setBlackboardData(newBoard);
    if (sfxEnabled) playChalkSound();

    setActiveBubbles({
      bob: null,
      alice: null,
      charlie: null,
      user: null,
    });
    setActiveSpeaker(null);
    setActiveGesture(undefined);
  };

  const handleResetScene = () => {
    clearTimeouts();
    setBlackboardData(INITIAL_BLACKBOARD);
    setCameraMode('desk_pov');
    setActiveBubbles({
      bob: null,
      alice: null,
      charlie: null,
      user: null,
    });
    setActiveSpeaker(null);
    setActiveGesture(undefined);
  };

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-slate-950 font-sans">
      {/* 3D Three.js Classroom Canvas */}
      <Classroom3D
        blackboardData={blackboardData}
        activeSpeaker={activeSpeaker}
        activeGesture={activeGesture}
        cameraMode={cameraMode}
        onCoordinatesUpdate={handleCoordinatesUpdate}
        onCameraModeChange={setCameraMode}
      />

      {/* 3D Anchored Speech Bubbles */}
      <SpeechBubble
        speaker="bob"
        speakerName="Bob"
        text={activeBubbles.bob?.text || ''}
        emotion={activeBubbles.bob?.emotion}
        coord={screenCoords.bob}
        isActive={activeSpeaker === 'bob'}
        ttsEnabled={ttsEnabled}
      />
      <SpeechBubble
        speaker="alice"
        speakerName="Alice"
        text={activeBubbles.alice?.text || ''}
        emotion={activeBubbles.alice?.emotion}
        coord={screenCoords.alice}
        isActive={activeSpeaker === 'alice'}
        ttsEnabled={ttsEnabled}
      />
      <SpeechBubble
        speaker="charlie"
        speakerName="Charlie"
        text={activeBubbles.charlie?.text || ''}
        emotion={activeBubbles.charlie?.emotion}
        coord={screenCoords.charlie}
        isActive={activeSpeaker === 'charlie'}
        ttsEnabled={ttsEnabled}
      />
      {activeBubbles.user && (
        <SpeechBubble
          speaker="user"
          speakerName="You"
          text={activeBubbles.user.text}
          emotion={activeBubbles.user.emotion}
          coord={screenCoords.user}
          isActive={activeSpeaker === 'user'}
          ttsEnabled={ttsEnabled}
        />
      )}

      {/* Interactive UI Overlay */}
      <ClassroomUI
        currentTopic={currentTopic}
        onTopicChange={handleTopicChange}
        onSubmitQuery={handleSubmitQuery}
        isLoading={isLoading}
        cameraMode={cameraMode}
        onCameraModeChange={setCameraMode}
        ttsEnabled={ttsEnabled}
        onToggleTTS={() => setTtsEnabled(!ttsEnabled)}
        sfxEnabled={sfxEnabled}
        onToggleSFX={() => setSfxEnabled(!sfxEnabled)}
        notebookNotes={notebookNotes}
        dialogueHistory={dialogueHistory}
        onResetScene={handleResetScene}
      />
    </div>
  );
}
