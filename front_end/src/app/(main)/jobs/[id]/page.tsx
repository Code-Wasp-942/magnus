// front_end/src/app/(main)/jobs/[id]/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Terminal, Clock, GitBranch, Cpu, Play, AlertCircle, CheckCircle2, PauseCircle, Box, Copy, Check } from "lucide-react";
import { client } from "@/lib/api";
import { CopyableText } from "@/components/ui/copyable-text";
import { POLL_INTERVAL } from "@/lib/config";

// --- Types (保持与列表页一致) ---
interface Job {
  id: string;
  task_name: string;
  description?: string;
  status: string;
  namespace: string;
  repo_name: string;
  branch: string;
  commit_sha: string;
  gpu_count: number;
  gpu_type: string;
  entry_command: string;
  job_type: string;
  created_at: string;
  slurm_job_id?: string;
}

// 复用 Badge 组件
function JobPriorityBadge({ type }: { type: string }) {
  const isNoble = type && type.startsWith('A');
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-mono font-bold tracking-tight border shadow-sm select-none
      ${isNoble 
        ? 'bg-purple-500/10 text-purple-400 border-purple-500/30' 
        : 'bg-zinc-800/80 text-zinc-400 border-zinc-700/50'
      }`}>
      {type || 'A2'}
    </span>
  );
}

// 状态图标映射
const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case "Running": return <Play className="w-5 h-5 text-blue-500 animate-pulse" />;
    case "Success": return <CheckCircle2 className="w-5 h-5 text-green-500" />;
    case "Failed": return <AlertCircle className="w-5 h-5 text-red-500" />;
    case "Paused": return <PauseCircle className="w-5 h-5 text-orange-500" />;
    default: return <Clock className="w-5 h-5 text-yellow-500" />;
  }
};

// 专门为标题设计的复制组件
function TitleCopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button 
      onClick={handleCopy}
      className="ml-3 p-1.5 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-md transition-all opacity-0 group-hover:opacity-100"
      title="Copy Task Name"
    >
      {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
    </button>
  );
}

export default function JobDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;
  
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  // 1. 获取任务详情
  useEffect(() => {
    const fetchJob = async () => {
      try {
        const data = await client(`/api/jobs/${jobId}`);
        setJob(data);
      } catch (e) {
        console.error("Failed to fetch job", e);
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [jobId]);

  // 2. 轮询日志
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await client(`/api/jobs/${jobId}/logs`);
        const logContent = typeof res === 'string' ? res : (res.logs || res.content || "");
        setLogs(logContent);
      } catch (e) {
        // 忽略错误
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [jobId]);

  // 自动滚动
  useEffect(() => {
    if (logEndRef.current && job?.status === 'Running') {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, job?.status]);

  if (loading) {
    return <div className="flex items-center justify-center h-[50vh] text-zinc-500">Loading Job Context...</div>;
  }

  if (!job) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] text-zinc-500 gap-4">
        <p>Job not found</p>
        <button onClick={() => router.back()} className="text-blue-500 hover:underline">Go Back</button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto pb-20">
      
      {/* 顶部导航 */}
      <div className="mb-8">
        <button 
          onClick={() => router.push('/jobs')} 
          className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm mb-6 group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          Back to Jobs
        </button>

        {/* 顶部 Header 区域 - 优化布局 */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex-1 min-w-0 pr-8"> {/* 增加右侧 padding 防止拥挤 */}
            
            {/* 任务名 & 优先级 */}
            <div className="flex items-center gap-4 mb-3 group">
              <h1 className="text-3xl font-bold text-white tracking-tight break-all leading-tight">
                {job.task_name}
              </h1>
              <div className="flex items-center flex-shrink-0">
                  <JobPriorityBadge type={job.job_type} />
                  {/* 新增：任务名复制按钮 */}
                  <TitleCopyButton text={job.task_name} />
              </div>
            </div>
            
            {/* ID & 时间 */}
            <div className="flex items-center gap-4 text-sm text-zinc-500 font-mono">
              <div className="flex items-center gap-2">
                 <span className="text-zinc-600">ID:</span>
                 <CopyableText text={job.id} variant="id" />
              </div>
              <span className="text-zinc-700">|</span>
              <span className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                {new Date(job.created_at).toLocaleString()}
              </span>
            </div>
          </div>
          
          {/* 状态大卡片 - 保持靠右 */}
          <div className="flex items-center gap-4 bg-zinc-900/50 border border-zinc-800 px-6 py-4 rounded-xl backdrop-blur-sm flex-shrink-0 shadow-lg shadow-black/20">
            <StatusIcon status={job.status} />
            <div className="flex flex-col">
              <span className="text-xs text-zinc-500 uppercase font-bold tracking-wider mb-0.5">Status</span>
              <span className={`text-base font-bold tracking-wide
                ${job.status === 'Running' ? 'text-blue-400' : 
                  job.status === 'Success' ? 'text-green-400' :
                  job.status === 'Failed' ? 'text-red-400' : 'text-zinc-300'}`}>
                {job.status.toUpperCase()}
              </span>
            </div>
            {job.slurm_job_id && (
               <div className="ml-4 pl-6 border-l border-zinc-700/50 flex flex-col">
                  <span className="text-xs text-zinc-500 uppercase font-bold tracking-wider mb-0.5">Slurm ID</span>
                  <span className="text-base font-mono text-zinc-200">#{job.slurm_job_id}</span>
               </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* 左侧：配置详情 */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* 代码信息 */}
          <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-800 bg-zinc-900/50 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-zinc-400" />
              <h3 className="text-sm font-semibold text-zinc-200">Repository</h3>
            </div>
            <div className="p-5 space-y-5">
              
              {/* Repo Name */}
              <div>
                {/* 🟢 修改点：标题作为跳转入口 */}
                <div className="flex items-center gap-2 mb-2">
                    <a 
                        href={`https://github.com/${job.namespace}/${job.repo_name}`} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-xs font-medium uppercase tracking-wider text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1 cursor-pointer transition-colors w-fit"
                        title="Open Repository in GitHub"
                    >
                        Github Repository
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                    </a>
                </div>
                
                {/* 值作为复制区域 (保持干净，只负责显示和复制) */}
                <div className="flex items-center gap-2 text-sm text-zinc-200 bg-zinc-950 px-3 py-2 rounded-lg border border-zinc-800/50 shadow-inner">
                  <Box className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                  <span className="truncate flex-1">{job.namespace} / {job.repo_name}</span>
                  <div className="border-l border-zinc-800 pl-2 ml-1">
                      <CopyableText text={`${job.namespace}/${job.repo_name}`} variant="id" />
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-1 gap-4">
                  
                  {/* Branch */}
                  <div>
                    {/* 🟢 修改点：标题作为跳转入口 */}
                    <div className="flex items-center gap-2 mb-1.5">
                        <a 
                            href={`https://github.com/${job.namespace}/${job.repo_name}/tree/${job.branch}`}
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-xs font-medium uppercase tracking-wider text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1 cursor-pointer w-fit"
                            title="View Branch Tree"
                        >
                            Branch
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                        </a>
                    </div>
                    <div className="text-sm font-mono text-zinc-300 bg-zinc-950/50 px-2 py-1.5 rounded border border-zinc-800/50 flex items-center justify-between">
                        <span className="truncate mr-2">{job.branch}</span>
                        <CopyableText text={job.branch} variant="id" />
                    </div>
                  </div>

                  {/* Commit SHA */}
                  <div>
                    {/* 🟢 修改点：标题作为跳转入口 */}
                    <div className="flex items-center gap-2 mb-1.5">
                        <a 
                            href={`https://github.com/${job.namespace}/${job.repo_name}/commit/${job.commit_sha}`}
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-xs font-medium uppercase tracking-wider text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1 cursor-pointer w-fit"
                            title="View Commit Details"
                        >
                            Commit SHA
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                        </a>
                    </div>
                    <div className="text-sm font-mono text-zinc-400 bg-zinc-950/50 px-2 py-1.5 rounded border border-zinc-800/50 flex items-center justify-between">
                        <span className="truncate mr-2">{job.commit_sha.substring(0, 7)}...</span>
                        <CopyableText text={job.commit_sha} variant="id" />
                    </div>
                  </div>

              </div>

            </div>
          </div>

          {/* 资源配置 */}
          <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-800 bg-zinc-900/50 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-zinc-400" />
              <h3 className="text-sm font-semibold text-zinc-200">Resources</h3>
            </div>
            <div className="p-5 grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-zinc-500 font-medium uppercase tracking-wider block mb-1.5">Accelerator</label>
                <span className="text-base text-white font-medium block">
                   {job.gpu_type === 'CPU' ? 'CPU Only' : job.gpu_type}
                </span>
              </div>
              <div>
                <label className="text-xs text-zinc-500 font-medium uppercase tracking-wider block mb-1.5">Quantity</label>
                <span className="text-base text-white font-medium block">{job.gpu_count} GPUs</span>
              </div>
            </div>
          </div>

           {/* 入口命令 */}
           <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-800 bg-zinc-900/50 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-zinc-400" />
              <h3 className="text-sm font-semibold text-zinc-200">Entry Command</h3>
            </div>
            <div className="p-4 bg-zinc-950 min-h-[80px]">
              <CopyableText 
                text={job.entry_command} 
                variant="text" 
                className="text-xs font-mono text-green-400 leading-relaxed" 
              />
            </div>
          </div>

        </div>

        {/* 右侧：实时日志 */}
        <div className="lg:col-span-2 flex flex-col h-[650px] bg-[#0c0c0e] border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
          <div className="px-5 py-3 border-b border-zinc-800 bg-zinc-900/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
               <Terminal className="w-4 h-4 text-zinc-400" />
               <h3 className="text-sm font-semibold text-zinc-200">Console Output</h3>
               {/* 正在跑的时候显示个呼吸灯，提示用户这是"活"的 */}
               {job.status === 'Running' && (
                  <span className="flex h-2 w-2 ml-2 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
               )}
            </div>
            
            {/* Running 时提示正在自动刷新 */}
            {job.status === 'Running' && (
                <div className="text-xs text-zinc-500 font-medium flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500/50"></span>
                    Live
                </div>
            )}
          </div>
          
          <div className="flex-1 overflow-auto p-5 custom-scrollbar font-mono text-xs leading-5">
            {logs ? (
              <pre className="text-zinc-300 whitespace-pre-wrap break-all">
                {logs}
              </pre>
            ) : (
               <div className="h-full flex flex-col items-center justify-center text-zinc-600 gap-3">
                  <Terminal className="w-10 h-10 opacity-20" />
                  <p>Waiting for output...</p>
               </div>
            )}
            <div ref={logEndRef} />
          </div>
        </div>

      </div>
    </div>
  );
}