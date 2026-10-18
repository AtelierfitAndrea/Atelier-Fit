import { FilesetResolver, PoseLandmarker } from "@mediapipe/tasks-vision";

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.1.1/wasm";
const MODEL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task";

let landmarkerPromise = null;
const getLandmarker = () => {
  if (!landmarkerPromise) {
    landmarkerPromise = FilesetResolver.forVisionTasks(WASM).then((fs) =>
      PoseLandmarker.createFromOptions(fs, {
        baseOptions: { modelAssetPath: MODEL, delegate: "CPU" },
        runningMode: "IMAGE",
        numPoses: 1,
        outputSegmentationMasks: true,
      })
    );
    landmarkerPromise.catch(() => { landmarkerPromise = null; });
  }
  return landmarkerPromise;
};

const median = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };

// Width (px) of the silhouette run that contains the body centre on row y.
function runWidth(mask, W, y, cx) {
  const row = y * W;
  let x = cx;
  for (let d = 0; d < W * 0.05 && mask[row + x] < 0.5; d += 1) x = cx + (d % 2 ? d : -d);
  if (mask[row + x] < 0.5) return 0;
  let l = x; let r = x;
  while (l > 0 && mask[row + l - 1] >= 0.5) l -= 1;
  while (r < W - 1 && mask[row + r + 1] >= 0.5) r += 1;
  return r - l + 1;
}

function bandWidths(mask, W, H, y0, y1, cx) {
  const out = [];
  for (let y = Math.max(0, Math.round(y0 * H)); y <= Math.min(H - 1, Math.round(y1 * H)); y += 1) {
    const w = runWidth(mask, W, y, Math.round(cx * W));
    if (w) out.push(w);
  }
  return out;
}

/** Runs MediaPipe Pose in the browser and returns body proportions (ratios of the body height). */
// Average brightness 0-255 on a small thumbnail.
function meanLuma(bitmap) {
  const c = document.createElement("canvas");
  c.width = 64; c.height = 64;
  const ctx = c.getContext("2d");
  ctx.drawImage(bitmap, 0, 0, 64, 64);
  const d = ctx.getImageData(0, 0, 64, 64).data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
  return sum / (d.length / 4);
}

export async function extractBodyRatios(file) {
  const landmarker = await getLandmarker();
  const bitmap = await createImageBitmap(file);
  if (meanLuma(bitmap) < 55) { bitmap.close?.(); throw new Error("too_dark"); }
  const res = landmarker.detect(bitmap);
  bitmap.close?.();
  const p = res.landmarks?.[0];
  const maskObj = res.segmentationMasks?.[0];
  if (!p || !maskObj) throw new Error("no_pose");
  const vis = (i) => (p[i].visibility ?? 1) >= 0.5;
  const fail = (code) => { maskObj.close(); throw new Error(code); };
  if (![11, 12, 23, 24].every(vis)) fail("no_pose");
  if (!vis(0)) fail("no_head");
  if (![27, 28].every(vis)) fail("no_feet");

  const W = maskObj.width; const H = maskObj.height;
  const mask = maskObj.getAsFloat32Array();
  maskObj.close();

  let top = -1; let bottom = -1;
  for (let y = 0; y < H && top < 0; y += 1) for (let x = 0; x < W; x += 4) if (mask[y * W + x] >= 0.5) { top = y; break; }
  for (let y = H - 1; y >= 0 && bottom < 0; y -= 1) for (let x = 0; x < W; x += 4) if (mask[y * W + x] >= 0.5) { bottom = y; break; }
  const bodyH = bottom - top;
  if (top < 0) throw new Error("no_pose");
  if (top <= H * 0.005) throw new Error("cut_top");
  if (bottom >= H - 2) throw new Error("cut_bottom");
  if (bodyH < H * 0.4) throw new Error("too_far");

  const sY = (p[11].y + p[12].y) / 2; const hY = (p[23].y + p[24].y) / 2; const torso = hY - sY;
  const cx = (p[11].x + p[12].x + p[23].x + p[24].x) / 4;
  const shoulder = Math.hypot((p[11].x - p[12].x) * W, (p[11].y - p[12].y) * H);
  const hipJ = Math.hypot((p[23].x - p[24].x) * W, (p[23].y - p[24].y) * H);
  // Arms touching the torso widen the silhouette: cap each width with anatomical limits from the joints.
  const chest = Math.min(median(bandWidths(mask, W, H, sY + 0.25 * torso, sY + 0.4 * torso, cx)), shoulder * 1.0);
  const waist = Math.min(...bandWidths(mask, W, H, sY + 0.55 * torso, sY + 0.85 * torso, cx), chest * 0.88);
  const hips = Math.max(Math.min(Math.max(...bandWidths(mask, W, H, hY - 0.05 * torso, hY + 0.2 * torso, cx)), hipJ * 1.85), waist);
  const inseam = (bottom - hY * H) * 0.86;
  if (!chest || !Number.isFinite(waist) || !Number.isFinite(hips)) throw new Error("no_pose");

  return {
    shoulder_r: shoulder / bodyH,
    chest_r: chest / bodyH,
    waist_r: waist / bodyH,
    hips_r: hips / bodyH,
    inseam_r: inseam / bodyH,
  };
}

