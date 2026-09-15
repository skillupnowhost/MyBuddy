export default function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-1" aria-label="MyBuddy is thinking">
      <span className="h-2 w-2 rounded-full bg-indigo-400 animate-dot-bounce" style={{ animationDelay: "0ms" }} />
      <span className="h-2 w-2 rounded-full bg-indigo-400 animate-dot-bounce" style={{ animationDelay: "150ms" }} />
      <span className="h-2 w-2 rounded-full bg-indigo-400 animate-dot-bounce" style={{ animationDelay: "300ms" }} />
    </div>
  );
}
