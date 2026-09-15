import {
  Code2,
  Image as ImageIcon,
  PenTool,
  Film,
  Clapperboard,
  Target,
  Wand2,
  FileText,
  Brain,
  FolderOpen,
  type LucideIcon,
} from "lucide-react";

export interface ToolLink {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const TOOL_LINKS: ToolLink[] = [
  { href: "/code", label: "Code", icon: Code2 },
  { href: "/image", label: "Image", icon: ImageIcon },
  { href: "/vector", label: "Vector", icon: PenTool },
  { href: "/animation", label: "Animator", icon: Film },
  { href: "/motion", label: "Motion", icon: Clapperboard },
  { href: "/creative", label: "Creative Director", icon: Target },
  { href: "/image-edit", label: "Image Edit", icon: Wand2 },
];

export type LibraryActionKey = "documents" | "memory";

export interface LibraryAction {
  key: LibraryActionKey;
  label: string;
  icon: LucideIcon;
}

export const LIBRARY_ACTIONS: LibraryAction[] = [
  { key: "documents", label: "Knowledge base", icon: FileText },
  { key: "memory", label: "Memory", icon: Brain },
];

export const PROJECT_LINKS: ToolLink[] = [{ href: "/code", label: "Code Projects", icon: FolderOpen }];
