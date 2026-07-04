import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { Plus, FolderGit2, Search, ArrowRight, Activity, GitBranch } from "lucide-react";

export default function Dashboard() {
  const [search, setSearch] = useState("");
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRepos = async () => {
      try {
        const response = await axios.get("http://localhost:5000/api/repos");
        setRepos(response.data);
      } catch (error) {
        console.error("Failed to fetch repositories:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchRepos();
  }, []);

  const filteredRepos = repos.filter(repo => repo.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex-1 flex flex-col h-full bg-white dark:bg-zinc-950 text-zinc-950 dark:text-zinc-50 overflow-y-auto">
      <header className="px-8 py-6 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Workspaces</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Manage and query your indexed repositories.</p>
          </div>
          <button className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950 dark:focus-visible:ring-zinc-300 bg-zinc-900 dark:bg-zinc-50 text-zinc-50 dark:text-zinc-900 shadow hover:bg-zinc-900/90 dark:hover:bg-zinc-50/90 h-9 px-4 py-2">
            <Plus className="w-4 h-4 mr-2" />
            Add Repository
          </button>
        </div>
      </header>

      <div className="p-8">
        <div className="relative mb-6">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500 dark:text-zinc-400" />
          <input
            type="text"
            placeholder="Search repositories..."
            className="flex h-9 w-full md:w-[300px] rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-zinc-500 dark:placeholder:text-zinc-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950 dark:focus-visible:ring-zinc-300 pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="grid gap-4">
          {loading ? (
            <div className="text-zinc-500 text-sm">Loading repositories...</div>
          ) : filteredRepos.length === 0 ? (
            <div className="text-zinc-500 text-sm">No repositories found. Add one to get started.</div>
          ) : (
            filteredRepos.map((repo) => (
              <div
                key={repo.id}
              className="group flex flex-col sm:flex-row sm:items-center justify-between p-6 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 text-zinc-950 dark:text-zinc-50 shadow-sm hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-full bg-zinc-100 dark:bg-zinc-900 flex items-center justify-center">
                  <FolderGit2 className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg flex items-center gap-2">
                    {repo.name}
                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-950 border-transparent bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100">
                      {repo.status}
                    </span>
                  </h3>
                  <div className="flex items-center text-sm text-zinc-500 dark:text-zinc-400 mt-1 gap-4">
                    <span className="flex items-center gap-1">
                      <GitBranch className="h-3.5 w-3.5" />
                      {repo.branch}
                    </span>
                    <span className="flex items-center gap-1">
                      <Activity className="h-3.5 w-3.5" />
                      {repo.lastSync}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-4 sm:mt-0 flex items-center gap-6">
                <div className="flex items-center gap-4 text-sm text-zinc-500 dark:text-zinc-400">
                  <div className="flex flex-col items-end">
                    <span className="font-medium text-zinc-900 dark:text-zinc-100">{repo.nodes}</span>
                    <span className="text-xs">Nodes</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="font-medium text-zinc-900 dark:text-zinc-100">{repo.edges}</span>
                    <span className="text-xs">Edges</span>
                  </div>
                </div>
                <Link
                  to={`/repo/${repo.id}`}
                  className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950 dark:focus-visible:ring-zinc-300 border border-zinc-200 dark:border-zinc-800 bg-transparent shadow-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-50 h-9 px-4 py-2 opacity-0 group-hover:opacity-100"
                >
                  Explore <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </div>
            </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
