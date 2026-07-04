import { Link, useLocation } from "react-router-dom";
import { FolderGit2, Search, Database, Moon, Sun, Settings, LayoutDashboard } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { cn } from "../lib/utils";

export default function Sidebar() {
  const { pathname } = useLocation();
  const { theme, setTheme } = useTheme();

  const links = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Repositories", href: "/", icon: FolderGit2 },
    { name: "Global Search", href: "/", icon: Search },
    { name: "Graph Explorer", href: "/repo/demo", icon: Database },
  ];

  return (
    <aside className="w-64 border-r border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50 backdrop-blur flex flex-col h-full">
      <div className="h-16 flex items-center px-6 border-b border-zinc-200 dark:border-zinc-800">
        <Database className="w-6 h-6 mr-2 text-blue-600 dark:text-blue-400" />
        <span className="font-semibold tracking-tight">RepoRover</span>
      </div>

      <div className="flex-1 overflow-y-auto py-6 px-4 space-y-1">
        {links.map((link) => {
          const isActive = pathname === link.href && link.name === "Dashboard"; // simplified
          const Icon = link.icon;
          return (
            <Link
              key={link.name}
              to={link.href}
              className={cn(
                "flex items-center px-3 py-2 text-sm rounded-md transition-colors",
                isActive
                  ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium"
                  : "text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100"
              )}
            >
              <Icon className="w-4 h-4 mr-3" />
              {link.name}
            </Link>
          );
        })}
      </div>

      <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
        <button className="flex items-center text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
          <Settings className="w-4 h-4 mr-2" />
          Settings
        </button>
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="p-2 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
        >
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </aside>
  );
}
