import { useState, useEffect, useCallback } from 'react';
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
 * @param {string} props.conversationId - The conversation ID (for per-conversation config)
 * @param {boolean} props.isNewConversation - Whether this is a new conversation (no messages yet)
 * @param {boolean} props.isDraftMode - Whether this is a draft conversation (not yet created)
 * @param {Object} props.draftConfig - Draft config object (for draft mode)
 * @param {Function} props.onDraftConfigChange - Callback to update draft config
 */
export default function CouncilConfig({
  isOpen,
  onClose,
  conversationId,
  isNewConversation = false,
  isDraftMode = false,
  draftConfig = null,
  onDraftConfigChange
}) {
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [setAsDefault, setSetAsDefault] = useState(true); // For new conversations only
  // loadedConfig is the baseline for detecting changes (the persisted/saved state)
  const [loadedConfig, setLoadedConfig] = useState({ council_models: [], chairman_model: '', web_search_enabled: false });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [selectorMode, setSelectorMode] = useState('council'); // 'council' or 'chairman'
  const [hasChanges, setHasChanges] = useState(false);

  // Load config when opened
  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let config;
      if (isDraftMode && draftConfig) {
        // Use draft config if available
        config = draftConfig;
      } else if (isDraftMode) {
        // Load global config for new draft
        config = await api.getCouncilConfig();
      } else if (conversationId) {
        // Load conversation-specific config
        config = await api.getConversationConfig(conversationId);
      } else {
        // Fall back to global config
        config = await api.getCouncilConfig();
      }
      const currentCouncil = config.council_models || [];
      const currentChairman = config.chairman_model || '';
      const currentWebSearch = config.web_search_enabled || false;
      setCouncilModels(currentCouncil);
      setChairmanModel(currentChairman);
      setWebSearchEnabled(currentWebSearch);
      // Set the loaded config as the baseline for change detection
      setLoadedConfig({ council_models: currentCouncil, chairman_model: currentChairman, web_search_enabled: currentWebSearch });
    } catch (err) {
      setError('Failed to load configuration');
      console.error('Failed to load config:', err);
    } finally {
      setLoading(false);
    }
  }, [isDraftMode, draftConfig, conversationId]);

  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen, loadConfig]);

  // Track changes against the loaded (persisted) config, not the factory defaults
  useEffect(() => {
    const configChanged =
      JSON.stringify(councilModels) !== JSON.stringify(loadedConfig.council_models) ||
      chairmanModel !== loadedConfig.chairman_model ||
      webSearchEnabled !== loadedConfig.web_search_enabled;
    setHasChanges(configChanged);
  }, [councilModels, chairmanModel, webSearchEnabled, loadedConfig]);

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
      if (isDraftMode) {
        // Save to draft config (will be used when conversation is created)
        const newDraftConfig = {
          council_models: councilModels,
          chairman_model: chairmanModel,
          web_search_enabled: webSearchEnabled,
        };
        onDraftConfigChange(newDraftConfig);

        // Update loaded config baseline
        setLoadedConfig({
          council_models: councilModels,
          chairman_model: chairmanModel,
          web_search_enabled: webSearchEnabled
        });

        // If "Set as default" is checked, also update global
        if (setAsDefault) {
          try {
            await api.updateCouncilConfig(councilModels, chairmanModel, webSearchEnabled);
          } catch (err) {
            console.warn('Failed to update global config:', err);
            // Don't fail the whole save if global update fails
          }
        }
      } else if (conversationId) {
        // Save to conversation-specific config
        const result = await api.updateConversationConfig(
          conversationId,
          councilModels,
          chairmanModel,
          webSearchEnabled
        );
        // Update the loaded config baseline after successful save
        setLoadedConfig({
          council_models: result.council_models,
          chairman_model: result.chairman_model,
          web_search_enabled: result.web_search_enabled
        });

        // If "Set as default" is checked for new conversations, also update global
        if (isNewConversation && setAsDefault) {
          try {
            await api.updateCouncilConfig(councilModels, chairmanModel, webSearchEnabled);
          } catch (err) {
            console.warn('Failed to update global config:', err);
            // Don't fail the whole save if global update fails
          }
        }
      } else {
        // Fall back to global config update (shouldn't happen in normal flow)
        const result = await api.updateCouncilConfig(councilModels, chairmanModel, webSearchEnabled);
        setLoadedConfig({
          council_models: result.council_models,
          chairman_model: result.chairman_model,
          web_search_enabled: result.web_search_enabled
        });
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    // Context-aware confirmation message
    const confirmMessage = isDraftMode || isNewConversation
      ? 'Reset to factory defaults?'
      : 'Load factory defaults? Click Save to apply to this conversation.';

    if (!window.confirm(confirmMessage)) return;

    setSaving(true);
    setError(null);
    try {
      let result;
      let didPersist = false; // Track whether we actually persisted changes

      if (isDraftMode || isNewConversation) {
        // Only persist global defaults when "Set as default" is checked
        if (setAsDefault) {
          result = await api.resetCouncilConfig();
          didPersist = true;
        } else {
          // Just load defaults without persisting
          const globalConfig = await api.getCouncilConfig();
          result = globalConfig.defaults || {
            council_models: globalConfig.council_models,
            chairman_model: globalConfig.chairman_model,
            web_search_enabled: globalConfig.web_search_enabled || false
          };
        }
      } else {
        // For existing conversations, load global config WITHOUT persisting
        // This loads factory defaults into the form but doesn't mutate global config
        const globalConfig = await api.getCouncilConfig();
        result = globalConfig.defaults || {
          council_models: globalConfig.council_models,
          chairman_model: globalConfig.chairman_model,
          web_search_enabled: globalConfig.web_search_enabled || false
        };
      }

      setCouncilModels(result.council_models);
      setChairmanModel(result.chairman_model);
      setWebSearchEnabled(result.web_search_enabled || false);

      // Only update loadedConfig if we actually persisted changes
      // Otherwise, leave loadedConfig unchanged to show unsaved changes
      if (didPersist) {
        setLoadedConfig({
          council_models: result.council_models,
          chairman_model: result.chairman_model,
          web_search_enabled: result.web_search_enabled || false
        });
      }
      // If not persisted, loadedConfig stays as-is, creating hasChanges=true
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
            <h2>{isDraftMode || isNewConversation ? 'Configure New Conversation' : 'Conversation Settings'}</h2>
            <button className="close-btn" aria-label="Close" onClick={onClose}>×</button>
          </div>

          {loading ? (
            <div className="loading-state">Loading configuration...</div>
          ) : (
            <div className="council-config-content">
              {!isNewConversation && !isDraftMode && (
                <div className="config-notice">
                  Changes will only affect this conversation, not other conversations or future ones.
                </div>
              )}
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

              {/* Set as Default (only for new/draft conversations) */}
              {(isNewConversation || isDraftMode) && (
                <section className="config-section">
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={setAsDefault}
                      onChange={(e) => setSetAsDefault(e.target.checked)}
                      disabled={saving}
                    />
                    <span className="checkbox-label">
                      Set as default for future conversations
                    </span>
                  </label>
                  <div className="checkbox-description">
                    When checked, this configuration will be saved as the global default for all new conversations.
                  </div>
                </section>
              )}

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
