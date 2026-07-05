import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  Layers,
  Plus,
  Trash2,
  Loader2,
  ArrowLeft,
  FileCode,
  CheckCircle,
  Settings,
  Monitor,
  Server,
  Database,
  Zap,
  Cpu,
  Users,
  Link2,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const CATEGORY_META = {
  frontend: { label: 'Frontend', icon: Monitor, color: 'sky' },
  backend: { label: 'Backend', icon: Server, color: 'emerald' },
  database: { label: 'Database', icon: Database, color: 'amber' },
  cache: { label: 'Cache', icon: Zap, color: 'rose' },
  worker: { label: 'Worker', icon: Cpu, color: 'violet' },
};

const COLOR_CLASSES = {
  sky: 'border-sky-500/30 bg-sky-500/10 text-sky-300',
  emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  amber: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  rose: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
  violet: 'border-violet-500/30 bg-violet-500/10 text-violet-300',
};

const COLOR_INACTIVE = 'border-white/10 bg-white/[0.02] text-gray-400 hover:border-white/20 hover:text-gray-200';

function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('create');
  const [availableStacks, setAvailableStacks] = useState({});
  const [loadingStacks, setLoadingStacks] = useState(true);

  const [techStack, setTechStack] = useState({
    frontend: '',
    backend: '',
    database: '',
    cache: '',
    worker: '',
  });

  const [previewProject, setPreviewProject] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [isSaving, setIsSaving] = useState(false);

  const [testConfig, setTestConfig] = useState({
    testId: '',
    name: '',
    description: '',
    duration: 3600,
    codeEdit: 0,
    requirements: [],
    checks: [],
  });

  const [newRequirement, setNewRequirement] = useState({ title: '', description: '' });
  const [newCheck, setNewCheck] = useState({ type: 'element_exists', selector: '', points: 10 });

  const [mapperLoading, setMapperLoading] = useState(false);
  const [mapperUsers, setMapperUsers] = useState([]);
  const [mapperTests, setMapperTests] = useState([]);
  const [mapperMappings, setMapperMappings] = useState([]);
  const [mapperForm, setMapperForm] = useState({ hash: '', testId: '' });

  useEffect(() => {
    fetch(`${API_BASE_URL}/admin/stacks/available`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.stacks) {
          setAvailableStacks(data.stacks);
        }
      })
      .catch(() => toast.error('Failed to load available stacks'))
      .finally(() => setLoadingStacks(false));
  }, []);

  const generatePreview = useCallback(async () => {
    const hasSelection = Object.values(techStack).some((v) => v);
    if (!hasSelection) {
      setPreviewProject(null);
      return;
    }

    setPreviewLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/stacks/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ authToken: user?.authToken || '', techStack }),
      });
      const data = await res.json();
      if (data.success && data.project) {
        setPreviewProject(data.project);
      }
    } catch {
      // silent
    } finally {
      setPreviewLoading(false);
    }
  }, [techStack, user]);

  useEffect(() => {
    const timer = setTimeout(generatePreview, 400);
    return () => clearTimeout(timer);
  }, [generatePreview]);

  const loadMapperData = async () => {
    setMapperLoading(true);
    try {
      const [usersRes, testsRes, mappingsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/admin/test-mapper/users`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ authToken: user?.authToken || '' }),
        }),
        fetch(`${API_BASE_URL}/admin/test-mapper/tests`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ authToken: user?.authToken || '' }),
        }),
        fetch(`${API_BASE_URL}/admin/test-mapper/list`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ authToken: user?.authToken || '' }),
        }),
      ]);

      const [usersData, testsData, mappingsData] = await Promise.all([
        usersRes.json(),
        testsRes.json(),
        mappingsRes.json(),
      ]);

      if (usersData.success) setMapperUsers(usersData.users || []);
      if (testsData.success) setMapperTests(testsData.tests || []);
      if (mappingsData.success) setMapperMappings(mappingsData.mappings || []);
    } catch (err) {
      toast.error('Failed to load mapper data: ' + err.message);
    } finally {
      setMapperLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'mapper') {
      loadMapperData();
    }
  }, [activeTab, user?.authToken]);

  const handleAssignTest = async () => {
    if (!mapperForm.hash || !mapperForm.testId) {
      toast.error('Select both user and test');
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/admin/test-mapper/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          authToken: user?.authToken || '',
          hash: mapperForm.hash,
          testId: mapperForm.testId,
        }),
      });
      const data = await res.json();

      if (data.success) {
        toast.success(data.existing ? 'Mapping already exists' : 'Test assigned to user');
        setMapperForm({ hash: '', testId: '' });
        loadMapperData();
      } else {
        toast.error(data.detail || 'Failed to assign test');
      }
    } catch (err) {
      toast.error('Failed: ' + err.message);
    }
  };

  const handleRemoveMapping = async (hash, testId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/test-mapper/remove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          authToken: user?.authToken || '',
          hash,
          testId,
        }),
      });
      const data = await res.json();

      if (data.success) {
        toast.success('Mapping removed');
        loadMapperData();
      } else {
        toast.error(data.detail || 'Failed to remove mapping');
      }
    } catch (err) {
      toast.error('Failed: ' + err.message);
    }
  };

  const getUserName = (hash) => {
    const user = mapperUsers.find((u) => u.hash === hash);
    return user ? (user.name || user.email || hash.slice(0, 12) + '...') : hash.slice(0, 12) + '...';
  };

  const getTestName = (testId) => {
    const test = mapperTests.find((t) => t.testId === testId);
    return test ? test.name : testId;
  };

  const selectStack = (category, stackId) => {
    setTechStack((prev) => ({
      ...prev,
      [category]: prev[category] === stackId ? '' : stackId,
    }));
  };

  const handleCreateTest = async () => {
    if (!testConfig.testId || !testConfig.name) {
      toast.error('Test ID and Name are required');
      return;
    }

    const hasStack = Object.values(techStack).some((v) => v);
    if (!hasStack) {
      toast.error('Select at least one technology');
      return;
    }

    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/test/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          authToken: user?.authToken || '',
          ...testConfig,
          techStack,
        }),
      });
      const data = await res.json();

      if (data.success) {
        toast.success(`Test created with ${data.filesCount} files`);
        setTestConfig({
          testId: '',
          name: '',
          description: '',
          duration: 3600,
          codeEdit: 0,
          requirements: [],
          checks: [],
        });
      } else {
        toast.error(data.detail || 'Failed to create test');
      }
    } catch (err) {
      toast.error('Failed: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const addRequirement = () => {
    if (newRequirement.title) {
      setTestConfig((prev) => ({
        ...prev,
        requirements: [...prev.requirements, { ...newRequirement, id: Date.now().toString() }],
      }));
      setNewRequirement({ title: '', description: '' });
    }
  };

  const removeRequirement = (id) => {
    setTestConfig((prev) => ({
      ...prev,
      requirements: prev.requirements.filter((r) => r.id !== id),
    }));
  };

  const addCheck = () => {
    if (newCheck.selector) {
      setTestConfig((prev) => ({
        ...prev,
        checks: [...prev.checks, { ...newCheck, id: Date.now().toString() }],
      }));
      setNewCheck({ type: 'element_exists', selector: '', points: 10 });
    }
  };

  const removeCheck = (id) => {
    setTestConfig((prev) => ({
      ...prev,
      checks: prev.checks.filter((c) => c.id !== id),
    }));
  };

  const renderStackSelector = () => {
    if (loadingStacks) {
      return (
        <div className="flex items-center justify-center py-12 text-gray-500">
          <Loader2 size={20} className="animate-spin mr-2" /> Loading stacks...
        </div>
      );
    }

    return Object.entries(availableStacks).map(([category, stacks]) => {
      const meta = CATEGORY_META[category] || { label: category, icon: Layers, color: 'violet' };
      const Icon = meta.icon;
      const selected = techStack[category];

      return (
        <div key={category} className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Icon size={16} className="text-gray-400" />
            <h3 className="text-sm font-medium text-gray-300">{meta.label}</h3>
            {selected && (
              <span className="text-xs text-gray-600 ml-auto">click again to deselect</span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {stacks.map((stack) => {
              const isActive = selected === stack.id;
              const colorClass = COLOR_CLASSES[meta.color] || COLOR_CLASSES.violet;
              return (
                <button
                  key={stack.id}
                  onClick={() => selectStack(category, stack.id)}
                  className={`relative px-4 py-3 rounded-lg border text-left transition-all ${
                    isActive ? colorClass : COLOR_INACTIVE
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{stack.label}</span>
                    {isActive && <CheckCircle size={14} className="flex-shrink-0" />}
                  </div>
                  {stack.language && (
                    <span className="text-xs opacity-60 mt-0.5 block">{stack.language}</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      );
    });
  };

  return (
    <div className="min-h-screen bg-[#0a0a0b] text-gray-100">
      <header className="border-b border-white/10 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <h1 className="text-xl font-semibold">Admin Dashboard</h1>
          </div>
          <div className="text-sm text-gray-500">Create Tests with Tech Stack Selector</div>
        </div>
      </header>

      <main className="p-6 max-w-7xl mx-auto">
        <div className="flex gap-2 mb-6">
          {[
            { id: 'create', label: 'Create Test', icon: Plus },
            { id: 'mapper', label: 'Test Mapper', icon: Link2 },
            { id: 'settings', label: 'Settings', icon: Settings },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-violet-500/10 text-violet-400 border border-violet-500/20'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'create' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* LEFT: Stack selector + test config */}
            <div className="space-y-6">
              {/* Tech Stack Selector */}
              <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Layers size={18} className="text-violet-400" />
                  <h2 className="text-lg font-medium">Tech Stack</h2>
                </div>
                {renderStackSelector()}
              </div>

              {/* Test Details */}
              <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
                <h2 className="text-lg font-medium mb-4">Test Details</h2>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Test ID *</label>
                    <input
                      type="text"
                      value={testConfig.testId}
                      onChange={(e) => setTestConfig((prev) => ({ ...prev, testId: e.target.value }))}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50"
                      placeholder="todo-app-test"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Test Name *</label>
                    <input
                      type="text"
                      value={testConfig.name}
                      onChange={(e) => setTestConfig((prev) => ({ ...prev, name: e.target.value }))}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50"
                      placeholder="Build a Todo App"
                    />
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <textarea
                    value={testConfig.description}
                    onChange={(e) => setTestConfig((prev) => ({ ...prev, description: e.target.value }))}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50 h-20 resize-none"
                    placeholder="Build a full-stack todo app with React and FastAPI..."
                  />
                </div>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Duration (seconds)</label>
                    <input
                      type="number"
                      value={testConfig.duration}
                      onChange={(e) => setTestConfig((prev) => ({ ...prev, duration: parseInt(e.target.value) || 3600 }))}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Code Edit Mode</label>
                    <select
                      value={testConfig.codeEdit}
                      onChange={(e) => setTestConfig((prev) => ({ ...prev, codeEdit: parseInt(e.target.value) }))}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                    >
                      <option value={0}>Read-only (AI generates)</option>
                      <option value={1}>Editable by student</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Requirements */}
              <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
                <h2 className="text-lg font-medium mb-4">Requirements</h2>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={newRequirement.title}
                    onChange={(e) => setNewRequirement((prev) => ({ ...prev, title: e.target.value }))}
                    className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50"
                    placeholder="Title"
                    onKeyDown={(e) => e.key === 'Enter' && addRequirement()}
                  />
                  <input
                    type="text"
                    value={newRequirement.description}
                    onChange={(e) => setNewRequirement((prev) => ({ ...prev, description: e.target.value }))}
                    className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50"
                    placeholder="Description"
                    onKeyDown={(e) => e.key === 'Enter' && addRequirement()}
                  />
                  <button
                    onClick={addRequirement}
                    className="px-3 py-2 bg-violet-500/20 text-violet-300 rounded-lg hover:bg-violet-500/30"
                  >
                    <Plus size={16} />
                  </button>
                </div>
                {testConfig.requirements.length > 0 && (
                  <div className="space-y-1">
                    {testConfig.requirements.map((req) => (
                      <div
                        key={req.id}
                        className="flex items-center justify-between px-3 py-2 bg-white/5 rounded-lg"
                      >
                        <div>
                          <span className="text-white">{req.title}</span>
                          <span className="text-gray-500 text-sm ml-2">- {req.description}</span>
                        </div>
                        <button
                          onClick={() => removeRequirement(req.id)}
                          className="text-gray-500 hover:text-red-400"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Evaluation Checks */}
              <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
                <h2 className="text-lg font-medium mb-4">Evaluation Checks</h2>
                <div className="flex gap-2 mb-2">
                  <select
                    value={newCheck.type}
                    onChange={(e) => setNewCheck((prev) => ({ ...prev, type: e.target.value }))}
                    className="w-40 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                  >
                    <option value="element_exists">Element Exists</option>
                    <option value="api_call">API Call</option>
                    <option value="screenshot_match">Screenshot Match</option>
                  </select>
                  <input
                    type="text"
                    value={newCheck.selector}
                    onChange={(e) => setNewCheck((prev) => ({ ...prev, selector: e.target.value }))}
                    className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50"
                    placeholder="Selector / Endpoint"
                    onKeyDown={(e) => e.key === 'Enter' && addCheck()}
                  />
                  <input
                    type="number"
                    value={newCheck.points}
                    onChange={(e) =>
                      setNewCheck((prev) => ({ ...prev, points: parseInt(e.target.value) || 10 }))
                    }
                    className="w-20 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                  />
                  <button
                    onClick={addCheck}
                    className="px-3 py-2 bg-violet-500/20 text-violet-300 rounded-lg hover:bg-violet-500/30"
                  >
                    <Plus size={16} />
                  </button>
                </div>
                {testConfig.checks.length > 0 && (
                  <div className="space-y-1">
                    {testConfig.checks.map((check) => (
                      <div
                        key={check.id}
                        className="flex items-center justify-between px-3 py-2 bg-white/5 rounded-lg"
                      >
                        <div>
                          <span className="text-violet-300 text-xs uppercase">{check.type}</span>
                          <span className="text-white ml-2">{check.selector}</span>
                          <span className="text-gray-500 text-sm ml-2">({check.points} pts)</span>
                        </div>
                        <button
                          onClick={() => removeCheck(check.id)}
                          className="text-gray-500 hover:text-red-400"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={handleCreateTest}
                disabled={isSaving || !testConfig.testId || !testConfig.name}
                className="w-full py-3 bg-violet-500 text-white rounded-lg font-medium hover:bg-violet-600 transition-colors disabled:opacity-50"
              >
                {isSaving ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={18} className="animate-spin" /> Creating...
                  </span>
                ) : (
                  'Create Test'
                )}
              </button>
            </div>

            {/* RIGHT: Live preview */}
            <div className="space-y-6">
              <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6 sticky top-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-medium flex items-center gap-2">
                    <FileCode size={18} className="text-violet-400" />
                    Generated Project
                  </h2>
                  {previewLoading && <Loader2 size={16} className="animate-spin text-gray-500" />}
                </div>

                {!previewProject && !previewLoading && (
                  <div className="text-center py-12 text-gray-600 text-sm">
                    Select technologies to see generated project files
                  </div>
                )}

                {previewProject && (
                  <>
                    {/* Services badges */}
                    {previewProject.meta?.services?.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        {previewProject.meta.services.map((s) => (
                          <span
                            key={s}
                            className="px-2 py-0.5 text-xs bg-violet-500/10 text-violet-300 rounded border border-violet-500/20"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* File list */}
                    <div className="mb-4">
                      <h3 className="text-xs text-gray-500 uppercase tracking-wide mb-2">
                        Files ({Object.keys(previewProject.files).length})
                      </h3>
                      <div className="max-h-48 overflow-y-auto space-y-0.5">
                        {Object.keys(previewProject.files).map((path) => (
                          <div
                            key={path}
                            className="px-2 py-1 text-sm text-gray-400 bg-black/20 rounded font-mono"
                          >
                            {path}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* docker-compose.yml preview */}
                    {previewProject.composeContent && (
                      <div>
                        <h3 className="text-xs text-gray-500 uppercase tracking-wide mb-2">
                          docker-compose.yml
                        </h3>
                        <pre className="px-4 py-3 bg-black/30 border border-white/10 rounded-lg text-gray-300 font-mono text-xs overflow-x-auto max-h-96 overflow-y-auto">
                          {previewProject.composeContent}
                        </pre>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
            <h2 className="text-lg font-medium mb-4">Platform Settings</h2>
            <p className="text-gray-500 text-sm">Configuration options coming soon...</p>
          </div>
        )}

        {activeTab === 'mapper' && (
          <div className="space-y-6">
            <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
              <div className="flex items-center gap-2 mb-4">
                <Users size={18} className="text-violet-400" />
                <h2 className="text-lg font-medium">Assign Test to User</h2>
              </div>

              {mapperLoading ? (
                <div className="flex items-center justify-center py-8 text-gray-500">
                  <Loader2 size={20} className="animate-spin mr-2" /> Loading...
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Select User</label>
                    <select
                      value={mapperForm.hash}
                      onChange={(e) => setMapperForm((prev) => ({ ...prev, hash: e.target.value }))}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                    >
                      <option value="">-- Select User --</option>
                      {mapperUsers.map((u) => (
                        <option key={u.hash} value={u.hash}>
                          {u.name || u.email || u.hash.slice(0, 12)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Select Test</label>
                    <select
                      value={mapperForm.testId}
                      onChange={(e) => setMapperForm((prev) => ({ ...prev, testId: e.target.value }))}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                    >
                      <option value="">-- Select Test --</option>
                      {mapperTests.map((t) => (
                        <option key={t.testId} value={t.testId}>
                          {t.name || t.testId}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <button
                      onClick={handleAssignTest}
                      disabled={!mapperForm.hash || !mapperForm.testId}
                      className="w-full py-2 bg-violet-500 text-white rounded-lg font-medium hover:bg-violet-600 transition-colors disabled:opacity-50"
                    >
                      Assign Test
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Link2 size={18} className="text-violet-400" />
                  <h2 className="text-lg font-medium">Current Mappings</h2>
                </div>
                <span className="text-sm text-gray-500">{mapperMappings.length} mappings</span>
              </div>

              {mapperLoading ? (
                <div className="flex items-center justify-center py-8 text-gray-500">
                  <Loader2 size={20} className="animate-spin mr-2" /> Loading...
                </div>
              ) : mapperMappings.length === 0 ? (
                <div className="text-center py-8 text-gray-600 text-sm">No test mappings found</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-sm text-gray-500 border-b border-white/10">
                        <th className="pb-2 pr-4">User</th>
                        <th className="pb-2 pr-4">Test</th>
                        <th className="pb-2 pr-4">Assigned At</th>
                        <th className="pb-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {mapperMappings.map((m, idx) => (
                        <tr key={idx} className="border-b border-white/5">
                          <td className="py-3 pr-4">
                            <span className="text-white">{getUserName(m.hash)}</span>
                            <span className="block text-xs text-gray-500 font-mono">{m.hash.slice(0, 16)}...</span>
                          </td>
                          <td className="py-3 pr-4">
                            <span className="text-white">{getTestName(m.testId)}</span>
                            <span className="block text-xs text-gray-500">{m.testId}</span>
                          </td>
                          <td className="py-3 pr-4 text-sm text-gray-400">
                            {m.assignedAt ? new Date(m.assignedAt).toLocaleDateString() : '-'}
                          </td>
                          <td className="py-3">
                            <button
                              onClick={() => handleRemoveMapping(m.hash, m.testId)}
                              className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                            >
                              <Trash2 size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default AdminDashboard;
