import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getModelDisplayName } from '../utils';
import './Stage2.css';

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual model name
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = getModelDisplayName(model);
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, errors }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  const totalQueried = rankings.length + (errors?.length || 0);
  const hasFailed = errors && errors.length > 0;

  return (
    <div className="stage stage2">
      <h3 className="stage-title">
        Stage 2: Peer Rankings
        {totalQueried > 0 && (
          <span className="model-count">
            {' '}[{totalQueried} models queried, {rankings.length} successful
            {hasFailed && `, ${errors.length} failed`}]
          </span>
        )}
      </h3>

      {hasFailed && (
        <div className="error-section">
          <div className="error-header">⚠ Failed Models:</div>
          <ul className="error-list">
            {errors.map((error, index) => (
              <li key={index} className="error-item">
                <span className="error-model">{getModelDisplayName(error.model)}</span>
                <span className="error-separator"> - </span>
                <span className="error-message">
                  {error.error_type === 'timeout' && 'Timeout (120s exceeded)'}
                  {error.error_type === 'rate_limit' && 'Rate limit exceeded'}
                  {error.error_type === 'auth' && 'Authentication failed'}
                  {error.error_type === 'payment' && 'Payment required'}
                  {error.error_type === 'not_found' && 'Model not found'}
                  {error.error_type === 'server' && `Server error (${error.status_code})`}
                  {error.error_type === 'unknown' && (error.message || 'Unknown error')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <h4>Raw Evaluations</h4>
      <p className="stage-description">
        Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
        Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
      </p>

      <div className="tabs">
        {rankings.map((rank, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {getModelDisplayName(rank.model)}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="ranking-model">
          {rankings[activeTab].model}
        </div>
        <div className="ranking-content markdown-content">
          <ReactMarkdown>
            {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
          </ReactMarkdown>
        </div>

        {rankings[activeTab].parsed_ranking &&
         rankings[activeTab].parsed_ranking.length > 0 && (
          <div className="parsed-ranking">
            <strong>Extracted Ranking:</strong>
            <ol>
              {rankings[activeTab].parsed_ranking.map((label, i) => (
                <li key={i}>
                  {labelToModel && labelToModel[label]
                    ? getModelDisplayName(labelToModel[label])
                    : label}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aggregate-rankings">
          <h4>Aggregate Rankings (Street Cred)</h4>
          <p className="stage-description">
            Combined results across all peer evaluations (lower score is better):
          </p>
          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => (
              <div key={index} className="aggregate-item">
                <span className="rank-position">#{index + 1}</span>
                <span className="rank-model">
                  {getModelDisplayName(agg.model)}
                </span>
                <span className="rank-score">
                  Avg: {agg.average_rank.toFixed(2)}
                </span>
                <span className="rank-count">
                  ({agg.rankings_count} votes)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
