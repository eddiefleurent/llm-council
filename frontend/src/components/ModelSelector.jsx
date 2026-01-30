import { useState, useEffect } from 'react';
import { api } from '../api';
import { getProviderColor } from '../providerColors';
import { getModelDisplayName as getDisplayName } from '../utils';
import './ModelSelector.css';

/**
 * Get display name from model object or ID string.
 */
function getModelDisplayName(model) {
  if (!model) return 'Unknown';
  const name = model.name || model.id || model;
  return getDisplayName(name);
}

/**
 * Model selector component with provider grouping.
 * 
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the selector is open
 * @param {Function} props.onClose - Called when selector is closed
 * @param {Function} props.onSelect - Called when a model is selected: (modelId) => void
 * @param {string[]} props.selectedModels - Currently selected model IDs (for highlighting)
 * @param {string} props.title - Title for the selector (e.g., "Add Council Member")
 */
export default function ModelSelector({ 
  isOpen, 
  onClose, 
  onSelect, 
  selectedModels = [],
  title = 'Select Model'
}) {
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load providers when opened
  useEffect(() => {
    if (isOpen) {
      loadProviders();
    }
  }, [isOpen]);

  // Reset to provider list when closed and reopened
  useEffect(() => {
    if (isOpen) {
      setSelectedProvider(null);
    }
  }, [isOpen]);

  const loadProviders = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getModels();
      setProviders(data.providers || []);
    } catch (err) {
      setError('Failed to load models. Please try again.');
      console.error('Failed to load models:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleProviderClick = (provider) => {
    setSelectedProvider(provider);
  };

  const handleModelClick = (model) => {
    onSelect(model.id);
    onClose();
  };

  const handleBack = () => {
    setSelectedProvider(null);
  };

  if (!isOpen) return null;

  return (
    <div className="model-selector-overlay" onClick={onClose}>
      <div className="model-selector-panel" onClick={(e) => e.stopPropagation()}>
        <div className="model-selector-header">
          {selectedProvider ? (
            <>
              <button className="back-btn" onClick={handleBack}>
                ← Back
              </button>
              <h3>{selectedProvider.name}</h3>
            </>
          ) : (
            <>
              <h3>{title}</h3>
              <span className="subtitle">Select Source</span>
            </>
          )}
          <button className="close-btn" aria-label="Close" onClick={onClose}>×</button>
        </div>

        <div className="model-selector-content">
          {loading && (
            <div className="loading-state">Loading models...</div>
          )}
          
          {error && (
            <div className="error-state">
              {error}
              <button onClick={loadProviders}>Retry</button>
            </div>
          )}

          {!loading && !error && !selectedProvider && (
            <div className="provider-grid">
              {providers.map((provider) => {
                const colors = getProviderColor(provider.id);
                return (
                  <button
                    key={provider.id}
                    className="provider-btn"
                    style={{ 
                      backgroundColor: colors.bg, 
                      color: colors.text 
                    }}
                    onClick={() => handleProviderClick(provider)}
                  >
                    <span className="provider-name">{provider.name}</span>
                    <span className="provider-count">{provider.model_count} models</span>
                  </button>
                );
              })}
            </div>
          )}

          {!loading && !error && selectedProvider && (
            <div className="model-list">
              {selectedProvider.models.map((model) => {
                const isSelected = selectedModels.includes(model.id);
                return (
                  <button
                    key={model.id}
                    className={`model-btn ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleModelClick(model)}
                  >
                    <div className="model-info">
                      <span className="model-name">{getModelDisplayName(model)}</span>
                      <span className="model-id">{model.id}</span>
                    </div>
                    <div className="model-meta">
                      <span className="context-length">
                        {(() => {
                          const ctxLen = Number(model.context_length);
                          if (isFinite(ctxLen) && ctxLen > 0) {
                            return `${(ctxLen / 1000).toFixed(0)}k ctx`;
                          }
                          return 'N/A ctx';
                        })()}
                      </span>
                      {isSelected && <span className="selected-badge">Selected</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
