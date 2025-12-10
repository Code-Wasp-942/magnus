// front_end/src/components/layout/header.tsx
"use client";

import { Bell, User as UserIcon } from "lucide-react";
import { useAuth } from "@/context/auth-context"; // ✅ 引入 Auth Context

export function Header() {
  const { user, isLoading } = useAuth(); // ✅ 获取真实用户状态

  return (
    <header className="h-16 border-b border-zinc-800 bg-zinc-950/50 backdrop-blur sticky top-0 z-40 flex items-center justify-end px-8 gap-4">
      
      {/* Notifications - 暂时保留静态，未来可接后端 */}
      <button className="p-2 text-zinc-400 hover:text-white transition-colors relative">
        <Bell className="w-4 h-4" />
        <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full"></span>
      </button>

      {/* User Profile Area */}
      {/* 只有在非加载状态且用户已登录时才显示 */}
      {!isLoading && user && (
        <div className="flex items-center gap-3 pl-4 border-l border-zinc-800">
          <div className="text-right hidden md:block">
            {/* ✅ 真实姓名 */}
            <div className="text-sm font-medium text-zinc-200 leading-none mb-1">
                {user.name}
            </div>
            {/* ✅ 用 Email 或 Namespace 代替 Researcher */}
            <div className="text-xs text-zinc-500 font-mono">
                {user.email || "PKU-Plasma"}
            </div>
          </div>
          
          <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700/50 flex items-center justify-center text-zinc-400 overflow-hidden shadow-sm">
            {user.avatar_url ? (
               // eslint-disable-next-line @next/next/no-img-element
               <img src={user.avatar_url} alt={user.name} className="w-full h-full object-cover" />
            ) : (
               <span className="text-xs font-bold">{user.name.substring(0, 1).toUpperCase()}</span>
            )}
          </div>
        </div>
      )}
    </header>
  );
}