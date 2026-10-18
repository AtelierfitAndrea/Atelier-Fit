// Lens mock layered on top of cam_mock_avatar.js: fakes a phone whose default facingMode stream is the 0.5x ultra-wide.
(() => {
  window.__gum = []; window.__applied = [];
  window.__devs = window.__devs || [
    { deviceId: 'uw-id', kind: 'videoinput', label: 'Back Ultra Wide Camera', groupId: 'g' },
    { deviceId: 'back-id', kind: 'videoinput', label: 'Back Camera', groupId: 'g' },
    { deviceId: 'front-id', kind: 'videoinput', label: 'Front Camera', groupId: 'g' },
  ];
  // default label returned for a facingMode request (per facing)
  window.__defaultLabel = window.__defaultLabel || { environment: 'Back Ultra Wide Camera', user: 'Front Camera' };
  const base = navigator.mediaDevices.getUserMedia;
  navigator.mediaDevices.enumerateDevices = async () => window.__devs.map((d) => ({ ...d, toJSON() { return d; } }));
  navigator.mediaDevices.getUserMedia = async (c) => {
    window.__gum.push(JSON.parse(JSON.stringify(c)));
    const st = await base(c);
    const tr = st.getVideoTracks()[0];
    let dev;
    if (c.video.deviceId) dev = window.__devs.find((d) => d.deviceId === c.video.deviceId.exact);
    else dev = window.__devs.find((d) => d.label === window.__defaultLabel[c.video.facingMode]);
    Object.defineProperty(tr, 'label', { get: () => dev ? dev.label : '' });
    tr.getSettings = () => ({ deviceId: dev ? dev.deviceId : '' });
    tr.getCapabilities = () => ({ zoom: { min: 0.5, max: 10 } });
    tr.applyConstraints = async (k) => { window.__applied.push({ label: tr.label, k: JSON.parse(JSON.stringify(k)) }); };
    return st;
  };
})();
