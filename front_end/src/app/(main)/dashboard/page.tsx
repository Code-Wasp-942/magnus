// front_end/src/app/(main)/dashboard/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { Zap, Plus, Activity, Cpu, Clock, CalendarDays } from "lucide-react"; 
import { client } from "@/lib/api";
import { Job } from "@/types/job";
import { POLL_INTERVAL } from "@/lib/config";
import { useAuth } from "@/context/auth-context";
import { JobDrawer } from "@/components/jobs/job-drawer";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";

// Refactoring Imports
import { useJobOperations } from "@/hooks/use-job-operations";
import { JobTable } from "@/components/jobs/job-table";

interface DashboardStats {
  total_occupancy_24h: number;
  total_occupancy_7d: number;
  magnus_utilization_24h: number;
  magnus_utilization_7d: number;
}

function StatCard({ 
  label, value, subLabel, icon: Icon, colorClass 
}: { 
  label: string; value: number | null; subLabel: string; icon: any; colorClass: string 
}) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 flex items-start justify-between shadow-sm backdrop-blur-sm hover:border-zinc-700 transition-colors">
      <div>
        <p className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-1">{label}</p>
        <div className="flex items-baseline gap-2">
          {value === null ? (
            <div className="h-8 w-16 bg-zinc-800 animate-pulse rounded my-1" />
          ) : (
            <h3 className="text-2xl font-bold text-zinc-100">{(value * 100).toFixed(1)}%</h3>
          )}
        </div>
        <p className="text-zinc-500 text-xs mt-1">{subLabel}</p>
      </div>
      <div className={`p-2 rounded-lg ${colorClass} bg-opacity-10`}>
        <Icon className={`w-5 h-5 ${colorClass.replace("bg-", "text-")}`} />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user: currentUser } = useAuth();
  
  const [activeJobs, setActiveJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboardData = useCallback(async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    try {
      const [jobsData, statsData] = await Promise.all([
        client("/api/dashboard/my-active-jobs"),
        client("/api/dashboard/stats").catch(e => {
            console.warn("Failed to fetch stats", e);
            return null;
        })
      ]);
      setActiveJobs(jobsData);
      if (statsData) setStats(statsData);
    } catch (e) {
      console.error("Failed to fetch dashboard data", e);
    } finally {
      if (!isBackground) setLoading(false);
    }
  }, []);

  // Hook 注入
  const { 
    drawerProps, 
    terminateDialogProps, 
    handleNewJob, 
    handleCloneJob, 
    onClickTerminate 
  } = useJobOperations({ onSuccess: fetchDashboardData });

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(() => fetchDashboardData(true), POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  return (
    <div className="pb-20 relative min-h-[calc(100vh-8rem)]">
      <style jsx global>{`
        ::-webkit-scrollbar { display: none; }
        html { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>

      <div className="mb-8 flex items-center justify-between">
        <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">Dashboard</h1>
            <p className="text-zinc-500 text-sm mt-1">Welcome back, {currentUser?.name}. Here is your workload overview.</p>
        </div>
        <button 
          onClick={handleNewJob} 
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors shadow-lg shadow-blue-900/20 active:scale-95 border border-blue-500/50"
        >
          <Plus className="w-4 h-4" /> New Job
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Occupancy (24h)" value={stats?.total_occupancy_24h ?? null} subLabel="All Slurm Tasks" icon={Activity} colorClass="bg-emerald-500 text-emerald-500" />
        <StatCard label="Total Occupancy (7d)" value={stats?.total_occupancy_7d ?? null} subLabel="All Slurm Tasks" icon={CalendarDays} colorClass="bg-teal-500 text-teal-500" />
        <StatCard label="Magnus Utilization (24h)" value={0.0} subLabel="Platform Managed（施工中）" icon={Cpu} colorClass="bg-blue-500 text-blue-500" />
        <StatCard label="Magnus Utilization (7d)" value={0.0} subLabel="Platform Managed（施工中）" icon={Clock} colorClass="bg-indigo-500 text-indigo-500" />
      </div>

      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2 text-zinc-200 font-semibold text-lg">
            <Zap className="w-5 h-5 text-yellow-500 fill-yellow-500/20" />
            My Active Jobs
        </div>
        
        {/* Replaced Active Tasks Table */}
        <JobTable 
          jobs={activeJobs}
          loading={loading && activeJobs.length === 0}
          onClone={handleCloneJob}
          onTerminate={onClickTerminate}
          emptyMessage="No active jobs."
        />
      </div>

      {/* Dialogs */}
      <JobDrawer {...drawerProps} />
      <ConfirmationDialog {...terminateDialogProps} />
    </div>
  );
}