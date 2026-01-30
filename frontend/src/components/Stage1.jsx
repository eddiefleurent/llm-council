import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import CopyButton from './CopyButton';
import { getModelDisplayName, getErrorMessage } from '../utils';
import './Stage1.css';

export default function Stage1({ responses, errors }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  const totalQueried = responses.length + (errors?.length || 0);
  const hasFailed = errors && errors.length > 0;

  return (
    <div className="stage stage1">
      <h3 className="stage-title">
        Stage 1: Individual Responses
        <span className="model-count">
          {' '}[{totalQueried} models queried, {responses.length} successful
          {hasFailed && `, ${errors.length} failed`}]
        </span>
      </h3>

      {hasFailed && (
        <div className="error-section">
          <div className="error-header">⚠ Failed Models:</div>
          <ul className="error-list">
            {errors.map((error, index) => (
              <li key={index} className="error-item">
                <span className="error-model">{getModelDisplayName(error.model)}</span>
                <span className="error-separator"> - </span>
                <span className="error-message">{getErrorMessage(error)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {getModelDisplayName(resp.model)}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="response-header">
          <div className="model-name" title={responses[activeTab].model}>
            {getModelDisplayName(responses[activeTab].model)}
          </div>
          <CopyButton 
            text={responses[activeTab].response} 
            label="Copy markdown response"
          />
        </div>
        <div className="response-text markdown-content">
          <ReactMarkdown>{responses[activeTab].response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
