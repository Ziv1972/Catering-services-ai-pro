'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, Plus, CheckCircle2, Circle, Clock, Ban,
  Pencil, Trash2, Link2, GripVertical
} from 'lucide-react';
import { projectsAPI } from '@/lib/api';
import { format } from 'date-fns';

const TASK_STATUSES = ['pending', 'in_progress', 'done', 'blocked'];
const ENTITY_TYPES = ['menu_check', 'proforma', 'supplier', 'contract', 'compliance_rule'];
const PROJECT_STATUSES = ['planning', 'active', 'on_hold', 'completed', 'cancelled'];

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = Number(params.id);
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [editingTask, setEditingTask] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [taskForm, setTaskForm] = useState({
    title: '', description: '', assigned_to: '', due_date: '',
    linked_entity_type: '', linked_entity_label: '', notes: '', order: 0,
  });

  useEffect(() => { loadProject(); }, [projectId]);

  const loadProject = async () => {
    try {
      const data = await projectsAPI.get(projectId);
      setProject(data);
    } finally { setLoading(false); }
  };

  const handleAddTask = async () => {
    setSaving(true);
    try {
      const payload: any = { ...taskForm };
      if (!payload.assigned_to) delete payload.assigned_to;
      if (!payload.due_date) delete payload.due_date;
      if (!payload.linked_entity_type) { delete payload.linked_entity_type; delete payload.linked_entity_label; }
      if (!payload.description) delete payload.description;
      if (!payload.notes) delete payload.notes;
      payload.order = project.tasks?.length || 0;

      await projectsAPI.addTask(projectId, payload);
      setShowTaskForm(false);
      setTaskForm({ title: '', description: '', assigned_to: '', due_date: '', linked_entity_type: '', linked_entity_label: '', notes: '', order: 0 });
      await loadProject();
    } finally { setSaving(false); }
  };

  const handleUpdateTaskStatus = async (taskId: number, newStatus: string) => {
    await projectsAPI.updateTask(projectId, taskId, { status: newStatus });
    await loadProject();
  };

  const handleUpdateProjectStatus = async (newStatus: string) => {
    await projectsAPI.update(projectId, { status: newStatus });
    await loadProject();
  };

  const handleDeleteTask = async (taskId: number) => {
    await projectsAPI.deleteTask(projectId, taskId);
    await loadProject();
  };

  const getStatusIcon = (s: string) => {
    const icons: Record<string, any> = {
      pending: <Circle className="w-4 h-4 text-gray-400" />,
      in_progress: <Clock className="w-4 h-4 text-blue-500" />,
      done: <CheckCircle2 className="w-4 h-4 text-green-500" />,
      blocked: <Ban className="w-4 h-4 text-red-500" />,
    };
    return icons[s] || icons.pending;
  };

  const getStatusColor = (s: string) => {
    const colors: Record<string, string> = {
      planning: 'bg-purple-100 text-purple-800',
      active: 'bg-green-100 text-green-800',
      on_hold: 'bg-yellow-100 text-yellow-800',
      completed: 'bg-blue-100 text-blue-800',
      cancelled: 'bg-gray-100 text-gray-600',
    };
    return colors[s] || 'bg-gray-100 text-gray-700';
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen"><p className="text-gray-500">Loading project...</p></div>;
  }

  if (!project) {
    return <div className="flex items-center justify-center h-screen"><p className="text-gray-500">Project not found</p></div>;
  }

  const tasks = project.tasks || [];
  const doneCount = tasks.filter((t: any) => t.status === 'done').length;
  const progress = tasks.length > 0 ? Math.round(doneCount / tasks.length * 100) : 0;

  return (
    <main className="max-w-5xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" onClick={() => router.push('/projects')}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
      </div>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          {project.description && <p className="text-gray-600 mt-1">{project.description}</p>}
          <div className="flex items-center gap-3 mt-3">
            <Badge className={getStatusColor(project.status)}>{project.status}</Badge>
            {project.site_name && <Badge variant="outline">{project.site_name}</Badge>}
            {project.target_end_date && (
              <span className="text-sm text-gray-500">
                Target: {format(new Date(project.target_end_date), 'MMM d, yyyy')}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {PROJECT_STATUSES.filter(s => s !== project.status).slice(0, 2).map(s => (
            <Button key={s} variant="outline" size="sm" onClick={() => handleUpdateProjectStatus(s)}>
              → {s}
            </Button>
          ))}
        </div>
      </div>

      {/* Progress */}
      <Card className="mb-6">
        <CardContent className="py-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium">Progress</span>
                <span className="text-sm text-gray-600">{doneCount}/{tasks.length} tasks · {progress}%</span>
              </div>
              <div className="h-3 bg-gray-200 rounded-full">
                <div className="h-3 bg-purple-500 rounded-full transition-all" style={{ width: `${progress}%` }} />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tasks */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Tasks & Phases</h2>
        <Button onClick={() => setShowTaskForm(!showTaskForm)} size="sm" className="bg-purple-600 hover:bg-purple-700">
          <Plus className="w-4 h-4 mr-1" /> Add Task
        </Button>
      </div>

      {showTaskForm && (
        <Card className="mb-4 border-purple-200">
          <CardContent className="py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
              <input value={taskForm.title} onChange={e => setTaskForm({...taskForm, title: e.target.value})}
                placeholder="Task title" className="px-3 py-2 border rounded-md" />
              <input value={taskForm.assigned_to} onChange={e => setTaskForm({...taskForm, assigned_to: e.target.value})}
                placeholder="Assigned to (e.g. David)" className="px-3 py-2 border rounded-md" />
              <input type="date" value={taskForm.due_date} onChange={e => setTaskForm({...taskForm, due_date: e.target.value})}
                className="px-3 py-2 border rounded-md" />
              <div className="flex gap-2">
                <select value={taskForm.linked_entity_type} onChange={e => setTaskForm({...taskForm, linked_entity_type: e.target.value})}
                  className="flex-1 px-3 py-2 border rounded-md">
                  <option value="">Link to... (optional)</option>
                  {ENTITY_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                </select>
                {taskForm.linked_entity_type && (
                  <input value={taskForm.linked_entity_label} onChange={e => setTaskForm({...taskForm, linked_entity_label: e.target.value})}
                    placeholder="Label" className="flex-1 px-3 py-2 border rounded-md" />
                )}
              </div>
            </div>
            <textarea value={taskForm.description} onChange={e => setTaskForm({...taskForm, description: e.target.value})}
              placeholder="Description (optional)" className="w-full px-3 py-2 border rounded-md mb-3" rows={2} />
            <div className="flex gap-3">
              <Button onClick={handleAddTask} disabled={saving || !taskForm.title} className="bg-purple-600 hover:bg-purple-700">
                {saving ? 'Adding...' : 'Add Task'}
              </Button>
              <Button variant="outline" onClick={() => setShowTaskForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {tasks.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-gray-500">No tasks yet. Add your first task above.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {tasks.map((t: any, idx: number) => (
            <Card key={t.id} className={`${t.status === 'done' ? 'opacity-60' : ''}`}>
              <CardContent className="py-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-6">{idx + 1}</span>
                  <button onClick={() => handleUpdateTaskStatus(t.id, t.status === 'done' ? 'pending' : 'done')}>
                    {getStatusIcon(t.status)}
                  </button>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${t.status === 'done' ? 'line-through text-gray-400' : ''}`}>
                        {t.title}
                      </span>
                      {t.assigned_to && (
                        <Badge variant="outline" className="text-xs">→ {t.assigned_to}</Badge>
                      )}
                      {t.linked_entity_type && (
                        <Badge variant="outline" className="text-xs">
                          <Link2 className="w-3 h-3 mr-1" />{t.linked_entity_label || t.linked_entity_type}
                        </Badge>
                      )}
                    </div>
                    {t.due_date && (
                      <span className="text-xs text-gray-500">
                        Due: {format(new Date(t.due_date), 'MMM d')}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-wrap justify-end">
                    {TASK_STATUSES.filter(s => s !== t.status).map(s => (
                      <button key={s} onClick={() => handleUpdateTaskStatus(t.id, s)}
                        className="text-xs px-2 py-1 rounded hover:bg-gray-100 text-gray-500 hidden sm:inline-block">
                        {s === 'in_progress' ? 'start' : s}
                      </button>
                    ))}
                    <button onClick={() => handleDeleteTask(t.id)}
                      className="text-xs px-2 py-1 rounded hover:bg-red-50 text-red-400">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
