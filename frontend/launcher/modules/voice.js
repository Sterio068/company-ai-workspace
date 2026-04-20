/**
 * Web Speech API 語音輸入 · 繁中(zh-TW)
 */
import { modal } from "./modal.js";

export const voice = {
  recognition: null,

  _init() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    const r = new SR();
    r.lang = "zh-TW";
    r.interimResults = true;
    r.continuous = false;
    return r;
  },

  toggle(targetInputId = "hero-input") {
    if (!this.recognition) this.recognition = this._init();
    if (!this.recognition) {
      modal.alert("你的瀏覽器不支援語音辨識 · 請用 <strong>Chrome / Safari</strong>", { title: "不支援", icon: "🎤" });
      return;
    }
    const input = document.getElementById(targetInputId);
    const btn = document.getElementById("voice-btn");
    if (!btn) return;
    btn.classList.toggle("recording");

    if (btn.classList.contains("recording")) {
      this.recognition.start();
      this.recognition.onresult = (ev) => {
        let transcript = "";
        for (let i = 0; i < ev.results.length; i++) transcript += ev.results[i][0].transcript;
        if (input) input.value = transcript;
      };
      this.recognition.onend   = () => btn.classList.remove("recording");
      this.recognition.onerror = () => btn.classList.remove("recording");
    } else {
      this.recognition.stop();
    }
  },
};
