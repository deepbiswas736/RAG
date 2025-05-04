export interface Document {
  id: string;
  title: string;
  file?: string;
  metadata?: Record<string, any>;
}