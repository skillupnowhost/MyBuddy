import { FileText, Folder } from "lucide-react";
import type { CodeFileItem } from "@/lib/types";

interface TreeNode {
  name: string;
  file: CodeFileItem | null;
  children: Map<string, TreeNode>;
}

function buildTree(files: CodeFileItem[]): TreeNode {
  const root: TreeNode = { name: "", file: null, children: new Map() };
  for (const file of files) {
    const parts = file.relative_path.split("/").filter(Boolean);
    let node = root;
    parts.forEach((part, i) => {
      const isLeaf = i === parts.length - 1;
      let child = node.children.get(part);
      if (!child) {
        child = { name: part, file: isLeaf ? file : null, children: new Map() };
        node.children.set(part, child);
      }
      node = child;
    });
  }
  return root;
}

function TreeNodeView({
  node,
  depth,
  selectedId,
  onSelect,
}: {
  node: TreeNode;
  depth: number;
  selectedId: string | null;
  onSelect: (file: CodeFileItem) => void;
}) {
  const entries = [...node.children.entries()].sort(([aName, a], [bName, b]) => {
    const aIsDir = a.file === null;
    const bIsDir = b.file === null;
    if (aIsDir !== bIsDir) return aIsDir ? -1 : 1;
    return aName.localeCompare(bName);
  });

  return (
    <>
      {entries.map(([name, child]) => (
        <div key={name}>
          {child.file ? (
            <button
              onClick={() => onSelect(child.file!)}
              style={{ paddingLeft: `${depth * 14 + 12}px` }}
              className={`group flex w-full items-center gap-1.5 truncate px-2 py-1 text-left text-xs transition ${
                selectedId === child.file.id ? "bg-gray-100 text-gray-900" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              }`}
            >
              <FileText className="h-3.5 w-3.5 shrink-0 transition-transform duration-200 group-hover:scale-110" strokeWidth={2} />
              {name}
            </button>
          ) : (
            <div
              style={{ paddingLeft: `${depth * 14 + 12}px` }}
              className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-gray-400"
            >
              <Folder className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
              {name}
            </div>
          )}
          {child.children.size > 0 && (
            <TreeNodeView node={child} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} />
          )}
        </div>
      ))}
    </>
  );
}

export default function CodeFileTree({
  files,
  selectedId,
  onSelect,
}: {
  files: CodeFileItem[];
  selectedId: string | null;
  onSelect: (file: CodeFileItem) => void;
}) {
  if (files.length === 0) {
    return <p className="py-4 text-center text-xs text-gray-400">No files yet.</p>;
  }
  const tree = buildTree(files);
  return (
    <div className="space-y-0.5">
      <TreeNodeView node={tree} depth={0} selectedId={selectedId} onSelect={onSelect} />
    </div>
  );
}
