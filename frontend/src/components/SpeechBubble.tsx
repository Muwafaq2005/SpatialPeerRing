import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ScreenCoord, SpeakerId } from '../types';
import { Sparkles, HelpCircle, GraduationCap, User, Volume2 } from 'lucide-react';
import { speakTurn } from '../classroom/audioEffects';

interface SpeechBubbleProps {
  speaker: SpeakerId;
  speakerName: string;
  text: string;
  emotion?: string;
  coord: ScreenCoord;
  isActive: boolean;
  ttsEnabled: boolean;
}

export const SpeechBubble: React.FC<SpeechBubbleProps> = ({
  speaker,
  speakerName,
  text,
  emotion,
  coord,
  isActive,
}) => {
  if (!isActive || !coord.visible || !text) return null;

  // Color schemes for participants
  const config = {
    bob: {
      bg: 'bg-slate-900/90 border-cyan-500/40 text-slate-100',
      badge: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
      icon: GraduationCap,
      accent: 'text-cyan-400',
      role: 'AI Tutor',
      glow: 'shadow-[0_0_24px_rgba(6,182,212,0.25)]',
    },
    alice: {
      bg: 'bg-stone-900/90 border-amber-500/40 text-stone-100',
      badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      icon: Sparkles,
      accent: 'text-amber-400',
      role: 'Hints & Peer Insight',
      glow: 'shadow-[0_0_24px_rgba(245,158,11,0.25)]',
    },
    charlie: {
      bg: 'bg-zinc-900/90 border-blue-500/40 text-zinc-100',
      badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
      icon: HelpCircle,
      accent: 'text-blue-400',
      role: 'Student Misconception & Doubt',
      glow: 'shadow-[0_0_24px_rgba(59,130,246,0.25)]',
    },
    user: {
      bg: 'bg-emerald-950/90 border-emerald-500/50 text-emerald-50',
      badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
      icon: User,
      accent: 'text-emerald-400',
      role: 'Your Query',
      glow: 'shadow-[0_0_24px_rgba(16,185,129,0.3)]',
    },
  }[speaker];

  const Icon = config.icon;

  // Clamp bubble on screen
  const bubbleWidth = 320;
  const leftPos = Math.max(16, Math.min(window.innerWidth - bubbleWidth - 16, coord.x - bubbleWidth / 2));
  const topPos = Math.max(20, coord.y - 150);

  const handleSpeak = (e: React.MouseEvent) => {
    e.stopPropagation();
    speakTurn(text, speaker, true);
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.85, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: -6 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        style={{
          position: 'absolute',
          left: `${leftPos}px`,
          top: `${topPos}px`,
          width: `${bubbleWidth}px`,
          zIndex: isActive ? 40 : 25,
          pointerEvents: 'auto',
        }}
        className={`rounded-2xl border backdrop-blur-xl p-3.5 ${config.bg} ${config.glow} shadow-2xl transition-all duration-300`}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-2 mb-1.5 pb-1 border-b border-white/10">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className={`p-1 rounded-md ${config.badge} flex items-center justify-center shrink-0`}>
              <Icon className="w-3.5 h-3.5" />
            </span>
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-xs font-semibold tracking-tight text-white truncate">
                {speakerName}
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-white/10 text-white/70 shrink-0">
                {config.role}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {emotion && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-black/40 text-white/60 capitalize font-mono">
                {emotion.replace('_', ' ')}
              </span>
            )}
            <button
              onClick={handleSpeak}
              title="Speak message aloud"
              className="p-1 rounded hover:bg-white/10 text-white/70 hover:text-white transition-colors"
            >
              <Volume2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Message body */}
        <p className="text-xs sm:text-[13px] leading-relaxed font-normal text-slate-100/95 selection:bg-cyan-500/30">
          {text}
        </p>

        {/* Tail pointing towards participant */}
        <div
          className="absolute -bottom-2.5 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[8px] border-l-transparent border-r-[8px] border-r-transparent border-t-[10px]"
          style={{
            borderTopColor: speaker === 'bob' ? '#0f172a' : speaker === 'alice' ? '#1c1917' : speaker === 'charlie' ? '#18181b' : '#022c22',
          }}
        />
      </motion.div>
    </AnimatePresence>
  );
};
