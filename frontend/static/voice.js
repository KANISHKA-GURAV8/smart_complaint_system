/* voice.js — Web Speech API wrapper */

const LANG_BCP47 = {
  'en': 'en-IN', 'hi': 'hi-IN', 'ta': 'ta-IN', 'te': 'te-IN',
  'kn': 'kn-IN', 'ml': 'ml-IN', 'bn': 'bn-IN', 'mr': 'mr-IN',
  'gu': 'gu-IN', 'pa': 'pa-IN', 'or': 'or-IN', 'auto': 'en-IN'
};

class VoiceRecorder {
  constructor({ onInterim, onFinal, onError, onStop }) {
    this.onInterim = onInterim || (() => {});
    this.onFinal   = onFinal   || (() => {});
    this.onError   = onError   || (() => {});
    this.onStop    = onStop    || (() => {});
    this.recognition = null;
    this.isRecording = false;
    this._supported = false;
    this._init();
  }

  _init() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { console.warn('Speech Recognition not supported'); return; }
    this._supported = true;
    this.recognition = new SR();
    this.recognition.continuous      = true;
    this.recognition.interimResults  = true;
    this.recognition.maxAlternatives = 1;

    this.recognition.onresult = (e) => {
      let interim = '', final = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += t;
        else interim += t;
      }
      if (interim) this.onInterim(interim);
      if (final)   this.onFinal(final);
    };

    this.recognition.onerror = (e) => {
      this.isRecording = false;
      this.onError(e.error);
    };

    this.recognition.onend = () => {
      if (this.isRecording) {
        // auto-restart if we didn't manually stop
        try { this.recognition.start(); } catch(_) {}
      } else {
        this.onStop();
      }
    };
  }

  get supported() { return this._supported; }

  setLang(code) {
    if (this.recognition) {
      this.recognition.lang = LANG_BCP47[code] || 'en-IN';
    }
  }

  start(langCode = 'en') {
    if (!this._supported || this.isRecording) return false;
    this.setLang(langCode);
    try {
      this.recognition.start();
      this.isRecording = true;
      return true;
    } catch (e) {
      this.onError(e.message);
      return false;
    }
  }

  stop() {
    if (!this.isRecording) return;
    this.isRecording = false;
    try { this.recognition.stop(); } catch(_) {}
  }

  toggle(langCode = 'en') {
    if (this.isRecording) { this.stop(); return false; }
    return this.start(langCode);
  }
}
