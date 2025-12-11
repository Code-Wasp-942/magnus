// front_end/src/app/(main)/jobs/page.tsx
"use client";

import { useState, useEffect } from "react";
import { Plus, Search, RefreshCw, Box, Rocket, Loader2, User as UserIcon } from "lucide-react";
import JobForm, { JobFormData } from "@/components/jobs/job-form";
import { SearchableSelect } from "@/components/ui/searchable-select";
import { CopyableText } from "@/components/ui/copyable-text"; // ✅ 复用通用组件
import { client } from "@/lib/api";

// --- Types ---
interface User {
  id: string;
  name: string;
  avatar_url?: string;
}

interface Job {
  id: string; 
  task_name: string;
  description?: string;
  user?: User;
  status: string;
  namespace: string;
  repo_name: string;
  branch: string;
  commit_sha: string;
  gpu_count: number;
  gpu_type: string;
  entry_command: string;
  created_at: string;
}

// --- Components ---
function UserAvatar({ user }: { user?: User }) {
  if (!user) {
    return (
      <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center border border-zinc-700">
         <UserIcon className="w-4 h-4 text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2.5">
      {user.avatar_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img 
          src={user.avatar_url} 
          alt={user.name} 
          className="w-8 h-8 rounded-full border border-zinc-700/50 object-cover shadow-sm"
        />
      ) : (
        <div className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold border border-indigo-500/30">
          {user.name.substring(0, 2).toUpperCase()}
        </div>
      )}
      <div className="flex flex-col">
        <span className="text-sm font-medium text-zinc-200 leading-tight">{user.name}</span>
      </div>
    </div>
  );
}

const USER_FILTER_OPTIONS = [
  { label: "All Users", value: "all" },
  { label: "My Jobs Only", value: "mine" },
];

