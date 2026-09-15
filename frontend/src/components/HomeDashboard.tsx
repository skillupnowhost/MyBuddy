import Image from "next/image";
import Link from "next/link";
import { ChevronLeft, ImageIcon, PenLine, Code2, Search, Sparkles, ArrowRight, type LucideIcon } from "lucide-react";
import robotImg from "@/images/AI Agent.png";
import RightPanel from "@/components/RightPanel";
import AnimatedIcon from "@/components/AnimatedIcon";

interface QuickAction {
  title: string;
  description: string;
  icon: LucideIcon;
  href?: string;
  onClick?: () => void;
}

interface HomeDashboardProps {
  displayName: string;
  isAdmin: boolean;
  onPromptSelect: (text: string) => void;
  onOpenDocuments: () => void;
}

const SUGGESTIONS = [
  "Create a 7-day learning plan for React",
  "Write a professional email to a client",
  "Explain how a hash map works, simply",
  "Debug this Python function for me",
  "Summarize what's in my uploaded documents",
  "Give me 5 icebreaker questions for a team meeting",
];

export default function HomeDashboard({ displayName, isAdmin, onPromptSelect, onOpenDocuments }: HomeDashboardProps) {
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
      <section className="grid grid-cols-1 items-center gap-6 lg:grid-cols-2">
        <div>
          <span className="mb-4 inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-500">
            <ChevronLeft className="h-3 w-3" strokeWidth={2.5} /> Your Personal AI Agent
          </span>
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

        <div className="relative mx-auto w-full max-w-sm overflow-hidden rounded-3xl shadow-xl shadow-indigo-100">
          <Image src={robotImg} alt="MyBuddy AI" priority className="h-full w-full object-cover" />
        </div>
      </section>

      <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
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
              className="group flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 transition hover:border-indigo-300 hover:shadow-md"
            >
              {content}
            </Link>
          ) : (
            <button
              key={action.title}
              onClick={action.onClick}
              className="group flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 text-left transition hover:border-indigo-300 hover:shadow-md"
            >
              {content}
            </button>
          );
        })}
      </section>

      <section className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_320px]">
        <div>
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Try asking me...</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => onPromptSelect(s)}
                className="group flex items-center justify-between gap-2 rounded-lg border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 transition hover:border-indigo-300 hover:bg-indigo-50/50"
              >
                {s}
                <ArrowRight className="h-4 w-4 shrink-0 text-gray-300 transition-transform duration-200 group-hover:translate-x-1 group-hover:text-indigo-500" />
              </button>
            ))}
          </div>
        </div>

        <RightPanel isAdmin={isAdmin} />
      </section>
    </div>
  );
}