function rowRun(mask, W, y, cx) {
  const row = y * W;
  let x = Math.max(0, Math.min(W - 1, Math.round(cx)));
  for (let d = 0; d < W * 0.08 && mask[row + x] < 0.5; d += 1) x = Math.max(0, Math.min(W - 1, Math.round(cx) + (d % 2 ? d : -d)));
  if (mask[row + x] < 0.5) return null;
  let l = x; let r = x;
  while (l > 0 && mask[row + l - 1] >= 0.5) l -= 1;
  while (r < W - 1 && mask[row + r + 1] >= 0.5) r += 1;
  return [l, r];
}

// Silhouette width profile (one entry per row) from y0 to y1, following the body centre.
function profile(d, y0, y1) {
  const out = [];
  let cx = d.hipX;
  for (let y = Math.max(0, Math.round(y0)); y <= Math.min(d.H - 1, Math.round(y1)); y += 1) {
    const run = rowRun(d.mask, d.W, y, cx);
    if (run) { out.push({ y, w: run[1] - run[0] + 1, c: (run[0] + run[1]) / 2 }); cx = (run[0] + run[1]) / 2; } else out.push({ y, w: 0, c: cx });
  }
  return out;
}

/** Finds scale s and offsets (t, dx) so that photo-2 rows y2 map to photo-1 rows y1 = t + s*y2, by matching the overlapping silhouette. */
function registerParts(u, l) {
  const torso = u.hipY - ((u.p[11].y + u.p[12].y) / 2) * u.H;
  // Skip the last rows of photo 1: the segmentation mask tapers at the frame edge.
  const a = profile(u, u.hipY - 0.35 * torso, u.H * 0.97).filter((r) => r.w > 0);
  const b = profile(l, l.H * 0.03, Math.min(l.bottom, l.hipY + (l.bottom - l.hipY) * 0.6));
  if (a.length < 20 || b.length < 20) return null;
  const bw = new Map(b.map((r) => [r.y, r]));
  let best = null;
  for (let k = 0; k <= 70; k += 1) {
    const s = 0.5 * Math.pow(4, k / 70);
    const tMin = a[0].y - s * b[b.length - 1].y; const tMax = a[a.length - 1].y - s * 10;
    for (let t = tMin; t <= tMax; t += 2) {
      let err = 0; let n = 0;
      for (let i = 0; i < a.length; i += 2) {
        const r2 = bw.get(Math.round((a[i].y - t) / s));
        if (!r2 || !r2.w) continue;
        err += Math.min(0.5, Math.abs(a[i].w - s * r2.w) / Math.max(a[i].w, s * r2.w)); n += 1;
      }
      if (n >= 12) {
        const cost = err / n + 0.15 / Math.sqrt(n);
        if (!best || cost < best.cost) best = { s, t, cost, n };
      }
    }
  }
  if (!best || best.cost > 0.2) return null;
  const dxs = a.map((r) => { const r2 = bw.get(Math.round((r.y - best.t) / best.s)); return r2?.w ? r.c - best.s * r2.c : null; }).filter((v) => v !== null);
  return { s: best.s, t: best.t, dx: median(dxs) };
}

