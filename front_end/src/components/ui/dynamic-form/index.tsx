// front_end/src/components/ui/dynamic-form/index.tsx
import React from "react";
import { Terminal, Loader2 } from "lucide-react";
import { NumberStepper } from "@/components/ui/number-stepper";
import { FieldSchema } from "./types";

interface DynamicFormProps {
  schema: FieldSchema[];
  values: Record<string, any>;
  onChange: (key: string, value: any) => void;
  isLoading?: boolean;
  emptyMessage?: string;
}

export function DynamicForm({
  schema,
  values,
  onChange,
  isLoading = false,
  emptyMessage = "No parameters required.",
}: DynamicFormProps) {
  
  if (isLoading) {
    return (
      <div className="py-10 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-600" />
      </div>
    );
  }

  if (schema.length === 0) {
    return <div className="text-center text-zinc-500 py-4">{emptyMessage}</div>;
  }

  return (
    <div className="space-y-5">
      {schema.map((field) => (
        <div key={field.key} className="space-y-1.5">
          <label className="text-xs uppercase tracking-wider mb-1.5 block font-medium text-zinc-500">
            {field.label || field.key}
          </label>

          {/* 1. 数字类型 */}
          {field.type === "number" ? (
            <NumberStepper
              label=""
              value={Number(values[field.key])}
              onChange={(val) => onChange(field.key, val)}
              min={field.min}
              max={field.max}
            />
          ) : field.type === "select" ? (
            /* 2. 下拉选择类型 (包含未来的 Literal 支持基础) */
            <div className="relative">
              <select
                value={values[field.key]}
                onChange={(e) => onChange(field.key, e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm text-zinc-200 focus:outline-none focus:border-blue-500 transition-all appearance-none"
              >
                {field.options?.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <div className="absolute right-3 top-3 pointer-events-none text-zinc-500">
                <Terminal className="w-4 h-4" />
              </div>
            </div>
          ) : field.type === "boolean" ? (
            /* 3. 布尔类型 */
            <select
              value={String(values[field.key])}
              onChange={(e) => onChange(field.key, e.target.value === "true")}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm text-zinc-200 focus:outline-none focus:border-blue-500 transition-all appearance-none"
            >
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          ) : (
            /* 4. 默认文本类型 */
            <input
              type="text"
              value={values[field.key]}
              onChange={(e) => onChange(field.key, e.target.value)}
              placeholder={field.placeholder}
              className="w-full bg-zinc-950 border border-zinc-800 px-3 py-2.5 rounded-lg text-white text-sm focus:border-blue-500 outline-none transition-all placeholder-zinc-700"
            />
          )}

          {/* 描述信息 */}
          {field.description && (
            <p className="text-[11px] text-zinc-500 mt-1 ml-0.5">
              {field.description}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}