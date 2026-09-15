import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { ImageIcon, PenLine, Code2, Search, Sparkles, type LucideIcon } from "lucide-react";
import robotImg from "@/images/AI Agent.png";
import AnimatedIcon from "@/components/AnimatedIcon";
import QuickCreatePanel from "@/components/QuickCreatePanel";

interface QuickAction {
  title: string;
  description: string;
  icon: LucideIcon;
  href?: string;
  onClick?: () => void;
}

interface HomeDashboardProps {
  displayName: string;
  onPromptSelect: (text: string) => void;
  onOpenDocuments: () => void;
}

export default function HomeDashboard({ displayName, onPromptSelect, onOpenDocuments }: HomeDashboardProps) {
  // Collapses once the user starts a Quick Create request, so the panel and its result get
  // the room the greeting was taking up — reappears if they clear back out to a clean idle
  // state (see QuickCreatePanel's hasActivity effect).
  const [heroHidden, setHeroHidden] = useState(false);

  const quickActions: QuickAction[] = [
    { title: "Create Image", description: "Generate stunning images from your ideas", icon: ImageIcon, href: "/image" },
    {
      title: "Write & Edit",
      description: "Draft, improve, or rewrite anything",
      icon: PenLine,
      onClick: () => onPromptSelect(""),
    },
    { title: "Code", description: "Build, debug, and get help with code", icon: Code2, href: "/code" },
    { title: "Research", description: "Ask questions grounded in your documents", icon: Search, onClick: onOpenDocuments },
    { title: "More Agents", description: "Explore the Creative Director & tools", icon: Sparkles, href: "/creative" },
  ];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-8">
      <div
        aria-hidden={heroHidden}
        className={`grid transition-[grid-template-rows,opacity,margin] duration-500 ease-in-out ${
          // The negative bottom margin cancels out the parent's gap-10 while collapsed —
          // otherwise a 2.5rem gap would linger where the hero used to be even at 0 height.
          heroHidden ? "grid-rows-[0fr] opacity-0 -mb-10" : "grid-rows-[1fr] opacity-100 mb-0"
        }`}
      >
        <section className="grid grid-cols-1 items-center gap-6 overflow-hidden lg:grid-cols-2">
          <div>
            <h1 className="text-4xl font-semibold leading-tight text-gray-900 sm:text-5xl">
              Hello {displayName},
              <br />
              How can I help you today?
            </h1>
            <p className="mt-2 bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-3xl font-bold text-transparent sm:text-4xl">
              MyBuddy
            </p>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-gray-500">
              Ask me anything, solve problems, write code, generate images, or just chat. I&apos;m here to be your AI
              companion &mdash; always, and entirely on your own hardware.
            </p>
          </div>

          <div className="relative mx-auto w-full max-w-md">
            <Image src={robotImg} alt="MyBuddy AI" priority className="h-full w-full object-contain" />
          </div>
        </section>
      </div>

      <QuickCreatePanel onActivityChange={setHeroHidden} />

      <section className="thin-scroll flex snap-x gap-4 overflow-x-auto pb-1">
        {quickActions.map((action) => {
          const Icon = action.icon;
          const content = (
            <>
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 transition-transform duration-200 group-hover:scale-110">
                <AnimatedIcon icon={Icon} className="h-[18px] w-[18px] text-indigo-600" />
              </span>
              <span className="text-sm font-medium text-gray-900">{action.title}</span>
              <span className="text-xs leading-snug text-gray-500">{action.description}</span>
            </>
          );
          return action.href ? (
            <Link
              key={action.title}
              href={action.href}
              className="group flex w-44 shrink-0 snap-start flex-col gap-2 rounded-2xl border border-gray-200 bg-white p-4 transition hover:border-indigo-300 hover:shadow-md sm:w-48"
            >
              {content}
            </Link>
          ) : (
            <button
              key={action.title}
              onClick={action.onClick}
              className="group flex w-44 shrink-0 snap-start flex-col gap-2 rounded-2xl border border-gray-200 bg-white p-4 text-left transition hover:border-indigo-300 hover:shadow-md sm:w-48"
            >
              {content}
            </button>
          );
        })}
      </section>
    </div>
  );
}
