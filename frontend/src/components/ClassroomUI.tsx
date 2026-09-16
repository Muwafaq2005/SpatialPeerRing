import React, { useState } from 'react';
import {
  Send,
  BookOpen,
  Volume2,
  VolumeX,
  Eye,
  Sparkles,
  RotateCcw,
  GraduationCap,
  Layers,
  X,
  HelpCircle,
} from 'lucide-react';
import { CameraViewMode, BlackboardData, DialogueTurn } from '../types';

interface ClassroomUIProps {
  currentTopic: string | null;
  onTopicChange: (topic: string) => void;
  onSubmitQuery: (query: string) => void;
  isLoading: boolean;
  cameraMode: CameraViewMode;
  onCameraModeChange: (mode: CameraViewMode) => void;
  ttsEnabled: boolean;
  onToggleTTS: () => void;
  sfxEnabled: boolean;
  onToggleSFX: () => void;
  notebookNotes: { timestamp: string; topic: string; summary: string; board: BlackboardData }[];
  dialogueHistory: DialogueTurn[];
  onResetScene: () => void;
}

const PRESET_TOPICS = [
  "Newton's Laws of Motion & Gravity",
  'Photosynthesis & Solar Energy Conversion',
  'Quantum Mechanics & Wave-Particle Duality',
  'How Large Language Models & Neural Nets Work',
  'Calculus: Derivatives as Rates of Change',
  'Plate Tectonics & Continental Drift',
];

const PRESET_DOUBTS = [
  'Why do heavy and light objects hit the ground at the same time in vacuum?',
  'If every action has an equal and opposite reaction, why does anything move?',
  "Why doesn't the Moon fall straight into Earth if gravity is pulling it?",
  'Does cold air leak into a warm room, or does heat escape?',
  'Can an object have zero velocity but non-zero acceleration?',
];

