export interface Conversation {
  id: string;
  title: string;
  system_prompt: string | null;
  model: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "system" | "user" | "assistant";
  content: string;
  created_at: string;
}
