"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

export interface MaskCanvasHandle {
  exportMaskBlob: () => Promise<Blob>;
  clear: () => void;
}

interface MaskCanvasProps {
  imageBlobUrl: string;
  brushSize?: number;
}

/** Paint white over the areas you want the model to regenerate — black stays untouched.
 * Two stacked canvases: a background one draws the source image once, a transparent
 * foreground one captures pointer-drag strokes (solid white circles/lines) and is shown at
 * ~50% opacity for visual feedback. Exporting composites the foreground's white strokes
 * onto a fresh black canvas, producing the black/white PNG diffusers expects as a mask. */
const MaskCanvas = forwardRef<MaskCanvasHandle, MaskCanvasProps>(function MaskCanvas(
  { imageBlobUrl, brushSize = 24 },
  ref,
) {
  const bgCanvasRef = useRef<HTMLCanvasElement>(null);
  const fgCanvasRef = useRef<HTMLCanvasElement>(null);
  const isDrawingRef = useRef(false);
  const [dims, setDims] = useState<{ width: number; height: number } | null>(null);

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setDims({ width: img.naturalWidth, height: img.naturalHeight });
      const bg = bgCanvasRef.current;
      if (bg) {
        bg.width = img.naturalWidth;
        bg.height = img.naturalHeight;
        bg.getContext("2d")?.drawImage(img, 0, 0);
      }
      const fg = fgCanvasRef.current;
      if (fg) {
        fg.width = img.naturalWidth;
        fg.height = img.naturalHeight;
      }
    };
    img.src = imageBlobUrl;
  }, [imageBlobUrl]);

  function pointerToCanvasCoords(canvas: HTMLCanvasElement, e: React.PointerEvent): [number, number] {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return [(e.clientX - rect.left) * scaleX, (e.clientY - rect.top) * scaleY];
  }

  function drawDot(x: number, y: number) {
    const fg = fgCanvasRef.current;
    const ctx = fg?.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "white";
    ctx.beginPath();
    ctx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
    ctx.fill();
  }

  function handlePointerDown(e: React.PointerEvent<HTMLCanvasElement>) {
    isDrawingRef.current = true;
    const [x, y] = pointerToCanvasCoords(e.currentTarget, e);
    drawDot(x, y);
  }

  function handlePointerMove(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!isDrawingRef.current) return;
    const [x, y] = pointerToCanvasCoords(e.currentTarget, e);
    drawDot(x, y);
  }

  function stopDrawing() {
    isDrawingRef.current = false;
  }

  useImperativeHandle(ref, () => ({
    clear() {
      const fg = fgCanvasRef.current;
      const ctx = fg?.getContext("2d");
      if (fg && ctx) ctx.clearRect(0, 0, fg.width, fg.height);
    },
    exportMaskBlob() {
      return new Promise<Blob>((resolve, reject) => {
        const fg = fgCanvasRef.current;
        if (!fg) {
          reject(new Error("Mask canvas not ready"));
          return;
        }
        const out = document.createElement("canvas");
        out.width = fg.width;
        out.height = fg.height;
        const ctx = out.getContext("2d");
        if (!ctx) {
          reject(new Error("Could not create export canvas"));
          return;
        }
        ctx.fillStyle = "black";
        ctx.fillRect(0, 0, out.width, out.height);
        ctx.drawImage(fg, 0, 0);
        out.toBlob((blob) => {
          if (blob) resolve(blob);
          else reject(new Error("Could not export mask"));
        }, "image/png");
      });
    },
  }));

  return (
    <div className="relative inline-block max-w-full" style={dims ? { aspectRatio: `${dims.width}/${dims.height}` } : undefined}>
      <canvas ref={bgCanvasRef} className="max-w-full rounded-lg" />
      <canvas
        ref={fgCanvasRef}
        className="absolute inset-0 max-w-full cursor-crosshair rounded-lg opacity-50"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={stopDrawing}
        onPointerLeave={stopDrawing}
      />
    </div>
  );
});

export default MaskCanvas;