export const ClassroomUI: React.FC<ClassroomUIProps> = ({
  currentTopic,
  onTopicChange,
  onSubmitQuery,
  isLoading,
  cameraMode,
  onCameraModeChange,
  ttsEnabled,
  onToggleTTS,
  notebookNotes,
  dialogueHistory,
  onResetScene,
}) => {
  const [queryInput, setQueryInput] = useState('');
  const [isNotebookOpen, setIsNotebookOpen] = useState(false);
  const [isCustomTopicOpen, setIsCustomTopicOpen] = useState(false);
  const [customTopicInput, setCustomTopicInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim() || isLoading) return;
    onSubmitQuery(queryInput.trim());
    setQueryInput('');
  };

  const handleSelectPresetDoubt = (doubt: string) => {
    if (isLoading) return;
    onSubmitQuery(doubt);
  };

  const handleCustomTopicSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customTopicInput.trim()) {
      onTopicChange(customTopicInput.trim());
      setIsCustomTopicOpen(false);
    }
  };

  return (
    <>
      {/* TOP HEADER BAR */}
      <header className="absolute top-0 left-0 right-0 z-30 p-3 sm:p-4 flex items-center justify-between gap-3 pointer-events-none">
        {/* Left: App Title & Topic Selector */}
        <div className="flex items-center gap-2 pointer-events-auto bg-slate-900/85 backdrop-blur-xl border border-white/10 p-1.5 pl-3 rounded-2xl shadow-xl">
          <div className="flex items-center gap-2 pr-2 border-r border-white/10">
            <GraduationCap className="w-5 h-5 text-cyan-400 shrink-0" />
            <span className="text-xs sm:text-sm font-semibold tracking-tight text-white hidden md:inline">
              3D AI Classroom
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <select
              value={currentTopic ? (PRESET_TOPICS.includes(currentTopic) ? currentTopic : 'custom') : ''}
              onChange={(e) => {
                if (e.target.value === 'custom') {
                  setIsCustomTopicOpen(true);
                } else if (e.target.value) {
                  onTopicChange(e.target.value);
                }
              }}
              className="bg-slate-800/80 hover:bg-slate-800 text-xs sm:text-sm text-slate-200 py-1 px-2.5 rounded-xl border border-white/10 focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer max-w-[200px] sm:max-w-[280px] truncate"
            >
              <option value="" disabled hidden>
                Select Topic...
              </option>
              {PRESET_TOPICS.map((topic) => (
                <option key={topic} value={topic}>
                  {topic}
                </option>
              ))}
              <option value="custom">✎ Custom Topic...</option>
            </select>
          </div>
        </div>

        {/* Right: Camera View Modes & Audio Controls */}
        <div className="flex items-center gap-2 pointer-events-auto">
          {/* Camera View Switcher */}
          <div className="hidden sm:flex items-center bg-slate-900/85 backdrop-blur-xl border border-white/10 p-1 rounded-2xl shadow-xl">
            <button
              onClick={() => onCameraModeChange('desk_pov')}
              title="Desk POV (Your Seat)"
              className={`px-3 py-1.5 text-xs font-medium rounded-xl transition-all flex items-center gap-1.5 ${
                cameraMode === 'desk_pov'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Desk POV</span>
            </button>
            <button
              onClick={() => onCameraModeChange('blackboard_focus')}
              title="Focus on Blackboard & Bob"
              className={`px-3 py-1.5 text-xs font-medium rounded-xl transition-all flex items-center gap-1.5 ${
                cameraMode === 'blackboard_focus'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Blackboard</span>
            </button>
            <button
              onClick={() => onCameraModeChange('classmate_focus')}
              title="Focus on Alice & Charlie"
              className={`px-3 py-1.5 text-xs font-medium rounded-xl transition-all flex items-center gap-1.5 ${
                cameraMode === 'classmate_focus'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              }`}
            >
              <span>Peers</span>
            </button>
            <button
              onClick={() => onCameraModeChange('free_orbit')}
              title="Wide Overview"
              className={`px-3 py-1.5 text-xs font-medium rounded-xl transition-all flex items-center gap-1.5 ${
                cameraMode === 'free_orbit'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              }`}
            >
              <span>Room</span>
            </button>
          </div>

          {/* Sound & Notebook Toggles */}
          <div className="flex items-center gap-1 bg-slate-900/85 backdrop-blur-xl border border-white/10 p-1 rounded-2xl shadow-xl">
            <button
              onClick={onToggleTTS}
              title={ttsEnabled ? 'Mute AI Voices' : 'Enable AI Voices'}
              className={`p-2 rounded-xl transition-all ${
                ttsEnabled ? 'text-cyan-400 bg-cyan-500/15' : 'text-slate-400 hover:text-white'
              }`}
            >
              {ttsEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setIsNotebookOpen(true)}
              title="Student Notebook & Lesson Notes"
              className="px-3 py-1.5 rounded-xl text-xs font-medium text-slate-200 hover:text-white hover:bg-white/10 transition-all flex items-center gap-1.5"
            >
              <BookOpen className="w-4 h-4 text-amber-400" />
              <span className="hidden md:inline">Notebook</span>
              {notebookNotes.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold">
                  {notebookNotes.length}
                </span>
              )}
            </button>
            <button
              onClick={onResetScene}
              title="Reset View"
              className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-all"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* BOTTOM QUESTION INPUT BAR */}
      <footer className="absolute bottom-0 left-0 right-0 z-30 p-3 sm:p-5 flex flex-col items-center pointer-events-none">
        {/* Suggestion Chips */}
        <div className="w-full max-w-4xl flex items-center gap-2 overflow-x-auto pb-2 mb-2 no-scrollbar pointer-events-auto">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-300 uppercase tracking-wider shrink-0 bg-slate-900/70 backdrop-blur-md px-2 py-1 rounded-lg border border-white/10">
            <HelpCircle className="w-3.5 h-3.5 text-cyan-400" />
            <span>Try Doubts:</span>
          </div>
          {PRESET_DOUBTS.map((doubt, idx) => (
            <button
              key={idx}
              disabled={isLoading}
              onClick={() => handleSelectPresetDoubt(doubt)}
              className="text-xs bg-slate-900/80 hover:bg-slate-800/95 text-slate-200 border border-white/15 px-3 py-1.5 rounded-full whitespace-nowrap backdrop-blur-md transition-all hover:border-cyan-400/50 hover:text-white disabled:opacity-50 shrink-0"
            >
              {doubt}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="w-full max-w-4xl pointer-events-auto">
          <form
            onSubmit={handleSubmit}
            className="relative flex items-center bg-slate-900/90 backdrop-blur-2xl border border-white/20 rounded-2xl shadow-2xl p-1.5 pl-4 focus-within:border-cyan-400/80 focus-within:ring-2 focus-within:ring-cyan-500/20 transition-all"
          >
            <input
              type="text"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder={
                isLoading
                  ? 'Bob, Alice & Charlie are discussing your question...'
                  : 'Raise your hand or ask a doubt (e.g. "What if there is no friction?")...'
              }
              disabled={isLoading}
              className="w-full bg-transparent text-sm sm:text-base text-white placeholder-slate-400 focus:outline-none pr-3"
            />
            <button
              type="submit"
              disabled={!queryInput.trim() || isLoading}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-xs sm:text-sm flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shrink-0"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span className="hidden sm:inline">Discussing...</span>
                </>
              ) : (
                <>
                  <span>Ask Class</span>
                  <Send className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </footer>

      {/* CUSTOM TOPIC MODAL */}
      {isCustomTopicOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm pointer-events-auto">
          <div className="bg-slate-900 border border-white/20 rounded-2xl p-5 max-w-md w-full shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-semibold text-white">Set Custom Lesson Topic</h3>
              </div>
              <button
                onClick={() => setIsCustomTopicOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCustomTopicSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  What subject or concept should Bob and the class explore?
                </label>
                <input
                  type="text"
                  value={customTopicInput}
                  onChange={(e) => setCustomTopicInput(e.target.value)}
                  placeholder="e.g. Einstein's Theory of Special Relativity"
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-400"
                  autoFocus
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsCustomTopicOpen(false)}
                  className="px-4 py-2 text-xs text-slate-300 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!customTopicInput.trim()}
                  className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs transition-colors disabled:opacity-50"
                >
                  Start Lesson
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* STUDENT NOTEBOOK DRAWER */}
      {isNotebookOpen && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-slate-950/95 border-l border-white/10 shadow-2xl backdrop-blur-2xl p-6 flex flex-col pointer-events-auto">
          {/* Notebook Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-amber-400" />
              <h2 className="text-lg font-bold text-white">Student Study Notebook</h2>
            </div>
            <button
              onClick={() => setIsNotebookOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Notes List */}
          <div className="flex-1 overflow-y-auto py-4 space-y-4 no-scrollbar">
            {notebookNotes.length === 0 ? (
              <div className="text-center py-12 text-slate-400 space-y-2">
                <GraduationCap className="w-10 h-10 text-slate-600 mx-auto" />
                <p className="text-sm font-medium">Your notebook is currently empty.</p>
                <p className="text-xs text-slate-500 max-w-xs mx-auto">
                  Ask a doubt or question to Bob, Alice, and Charlie to generate real-time chalkboard notes and takeaways!
                </p>
              </div>
            ) : (
              notebookNotes.map((note, index) => (
                <div
                  key={index}
                  className="bg-slate-900/80 border border-white/10 rounded-xl p-4 space-y-2.5 shadow-sm"
                >
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span className="font-semibold text-amber-300">{note.topic}</span>
                    <span>{note.timestamp}</span>
                  </div>
                  <h4 className="text-sm font-bold text-white">{note.board.title}</h4>
                  <ul className="text-xs text-slate-300 space-y-1 pl-3 list-disc">
                    {note.board.bullets.map((bullet, bIdx) => (
                      <li key={bIdx}>{bullet}</li>
                    ))}
                  </ul>
                  <div className="pt-2 border-t border-white/10 flex items-start gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                    <p className="text-xs italic text-cyan-200">{note.summary}</p>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Transcript History */}
          <div className="pt-4 border-t border-white/10 text-xs text-slate-400 flex items-center justify-between">
            <span>{dialogueHistory.length} dialogue turns recorded</span>
            <button
              onClick={() => {
                const text = notebookNotes
                  .map(
                    (n) =>
                      `=== ${n.topic} (${n.timestamp}) ===\n${n.board.title}\n${n.board.bullets.join('\n')}\nTakeaway: ${n.summary}\n`
                  )
                  .join('\n\n');
                navigator.clipboard.writeText(text);
              }}
              className="text-cyan-400 hover:underline"
            >
              Copy Notes
            </button>
          </div>
        </div>
      )}
    </>
  );
};
