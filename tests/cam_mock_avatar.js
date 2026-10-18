(() => {
  window.__imgs = __IMGS__;
  window.__cur = window.__cur || 'up';
  window.__speech = [];
  window.__snaps = 0;
  const cache = {};
  const load = (k) => cache[k] || (cache[k] = new Promise((r) => { const i = new Image(); i.onload = () => r(i); i.src = window.__imgs[k]; }));
  window.__setImg = (k) => { window.__cur = k; };
  const origSpeak = SpeechSynthesis.prototype.speak;
  SpeechSynthesis.prototype.speak = function (u) { window.__speech.push({ text: u.text, lang: u.lang, t: Date.now() }); };
  SpeechSynthesis.prototype.cancel = function () {};
  const origToBlob = HTMLCanvasElement.prototype.toBlob;
  HTMLCanvasElement.prototype.toBlob = function (...a) { if (this.width === 960 && this.height === 1000) window.__snaps += 1; return origToBlob.apply(this, a); };
  const fake = async () => {
    const c = document.createElement('canvas'); c.width = 960; c.height = 1000;
    const x = c.getContext('2d');
    const draw = async () => {
      const i = await load(window.__cur);
      x.save(); x.setTransform(1, 0, 0, 1, 0, 0);
      x.fillStyle = '#fff'; x.fillRect(0, 0, 960, 1000);
      const s = Math.min(960 / i.naturalWidth, 1000 / i.naturalHeight); const w = i.naturalWidth * s, h = i.naturalHeight * s;
      x.translate(960, 0); x.scale(-1, 1);
      x.drawImage(i, (960 - w) / 2, (1000 - h) / 2, w, h);
      x.restore();
    };
    await draw();
    setInterval(draw, 100);
    const st = c.captureStream(15);
    return st;
  };
  if (!navigator.mediaDevices) Object.defineProperty(navigator, 'mediaDevices', { value: {} });
  navigator.mediaDevices.getUserMedia = async () => { if (window.__camFail) throw new Error('denied'); return fake(); };
})();
