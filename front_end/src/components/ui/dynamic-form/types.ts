// front_end/src/components/ui/dynamic-form/types.ts
export type FieldType = "text" | "number" | "boolean" | "select";

export interface FieldSchema {
  key: string;
  label: string;
  type: FieldType;
  default?: any;
  options?: string[]; // 用于 select
  min?: number;       // 用于 number
  max?: number;       // 用于 number
  step?: number;      // 用于 number
  placeholder?: string;
  description?: string;
}