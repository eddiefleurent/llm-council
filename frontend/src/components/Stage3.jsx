import ReactMarkdown from 'react-markdown';
import CopyButton from './CopyButton';
import { getModelDisplayName } from '../utils';
import './Stage3.css';

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {getModelDisplayName(finalResponse.model)}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
        <CopyButton 
          text={finalResponse.response} 
          label="Copy response"
        />
      </div>
    </div>
  );
}
