// front_end/src/components/layout/header.tsx
"use client";

import { useAuth } from "@/context/auth-context";
import { NotificationsPopover } from "./notifications-popover";

export function Header() {
  const { user, isLoading } = useAuth();

  return (
    <header className="h-16 border-b border-zinc-800 bg-zinc-950/50 backdrop-blur sticky top-0 z-40 flex items-center justify-end px-8 gap-4">
      
      {/* Notifications */}
      <NotificationsPopover />

      {/* User Profile Area */}
      {!isLoading && user && (
        <div className="flex items-center gap-3 pl-4 border-l border-zinc-800">
          <div className="text-right hidden md:block">
            <div className="text-sm font-medium text-zinc-200 leading-none mb-1">
                {user.name}
            </div>
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