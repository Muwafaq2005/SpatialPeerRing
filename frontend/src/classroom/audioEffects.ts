/**
 * Procedural Web Audio API sound effects and Web Speech API text-to-speech
 */

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

/**
 * Realistic chalk-writing sound on a chalkboard using filtered noise bursts
 */
export function playChalkSound(): void {
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const bufferSize = Math.floor(ctx.sampleRate * 0.4);
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    // Filtered pink/chalk noise with micro-taps
    for (let i = 0; i < bufferSize; i++) {
      const white = Math.random() * 2 - 1;
      const grain = (i % 2200 < 500) ? 1.5 : 0.4;
      data[i] = white * grain * Math.exp(-i / (ctx.sampleRate * 0.35));
    }
    const noiseSource = ctx.createBufferSource();
    noiseSource.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(2400, ctx.currentTime);
    filter.Q.setValueAtTime(2.2, ctx.currentTime);
    const gainNode = ctx.createGain();
    gainNode.gain.setValueAtTime(0.08, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.38);
    noiseSource.connect(filter);
    filter.connect(gainNode);
    gainNode.connect(ctx.destination);
    noiseSource.start();
  } catch (e) {
    console.debug('Audio not allowed yet:', e);
  }
}

/**
 * Pleasant classroom chime when someone speaks or raises hand
 */
export function playBellChime(pitch: number = 587.33): void {
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(pitch, ctx.currentTime);
    gain.gain.setValueAtTime(0.06, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.6);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.6);
  } catch (e) {
    console.debug('Audio error:', e);
  }
}

/**
 * Text-to-Speech using standard browser Web Speech API
 */
export function speakTurn(
  text: string,
  speaker: 'bob' | 'alice' | 'charlie' | 'user',
  enabled: boolean = true
): void {
  if (!enabled || typeof window === 'undefined' || !('speechSynthesis' in window)) {
    return;
  }
  try {
    window.speechSynthesis.cancel(); // Stop any pending speech
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    // Select distinct voice characteristics
    if (speaker === 'bob') {
      utterance.pitch = 0.9;
      utterance.rate = 1.0;
      const englishMale = voices.find(v => v.lang.startsWith('en') && (v.name.toLowerCase().includes('male') || v.name.toLowerCase().includes('david') || v.name.toLowerCase().includes('george') || v.name.toLowerCase().includes('daniel')));
      if (englishMale) utterance.voice = englishMale;
    } else if (speaker === 'alice') {
      utterance.pitch = 1.25;
      utterance.rate = 1.05;
      const englishFemale = voices.find(v => v.lang.startsWith('en') && (v.name.toLowerCase().includes('female') || v.name.toLowerCase().includes('samantha') || v.name.toLowerCase().includes('victoria') || v.name.toLowerCase().includes('zira')));
      if (englishFemale) utterance.voice = englishFemale;
    } else if (speaker === 'charlie') {
      utterance.pitch = 1.05;
      utterance.rate = 1.08;
      const youngVoice = voices.find(v => v.lang.startsWith('en') && (v.name.toLowerCase().includes('alex') || v.name.toLowerCase().includes('natural') || v.name.toLowerCase().includes('fred')));
      if (youngVoice) utterance.voice = youngVoice;
    }
    window.speechSynthesis.speak(utterance);
  } catch (e) {
    console.debug('Speech synthesis error:', e);
  }
}

export function stopSpeaking(): void {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
}
