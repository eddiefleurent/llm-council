import { useState, useEffect } from 'react';
import { api } from '../api';
import ModelSelector from './ModelSelector';
import { getModelDisplayName } from '../utils';
import './CouncilConfig.css';

/**
 * Provider badge colors - matching ModelSelector
 */
const PROVIDER_COLORS = {
  openai: { bg: '#10a37f', text: '#fff' },
  anthropic: { bg: '#d4a27f', text: '#000' },
  google: { bg: '#4285f4', text: '#fff' },
  'x-ai': { bg: '#000', text: '#fff' },
  'meta-llama': { bg: '#0668e1', text: '#fff' },
  mistralai: { bg: '#f7931a', text: '#000' },
  deepseek: { bg: '#6366f1', text: '#fff' },
  cohere: { bg: '#39594d', text: '#fff' },
};

function getProviderFromModelId(modelId) {
  if (!modelId || typeof modelId !== 'string') return null;
  const parts = modelId.split('/');
  return parts.length > 1 ? parts[0] : null;
}

function getProviderColor(providerId) {
  return PROVIDER_COLORS[providerId] || { bg: '#6b7280', text: '#fff' };
}

/**
 * A compact model chip with provider color coding.
 */
function ModelChip({ modelId, onRemove, showRemove = true }) {
  const provider = getProviderFromModelId(modelId);
  const colors = getProviderColor(provider);
  const displayName = getModelDisplayName(modelId);
  
  return (
    <div 
      className="model-chip"
      style={{ 
        borderColor: colors.bg,
        backgroundColor: `${colors.bg}15`
      }}
    >
      <span 
        className="provider-dot"
        style={{ backgroundColor: colors.bg }}
      />
      <span className="chip-name">{displayName}</span>
      {showRemove && (
        <button 
          className="chip-remove"
          onClick={(e) => {
            e.stopPropagation();
            onRemove(modelId);
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}

/**
 * Council configuration panel.
 * 
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the config panel is open
 * @param {Function} props.onClose - Called when panel is closed
 */
export default function CouncilConfig({ isOpen, onClose }) {
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [defaults, setDefaults] = useState({ council_models: [], chairman_model: '' });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [selectorMode, setSelectorMode] = useState('council'); // 'council' or 'chairman'
  const [hasChanges, setHasChanges] = useState(false);

  // Load config when opened
  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen]);

  // Track changes
  useEffect(() => {
    const configChanged = 
      JSON.stringify(councilModels) !== JSON.stringify(defaults.council_models) ||
      chairmanModel !== defaults.chairman_model;
    setHasChanges(configChanged);
  }, [councilModels, chairmanModel, defaults]);

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const config = await api.getCouncilConfig();
      setCouncilModels(config.council_models || []);
      setChairmanModel(config.chairman_model || '');
      setDefaults(config.defaults || { council_models: [], chairman_model: '' });
    } catch (err) {
      setError('Failed to load council configuration');
      console.error('Failed to load config:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (councilModels.length === 0) {
      setError('At least one council model is required');
      return;
    }
    if (!chairmanModel) {
      setError('Chairman model is required');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await api.updateCouncilConfig(councilModels, chairmanModel);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset to default configuration?')) return;
    
    setSaving(true);
    setError(null);
    try {
      const result = await api.resetCouncilConfig();
      setCouncilModels(result.council_models);
      setChairmanModel(result.chairman_model);
    } catch (err) {
      setError('Failed to reset configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleAddCouncilModel = () => {
    setSelectorMode('council');
    setShowModelSelector(true);
  };

  const handleSelectChairman = () => {
    setSelectorMode('chairman');
    setShowModelSelector(true);
  };

  const handleModelSelected = (modelId) => {
    if (selectorMode === 'council') {
      if (!councilModels.includes(modelId)) {
        setCouncilModels([...councilModels, modelId]);
      }
    } else {
      setChairmanModel(modelId);
    }
  };

  const handleRemoveCouncilModel = (modelId) => {
    setCouncilModels(councilModels.filter(m => m !== modelId));
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="council-config-overlay" onClick={onClose}>
        <div className="council-config-panel" onClick={(e) => e.stopPropagation()}>
          <div className="council-config-header">
            <h2>Council Configuration</h2>
            <button className="close-btn" onClick={onClose}>×</button>
          </div>

          {loading ? (
            <div className="loading-state">Loading configuration...</div>
          ) : (
            <div className="council-config-content">
              {error && (
                <div className="error-banner">{error}</div>
              )}

              {/* Council Members Section */}
              <section className="config-section">
                <div className="section-header">
                  <h3>Council Members</h3>
                  <span className="section-hint">
                    Models that respond to queries and rank each other
                  </span>
                </div>
                
                <div className="models-grid">
                  {councilModels.map((modelId, index) => (
                    <ModelChip
                      key={modelId}
                      modelId={modelId}
                      onRemove={handleRemoveCouncilModel}
                      showRemove={councilModels.length > 1}
                    />
                  ))}
                  
                  <button 
                    className="add-model-btn"
                    onClick={handleAddCouncilModel}
                  >
                    + Add Model
                  </button>
                </div>
              </section>

              {/* Chairman Section */}
              <section className="config-section">
                <div className="section-header">
                  <h3>Chairman</h3>
                  <span className="section-hint">
                    Model that synthesizes the final response
                  </span>
                </div>
                
                <div className="chairman-select" onClick={handleSelectChairman}>
                  {chairmanModel ? (
                    <ModelChip modelId={chairmanModel} showRemove={false} />
                  ) : (
                    <span className="placeholder">Select a chairman model</span>
                  )}
                  <span className="change-btn">Change</span>
                </div>
              </section>

              {/* Actions */}
              <div className="config-actions">
                <button 
                  className="reset-btn"
                  onClick={handleReset}
                  disabled={saving}
                >
                  Reset to Defaults
                </button>
                <div className="action-group">
                  <button 
                    className="cancel-btn"
                    onClick={onClose}
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button 
                    className="save-btn"
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                  >
                    {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <ModelSelector
        isOpen={showModelSelector}
        onClose={() => setShowModelSelector(false)}
        onSelect={handleModelSelected}
        selectedModels={selectorMode === 'council' ? councilModels : [chairmanModel]}
        title={selectorMode === 'council' ? 'Add Council Member' : 'Select Chairman'}
      />
    </>
  );
}
