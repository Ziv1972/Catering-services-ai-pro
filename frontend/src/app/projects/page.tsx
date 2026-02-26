'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FolderKanban, Plus, ChevronRight } from 'lucide-react';
import { projectsAPI } from '@/lib/api';
import { format } from 'date-fns';

const STATUS_OPTIONS = ['planning', 'active', 'on_hold', 'completed', 'cancelled'];
const PRIORITY_OPTIONS = ['low', 'medium', 'high'];

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', description: '', site_id: '', status: 'planning',
    priority: 'medium', start_date: '', target_end_date: '',
  });

  useEffect(() => { loadProjects(); }, []);

  const loadProjects = async () => {
    try {
      const data = await projectsAPI.list();
      setProjects(data);
    } finally { setLoading(false); }
  };

  const handleCreate = async () => {
    setSaving(true);
    try {
      const payload: any = { ...form };
      if (!payload.site_id) delete payload.site_id;
      else payload.site_id = parseInt(payload.site_id);
      if (!payload.start_date) delete payload.start_date;
      if (!payload.target_end_date) delete payload.target_end_date;

      await projectsAPI.create(payload);
      setShowForm(false);
      setForm({ name: '', description: '', site_id: '', status: 'planning', priority: 'medium', start_date: '', target_end_date: '' });
      await loadProjects();
    } finally { setSaving(false); }
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

  const getPriorityColor = (p: string) => {
    const colors: Record<string, string> = {
      high: 'bg-orange-100 text-orange-800',
      medium: 'bg-blue-100 text-blue-800',
      low: 'bg-gray-100 text-gray-700',
    };
    return colors[p] || 'bg-gray-100 text-gray-700';
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen"><p className="text-gray-500">Loading projects...</p></div>;
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="text-gray-500 text-sm">{projects.length} project(s)</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="bg-purple-600 hover:bg-purple-700">
          <Plus className="w-4 h-4 mr-2" /> New Project
        </Button>
      </div>

      {showForm && (
        <Card className="mb-6 border-purple-200">
          <CardHeader><CardTitle>Create Project</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" placeholder="e.g. Open Coffee Truck" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Site (optional)</label>
                <select value={form.site_id} onChange={e => setForm({...form, site_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  <option value="">All sites</option>
                  <option value="1">Nes Ziona</option>
                  <option value="2">Kiryat Gat</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                <select value={form.priority} onChange={e => setForm({...form, priority: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md">
                  {PRIORITY_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Target End Date</label>
                <input type="date" value={form.target_end_date} onChange={e => setForm({...form, target_end_date: e.target.value})}
                  className="w-full px-3 py-2 border rounded-md" />
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                className="w-full px-3 py-2 border rounded-md" rows={2} />
            </div>
            <div className="flex gap-3">
              <Button onClick={handleCreate} disabled={saving || !form.name} className="bg-purple-600 hover:bg-purple-700">
                {saving ? 'Creating...' : 'Create Project'}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {projects.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FolderKanban className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No projects yet. Create your first project above.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {projects.map((p: any) => (
            <Card key={p.id} className="hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => router.push(`/projects/${p.id}`)}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <FolderKanban className="w-5 h-5 text-purple-500" />
                      <h3 className="font-semibold text-lg">{p.name}</h3>
                      <Badge className={getStatusColor(p.status)}>{p.status}</Badge>
                      <Badge className={getPriorityColor(p.priority)}>{p.priority}</Badge>
                      {p.site_name && <Badge variant="outline">{p.site_name}</Badge>}
                    </div>
                    {p.description && <p className="text-sm text-gray-600 mb-3 ml-8">{p.description}</p>}
                    <div className="flex items-center gap-4 ml-8">
                      <div className="flex items-center gap-2 flex-1 max-w-xs">
                        <div className="flex-1 h-2.5 bg-gray-200 rounded-full">
                          <div className="h-2.5 bg-purple-500 rounded-full transition-all"
                            style={{ width: `${p.task_count > 0 ? Math.round((p.done_count / p.task_count) * 100) : 0}%` }} />
                        </div>
                        <span className="text-sm text-gray-600 font-medium">
                          {p.done_count}/{p.task_count} tasks
                        </span>
                      </div>
                      {p.target_end_date && (
                        <span className="text-xs text-gray-500">
                          Target: {format(new Date(p.target_end_date), 'MMM d, yyyy')}
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