async function detectPart(file) {
  const landmarker = await getLandmarker();
  const bitmap = await createImageBitmap(file);
  if (meanLuma(bitmap) < 55) { bitmap.close?.(); throw new Error("too_dark"); }
  const res = landmarker.detect(bitmap);
  const p = res.landmarks?.[0];
  const maskObj = res.segmentationMasks?.[0];
  if (!p || !maskObj) { bitmap.close?.(); throw new Error("no_pose"); }
  const W = maskObj.width; const H = maskObj.height;
  const mask = maskObj.getAsFloat32Array().slice();
  maskObj.close();
  const vis = (i) => (p[i].visibility ?? 1) >= 0.5;
  let top = -1; let bottom = -1;
  for (let y = 0; y < H && top < 0; y += 1) for (let x = 0; x < W; x += 4) if (mask[y * W + x] >= 0.5) { top = y; break; }
  for (let y = H - 1; y >= 0 && bottom < 0; y -= 1) for (let x = 0; x < W; x += 4) if (mask[y * W + x] >= 0.5) { bottom = y; break; }
  const hipY = ((p[23].y + p[24].y) / 2) * H;
  const hipX = ((p[23].x + p[24].x) / 2) * W;
  const hipJ = Math.hypot((p[23].x - p[24].x) * W, (p[23].y - p[24].y) * H);
  return { bitmap, p, mask, W, H, vis, top, bottom, hipY, hipX, hipJ };
}

/** Mirror mode, little space: photo 1 = head→hips, photo 2 = hips→feet. Hips are the shared anchor. */
export async function extractTwoPartRatios(upperFile, lowerFile) {
  const u = await detectPart(upperFile);
  if (![11, 12, 23, 24].every(u.vis)) { u.bitmap.close?.(); throw new Error("upper_no_hips"); }
  if (!u.vis(0)) { u.bitmap.close?.(); throw new Error("no_head"); }
  if (u.top <= u.H * 0.005) { u.bitmap.close?.(); throw new Error("cut_top"); }
  const l = await detectPart(lowerFile);
  const closeAll = () => { u.bitmap.close?.(); l.bitmap.close?.(); };
  if (![23, 24].every(l.vis)) { closeAll(); throw new Error("lower_no_hips"); }
  if (![27, 28].every(l.vis)) { closeAll(); throw new Error("no_feet"); }
  if (l.bottom >= l.H - 2) { closeAll(); throw new Error("cut_bottom"); }

  const { p, mask, W, H } = u;
  const reg = registerParts(u, l) || { s: u.hipJ / l.hipJ, t: u.hipY - l.hipY * (u.hipJ / l.hipJ), dx: u.hipX - l.hipX * (u.hipJ / l.hipJ) };
  const { s, t, dx } = reg;
  const feetY = t + l.bottom * s;
  const legLen = feetY - u.hipY;
  const bodyH = feetY - u.top;
  const sY = (p[11].y + p[12].y) / 2; const hY = (p[23].y + p[24].y) / 2; const torso = hY - sY;
  const cx = (p[11].x + p[12].x + p[23].x + p[24].x) / 4;
  const shoulder = Math.hypot((p[11].x - p[12].x) * W, (p[11].y - p[12].y) * H);
  const chest = Math.min(median(bandWidths(mask, W, H, sY + 0.25 * torso, sY + 0.4 * torso, cx)), shoulder * 1.0);
  const waist = Math.min(...bandWidths(mask, W, H, sY + 0.55 * torso, sY + 0.85 * torso, cx), chest * 0.88);
  const hipBand = bandWidths(mask, W, H, hY - 0.05 * torso, Math.min(hY + 0.2 * torso, 0.995), cx);
  const hips = Math.max(Math.min(Math.max(...hipBand), u.hipJ * 1.85), waist);
  if (!chest || !Number.isFinite(waist) || !Number.isFinite(hips) || bodyH <= 0) { closeAll(); throw new Error("no_pose"); }

  // Stitch: upper photo down to the hips + lower photo from the hips, scaled and centred on the hips.
  const lowEnd = Math.min(l.H, l.bottom + l.H * 0.03);
  const outH = Math.round(t + lowEnd * s);
  const c = document.createElement("canvas");
  c.width = W; c.height = outH;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, outH);
  ctx.drawImage(l.bitmap, dx, t, l.W * s, l.H * s);
  ctx.drawImage(u.bitmap, 0, 0, W, u.hipY, 0, 0, W, u.hipY);
  closeAll();
  const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.92));

  return {
    ratios: {
      shoulder_r: shoulder / bodyH,
      chest_r: chest / bodyH,
      waist_r: waist / bodyH,
      hips_r: hips / bodyH,
      inseam_r: (legLen * 0.86) / bodyH,
    },
    file: new File([blob], "avatar.jpg", { type: "image/jpeg" }),
  };
}
