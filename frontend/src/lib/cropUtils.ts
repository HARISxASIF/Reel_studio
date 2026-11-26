import { CropBox } from './types';

/**
 * Computes an effective crop box from the user-selected crop region such that:
 * 1. It is centered within the user-selected crop region.
 * 2. Its pixel aspect ratio exactly matches the target pane aspect ratio (paneWidth / paneHeight).
 * 3. When scaled to the pane, it fills 100% of the pane with ZERO black gaps or distortion.
 */
export function computeEffectiveCrop(
  crop: CropBox,
  paneWidth: number,
  paneHeight: number,
  sourceWidth: number = 1920,
  sourceHeight: number = 1080
): CropBox {
  const bx = Math.max(0.0, Math.min(1.0, crop?.x ?? 0.0));
  const by = Math.max(0.0, Math.min(1.0, crop?.y ?? 0.0));
  const bw = Math.max(0.01, Math.min(1.0 - bx, crop?.width ?? 1.0));
  const bh = Math.max(0.01, Math.min(1.0 - by, crop?.height ?? 1.0));

  const srcAspect = (sourceWidth || 1920) / (sourceHeight || 1080);
  const cropAspect = (bw / bh) * srcAspect;
  const paneAspect = paneWidth / paneHeight;

  let effW = bw;
  let effH = bh;
  let effX = bx;
  let effY = by;

  if (cropAspect > paneAspect) {
    // Selected crop is wider than pane -> center crop horizontally within the selected region
    effW = (bh * paneAspect) / srcAspect;
    effX = bx + (bw - effW) / 2.0;
  } else if (cropAspect < paneAspect) {
    // Selected crop is taller than pane -> center crop vertically within the selected region
    effH = (bw * srcAspect) / paneAspect;
    effY = by + (bh - effH) / 2.0;
  }

  return {
    x: Math.max(0.0, Math.min(1.0, effX)),
    y: Math.max(0.0, Math.min(1.0, effY)),
    width: Math.max(0.01, Math.min(1.0, effW)),
    height: Math.max(0.01, Math.min(1.0, effH)),
  };
}

/**
 * Calculates CSS translation percentage for Manual Pan Offset in 9:16 vertical canvas.
 * In a 16:9 video displayed with object-cover inside a 9:16 canvas, the total horizontal travel
 * from center to either edge is exactly 34.18% of the video element's width.
 */
export function getPanTranslatePercent(panXOffset: number): number {
  const clamped = Math.max(-1.0, Math.min(1.0, panXOffset || 0.0));
  // Video element moves opposite to the pan window direction to reveal the chosen region
  return -clamped * 34.18;
}
