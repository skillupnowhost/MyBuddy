export interface Conversation {
  id: string;
  title: string;
  system_prompt: string | null;
  model: string | null;
  rag_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface Source {
  filename: string;
  page_number: number | null;
}

export interface Message {
  id: string;
  role: "system" | "user" | "assistant";
  content: string;
  created_at: string;
  sources?: Source[];
}

export type DocumentStatus = "UPLOADING" | "PROCESSING" | "EMBEDDING" | "READY" | "FAILED";

export interface DocumentItem {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
}