export default function JobsPage() {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"create" | "clone">("create");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  
  const [userFilter, setUserFilter] = useState("all");
  const [cloneData, setCloneData] = useState<JobFormData | null>(null);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const data = await client("/api/jobs");
      setJobs(data);
    } catch (e) {
      console.error("Backend offline?", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleNewJob = () => {
    setDrawerMode("create");
    setCloneData(null); 
    setSelectedJobId(null);
    setIsDrawerOpen(true);
  };

  const handleCloneJob = (job: Job) => {
    setDrawerMode("clone");
    setSelectedJobId(job.id);
    setCloneData({
        taskName: `${job.task_name}-copy`,
        description: job.description || "",
        namespace: job.namespace, 
        repoName: job.repo_name,
        branch: job.branch,
        commit_sha: job.commit_sha,
        entry_command: job.entry_command,
        gpu_count: job.gpu_count,
        gpu_type: job.gpu_type
    });
    setIsDrawerOpen(true);
  };

  // ! PROTECTED: Must use absolute Beijing Time. Do NOT change.
  const formatBeijingTime = (isoString: string) => {
    if (!isoString) return "--";
    const date = new Date(isoString.endsWith("Z") ? isoString : `${isoString}Z`);
    return date.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/\//g, '-'); 
  };

  return (
    <div className="relative min-h-[calc(100vh-8rem)]">
      
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Job Management
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Monitor and schedule your training workloads.</p>
        </div>
        <button 
          onClick={handleNewJob} 
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors shadow-lg shadow-blue-900/20 active:scale-95 border border-blue-500/50"
        >
          <Plus className="w-4 h-4" /> New Job
        </button>
      </div>

      {/* Filters */}
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-1.5 mb-6 flex items-center gap-2 backdrop-blur-sm">
        <div className="relative flex-1 group">
           <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 group-focus-within:text-blue-500 transition-colors" />
           <input 
             type="text" 
             placeholder="Search tasks..." 
             className="w-full bg-transparent border-none py-2.5 pl-9 pr-4 text-sm text-zinc-200 focus:outline-none focus:ring-0 placeholder-zinc-600"
           />
        </div>
        <div className="h-6 w-px bg-zinc-800"></div>
        <div className="w-48"> 
          <SearchableSelect
             value={userFilter}
             onChange={setUserFilter}
             options={USER_FILTER_OPTIONS}
             placeholder="All Users"
             className="mb-0 border-none bg-transparent" 
          />
        </div>
      </div>

      {/* Table */}
      <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-900/30 min-h-[400px] shadow-sm">
        {loading ? (
           <div className="flex flex-col items-center justify-center h-80 text-zinc-500 gap-3">
             <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
             <p className="text-sm font-medium">Loading jobs...</p>
           </div>
        ) : jobs.length === 0 ? (
           <div className="flex flex-col items-center justify-center h-80 text-zinc-500">
             <div className="w-16 h-16 bg-zinc-800/50 rounded-full flex items-center justify-center mb-4">
                <Box className="w-8 h-8 opacity-40" />
             </div>
             <p className="text-lg font-medium text-zinc-400">No jobs found</p>
             <p className="text-sm mt-1">Get started by creating a new training task.</p>
           </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900/90 text-zinc-500 border-b border-zinc-800 backdrop-blur-md">
              <tr>
                <th className="px-6 py-4 font-medium w-[28%]">Task Details</th>
                <th className="px-6 py-4 font-medium w-[12%]">Status</th>
                <th className="px-6 py-4 font-medium w-[25%]">Code Source</th>
                <th className="px-6 py-4 font-medium w-[15%]">Resources</th>
                <th className="px-6 py-4 font-medium w-[20%]">Creator</th>
                <th className="px-6 py-4 font-medium text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-zinc-800/40 transition-colors group">
                  
                  {/* Task Details */}
                  <td className="px-6 py-4 align-top">
                    <div className="flex flex-col gap-1.5">
                      <span className="font-semibold text-zinc-200 text-base">{job.task_name}</span>
                      <div className="flex items-center gap-2">
                        {/* ✅ 复用组件: Display full ID, customized with tailwind classes */}
                        <CopyableText 
                            text={job.id} 
                            className="text-[10px] uppercase tracking-wider" 
                        />
                      </div>
                      {job.description && (
                        <p className="text-zinc-500 text-xs line-clamp-1 mt-0.5">{job.description}</p>
                      )}
                    </div>
                  </td>

                  {/* Status */}
                  <td className="px-6 py-4 align-top">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border shadow-sm
                      ${job.status === 'Running' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : 
                        job.status === 'Failed' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 
                        job.status === 'Pending' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                        'bg-green-500/10 text-green-400 border-green-500/20'}`}>
                      {job.status === 'Running' && <span className="relative flex h-1.5 w-1.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span><span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500"></span></span>}
                      {job.status}
                    </span>
                  </td>

                  {/* Code Source */}
                  <td className="px-6 py-4 align-top">
                      <div className="flex flex-col gap-1.5">
                          <span className="text-zinc-300 flex items-center gap-2 text-xs font-medium bg-zinc-900/50 w-fit px-2 py-1 rounded border border-zinc-800">
                            <Box className="w-3.5 h-3.5 text-zinc-500"/> 
                            {job.namespace} / {job.repo_name}
                          </span>
                          <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono ml-1">
                             <div className="w-1.5 h-1.5 rounded-full bg-zinc-600"></div>
                             {job.branch}
                             <span className="text-zinc-700">|</span>
                             <span className="bg-zinc-800 px-1.5 rounded text-zinc-400">{job.commit_sha.substring(0, 7)}</span>
                          </div>
                      </div>
                  </td>

                  {/* Resources */}
                  {/* ! PROTECTED: Single line format "Type × Count", do not change. */}
                  <td className="px-6 py-4 align-top">
                      <span className="text-zinc-300 text-sm font-medium">
                          {job.gpu_type === 'CPU' 
                              ? 'CPU Only' 
                              : `${job.gpu_type.replace(/_/g, ' ')} × ${job.gpu_count}`
                          }
                      </span>
                  </td>

                  {/* Creator */}
                  <td className="px-6 py-4 align-top">
                    <div className="flex flex-col gap-2">
                        <UserAvatar user={job.user} />
                        <span className="text-xs text-zinc-500 pl-11 font-mono tracking-tight">
                           {formatBeijingTime(job.created_at)}
                        </span>
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="px-6 py-4 align-middle text-right">
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-all transform translate-x-2 group-hover:translate-x-0">
                      <button 
                          onClick={() => handleCloneJob(job)} 
                          className="p-2 bg-zinc-800 hover:bg-zinc-700 hover:text-white rounded-lg text-zinc-400 transition-colors border border-zinc-700/50 shadow-sm" 
                          title="Clone & Rerun"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Drawer */}
      {isDrawerOpen && (
        <div 
          onClick={() => setIsDrawerOpen(false)} 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[90] transition-opacity" 
        />
      )}

      <div className={`fixed top-0 right-0 h-full w-[600px] bg-[#09090b] border-l border-zinc-800 shadow-2xl z-[100] transform transition-transform duration-300 ease-in-out ${isDrawerOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="h-full flex flex-col relative">
          
          <div className="px-6 py-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50 backdrop-blur-sm">
            <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    {drawerMode === 'create' ? <Rocket className="w-5 h-5 text-blue-500"/> : <RefreshCw className="w-5 h-5 text-purple-500"/>}
                    {drawerMode === 'create' ? "Submit New Job" : `Clone Job`}
                </h2>
                {drawerMode === 'clone' && <p className="text-xs text-zinc-500 mt-1">Configurations pre-filled from previous task</p>}
            </div>
            <button onClick={() => setIsDrawerOpen(false)} className="text-zinc-500 hover:text-white transition-colors bg-zinc-800/50 hover:bg-zinc-700 p-1.5 rounded-md">✕</button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 custom-scrollbar relative">
            <JobForm 
                key={drawerMode + (selectedJobId || "")} 
                mode={drawerMode}
                initialData={cloneData}
                onCancel={() => setIsDrawerOpen(false)}
                onSuccess={() => {
                   setIsDrawerOpen(false);
                   fetchJobs(); 
                }}
            />
          </div>
          
        </div>
      </div>

    </div>
  );
}