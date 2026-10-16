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
export async function extractBodyRatios(file) {
  const landmarker = await getLandmarker();
  const bitmap = await createImageBitmap(file);
  const res = landmarker.detect(bitmap);
  bitmap.close?.();
  const p = res.landmarks?.[0];
  const maskObj = res.segmentationMasks?.[0];
  if (!p || !maskObj) throw new Error("no_pose");
  const needed = [0, 11, 12, 23, 24, 27, 28];
  if (needed.some((i) => (p[i].visibility ?? 1) < 0.5)) { maskObj.close(); throw new Error("not_full_body"); }

  const W = maskObj.width; const H = maskObj.height;
  const mask = maskObj.getAsFloat32Array();
  maskObj.close();

  let top = -1; let bottom = -1;
  for (let y = 0; y < H && top < 0; y += 1) for (let x = 0; x < W; x += 4) if (mask[y * W + x] >= 0.5) { top = y; break; }
  for (let y = H - 1; y >= 0 && bottom < 0; y -= 1) for (let x = 0; x < W; x += 4) if (mask[y * W + x] >= 0.5) { bottom = y; break; }
  const bodyH = bottom - top;
  if (top < 0 || bodyH < H * 0.4) throw new Error("not_full_body");

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
