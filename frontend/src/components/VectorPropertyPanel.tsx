"use client";

import { useState } from "react";
import { updateVectorObject } from "@/lib/vector";
import type { VectorObjectItem } from "@/lib/types";

const COLOR_PROPS = new Set(["fill", "stroke"]);
const NUMBER_PROPS = new Set([
  "x", "y", "width", "height", "rx", "cx", "cy", "r", "rx", "ry",
  "x1", "y1", "x2", "y2", "stroke_width", "opacity", "font_size",
]);

const EDITABLE_PROPS_BY_TYPE: Record<string, string[]> = {
  RECT: ["x", "y", "width", "height", "rx", "fill", "stroke", "stroke_width", "opacity"],
  CIRCLE: ["cx", "cy", "r", "fill", "stroke", "stroke_width", "opacity"],
  ELLIPSE: ["cx", "cy", "rx", "ry", "fill", "stroke", "stroke_width", "opacity"],
  LINE: ["x1", "y1", "x2", "y2", "stroke", "stroke_width", "opacity"],
  POLYGON: ["fill", "stroke", "stroke_width", "opacity"],
  PATH: ["fill", "stroke", "stroke_width", "opacity"],
  TEXT: ["x", "y", "content", "font_size", "fill"],
};

export default function VectorPropertyPanel({
  documentId,
  object,
  onUpdated,
}: {
  documentId: string;
  object: VectorObjectItem | null;
  onUpdated: (updated: VectorObjectItem) => void;
}) {
  const [error, setError] = useState<string | null>(null);

  if (!object) {
    return <p className="p-3 text-xs text-gray-400">Select an object to edit its properties.</p>;
  }

  const editableProps = EDITABLE_PROPS_BY_TYPE[object.object_type] ?? [];

  async function commit(prop: string, rawValue: string) {
    setError(null);
    const value = NUMBER_PROPS.has(prop) ? Number(rawValue) : rawValue;
    try {
      const updated = await updateVectorObject(documentId, object!.id, prop, value);
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update property.");
    }
  }

  return (
    <div className="space-y-3 p-3">
      <p className="text-xs font-medium text-gray-700">{object.object_type}</p>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {editableProps.map((prop) => {
        const value = object.props[prop];
        if (COLOR_PROPS.has(prop)) {
          const isHex = typeof value === "string" && value.startsWith("#");
          return (
            <label key={prop} className="flex items-center justify-between gap-2 text-xs text-gray-500">
              {prop}
              <input
                type={isHex ? "color" : "text"}
                defaultValue={typeof value === "string" ? value : "#000000"}
                onBlur={(e) => commit(prop, e.target.value)}
                className="w-24 rounded border border-gray-200 bg-gray-50 px-1 py-0.5 text-xs text-gray-900"
              />
            </label>
          );
        }
        return (
          <label key={prop} className="flex items-center justify-between gap-2 text-xs text-gray-500">
            {prop}
            <input
              type={NUMBER_PROPS.has(prop) ? "number" : "text"}
              defaultValue={String(value ?? "")}
              onBlur={(e) => commit(prop, e.target.value)}
              className="w-24 rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
            />
          </label>
        );
      })}
    </div>
  );
}
