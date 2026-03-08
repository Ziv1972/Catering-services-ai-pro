'use client';

import { useEffect, useState, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Bot, Crown, BarChart3, ShieldCheck, Receipt, TrendingUp,
  MessageCircleWarning, Activity, Briefcase, CalendarCheck, Megaphone,
  Send, Loader2, ChevronDown, ChevronRight, Zap, Clock,
  Users, ArrowRight, X,
} from 'lucide-react';
import { agentCrewAPI } from '@/lib/api';

const ICON_MAP: Record<string, React.ElementType> = {
  crown: Crown,
  'bar-chart-3': BarChart3,
  'shield-check': ShieldCheck,
  receipt: Receipt,
  'trending-up': TrendingUp,
  'message-circle-warning': MessageCircleWarning,
  activity: Activity,
  handshake: Briefcase,
  'calendar-check': CalendarCheck,
  megaphone: Megaphone,
  bot: Bot,
};

interface AgentRole {
  id: string;
  title: string;
  goal: string;
  backstory: string;
  responsibilities: string[];
  tools: string[];
  interacts_with: string[];
  icon: string;
  color: string;
  status: string;
  is_manager: boolean;
  stats: {
    invocations: number;
    total_tokens: number;
    total_time_ms: number;
    avg_time_ms: number;
  };
}

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  agents_used?: string[];
  tasks?: Array<{
    agent_id: string;
    agent_title: string;
    objective: string;
    status: string;
    execution_time_ms: number;
    result_summary?: string;
  }>;
}

