import Link from "next/link";
import { ArrowLeft, type LucideIcon } from "lucide-react";
import AnimatedIcon from "@/components/AnimatedIcon";

interface WorkspaceHeaderProps {
  icon: LucideIcon;
  title: string;
}

/** Shared slim top bar for full-height multi-panel workspace pages (Code, Vector, Animator,
 * Motion, Creative Director) — same gradient icon badge and "Home" link as PageHeader, just
 * compact enough to sit in a fixed border-b strip above the panels. */
export default function WorkspaceHeader({ icon: Icon, title }: WorkspaceHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-2.5">
      <div className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500">
          <AnimatedIcon icon={Icon} className="h-4 w-4 text-white" strokeWidth={2.25} />
        </span>
        <h1 className="text-base font-semibold text-gray-900">{title}</h1>
      </div>
      <Link
        href="/chat"
        className="group inline-flex items-center gap-1.5 rounded-full border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:border-indigo-300 hover:text-indigo-600"
      >
        <ArrowLeft className="h-3.5 w-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" strokeWidth={2.25} />
        Home
      </Link>
    </div>
  );
}
