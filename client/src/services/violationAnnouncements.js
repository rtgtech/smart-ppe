let audioContext;
let announcementChain = Promise.resolve();

const PPE_SPEECH = {
  Helmet: 'safety helmet',
  Vest: 'safety vest',
  Boots: 'safety boots',
};

function context() {
  if (!audioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) audioContext = new AudioContextClass();
  }
  return audioContext;
}

export async function prepareViolationAudio() {
  const current = context();
  if (current?.state === 'suspended') {
    try { await current.resume(); } catch { /* browser may require another user gesture */ }
  }
  window.speechSynthesis?.getVoices();
}

function playTone(durationMs, { frequency, type, volume, secondFrequency }) {
  return new Promise((resolve) => {
    const current = context();
    if (!current) return resolve();

    void current.resume().then(() => {
      const gain = current.createGain();
      const startsAt = current.currentTime;
      const endsAt = startsAt + durationMs / 1000;
      gain.gain.setValueAtTime(0.0001, startsAt);
      gain.gain.exponentialRampToValueAtTime(volume, startsAt + 0.02);
      gain.gain.setValueAtTime(volume, Math.max(startsAt + 0.02, endsAt - 0.03));
      gain.gain.exponentialRampToValueAtTime(0.0001, endsAt);
      gain.connect(current.destination);

      const frequencies = secondFrequency ? [frequency, secondFrequency] : [frequency];
      const oscillators = frequencies.map((value) => {
        const oscillator = current.createOscillator();
        oscillator.type = type;
        oscillator.frequency.setValueAtTime(value, startsAt);
        oscillator.connect(gain);
        oscillator.start(startsAt);
        oscillator.stop(endsAt);
        return oscillator;
      });
      oscillators[0].onended = () => {
        oscillators.forEach((oscillator) => oscillator.disconnect());
        gain.disconnect();
        resolve();
      };
    }).catch(resolve);
  });
}

function playBuzzer() {
  return playTone(2000, {
    frequency: 380,
    secondFrequency: 420,
    type: 'square',
    volume: 0.12,
  });
}

function playShortBeep() {
  return playTone(220, { frequency: 880, type: 'sine', volume: 0.16 });
}

function indianEnglishVoice() {
  const voices = window.speechSynthesis?.getVoices() || [];
  return voices.find((voice) => voice.lang.toLowerCase() === 'en-in')
    || voices.find((voice) => voice.lang.toLowerCase().startsWith('en-in'))
    || null;
}

function speak(text) {
  return new Promise((resolve) => {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) return resolve();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-IN';
    utterance.voice = indianEnglishVoice();
    utterance.rate = 0.95;
    utterance.onend = resolve;
    utterance.onerror = resolve;
    window.speechSynthesis.speak(utterance);
  });
}

function joinWords(values) {
  if (values.length < 2) return values.join('');
  if (values.length === 2) return values.join(' and ');
  return `${values.slice(0, -1).join(', ')}, and ${values.at(-1)}`;
}

async function runAnnouncement(entry) {
  await prepareViolationAudio();
  const workerName = entry.worker?.name;
  if (!workerName) {
    await playBuzzer();
    await speak('Warning. Unidentified person detected.');
    return;
  }

  const missing = Object.entries(entry.evidence?.visual || {})
    .filter(([, value]) => value?.state === 'MISSING')
    .map(([name]) => PPE_SPEECH[name] || name.toLowerCase());
  if (missing.length) {
    const withArticles = joinWords(missing.map((item) => `a ${item}`));
    await speak(`Warning. ${workerName} is missing ${withArticles}.`);
    await playShortBeep();
    const violationItems = joinWords(missing);
    await speak(`PPE violation. ${violationItems.charAt(0).toUpperCase()}${violationItems.slice(1)} missing.`);
    return;
  }

  if (entry.reasons?.includes('PPE_CHECK_INCONCLUSIVE')) {
    const unconfirmed = Object.entries(entry.evidence?.visual || {})
      .filter(([, value]) => value?.state !== 'CONFIRMED')
      .map(([name]) => PPE_SPEECH[name] || name.toLowerCase());
    const itemText = joinWords(unconfirmed);
    await speak(
      `Warning. ${workerName}. PPE check inconclusive.${itemText ? ` Not confirmed: ${itemText}.` : ''}`,
    );
  }
}

export function announceEntryViolation(entry) {
  announcementChain = announcementChain
    .catch(() => {})
    .then(() => runAnnouncement(entry));
  return announcementChain;
}
