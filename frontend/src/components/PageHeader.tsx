import Link from "next/link";
import { ArrowLeft, type LucideIcon } from "lucide-react";
import AnimatedIcon from "@/components/AnimatedIcon";

interface PageHeaderProps {
  icon: LucideIcon;
  title: string;
  description?: string;
}

/** Shared header for centered "card list" tool pages (Image, Image Edit, Fine-tuning, Admin, Video)
 * — mirrors the homepage's gradient icon badge + gradient wordmark language so every tool reads as
 * part of the same product, and always links back to the homepage (the /chat route with no active
 * conversation). */
export default function PageHeader({ icon: Icon, title, description }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="flex items-center gap-3.5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 shadow-sm shadow-indigo-200">
          <AnimatedIcon icon={Icon} className="h-5 w-5 text-white" strokeWidth={2} />
        </span>
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>
          {description && <p className="mt-0.5 max-w-xl text-sm leading-relaxed text-gray-500">{description}</p>}
        </div>
      </div>
      <Link
        href="/chat"
        className="group inline-flex shrink-0 items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3.5 py-2 text-sm font-medium text-gray-600 transition hover:border-indigo-300 hover:text-indigo-600 hover:shadow-sm"
      >
        <ArrowLeft className="h-4 w-4 transition-transform duration-200 group-hover:-translate-x-0.5" strokeWidth={2.25} />
        Home
      </Link>
    </div>
  );
}