export default function AgentCrewPage() {
  const [crewInfo, setCrewInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<AgentRole | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadCrewInfo();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const loadCrewInfo = async () => {
    try {
      const data = await agentCrewAPI.getCrewInfo();
      setCrewInfo(data);
    } catch (err) {
      console.error('Failed to load crew info:', err);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const message = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: message }]);
    setChatLoading(true);

    try {
      const result = await agentCrewAPI.chat(message, sessionId);
      setSessionId(result.session?.session_id);
      setChatMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: result.response,
          agents_used: result.agents_used,
          tasks: result.tasks,
        },
      ]);
    } catch (err: any) {
      setChatMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: `Error: ${err.response?.data?.detail || err.message}`,
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const getIcon = (iconName: string) => {
    const IconComponent = ICON_MAP[iconName] || Bot;
    return IconComponent;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const manager = crewInfo?.agents?.find((a: AgentRole) => a.is_manager);
  const specialists = crewInfo?.agents?.filter((a: AgentRole) => !a.is_manager) || [];

  return (
    <div className="space-y-6">
      {/* Crew Header */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-gray-900 via-indigo-950 to-gray-900 p-6 text-white">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTM2IDE4YzMuMzE0IDAgNi0yLjY4NiA2LTZzLTIuNjg2LTYtNi02LTYgMi42ODYtNiA2IDIuNjg2IDYgNiA2eiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Bot className="w-8 h-8 text-amber-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">{crewInfo?.crew_name}</h1>
              <p className="text-indigo-300 text-sm">Full-Stack AI Agent Crew</p>
            </div>
          </div>
          <div className="flex gap-4 mt-4">
            <div className="flex items-center gap-1.5 text-sm text-indigo-200">
              <Users className="w-4 h-4" />
              <span>{crewInfo?.total_agents} Agents</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-indigo-200">
              <Crown className="w-4 h-4 text-amber-400" />
              <span>1 Manager</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-indigo-200">
              <Zap className="w-4 h-4 text-green-400" />
              <span>{specialists.length} Specialists</span>
            </div>
          </div>
        </div>
      </div>

      {/* Manager Card */}
      {manager && (
        <Card className="border-amber-200 bg-amber-50/30">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div
                className="p-2.5 rounded-xl"
                style={{ backgroundColor: `${manager.color}20` }}
              >
                <Crown className="w-6 h-6" style={{ color: manager.color }} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-lg">{manager.title}</CardTitle>
                  <Badge className="bg-amber-100 text-amber-800 text-xs">MANAGER</Badge>
                </div>
                <p className="text-sm text-gray-600 mt-0.5">{manager.goal}</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700 leading-relaxed mb-3">{manager.backstory}</p>
            <div className="flex flex-wrap gap-1.5">
              {manager.responsibilities?.map((r: string, i: number) => (
                <Badge key={i} variant="outline" className="text-xs bg-white">
                  {r}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Specialist Agent Grid */}
      <div>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Zap className="w-5 h-5 text-indigo-600" />
          Specialist Agents
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {specialists.map((agent: AgentRole) => {
            const IconComp = getIcon(agent.icon);
            const isExpanded = expandedAgent === agent.id;

            return (
              <Card
                key={agent.id}
                className="cursor-pointer transition-all hover:shadow-md group"
                onClick={() => setExpandedAgent(isExpanded ? null : agent.id)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start gap-3">
                    <div
                      className="p-2 rounded-lg shrink-0 transition-transform group-hover:scale-110"
                      style={{ backgroundColor: `${agent.color}15` }}
                    >
                      <IconComp className="w-5 h-5" style={{ color: agent.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-semibold truncate">
                          {agent.title}
                        </CardTitle>
                        {isExpanded
                          ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                          : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />}
                      </div>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{agent.goal}</p>
                    </div>
                  </div>
                </CardHeader>

                {isExpanded && (
                  <CardContent className="pt-0 space-y-3">
                    <div>
                      <p className="text-xs text-gray-700 leading-relaxed">{agent.backstory}</p>
                    </div>

                    <div>
                      <h4 className="text-xs font-semibold text-gray-900 mb-1">Responsibilities</h4>
                      <ul className="space-y-0.5">
                        {agent.responsibilities.map((r, i) => (
                          <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                            <ArrowRight className="w-3 h-3 mt-0.5 shrink-0" style={{ color: agent.color }} />
                            {r}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div>
                      <h4 className="text-xs font-semibold text-gray-900 mb-1">Tools</h4>
                      <div className="flex flex-wrap gap-1">
                        {agent.tools.map((t, i) => (
                          <Badge
                            key={i}
                            variant="outline"
                            className="text-[10px] px-1.5 py-0"
                            style={{ borderColor: `${agent.color}40`, color: agent.color }}
                          >
                            {t.replace(/_/g, ' ')}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-xs font-semibold text-gray-900 mb-1">Collaborates With</h4>
                      <div className="flex flex-wrap gap-1">
                        {agent.interacts_with.map((id, i) => {
                          const peer = crewInfo?.agents?.find((a: AgentRole) => a.id === id);
                          return (
                            <Badge
                              key={i}
                              variant="secondary"
                              className="text-[10px] px-1.5 py-0"
                            >
                              {peer?.title || id.replace(/_/g, ' ')}
                            </Badge>
                          );
                        })}
                      </div>
                    </div>

                    {(agent.stats.invocations > 0) && (
                      <div className="flex gap-3 pt-2 border-t">
                        <div className="text-center">
                          <p className="text-lg font-bold" style={{ color: agent.color }}>
                            {agent.stats.invocations}
                          </p>
                          <p className="text-[10px] text-gray-500">Runs</p>
                        </div>
                        <div className="text-center">
                          <p className="text-lg font-bold text-gray-700">
                            {agent.stats.avg_time_ms}ms
                          </p>
                          <p className="text-[10px] text-gray-500">Avg Time</p>
                        </div>
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      </div>

      {/* Crew Chat */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-indigo-600" />
            <CardTitle className="text-lg">Crew Chat</CardTitle>
            <Badge variant="outline" className="text-xs">
              Manager-orchestrated
            </Badge>
          </div>
          <p className="text-sm text-gray-500">
            Ask anything. The Operations Manager will delegate to the right specialists.
          </p>
        </CardHeader>
        <CardContent>
          {/* Messages */}
          <div className="border rounded-lg bg-gray-50 h-[400px] overflow-y-auto p-4 space-y-4 mb-3">
            {chatMessages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-2">
                <Bot className="w-12 h-12" />
                <p className="text-sm">Start a conversation with the crew</p>
                <div className="flex flex-wrap gap-2 max-w-md justify-center">
                  {[
                    'Analyze last month spending trends',
                    'Check compliance status across sites',
                    'Summarize recent complaints',
                    'Prepare for vendor review meeting',
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => {
                        setChatInput(suggestion);
                      }}
                      className="text-xs px-3 py-1.5 rounded-full bg-white border text-gray-600 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg p-3 ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white border shadow-sm'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.text}</p>

                  {/* Agent task breakdown */}
                  {msg.tasks && msg.tasks.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-gray-100 space-y-1.5">
                      <p className="text-xs font-semibold text-gray-500">Agents Involved:</p>
                      {msg.tasks.map((task, j) => (
                        <div
                          key={j}
                          className="flex items-center gap-2 text-xs bg-gray-50 rounded px-2 py-1"
                        >
                          <div className={`w-2 h-2 rounded-full ${
                            task.status === 'completed' ? 'bg-green-500' :
                            task.status === 'failed' ? 'bg-red-500' : 'bg-yellow-500'
                          }`} />
                          <span className="font-medium">{task.agent_title}</span>
                          <span className="text-gray-400">|</span>
                          <Clock className="w-3 h-3 text-gray-400" />
                          <span className="text-gray-500">{task.execution_time_ms}ms</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Agents used badges */}
                  {msg.agents_used && msg.agents_used.length > 0 && !msg.tasks?.length && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {msg.agents_used.map((agentId) => {
                        const agent = crewInfo?.agents?.find((a: AgentRole) => a.id === agentId);
                        return (
                          <Badge
                            key={agentId}
                            variant="secondary"
                            className="text-[10px]"
                          >
                            {agent?.title || agentId}
                          </Badge>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-white border rounded-lg p-3 shadow-sm flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                  <span className="text-sm text-gray-500">Manager is delegating to agents...</span>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder="Ask the crew anything about catering operations..."
              className="flex-1 px-4 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={chatLoading}
            />
            <Button
              onClick={sendMessage}
              disabled={chatLoading || !chatInput.trim()}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {chatLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>

          {sessionId && (
            <p className="text-[10px] text-gray-400 mt-1">
              Session: {sessionId.slice(0, 8)}...
            </p>
          )}
        </CardContent>
      </Card>

      {/* Agent Interaction Map */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-600" />
            Agent Interaction Map
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {crewInfo?.agents?.map((agent: AgentRole) => {
              const IconComp = getIcon(agent.icon);
              return (
                <div
                  key={agent.id}
                  className="flex flex-col items-center text-center p-3 rounded-lg border bg-white hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => setExpandedAgent(expandedAgent === agent.id ? null : agent.id)}
                >
                  <div
                    className="p-2 rounded-full mb-2"
                    style={{ backgroundColor: `${agent.color}15` }}
                  >
                    <IconComp className="w-5 h-5" style={{ color: agent.color }} />
                  </div>
                  <p className="text-xs font-medium text-gray-900 leading-tight">
                    {agent.title.split(' ').slice(0, 2).join(' ')}
                  </p>
                  {agent.is_manager && (
                    <Badge className="bg-amber-100 text-amber-800 text-[9px] mt-1">MANAGER</Badge>
                  )}
                  <p className="text-[10px] text-gray-400 mt-1">
                    {agent.interacts_with?.length || 0} connections
                  </p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
