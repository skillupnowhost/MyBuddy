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
              className={`block w-full truncate px-2 py-1 text-left text-xs transition ${
                selectedId === child.file.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
              }`}
            >
              📄 {name}
            </button>
          ) : (
            <div style={{ paddingLeft: `${depth * 14 + 12}px` }} className="px-2 py-1 text-xs font-medium text-white/40">
              📁 {name}
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
    return <p className="py-4 text-center text-xs text-white/40">No files yet.</p>;
  }
  const tree = buildTree(files);
  return (
    <div className="space-y-0.5">
      <TreeNodeView node={tree} depth={0} selectedId={selectedId} onSelect={onSelect} />
    </div>
  );
}
