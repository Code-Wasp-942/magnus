// front_end/src/app/(main)/blueprints/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  Play, 
  X, 
  Search,
  Loader2,
  ScrollText,
  Terminal,
  Bug
} from "lucide-react";
import { client } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { CopyableText } from "@/components/ui/copyable-text";
import { UserAvatar } from "@/components/ui/user-avatar";
import { NumberStepper } from "@/components/ui/number-stepper";

// --- 1. Blueprint Data Definition ---

type BlueprintParamType = 'text' | 'number' | 'select' | 'boolean';

interface BlueprintParam {
  key: string;
  label: string;
  type: BlueprintParamType;
  placeholder?: string;
  defaultValue?: string | number | boolean;
  options?: string[];
  description?: string;
  min?: number; // for number type
  max?: number; // for number type
}

interface Blueprint {
  id: string;
  title: string;
  description: string;
  icon: any;
  color: string;
  params: BlueprintParam[];
  updatedAt: string;
}

const MOCK_DATE = "2025/12/23";

const BLUEPRINTS_DB: Blueprint[] = [
  {
    id: "magnus-debug",
    title: "Magnus Debug",
    description: "Interactive debugging session with configurable timeout and GPU resources.",
    icon: Bug, 
    color: "text-amber-500", // Debug 用琥珀色/黄色比较醒目
    updatedAt: MOCK_DATE,
    params: [
      { 
        key: "user_name", 
        label: "User Name", 
        type: "text", 
        placeholder: "e.g. zycai",
        description: "The linux user to run the debug session" 
      },
      { 
        key: "gpu_count", 
        label: "GPU Count", 
        type: "number", 
        defaultValue: 1,
        min: 0,
        max: 8 
      },
      { 
        key: "timeout", 
        label: "Session Timeout", 
        type: "text", 
        defaultValue: "infinity", 
        placeholder: "e.g. 120 or infinity",
        description: "Integer in minutes (e.g., 60) or 'infinity' for no time limit."
      },
    ]
  }
];

// Mock User
const MAGNUS_USER = {
  id: "system",
  name: "Magnus",
  email: "system@magnus-platform.com",
  avatar_url: "/api/logo"
};

// --- 2. Main Page Component ---

