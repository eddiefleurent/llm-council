import { useState, useEffect } from 'react';
import { api } from '../api';
import { MODEL_PRESETS } from '../presets';
import ModelSelector from './ModelSelector';
import { getModelDisplayName } from '../utils';
import { getProviderColor } from '../providerColors';
import './CouncilConfig.css';

function getProviderFromModelId(modelId) {
  if (!modelId || typeof modelId !== 'string') return null;
  const parts = modelId.split('/');
  return parts.length > 1 ? parts[0] : null;
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
          aria-label={`Remove model ${displayName}`}
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
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  // loadedConfig is the baseline for detecting changes (the persisted/saved state)
  const [loadedConfig, setLoadedConfig] = useState({ council_models: [], chairman_model: '', web_search_enabled: false });
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

  // Track changes against the loaded (persisted) config, not the factory defaults
  useEffect(() => {
    const configChanged = 
      JSON.stringify(councilModels) !== JSON.stringify(loadedConfig.council_models) ||
      chairmanModel !== loadedConfig.chairman_model ||
      webSearchEnabled !== loadedConfig.web_search_enabled;
    setHasChanges(configChanged);
  }, [councilModels, chairmanModel, webSearchEnabled, loadedConfig]);

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const config = await api.getCouncilConfig();
      const currentCouncil = config.council_models || [];
      const currentChairman = config.chairman_model || '';
      const currentWebSearch = config.web_search_enabled || false;
      setCouncilModels(currentCouncil);
      setChairmanModel(currentChairman);
      setWebSearchEnabled(currentWebSearch);
      // Set the loaded config as the baseline for change detection
      setLoadedConfig({ council_models: currentCouncil, chairman_model: currentChairman, web_search_enabled: currentWebSearch });
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
      const result = await api.updateCouncilConfig(councilModels, chairmanModel, webSearchEnabled);
      // Update the loaded config baseline after successful save
      setLoadedConfig({ 
        council_models: result.council_models, 
        chairman_model: result.chairman_model,
        web_search_enabled: result.web_search_enabled
      });
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
      setWebSearchEnabled(result.web_search_enabled || false);
      // Update the loaded config baseline after reset (now using factory defaults)
      setLoadedConfig({
        council_models: result.council_models,
        chairman_model: result.chairman_model,
        web_search_enabled: result.web_search_enabled || false
      });
    } catch {
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

  const handleApplyPreset = (preset) => {
    setCouncilModels([...preset.council_models]);
    setChairmanModel(preset.chairman_model);
    // Web search toggle is intentionally left unchanged
  };

  /**
   * Determine which preset (if any) matches the current form state exactly.
   * Returns the preset id or null.
   */
  const getActivePresetId = () => {
    for (const preset of MODEL_PRESETS) {
      if (
        chairmanModel === preset.chairman_model &&
        councilModels.length === preset.council_models.length &&
        preset.council_models.every((m, i) => councilModels[i] === m)
      ) {
        return preset.id;
      }
    }
    return null;
  };

  const activePresetId = getActivePresetId();

  if (!isOpen) return null;

  return (
    <>
      <div className="council-config-overlay" onClick={onClose}>
        <div className="council-config-panel" onClick={(e) => e.stopPropagation()}>
          <div className="council-config-header">
            <h2>Council Configuration</h2>
            <button className="close-btn" aria-label="Close" onClick={onClose}>×</button>
          </div>

          {loading ? (
            <div className="loading-state">Loading configuration...</div>
          ) : (
            <div className="council-config-content">
              {error && (
                <div className="error-banner">{error}</div>
              )}

              {/* Quick Presets Section */}
              <section className="config-section">
                <div className="section-header">
                  <h3>Quick Presets</h3>
                  <span className="section-hint">
                    One-click model configurations — click Save to apply
                  </span>
                </div>
                <div className="presets-grid">
                  {MODEL_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      className={`preset-btn${activePresetId === preset.id ? ' preset-active' : ''}`}
                      onClick={() => handleApplyPreset(preset)}
                      title={preset.description}
                    >
                      <span className="preset-icon">{preset.icon}</span>
                      <span className="preset-name">{preset.name}</span>
                    </button>
                  ))}
                </div>
              </section>

              {/* Council Members Section */}
              <section className="config-section">
                <div className="section-header">
                  <h3>Council Members</h3>
                  <span className="section-hint">
                    Models that respond to queries and rank each other
                  </span>
                </div>
                
                <div className="models-grid">
                  {councilModels.map((modelId) => (
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

              {/* Web Search Section */}
              <section className="config-section">
                <div className="section-header">
                  <h3>Web Search</h3>
                  <span className="section-hint">
                    Enable real-time web search for up-to-date information
                  </span>
                </div>
                
                <label className="toggle-row">
                  <span className="toggle-label">
                    <span className="toggle-icon">🌐</span>
                    Enable web search
                  </span>
                  <div className="toggle-switch-wrapper">
                    <input
                      type="checkbox"
                      className="toggle-input"
                      checked={webSearchEnabled}
                      onChange={(e) => setWebSearchEnabled(e.target.checked)}
                    />
                    <span className="toggle-switch"></span>
                  </div>
                </label>
                {webSearchEnabled && (
                  <div className="toggle-description">
                    Models will have access to real-time web search results via OpenRouter&apos;s <code>:online</code> variant.
                  </div>
                )}
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
