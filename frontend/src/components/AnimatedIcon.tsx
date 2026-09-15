import type { LucideIcon } from "lucide-react";

interface AnimatedIconProps {
  icon: LucideIcon;
  className?: string;
  strokeWidth?: number;
}

export default function AnimatedIcon({ icon: Icon, className = "h-4 w-4", strokeWidth = 2 }: AnimatedIconProps) {
  return <Icon className={`animated-icon shrink-0 ${className}`} strokeWidth={strokeWidth} aria-hidden="true" />;
}