export default function BlueprintsPage() {
  const router = useRouter();
  
  // Table State
  const [displayedBlueprints, setDisplayedBlueprints] = useState<Blueprint[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(true);

  // Dialog State
  const [selectedBlueprint, setSelectedBlueprint] = useState<Blueprint | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [formValues, setFormValues] = useState<Record<string, any>>({});

  // Fetch Data Simulation
  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      let filtered = BLUEPRINTS_DB;
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        filtered = filtered.filter(bp => 
          bp.title.toLowerCase().includes(query) || 
          bp.id.toLowerCase().includes(query) ||
          bp.description.toLowerCase().includes(query)
        );
      }
      setTotalItems(filtered.length);
      const start = (currentPage - 1) * pageSize;
      const end = start + pageSize;
      setDisplayedBlueprints(filtered.slice(start, end));
      setLoading(false);
    }, 100); 
    return () => clearTimeout(timer);
  }, [searchQuery, currentPage, pageSize]);

  // Handlers
  const handleOpenDialog = (bp: Blueprint) => {
    const initialValues: Record<string, any> = {};
    bp.params.forEach(p => {
      initialValues[p.key] = p.defaultValue ?? "";
    });
    setFormValues(initialValues);
    setSelectedBlueprint(bp);
  };

  const handleCloseDialog = () => {
    setSelectedBlueprint(null);
    setIsRunning(false);
  };

  const handleInputChange = (key: string, value: any) => {
    setFormValues(prev => ({ ...prev, [key]: value }));
  };

  const handleRun = async () => {
    if (!selectedBlueprint) return;
    setIsRunning(true);
    try {
      const params = new URLSearchParams(formValues).toString();
      await client(`/api/blueprints/${selectedBlueprint.id}/run?${params}`, {
        method: "GET",
      });
      router.push('/jobs');
    } catch (e) {
      console.error("Failed to run blueprint", e);
      alert("Failed to start the task.");
      setIsRunning(false);
    }
  };

  return (
    <div className="relative min-h-[calc(100vh-8rem)] pb-20">
      <style jsx global>{`
        ::-webkit-scrollbar { display: none; }
        html { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Blueprints Registry
          </h1>
          <p className="text-zinc-500 text-sm mt-1">
            Standardized task templates for reproducible workflows.
          </p>
        </div>
      </div>

      {/* Filters & Search */}
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-1.5 mb-6 flex items-center gap-2 backdrop-blur-sm relative z-20">
        <div className="relative flex-1 group">
           <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 group-focus-within:text-blue-500 transition-colors" />
           <input 
             type="text" 
             value={searchQuery}
             onChange={(e) => {
               setSearchQuery(e.target.value);
               setCurrentPage(1);
             }}
             placeholder="Search Blueprints..." 
             className="w-full bg-transparent border-none py-2.5 pl-9 pr-4 text-sm text-zinc-200 focus:outline-none focus:ring-0 placeholder-zinc-600"
           />
        </div>
      </div>

      {/* Table Area */}
      <div className="border border-zinc-800 rounded-xl bg-zinc-900/30 shadow-sm flex flex-col overflow-hidden min-h-[400px]">
        <div className="overflow-x-auto w-full min-h-[400px]">
          <table className="w-full text-left text-sm whitespace-nowrap table-fixed">
            <thead className="bg-zinc-900/90 text-zinc-500 border-b border-zinc-800 backdrop-blur-md">
              <tr>
                <th className="px-6 py-4 font-medium w-[25%]">Blueprint / ID</th>
                <th className="px-6 py-4 font-medium w-[45%]">Description</th>
                <th className="px-6 py-4 font-medium w-[15%] text-center">Creator / Created at</th>
                <th className="px-6 py-4 font-medium text-right w-[15%]"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {loading ? (
                <tr>
                  <td colSpan={4} className="h-64 text-center text-zinc-500">
                    <div className="flex flex-col items-center gap-3">
                       <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                       <span>Loading registry...</span>
                    </div>
                  </td>
                </tr>
              ) : displayedBlueprints.length === 0 ? (
                <tr>
                  <td colSpan={4} className="h-64 text-center text-zinc-500">
                    <div className="flex flex-col items-center gap-3">
                       <ScrollText className="w-10 h-10 opacity-20" />
                       <span>No blueprints found.</span>
                    </div>
                  </td>
                </tr>
              ) : (
                displayedBlueprints.map((bp) => (
                  <tr 
                    key={bp.id} 
                    onClick={() => handleOpenDialog(bp)}
                    className="hover:bg-zinc-800/40 transition-colors group border-b border-zinc-800/50 last:border-0 cursor-pointer"
                  >
                    <td className="px-6 py-4 align-top whitespace-normal break-all">
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center gap-2">
                          <CopyableText 
                            text={bp.title} 
                            variant="text" 
                            className="font-semibold text-zinc-200 text-base"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                           <CopyableText text={bp.id} className="text-[10px] tracking-wider" />
                        </div>
                      </div>
                    </td>

                    <td className="px-6 py-4 align-top whitespace-normal">
                      <p className="text-zinc-400 text-sm leading-relaxed line-clamp-2">
                        {bp.description}
                      </p>
                    </td>

                    <td className="px-6 py-4 align-top">
                      <div className="flex justify-center">
                        <UserAvatar 
                          user={MAGNUS_USER} 
                          subText={bp.updatedAt} 
                        />
                      </div>
                    </td>

                    <td className="px-6 py-4 align-middle text-right">
                      <div className="flex justify-end opacity-0 group-hover:opacity-100 transition-all transform translate-x-2 group-hover:translate-x-0">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDialog(bp);
                          }}
                          className="flex items-center gap-2 px-3 py-1.5 bg-blue-600/10 hover:bg-blue-600 hover:text-white text-blue-500 rounded-lg transition-colors border border-blue-600/20 shadow-sm"
                        >
                          <Play className="w-3.5 h-3.5 fill-current" />
                          <span className="text-xs font-bold">Run</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalItems > 0 && (
          <div className="px-6 py-2 border-t border-zinc-800 bg-zinc-900/30">
            <PaginationControls 
              currentPage={currentPage}
              totalPages={Math.ceil(totalItems / pageSize)}
              pageSize={pageSize}
              totalItems={totalItems}
              onPageChange={setCurrentPage}
              onPageSizeChange={(newSize) => {
                 setPageSize(newSize);
                 setCurrentPage(1);
              }}
            />
          </div>
        )}
      </div>

      {/* --- Enhanced Run Dialog --- */}
      {selectedBlueprint && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#0c0c0e] border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
            
            {/* Header */}
            <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-900/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-lg bg-zinc-900 border border-zinc-800", selectedBlueprint.color)}>
                  <selectedBlueprint.icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-zinc-100">{selectedBlueprint.title}</h3>
                  <p className="text-xs text-zinc-500">Configure parameters</p>
                </div>
              </div>
              <button onClick={handleCloseDialog} className="text-zinc-500 hover:text-zinc-300 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 space-y-5">
              {selectedBlueprint.params.map((param) => (
                <div key={param.key} className="space-y-1.5">
                  {/* 复用 JobForm 的 Label 样式 */}
                  <label className="text-xs uppercase tracking-wider mb-1.5 block font-medium text-zinc-500">
                    {param.label}
                  </label>
                  
                  {/* 针对不同类型渲染不同组件 */}
                  {param.type === 'number' ? (
                     <NumberStepper
                       label="" // 组件内部有 Label，但我们这里外部统一写了，所以传空或者改组件
                       value={Number(formValues[param.key])}
                       onChange={(val) => handleInputChange(param.key, val)}
                       min={param.min ?? 0}
                       max={param.max ?? 128}
                     />
                  ) : param.type === 'select' ? (
                    <div className="relative">
                      <select
                        value={formValues[param.key]}
                        onChange={(e) => handleInputChange(param.key, e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm text-zinc-200 focus:outline-none focus:border-blue-500 transition-all appearance-none"
                      >
                        {param.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                      </select>
                      <div className="absolute right-3 top-2.5 pointer-events-none text-zinc-500">
                         <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                      </div>
                    </div>
                  ) : (
                    // 默认 Text Input (复用 JobForm 样式)
                    <input
                      type="text"
                      value={formValues[param.key]}
                      onChange={(e) => handleInputChange(param.key, e.target.value)}
                      placeholder={param.placeholder}
                      className="w-full bg-zinc-950 border border-zinc-800 px-3 py-2.5 rounded-lg text-white text-sm focus:border-blue-500 outline-none transition-all placeholder-zinc-700"
                    />
                  )}

                  {/* Description Hint */}
                  {param.description && (
                    <p className="text-[11px] text-zinc-500 mt-1 ml-0.5">
                      {param.description}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 bg-zinc-900/50 border-t border-zinc-800 flex justify-end gap-3">
              <button onClick={handleCloseDialog} disabled={isRunning} className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors">Cancel</button>
              <button onClick={handleRun} disabled={isRunning} className="flex items-center gap-2 px-5 py-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-lg shadow-blue-500/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed">
                {isRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Launching...</> : <><Play className="w-4 h-4 fill-current" /> Start Debug</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}