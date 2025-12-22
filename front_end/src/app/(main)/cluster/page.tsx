// front_end/src/app/(main)/cluster/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { Activity, Server, Clock, Cpu } from "lucide-react";
import { client } from "@/lib/api";
import { Job } from "@/types/job";
import { POLL_INTERVAL } from "@/lib/config";
import { JobDrawer } from "@/components/jobs/job-drawer";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";

// Refactoring Imports
import { useJobOperations } from "@/hooks/use-job-operations";
import { JobTable } from "@/components/jobs/job-table";

interface ClusterStats {
  resources: {
    node: string;
    gpu_model: string;
    total: number;
    free: number;
    used: number;
  };
  running_jobs: Job[];
  pending_jobs: Job[];
}

export default function ClusterPage() {
  const [stats, setStats] = useState<ClusterStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    try {
      const data = await client("/api/cluster/stats");
      setStats(data);
    } catch (e) {
      console.error("Failed to fetch cluster stats", e);
    } finally {
      if (!isBackground) setLoading(false);
    }
  }, []);

  // Hook 注入
  const { 
    drawerProps, 
    terminateDialogProps, 
    handleCloneJob, 
    onClickTerminate 
  } = useJobOperations({ onSuccess: fetchStats });

  useEffect(() => {
    fetchStats();
    const interval = setInterval(() => fetchStats(true), POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStats]);

  if (loading && !stats) {
    return <div className="p-8 text-zinc-500">Loading cluster status...</div>;
  }

  if (!stats) return null;

  return (
    <div className="pb-20 relative">
      <style jsx global>{`
        ::-webkit-scrollbar { display: none; }
        html { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">Cluster Status</h1>
        <p className="text-zinc-500 text-sm mt-1">Real-time resource monitoring and queue status.</p>
      </div>

      {/* Resource Cards (保留) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
        <div className="bg-zinc-900/40 border border-zinc-800 p-5 rounded-xl backdrop-blur-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity"><Cpu className="w-24 h-24 text-emerald-500" /></div>
          <div className="relative z-10">
            <div className="flex items-center gap-2 text-emerald-400 mb-2"><Activity className="w-4 h-4" /><span className="text-sm font-bold uppercase tracking-wider">Available GPUs</span></div>
            <div className="flex items-baseline gap-2"><span className="text-4xl font-bold text-white">{stats.resources.free}</span><span className="text-zinc-500 text-sm">/ {stats.resources.total}</span></div>
            <div className="mt-3 flex items-center gap-2 text-xs text-zinc-400 font-mono bg-zinc-800/50 w-fit px-2 py-1 rounded"><Server className="w-3 h-3" />{stats.resources.node} · {stats.resources.gpu_model}</div>
          </div>
        </div>
        <div className="bg-zinc-900/40 border border-zinc-800 p-5 rounded-xl backdrop-blur-sm">
          <div className="flex items-center gap-2 text-blue-400 mb-2"><Activity className="w-4 h-4" /><span className="text-sm font-bold uppercase tracking-wider">Active Jobs</span></div>
          <div className="text-4xl font-bold text-white">{stats.running_jobs.length}</div>
          <p className="text-zinc-500 text-xs mt-2">Currently executing on cluster</p>
        </div>
        <div className="bg-zinc-900/40 border border-zinc-800 p-5 rounded-xl backdrop-blur-sm">
          <div className="flex items-center gap-2 text-amber-400 mb-2"><Clock className="w-4 h-4" /><span className="text-sm font-bold uppercase tracking-wider">Queue Depth</span></div>
          <div className="text-4xl font-bold text-white">{stats.pending_jobs.length}</div>
          <p className="text-zinc-500 text-xs mt-2">Jobs waiting for resources</p>
        </div>
      </div>

      <div className="flex flex-col gap-10">
        {/* Running Jobs Table */}
        <div className="flex flex-col gap-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>Running Jobs</h2>
          <JobTable 
             jobs={stats.running_jobs}
             loading={false} // Stats 整体 loading，这里不需要单独 loading
             onClone={handleCloneJob}
             onTerminate={onClickTerminate}
             emptyMessage="No running jobs."
             className="min-h-[175px]"
          />
        </div>

        {/* Pending Jobs Table */}
        <div className="flex flex-col gap-4">
           <h2 className="text-lg font-bold text-white flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-amber-500"></span>Queued Jobs</h2>
           <JobTable 
             jobs={stats.pending_jobs}
             loading={false}
             onClone={handleCloneJob}
             onTerminate={onClickTerminate}
             emptyMessage="Queue is empty."
             className="min-h-[175px]"
          />
        </div>
      </div>

      {/* Dialogs */}
      <JobDrawer {...drawerProps} />
      <ConfirmationDialog {...terminateDialogProps} />
    </div>
  );
}