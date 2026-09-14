"use client";

import type { VectorDocumentItem, VectorObjectItem } from "@/lib/types";

const SELECT_COLOR = "#38bdf8";

function renderShape(obj: VectorObjectItem, isSelected: boolean, onSelect: (id: string) => void) {
  const p = obj.props as Record<string, number | string | number[][] | undefined>;
  const fill = (p.fill as string | undefined) ?? "black";
  const stroke = isSelected ? SELECT_COLOR : ((p.stroke as string | undefined) ?? "none");
  const strokeWidth = isSelected ? Math.max(3, Number(p.stroke_width ?? 1)) : Number(p.stroke_width ?? 1);
  const opacity = Number(p.opacity ?? 1);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(obj.id);
  };

  const common = { key: obj.id, onClick: handleClick, style: { cursor: "pointer" as const } };

  switch (obj.object_type) {
    case "RECT":
      return (
        <rect
          {...common}
          x={p.x as number}
          y={p.y as number}
          width={p.width as number}
          height={p.height as number}
          rx={(p.rx as number) ?? 0}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          opacity={opacity}
        />
      );
    case "CIRCLE":
      return (
        <circle
          {...common}
          cx={p.cx as number}
          cy={p.cy as number}
          r={p.r as number}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          opacity={opacity}
        />
      );
    case "ELLIPSE":
      return (
        <ellipse
          {...common}
          cx={p.cx as number}
          cy={p.cy as number}
          rx={p.rx as number}
          ry={p.ry as number}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          opacity={opacity}
        />
      );
    case "LINE":
      return (
        <line
          {...common}
          x1={p.x1 as number}
          y1={p.y1 as number}
          x2={p.x2 as number}
          y2={p.y2 as number}
          stroke={stroke === "none" ? "black" : stroke}
          strokeWidth={strokeWidth}
          opacity={opacity}
        />
      );
    case "POLYGON": {
      const points = ((p.points as number[][]) ?? []).map(([x, y]) => `${x},${y}`).join(" ");
      return (
        <polygon {...common} points={points} fill={fill} stroke={stroke} strokeWidth={strokeWidth} opacity={opacity} />
      );
    }
    case "PATH":
      return (
        <path {...common} d={p.d as string} fill={fill} stroke={stroke} strokeWidth={strokeWidth} opacity={opacity} />
      );
    case "TEXT":
      return (
        <text
          {...common}
          x={p.x as number}
          y={p.y as number}
          fontSize={(p.font_size as number) ?? 16}
          fill={fill}
          stroke={stroke !== "none" ? stroke : undefined}
          strokeWidth={stroke !== "none" ? strokeWidth : undefined}
          opacity={opacity}
        >
          {p.content as string}
        </text>
      );
    default:
      return null;
  }
}

export default function VectorCanvas({
  document,
  selectedId,
  onSelect,
}: {
  document: VectorDocumentItem;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const sorted = [...document.objects].sort((a, b) => a.z_index - b.z_index);

  return (
    <svg
      width={document.canvas_width}
      height={document.canvas_height}
      viewBox={`0 0 ${document.canvas_width} ${document.canvas_height}`}
      className="max-w-full rounded-lg border border-white/10 bg-white"
      onClick={() => onSelect(null)}
    >
      {document.background_color && (
        <rect x={0} y={0} width={document.canvas_width} height={document.canvas_height} fill={document.background_color} />
      )}
      {sorted.map((obj) => renderShape(obj, obj.id === selectedId, (id) => onSelect(id)))}
    </svg>
  );
}
