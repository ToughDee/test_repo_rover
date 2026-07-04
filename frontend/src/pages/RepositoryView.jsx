import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import axios from "axios";
import { MessageSquare, Maximize2, Minimize2, Send, Terminal, Loader2 } from "lucide-react";
import { useTheme } from "../components/ThemeProvider";

export default function RepositoryView() {
  const { repoId } = useParams();
  const { theme } = useTheme();
  
  const [messages, setMessages] = useState([
    { role: "assistant", content: `Hi! I'm RepoRover. Ask me anything about the ${repoId} architecture, dependencies, or execution flows.` }
  ]);
  const [input, setInput] = useState("");
  const [isChatExpanded, setIsChatExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [isGraphLoading, setIsGraphLoading] = useState(true);
  
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        setIsGraphLoading(true);
        const res = await axios.get(`http://localhost:5000/api/graph/${repoId}`);
        setGraphData(res.data);
      } catch (error) {
        console.error("Failed to load graph:", error);
      } finally {
        setIsGraphLoading(false);
      }
    };
    fetchGraph();
  }, [repoId]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await axios.post("http://localhost:5000/api/query", {
        repoId,
        question: userMsg.content
      });
      setMessages((prev) => [...prev, { 
        role: "assistant", 
        content: res.data.answer 
      }]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [...prev, { 
        role: "assistant", 
        content: "Sorry, I encountered an error communicating with the agent." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const getGraphColors = () => {
    return {
      bg: theme === 'dark' ? '#09090b' : '#ffffff',
      text: theme === 'dark' ? '#a1a1aa' : '#71717a',
      link: theme === 'dark' ? '#27272a' : '#e4e4e7',
      node1: theme === 'dark' ? '#3b82f6' : '#2563eb', // blue
      node2: theme === 'dark' ? '#10b981' : '#059669', // green
      node3: theme === 'dark' ? '#f59e0b' : '#d97706', // amber
    }
  }

  const colors = getGraphColors();

  return (
    <div className="flex h-full w-full bg-white dark:bg-zinc-950 text-zinc-950 dark:text-zinc-50 relative overflow-hidden">
      
      {/* Graph Section */}
      <div className={`flex-1 transition-all duration-300 ${isChatExpanded ? 'hidden' : 'block'}`}>
        <div className="absolute top-4 left-4 z-10 bg-white/80 dark:bg-zinc-950/80 backdrop-blur border border-zinc-200 dark:border-zinc-800 p-3 rounded-md shadow-sm">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Terminal className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            {repoId} / Graph Explorer
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Interactive AST & Dependency Graph</p>
        </div>
        
        {isGraphLoading ? (
          <div className="flex items-center justify-center h-full text-zinc-500">
            <Loader2 className="w-8 h-8 animate-spin" />
          </div>
        ) : graphData.nodes.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-500 flex-col">
            <Terminal className="w-12 h-12 mb-2 text-zinc-400" />
            <p>No graph data found for this repository.</p>
          </div>
        ) : (
          <ForceGraph2D
            graphData={graphData}
            backgroundColor={colors.bg}
            linkColor={() => colors.link}
            nodeColor={(n) => n.group === 1 ? colors.node1 : n.group === 2 ? colors.node2 : colors.node3}
            nodeLabel="label"
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
            onNodeClick={(node) => {
              setInput(`Explain ${node.label}`);
            }}
          />
        )}
      </div>

      {/* Chat Section */}
      <div 
        className={`border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex flex-col transition-all duration-300 ease-in-out shadow-[-10px_0_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[-10px_0_30px_-15px_rgba(0,0,0,0.5)]
          ${isChatExpanded ? 'w-full max-w-4xl mx-auto border-l-0 shadow-none' : 'w-[400px]'}`
        }
      >
        <div className="h-14 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between px-4">
          <h3 className="font-medium flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            LangGraph Agent
          </h3>
          <button 
            onClick={() => setIsChatExpanded(!isChatExpanded)}
            className="p-1.5 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 transition-colors"
          >
            {isChatExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div 
                className={`max-w-[85%] rounded-lg p-3 text-sm 
                  ${msg.role === 'user' 
                    ? 'bg-blue-600 dark:bg-blue-500 text-white' 
                    : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100'
                  }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-lg p-3 text-sm bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing graph...
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <div className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about this repo..."
              className="w-full bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-md px-4 py-2.5 pr-12 text-sm focus:outline-none focus:ring-1 focus:ring-blue-600 shadow-sm"
            />
            <button 
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="absolute right-2 p-1.5 rounded-md text-zinc-500 hover:text-blue-600 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

    </div>
  );
}
