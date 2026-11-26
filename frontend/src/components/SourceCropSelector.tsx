'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { CropBox } from '@/lib/types';
import { User, Gamepad2, MoveHorizontal, Move } from 'lucide-react';

interface SourceCropSelectorProps {
  videoRef?: React.RefObject<HTMLVideoElement>;
  containerRef: React.RefObject<HTMLDivElement>;
  mode?: 'split' | 'pan';
  facecamCrop?: CropBox;
  gameplayCrop?: CropBox;
  onFacecamChange?: (box: CropBox) => void;
  onGameplayChange?: (box: CropBox) => void;
  activeTarget?: 'facecam' | 'gameplay';
  onSelectActiveTarget?: (target: 'facecam' | 'gameplay') => void;
  panXOffset?: number;
  onPanXOffsetChange?: (offset: number) => void;
}

export const SourceCropSelector: React.FC<SourceCropSelectorProps> = ({
  videoRef,
  containerRef,
  mode = 'split',
  facecamCrop = { x: 0.7, y: 0.05, width: 0.28, height: 0.35 },
  gameplayCrop = { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
  onFacecamChange,
  onGameplayChange,
  activeTarget = 'facecam',
  onSelectActiveTarget,
  panXOffset = 0.0,
  onPanXOffsetChange,
}) => {
  // Geometry of the actual rendered video within the container (accounting for letterboxing)
  const [videoRect, setVideoRect] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  }>({ left: 0, top: 0, width: 0, height: 0 });

  // Update video rendered rectangle inside container
  const updateVideoRect = useCallback(() => {
    const video = videoRef?.current;
    const container = containerRef.current;
    if (!container) return;

    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    if (containerWidth === 0 || containerHeight === 0) return;

    // Natural video dimensions (default to 16:9 if metadata not loaded yet)
    const naturalWidth = video?.videoWidth || 1920;
    const naturalHeight = video?.videoHeight || 1080;
    const videoRatio = naturalWidth / naturalHeight;
    const containerRatio = containerWidth / containerHeight;

    let renderW = containerWidth;
    let renderH = containerHeight;
    let offsetX = 0;
    let offsetY = 0;

    if (videoRatio > containerRatio) {
      // Letterbox top & bottom
      renderH = containerWidth / videoRatio;
      offsetY = (containerHeight - renderH) / 2;
    } else {
      // Pillarbox left & right
      renderW = containerHeight * videoRatio;
      offsetX = (containerWidth - renderW) / 2;
    }

    setVideoRect({
      left: offsetX,
      top: offsetY,
      width: renderW,
      height: renderH,
    });
  }, [videoRef, containerRef]);

  useEffect(() => {
    updateVideoRect();
    const handleResize = () => updateVideoRect();
    window.addEventListener('resize', handleResize);

    const video = videoRef?.current;
    if (video) {
      video.addEventListener('loadedmetadata', updateVideoRect);
    }
    return () => {
      window.removeEventListener('resize', handleResize);
      if (video) {
        video.removeEventListener('loadedmetadata', updateVideoRect);
      }
    };
  }, [updateVideoRect, videoRef]);

  // Dragging and resizing interaction state for Split screen
  const [dragState, setDragState] = useState<{
    target: 'facecam' | 'gameplay';
    mode: 'move' | 'nw' | 'ne' | 'sw' | 'se';
    startX: number;
    startY: number;
    initialBox: CropBox;
  } | null>(null);

  // Dragging interaction state for Manual Pan Offset
  const [panDragState, setPanDragState] = useState<{
    startX: number;
    initialPan: number;
  } | null>(null);

  const handlePointerDown = (
    e: React.PointerEvent,
    target: 'facecam' | 'gameplay',
    dragMode: 'move' | 'nw' | 'ne' | 'sw' | 'se'
  ) => {
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    onSelectActiveTarget?.(target);

    const initialBox = target === 'facecam' ? { ...facecamCrop } : { ...gameplayCrop };
    setDragState({
      target,
      mode: dragMode,
      startX: e.clientX,
      startY: e.clientY,
      initialBox,
    });
  };

  const handlePanPointerDown = (e: React.PointerEvent) => {
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setPanDragState({
      startX: e.clientX,
      initialPan: panXOffset,
    });
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (videoRect.width === 0 || videoRect.height === 0) return;

    // Handle Pan drag
    if (panDragState) {
      const boxWidth = videoRect.height * (9 / 16);
      const maxTravel = Math.max(0, videoRect.width - boxWidth);
      if (maxTravel > 0) {
        const deltaX = e.clientX - panDragState.startX;
        const deltaPan = (deltaX / maxTravel) * 2;
        const newPan = Math.max(-1.0, Math.min(1.0, panDragState.initialPan + deltaPan));
        onPanXOffsetChange?.(Number(newPan.toFixed(2)));
      }
      return;
    }

    // Handle Split box drag/resize
    if (!dragState) return;

    const deltaX = (e.clientX - dragState.startX) / videoRect.width;
    const deltaY = (e.clientY - dragState.startY) / videoRect.height;
    const { initialBox, mode: dragMode, target } = dragState;

    let { x, y, width, height } = initialBox;
    const minSize = 0.06;

    if (dragMode === 'move') {
      x = Math.max(0, Math.min(1 - width, initialBox.x + deltaX));
      y = Math.max(0, Math.min(1 - height, initialBox.y + deltaY));
    } else if (dragMode === 'se') {
      width = Math.max(minSize, Math.min(1 - initialBox.x, initialBox.width + deltaX));
      height = Math.max(minSize, Math.min(1 - initialBox.y, initialBox.height + deltaY));
    } else if (dragMode === 'sw') {
      const maxDeltaX = initialBox.width - minSize;
      const appliedDeltaX = Math.max(-initialBox.x, Math.min(maxDeltaX, deltaX));
      x = initialBox.x + appliedDeltaX;
      width = initialBox.width - appliedDeltaX;
      height = Math.max(minSize, Math.min(1 - initialBox.y, initialBox.height + deltaY));
    } else if (dragMode === 'ne') {
      width = Math.max(minSize, Math.min(1 - initialBox.x, initialBox.width + deltaX));
      const maxDeltaY = initialBox.height - minSize;
      const appliedDeltaY = Math.max(-initialBox.y, Math.min(maxDeltaY, deltaY));
      y = initialBox.y + appliedDeltaY;
      height = initialBox.height - appliedDeltaY;
    } else if (dragMode === 'nw') {
      const maxDeltaX = initialBox.width - minSize;
      const appliedDeltaX = Math.max(-initialBox.x, Math.min(maxDeltaX, deltaX));
      x = initialBox.x + appliedDeltaX;
      width = initialBox.width - appliedDeltaX;

      const maxDeltaY = initialBox.height - minSize;
      const appliedDeltaY = Math.max(-initialBox.y, Math.min(maxDeltaY, deltaY));
      y = initialBox.y + appliedDeltaY;
      height = initialBox.height - appliedDeltaY;
    }

    const updatedBox: CropBox = {
      x: Number(x.toFixed(4)),
      y: Number(y.toFixed(4)),
      width: Number(width.toFixed(4)),
      height: Number(height.toFixed(4)),
    };

    if (target === 'facecam') {
      onFacecamChange?.(updatedBox);
    } else {
      onGameplayChange?.(updatedBox);
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (dragState) {
      try {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      } catch {}
      setDragState(null);
    }
    if (panDragState) {
      try {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      } catch {}
      setPanDragState(null);
    }
  };

  // Convert normalized box to pixel coordinates on the overlay
  const getBoxStyle = (crop: CropBox) => {
    const left = videoRect.left + crop.x * videoRect.width;
    const top = videoRect.top + crop.y * videoRect.height;
    const width = crop.width * videoRect.width;
    const height = crop.height * videoRect.height;
    return { left, top, width, height };
  };

  const facecamStyle = getBoxStyle(facecamCrop);
  const gameplayStyle = getBoxStyle(gameplayCrop);

  // Manual Pan 9:16 frame geometry
  const panBoxWidth = videoRect.height * (9 / 16);
  const panMaxTravel = Math.max(0, videoRect.width - panBoxWidth);
  const panBoxLeft = videoRect.left + panMaxTravel * (0.5 + panXOffset * 0.5);

  return (
    <div
      className="absolute inset-0 z-30 select-none overflow-hidden"
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      {/* ========================================================================= */}
      {/* 1. MANUAL PAN OFFSET OVERLAY (9:16 Window & Dimmed Letterboxes)            */}
      {/* ========================================================================= */}
      {mode === 'pan' && videoRect.width > 0 && (
        <>
          {/* Dimmed area left of 9:16 frame */}
          <div
            style={{
              position: 'absolute',
              left: `${videoRect.left}px`,
              top: `${videoRect.top}px`,
              width: `${Math.max(0, panBoxLeft - videoRect.left)}px`,
              height: `${videoRect.height}px`,
            }}
            className="bg-black/60 pointer-events-none transition-all"
          />

          {/* Dimmed area right of 9:16 frame */}
          <div
            style={{
              position: 'absolute',
              left: `${panBoxLeft + panBoxWidth}px`,
              top: `${videoRect.top}px`,
              width: `${Math.max(0, videoRect.left + videoRect.width - (panBoxLeft + panBoxWidth))}px`,
              height: `${videoRect.height}px`,
            }}
            className="bg-black/60 pointer-events-none transition-all"
          />

          {/* Draggable 9:16 Vertical Window */}
          <div
            style={{
              position: 'absolute',
              left: `${panBoxLeft}px`,
              top: `${videoRect.top}px`,
              width: `${panBoxWidth}px`,
              height: `${videoRect.height}px`,
            }}
            className="cursor-ew-resize border-2 border-indigo-400 bg-indigo-500/10 shadow-2xl transition-colors hover:border-indigo-300 flex flex-col justify-between items-center p-3"
            onPointerDown={handlePanPointerDown}
          >
            <div className="flex items-center gap-1.5 rounded-md bg-indigo-900/90 px-2 py-0.5 text-[10px] font-bold text-white shadow border border-indigo-400/40 uppercase tracking-wider backdrop-blur-sm pointer-events-none">
              <MoveHorizontal className="h-3 w-3 text-indigo-300" />
              9:16 Vertical Frame ({panXOffset > 0 ? `+${panXOffset.toFixed(2)}` : panXOffset.toFixed(2)})
            </div>

            <div className="text-[10px] font-bold text-indigo-200/80 bg-black/60 px-2 py-0.5 rounded-full pointer-events-none">
              ◀ Drag horizontally to reframe ▶
            </div>
          </div>
        </>
      )}

      {/* ========================================================================= */}
      {/* 2. GAMING SPLIT SCREEN OVERLAYS (Facecam & Gameplay Boxes)                 */}
      {/* ========================================================================= */}
      {mode === 'split' && videoRect.width > 0 && (
        <>
          {/* Quick Target Switcher Pill on the Video Viewport */}
          <div className="absolute top-2 right-2 z-40 flex items-center gap-1 rounded-lg bg-black/80 p-1 border border-white/10 shadow-lg backdrop-blur-md">
            <button
              type="button"
              onPointerDown={(e) => {
                e.stopPropagation();
                onSelectActiveTarget?.('facecam');
              }}
              className={`flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold transition ${
                activeTarget === 'facecam'
                  ? 'bg-cyan-500 text-slate-950 shadow'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <User className="h-3 w-3" />
              Facecam
            </button>
            <button
              type="button"
              onPointerDown={(e) => {
                e.stopPropagation();
                onSelectActiveTarget?.('gameplay');
              }}
              className={`flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold transition ${
                activeTarget === 'gameplay'
                  ? 'bg-indigo-500 text-white shadow'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <Gamepad2 className="h-3 w-3" />
              Gameplay
            </button>
          </div>

          {/* Gameplay Crop Rectangle (Purple) */}
          <div
            style={{
              position: 'absolute',
              left: `${gameplayStyle.left}px`,
              top: `${gameplayStyle.top}px`,
              width: `${gameplayStyle.width}px`,
              height: `${gameplayStyle.height}px`,
            }}
            className={`cursor-move rounded-lg border-2 transition-colors ${
              activeTarget === 'gameplay'
                ? 'border-indigo-400 bg-indigo-500/20 shadow-lg shadow-indigo-500/25 z-15'
                : 'border-indigo-500/60 bg-indigo-500/10 hover:border-indigo-400 z-10'
            }`}
            onPointerDown={(e) => handlePointerDown(e, 'gameplay', 'move')}
          >
            {/* Label Badge */}
            <div className="absolute top-2 left-2 z-20 flex items-center gap-1.5 rounded-md bg-indigo-900/90 px-2 py-0.5 text-[10px] font-bold text-white shadow border border-indigo-400/40 uppercase tracking-wider backdrop-blur-sm pointer-events-none">
              <Gamepad2 className="h-3 w-3 text-indigo-300" />
              Gameplay Pane
            </div>

            {/* Corner resize handles */}
            {activeTarget === 'gameplay' && (
              <>
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'gameplay', 'nw')}
                  className="absolute -top-2 -left-2 h-4 w-4 rounded-full bg-white border-2 border-indigo-600 shadow cursor-nwse-resize z-20"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'gameplay', 'ne')}
                  className="absolute -top-2 -right-2 h-4 w-4 rounded-full bg-white border-2 border-indigo-600 shadow cursor-nesw-resize z-20"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'gameplay', 'sw')}
                  className="absolute -bottom-2 -left-2 h-4 w-4 rounded-full bg-white border-2 border-indigo-600 shadow cursor-nesw-resize z-20"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'gameplay', 'se')}
                  className="absolute -bottom-2 -right-2 h-4 w-4 rounded-full bg-white border-2 border-indigo-600 shadow cursor-nwse-resize z-20"
                />
              </>
            )}
          </div>

          {/* Facecam / Gamer Crop Rectangle (Cyan) - Always higher z-index so it is never trapped */}
          <div
            style={{
              position: 'absolute',
              left: `${facecamStyle.left}px`,
              top: `${facecamStyle.top}px`,
              width: `${facecamStyle.width}px`,
              height: `${facecamStyle.height}px`,
            }}
            className={`cursor-move rounded-lg border-2 transition-colors ${
              activeTarget === 'facecam'
                ? 'border-cyan-400 bg-cyan-500/25 shadow-lg shadow-cyan-500/30 z-30'
                : 'border-cyan-500/70 bg-cyan-500/15 hover:border-cyan-400 z-20'
            }`}
            onPointerDown={(e) => handlePointerDown(e, 'facecam', 'move')}
          >
            {/* Label Badge */}
            <div className="absolute top-2 left-2 z-35 flex items-center gap-1.5 rounded-md bg-cyan-900/90 px-2 py-0.5 text-[10px] font-bold text-white shadow border border-cyan-400/50 uppercase tracking-wider backdrop-blur-sm pointer-events-none">
              <User className="h-3 w-3 text-cyan-300" />
              Facecam / Gamer
            </div>

            {/* Corner resize handles */}
            {activeTarget === 'facecam' && (
              <>
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'facecam', 'nw')}
                  className="absolute -top-2 -left-2 h-4 w-4 rounded-full bg-white border-2 border-cyan-600 shadow cursor-nwse-resize"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'facecam', 'ne')}
                  className="absolute -top-2 -right-2 h-4 w-4 rounded-full bg-white border-2 border-cyan-600 shadow cursor-nesw-resize"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'facecam', 'sw')}
                  className="absolute -bottom-2 -left-2 h-4 w-4 rounded-full bg-white border-2 border-cyan-600 shadow cursor-nesw-resize"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'facecam', 'se')}
                  className="absolute -bottom-2 -right-2 h-4 w-4 rounded-full bg-white border-2 border-cyan-600 shadow cursor-nwse-resize"
                />
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
};
