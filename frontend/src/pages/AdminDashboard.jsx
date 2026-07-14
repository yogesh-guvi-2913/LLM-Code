import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  ArrowLeft,
  Box,
  Loader2,
  CheckCircle,
  Settings,
  Code,
  Clock,
  FileText,
  Zap,
  Play,
  Monitor,
  Server,
  AlertCircle,
  RefreshCw,
  Info,
  Users,
  UserCheck,
  X,
  Search,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/v1';

const KIND_META = {
  frontend: { label: 'Frontend', icon: Monitor, color: 'sky' },
  api: { label: 'Backend', icon: Server, color: 'emerald' },
};

const COLOR_CLASSES = {
  sky: 'border-sky-500/30 bg-sky-500/10 text-sky-300',
  emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
};

function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('create');
  const [flashTemplates, setFlashTemplates] = useState([]);
  const [flashEnabled, setFlashEnabled] = useState(false);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  
  const [testConfig, setTestConfig] = useState({
    testId: '',
    name: '',
    description: '',
    duration: 3600,
    codeEdit: 0,
    flashScoringEnabled: true,
  });

  const [isSaving, setIsSaving] = useState(false);
  const [scalingTemplate, setScalingTemplate] = useState(null);

  const [tests, setTests] = useState([]);
  const [users, setUsers] = useState([]);
  const [loadingTests, setLoadingTests] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [selectedTest, setSelectedTest] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [assigningTest, setAssigningTest] = useState(false);
  const [userSearch, setUserSearch] = useState('');

  const fetchFlashTemplates = async () => {
    setLoadingTemplates(true);
    try {
      const res = await fetch(`${API_BASE_URL}/v1/admin/flash/templates`);
      const data = await res.json();
      setFlashEnabled(data.enabled);
      if (data.success && data.templates) {
        setFlashTemplates(data.templates);
      }
    } catch (err) {
      console.error('Failed to fetch Flash templates:', err);
      toast.error('Failed to load Flash templates');
    } finally {
      setLoadingTemplates(false);
    }
  };

  const fetchTests = useCallback(async () => {
    setLoadingTests(true);
    try {
      const res = await fetch(`${API_BASE_URL}/v1/admin/tests?authToken=${user?.authToken}`);
      const data = await res.json();
      if (data.success) {
        setTests(data.tests || []);
      }
    } catch {
      toast.error('Failed to load tests');
    } finally {
      setLoadingTests(false);
    }
  }, [user?.authToken]);

  useEffect(() => {
    fetchFlashTemplates();
  }, []);

  useEffect(() => {
    if (activeTab === 'mapper') {
      fetchTests();
    }
  }, [activeTab, fetchTests]);

  const fetchUsers = async () => {
    setLoadingUsers(true);
    try {
      const res = await fetch(`${API_BASE_URL}/v1/admin/users?authToken=${user?.authToken}`);
      const data = await res.json();
      if (data.success) {
        setUsers(data.users || []);
      }
    } catch {
      toast.error('Failed to load users');
    } finally {
      setLoadingUsers(false);
    }
  };

  const fetchExistingMappings = async (testId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/v1/admin/test-mapper/${testId}?authToken=${user?.authToken}`);
      const data = await res.json();
      if (data.success) {
        return data.mappings || [];
      }
      return [];
    } catch {
      return [];
    }
  };

  const handleTestClick = async (test) => {
    setSelectedTest(test);
    setShowUserModal(true);
    setSelectedUsers([]);
    await fetchUsers();
    const mappings = await fetchExistingMappings(test.testId);
    const mappedHashes = mappings.map(m => m.hash);
    setSelectedUsers(mappedHashes);
  };

  const handleUserToggle = (userHash) => {
    setSelectedUsers(prev => 
      prev.includes(userHash) 
        ? prev.filter(h => h !== userHash)
        : [...prev, userHash]
    );
  };

  const handleAssignTest = async () => {
    if (!selectedTest || selectedUsers.length === 0) {
      toast.error('Please select at least one user');
      return;
    }

    setAssigningTest(true);
    try {
      const res = await fetch(`${API_BASE_URL}/v1/admin/test-mapper`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          authToken: user?.authToken,
          testId: selectedTest.testId,
          userHashes: selectedUsers,
        }),
      });
      const data = await res.json();
      if (data.success) {
        toast.success(data.message);
        setShowUserModal(false);
        setSelectedTest(null);
        setSelectedUsers([]);
      } else {
        toast.error(data.detail || 'Failed to assign test');
      }
    } catch {
      toast.error('Failed to assign test');
    } finally {
      setAssigningTest(false);
    }
  };

  const handleScaleTemplate = async (templateId, newMinWarm) => {
    setScalingTemplate(templateId);
    try {
      const res = await fetch(`${API_BASE_URL}/v1/flash/templates/${templateId}/scale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ min_warm: newMinWarm }),
      });
      const data = await res.json();
      if (data.success) {
        toast.success(`Scaled ${templateId} to ${newMinWarm} warm containers`);
        fetchFlashTemplates();
      }
    } catch {
      toast.error('Failed to scale template');
    } finally {
      setScalingTemplate(null);
    }
  };

  const handleCreateTest = async () => {
    if (!testConfig.testId || !testConfig.name) {
      toast.error('Test ID and Name are required');
      return;
    }

    if (!selectedTemplate) {
      toast.error('Please select a Flash template');
      return;
    }

    if (!flashEnabled) {
      toast.error('Flash integration is not available');
      return;
    }

    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/v1/admin/test/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          authToken: user?.authToken || '',
          ...testConfig,
          techStack: {},
          flashTemplateId: selectedTemplate,
          flashScoringEnabled: testConfig.flashScoringEnabled,
        }),
      });
      const data = await res.json();

      if (data.success) {
        toast.success(`Test created! (${data.filesCount} files from Flash template)`);
        setTestConfig({
          testId: '',
          name: '',
          description: '',
          duration: 3600,
          codeEdit: 0,
          flashScoringEnabled: true,
        });
        setSelectedTemplate(null);
      } else {
        toast.error(data.detail || 'Failed to create test');
      }
    } catch (err) {
      toast.error('Failed: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const selectedTemplateData = flashTemplates.find(t => t.id === selectedTemplate);

  const filteredUsers = users.filter(u => 
    u.name?.toLowerCase().includes(userSearch.toLowerCase()) ||
    u.email?.toLowerCase().includes(userSearch.toLowerCase())
  );

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
            <div>
              <h1 className="text-xl font-semibold">Admin Dashboard</h1>
              <p className="text-sm text-gray-500">Powered by Flash Sandbox</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
              flashEnabled ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
            }`}>
              <span className={`w-2 h-2 rounded-full ${flashEnabled ? 'bg-emerald-400' : 'bg-red-400'}`} />
              Flash: {flashEnabled ? 'Connected' : 'Disconnected'}
            </div>
            <div className="flex items-center gap-1 bg-white/[0.02] rounded-lg p-1">
              <button
                onClick={() => setActiveTab('create')}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  activeTab === 'create' 
                    ? 'bg-violet-500/10 text-violet-400' 
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Create
              </button>
              <button
                onClick={() => setActiveTab('mapper')}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  activeTab === 'mapper' 
                    ? 'bg-violet-500/10 text-violet-400' 
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Test Mapper
              </button>
              <button
                onClick={() => setActiveTab('settings')}
                className={`p-2 rounded-md transition-colors ${
                  activeTab === 'settings' 
                    ? 'bg-violet-500/10 text-violet-400' 
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Settings size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto">
        {activeTab === 'create' && (
          <div className="space-y-6">
            {!flashEnabled && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
                <AlertCircle size={20} className="text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-medium text-amber-300">Flash Not Connected</h3>
                  <p className="text-sm text-amber-400/80 mt-1">
                    Flash sandbox engine is not available. Start the Flash service on localhost:8090 to create tests.
                  </p>
                </div>
              </div>
            )}

            <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Box size={18} className="text-violet-400" />
                  <h2 className="text-lg font-medium">Select Flash Template</h2>
                </div>
                <button
                  onClick={fetchFlashTemplates}
                  disabled={loadingTemplates}
                  className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                >
                  <RefreshCw size={16} className={loadingTemplates ? 'animate-spin' : ''} />
                </button>
              </div>

              {loadingTemplates ? (
                <div className="flex items-center justify-center py-12 text-gray-500">
                  <Loader2 size={20} className="animate-spin mr-2" /> Loading templates...
                </div>
              ) : flashTemplates.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Box size={40} className="mx-auto mb-3 opacity-30" />
                  <p>No Flash templates available</p>
                  <p className="text-sm mt-1">Create templates in Flash dashboard first</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {flashTemplates.map((template) => {
                    const isSelected = selectedTemplate === template.id;
                    const kindMeta = KIND_META[template.kind] || KIND_META.api;
                    const Icon = kindMeta.icon;
                    const colorClass = COLOR_CLASSES[kindMeta.color] || COLOR_CLASSES.emerald;

                    return (
                      <button
                        key={template.id}
                        onClick={() => setSelectedTemplate(isSelected ? null : template.id)}
                        className={`relative p-4 rounded-xl border text-left transition-all ${
                          isSelected 
                            ? `${colorClass} border-opacity-50` 
                            : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <Icon size={16} className={isSelected ? '' : 'text-gray-400'} />
                            <span className="font-medium">{template.id}</span>
                          </div>
                          {isSelected && <CheckCircle size={18} className="flex-shrink-0" />}
                        </div>
                        
                        <p className="text-sm text-gray-400 mb-2">{template.title}</p>
                        
                        <div className="flex items-center gap-2 text-xs">
                          <span className={`px-2 py-0.5 rounded ${colorClass}`}>
                            {template.language}
                          </span>
                          <span className="text-gray-500 flex items-center gap-1">
                            <Play size={10} />
                            {template.warm_count} warm
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {selectedTemplateData && (
              <div className="bg-violet-500/5 rounded-xl border border-violet-500/20 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Info size={16} className="text-violet-400" />
                  <span className="text-sm font-medium text-violet-300">Selected Template</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">ID</span>
                    <p className="text-white font-mono">{selectedTemplateData.id}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Language</span>
                    <p className="text-white">{selectedTemplateData.language}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Type</span>
                    <p className="text-white capitalize">{selectedTemplateData.kind}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Warm Pool</span>
                    <p className="text-white">{selectedTemplateData.warm_count} instances</p>
                  </div>
                </div>
                {selectedTemplateData.description && (
                  <p className="text-sm text-gray-400 mt-3">{selectedTemplateData.description}</p>
                )}
              </div>
            )}

            <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
              <div className="flex items-center gap-2 mb-4">
                <FileText size={18} className="text-violet-400" />
                <h2 className="text-lg font-medium">Test Configuration</h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Test ID *</label>
                  <input
                    type="text"
                    value={testConfig.testId}
                    onChange={(e) => setTestConfig(prev => ({ ...prev, testId: e.target.value }))}
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50 font-mono"
                    placeholder="todo-app-test"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Test Name *</label>
                  <input
                    type="text"
                    value={testConfig.name}
                    onChange={(e) => setTestConfig(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50"
                    placeholder="Build a Todo App"
                  />
                </div>
              </div>

              <div className="mb-4">
                <label className="block text-sm text-gray-400 mb-1.5">Description</label>
                <textarea
                  value={testConfig.description}
                  onChange={(e) => setTestConfig(prev => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50 h-24 resize-none"
                  placeholder="Describe the test problem and objectives..."
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5 flex items-center gap-2">
                    <Clock size={14} />
                    Duration (minutes)
                  </label>
                  <input
                    type="number"
                    value={Math.floor(testConfig.duration / 60)}
                    onChange={(e) => setTestConfig(prev => ({ 
                      ...prev, 
                      duration: (parseInt(e.target.value) || 60) * 60 
                    }))}
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5 flex items-center gap-2">
                    <Code size={14} />
                    Code Mode
                  </label>
                  <select
                    value={testConfig.codeEdit}
                    onChange={(e) => setTestConfig(prev => ({ ...prev, codeEdit: parseInt(e.target.value) }))}
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-violet-500/50"
                  >
                    <option value={0}>Read-only (AI generates)</option>
                    <option value={1}>Editable by candidate</option>
                  </select>
                </div>
              </div>

              <div className="p-4 bg-white/[0.02] rounded-lg border border-white/[0.06]">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="flashScoring"
                    checked={testConfig.flashScoringEnabled}
                    onChange={(e) => setTestConfig(prev => ({ ...prev, flashScoringEnabled: e.target.checked }))}
                    className="rounded border-gray-600 bg-gray-700 text-violet-500 focus:ring-violet-500"
                  />
                  <div className="flex-1">
                    <label htmlFor="flashScoring" className="text-sm font-medium text-white cursor-pointer">
                      Enable Flash Auto-Scoring
                    </label>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Automatically score submissions using the template's test harness
                    </p>
                  </div>
                  <Zap size={18} className="text-amber-400" />
                </div>
              </div>
            </div>

            <button
              onClick={handleCreateTest}
              disabled={isSaving || !testConfig.testId || !testConfig.name || !selectedTemplate}
              className="w-full py-3.5 bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-xl font-semibold hover:from-violet-500 hover:to-purple-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isSaving ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Creating Test...
                </>
              ) : (
                <>
                  <Box size={18} />
                  Create Test from Flash Template
                </>
              )}
            </button>
          </div>
        )}

        {activeTab === 'mapper' && (
          <div className="space-y-6">
            <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Users size={18} className="text-violet-400" />
                  <h2 className="text-lg font-medium">Available Tests</h2>
                </div>
                <button
                  onClick={fetchTests}
                  disabled={loadingTests}
                  className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                >
                  <RefreshCw size={16} className={loadingTests ? 'animate-spin' : ''} />
                </button>
              </div>

              {loadingTests ? (
                <div className="flex items-center justify-center py-12 text-gray-500">
                  <Loader2 size={20} className="animate-spin mr-2" /> Loading tests...
                </div>
              ) : tests.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Box size={40} className="mx-auto mb-3 opacity-30" />
                  <p>No tests available</p>
                  <p className="text-sm mt-1">Create tests first to assign them to users</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {tests.map((test) => (
                    <button
                      key={test.testId}
                      onClick={() => handleTestClick(test)}
                      className="p-4 rounded-xl border border-white/10 bg-white/[0.02] hover:border-violet-500/50 hover:bg-violet-500/5 text-left transition-all"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">{test.name}</span>
                        <Users size={16} className="text-gray-400" />
                      </div>
                      <p className="text-xs text-gray-500 font-mono mb-2">{test.testId}</p>
                      {test.description && (
                        <p className="text-sm text-gray-400 line-clamp-2">{test.description}</p>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="space-y-6">
            <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Zap size={18} className={flashEnabled ? 'text-emerald-400' : 'text-gray-500'} />
                  <h2 className="text-lg font-medium">Flash Sandbox Status</h2>
                </div>
                <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
                  flashEnabled ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${flashEnabled ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  {flashEnabled ? 'Connected' : 'Disconnected'}
                </div>
              </div>
              <p className="text-sm text-gray-500">
                {flashEnabled 
                  ? `Flash engine is running with ${flashTemplates.length} templates available.` 
                  : 'Start the Flash orchestrator on localhost:8090 to enable sandbox creation.'}
              </p>
            </div>

            <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] p-6">
              <h2 className="text-lg font-medium mb-4">Template Warm Pools</h2>
              
              {loadingTemplates ? (
                <div className="flex items-center justify-center py-8 text-gray-500">
                  <Loader2 size={20} className="animate-spin mr-2" /> Loading...
                </div>
              ) : flashTemplates.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No templates configured</p>
              ) : (
                <div className="space-y-4">
                  {flashTemplates.map((template) => (
                    <div 
                      key={template.id}
                      className="flex items-center justify-between p-4 bg-white/[0.02] rounded-lg border border-white/[0.06]"
                    >
                      <div>
                        <p className="font-medium">{template.id}</p>
                        <p className="text-sm text-gray-500">{template.language} - {template.kind}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="range"
                          min="0"
                          max="10"
                          value={template.min_warm}
                          onChange={(e) => {
                            const newVal = parseInt(e.target.value);
                            if (newVal !== template.min_warm) {
                              handleScaleTemplate(template.id, newVal);
                            }
                          }}
                          disabled={scalingTemplate === template.id}
                          className="w-24 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
                        />
                        <span className="w-16 text-center text-sm">
                          {template.warm_count}/{template.min_warm}
                        </span>
                        {scalingTemplate === template.id && (
                          <Loader2 size={14} className="animate-spin text-gray-400" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {showUserModal && selectedTest && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#111] border border-white/10 rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium">Assign Test to Users</h3>
                <p className="text-sm text-gray-500">{selectedTest.name}</p>
              </div>
              <button
                onClick={() => {
                  setShowUserModal(false);
                  setSelectedTest(null);
                  setSelectedUsers([]);
                }}
                className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>

            <div className="p-4 border-b border-white/10">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  placeholder="Search users by name or email..."
                  className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50"
                />
              </div>
            </div>

            <div className="p-4 overflow-y-auto max-h-[40vh]">
              {loadingUsers ? (
                <div className="flex items-center justify-center py-8 text-gray-500">
                  <Loader2 size={20} className="animate-spin mr-2" /> Loading users...
                </div>
              ) : filteredUsers.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Users size={32} className="mx-auto mb-2 opacity-30" />
                  <p>No users found</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredUsers.map((u) => {
                    const isSelected = selectedUsers.includes(u.hash);
                    return (
                      <button
                        key={u.hash}
                        onClick={() => handleUserToggle(u.hash)}
                        className={`w-full p-3 rounded-lg border flex items-center justify-between transition-all ${
                          isSelected 
                            ? 'border-violet-500/50 bg-violet-500/10' 
                            : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                            isSelected ? 'bg-violet-500' : 'bg-white/10'
                          }`}>
                            {isSelected ? (
                              <UserCheck size={16} className="text-white" />
                            ) : (
                              <span className="text-sm font-medium">
                                {u.name?.charAt(0)?.toUpperCase() || 'U'}
                              </span>
                            )}
                          </div>
                          <div className="text-left">
                            <p className="font-medium">{u.name}</p>
                            <p className="text-xs text-gray-500">{u.email}</p>
                          </div>
                        </div>
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          u.role === 'admin' ? 'bg-amber-500/10 text-amber-400' :
                          u.role === 'instructor' ? 'bg-blue-500/10 text-blue-400' :
                          'bg-gray-500/10 text-gray-400'
                        }`}>
                          {u.role}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="p-4 border-t border-white/10 flex items-center justify-between">
              <p className="text-sm text-gray-500">
                {selectedUsers.length} user(s) selected
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    setShowUserModal(false);
                    setSelectedTest(null);
                    setSelectedUsers([]);
                  }}
                  className="px-4 py-2 rounded-lg border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAssignTest}
                  disabled={assigningTest || selectedUsers.length === 0}
                  className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {assigningTest ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Assigning...
                    </>
                  ) : (
                    <>
                      <CheckCircle size={16} />
                      Assign Test
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminDashboard;