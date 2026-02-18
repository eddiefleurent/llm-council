import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import CopyButton from './CopyButton';
import { getModelDisplayName } from '../utils';
import './Stage3.css';

export default function Stage3({ finalResponse, chairmanOnly = false }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!finalResponse) {
    return null;
  }

  return (
    <div className={`stage stage3 ${chairmanOnly ? 'chairman-only' : ''}`}>
      <div className="stage-header">
        <h3 className="stage-title">
          {chairmanOnly ? 'Chairman Response' : 'Stage 3: Final Council Answer'}
        </h3>
        <button
          type="button"
          className="stage-collapse-btn"
          onClick={() => setIsCollapsed((prev) => !prev)}
          aria-expanded={!isCollapsed}
        >
          {isCollapsed ? 'Expand' : 'Collapse'}
        </button>
      </div>
      {!isCollapsed && (
        <div className="final-response">
          <div className="chairman-label">
            {chairmanOnly ? '' : 'Chairman: '}{getModelDisplayName(finalResponse.model)}
          </div>
          <div className="final-text markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{finalResponse.response}</ReactMarkdown>
          </div>
          <CopyButton
            text={finalResponse.response}
            label="Copy response"
          />
        </div>
      )}
    </div>
  );
}
