export interface Conversation {
  id: string;
  title: string;
  system_prompt: string | null;
  model: string | null;
  rag_enabled: boolean;
  tools_enabled: boolean;
  code_project_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Source {
  filename: string;
  page_number: number | null;
  lines?: string | null;
}

export interface ImageItem {
  id: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Message {
  id: string;
  role: "system" | "user" | "assistant";
  content: string;
  created_at: string;
  sources?: Source[];
  toolCall?: string;
  images?: ImageItem[];
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

export interface MemoryItem {
  id: string;
  content: string;
  source: "manual" | "auto";
  created_at: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  role: "USER" | "ADMIN";
  created_at: string;
}

export type DatasetStatus = "UPLOADED" | "VALIDATED" | "INVALID";

export interface DatasetItem {
  id: string;
  filename: string;
  num_examples: number | null;
  status: DatasetStatus;
  error_message: string | null;
  created_at: string;
}

export type TrainingJobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface TrainingJobItem {
  id: string;
  dataset_id: string;
  base_model: string;
  status: TrainingJobStatus;
  config: Record<string, unknown>;
  output_path: string | null;
  error_message: string | null;
  eval_metrics: Record<string, number> | null;
  created_at: string;
  completed_at: string | null;
}

export type ModelStatus = "EXPERIMENTAL" | "CANARY" | "STAGING" | "PRODUCTION" | "ARCHIVED" | "REJECTED";

export interface RegisteredModelItem {
  id: string;
  name: string;
  version: string;
  base_model: string;
  capability: string;
  quantization: string | null;
  location: string;
  status: ModelStatus;
  eval_score: number | null;
  promoted_at: string | null;
  created_at: string;
}

export interface AdminUserItem {
  id: string;
  email: string;
  role: "USER" | "ADMIN";
  created_at: string;
}

export interface AdminStats {
  total_users: number;
  total_conversations: number;
  total_messages: number;
  total_documents: number;
  total_memories: number;
  total_training_jobs: number;
}

export type CodeProjectStatus = "UPLOADING" | "EXTRACTING" | "EMBEDDING" | "READY" | "FAILED";

export interface CodeProjectItem {
  id: string;
  name: string;
  status: CodeProjectStatus;
  file_count: number;
  total_size_bytes: number;
  error_message: string | null;
  created_at: string;
}

export interface CodeFileItem {
  id: string;
  relative_path: string;
  language: string | null;
  size_bytes: number;
}

export interface CodeFileContentItem extends CodeFileItem {
  content: string;
}

export type CodeExecutionStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "TIMEOUT" | "CANCELLED";

export interface CodeExecutionItem {
  id: string;
  language: string;
  status: CodeExecutionStatus;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  stdout_truncated: boolean;
  stderr_truncated: boolean;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ModelsResponse {
  models: string[];
  default_model: string;
  code_model: string;
  vision_model: string;
}

export type ImageGenerationStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface ImageGenerationJobItem {
  id: string;
  prompt: string;
  negative_prompt: string | null;
  width: number;
  height: number;
  steps: number;
  seed: number | null;
  status: ImageGenerationStatus;
  image_id: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export type ImageEditOperation = "INPAINT" | "OUTPAINT" | "REMOVE_BACKGROUND";
export type ImageEditJobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface ImageEditJobItem {
  id: string;
  operation: ImageEditOperation;
  source_image_id: string | null;
  mask_image_id: string | null;
  prompt: string | null;
  negative_prompt: string | null;
  steps: number | null;
  params: Record<string, number>;
  status: ImageEditJobStatus;
  result_image_id: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export type VectorObjectType = "RECT" | "CIRCLE" | "ELLIPSE" | "LINE" | "POLYGON" | "PATH" | "TEXT";
export type VectorDocumentPurpose = "GENERAL" | "ILLUSTRATION" | "LOGO" | "ICON";

export interface VectorObjectItem {
  id: string;
  object_type: VectorObjectType;
  z_index: number;
  layer_name: string;
  props: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface VectorDocumentItem {
  id: string;
  title: string;
  purpose: VectorDocumentPurpose;
  canvas_width: number;
  canvas_height: number;
  background_color: string | null;
  objects: VectorObjectItem[];
  created_at: string;
  updated_at: string;
}

export type AnimationEasing = "LINEAR" | "EASE_IN" | "EASE_OUT" | "EASE_IN_OUT";

export interface AnimationKeyframeItem {
  id: string;
  object_id: string;
  time_ms: number;
  prop: string;
  value: number | string;
  easing: AnimationEasing;
  created_at: string;
}

export interface AnimationDocumentItem {
  id: string;
  vector_document_id: string;
  title: string;
  frame_rate: number;
  duration_ms: number;
  loop: boolean;
  keyframes: AnimationKeyframeItem[];
  created_at: string;
  updated_at: string;
}

export interface MotionClipItem {
  id: string;
  animation_document_id: string;
  start_offset_ms: number;
  x_offset: number;
  y_offset: number;
  z_index: number;
  created_at: string;
}

export interface MotionProjectItem {
  id: string;
  title: string;
  canvas_width: number;
  canvas_height: number;
  total_duration_ms: number;
  loop: boolean;
  clips: MotionClipItem[];
  created_at: string;
  updated_at: string;
}

export interface SystemHealth {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  ram_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  disk_percent: number;
  database_ok: boolean;
  llm_ok: boolean;
}
