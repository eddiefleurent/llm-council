import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getModelDisplayName, getErrorMessage } from '../utils';
import './Stage2.css';

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Sort descending by label length so longer labels (e.g. "Response AA") are
  // replaced before shorter ones (e.g. "Response A") to avoid partial matches.
  Object.entries(labelToModel)
    .sort((a, b) => b[0].length - a[0].length)
    .forEach(([label, model]) => {
      const modelShortName = getModelDisplayName(model);
      const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      result = result.replace(new RegExp(escaped, 'g'), `**${modelShortName}**`);
    });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, tournamentRankings, errors, autoCollapse = false }) {
  const [activeTab, setActiveTab] = useState(0);
  const [isCollapsed, setIsCollapsed] = useState(autoCollapse);

  // Collapse once the final answer lands (adjusting state when props change).
  const [prevAutoCollapse, setPrevAutoCollapse] = useState(autoCollapse);
  if (autoCollapse !== prevAutoCollapse) {
    setPrevAutoCollapse(autoCollapse);
    if (autoCollapse) setIsCollapsed(true);
  }

  const displayRankings = (rankings || []).filter(
    (review) => review && (review.review || review.ranking),
  );
  const reviewCount = displayRankings.length;
  const hasFailed = errors && errors.length > 0;
  if (reviewCount === 0 && !hasFailed) {
    return null;
  }

  const totalQueried = reviewCount + (errors?.length || 0);
  const activeIndex = Math.min(activeTab, reviewCount - 1);
  const activeReview = displayRankings[activeIndex];

  // New reviews expose readable evaluation text. Older saved reviews keep their
  // raw payload visible, except empty findings lists that only contained JSON.
  let evaluation = activeReview?.review?.evaluation;
  if (evaluation == null) {
    if (activeReview?.review) {
      evaluation = activeReview.review.findings?.length ? activeReview.ranking : '';
    } else {
      evaluation = activeReview?.ranking ?? '';
    }
  }

  return (
    <div className="stage stage2">
      <div className="stage-header">
        <h2 className="stage-title">
          Stage 2: Evidence Review
          {totalQueried > 0 && (
            <span className="model-count">
              {' '}[{totalQueried} model{totalQueried === 1 ? '' : 's'} queried, {reviewCount} successful
              {hasFailed && `, ${errors.length} failed`}]
            </span>
          )}
        </h2>
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
        <>
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

          {aggregateRankings && aggregateRankings.length > 0 && (
            <div className="aggregate-rankings">
              <h3>Council Rankings</h3>
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

          {tournamentRankings && tournamentRankings.length > 0 &&
            tournamentRankings.some((entry) => entry.total_matchups > 0) && (
            <div className="aggregate-rankings tournament-rankings">
              <h3>Tournament Rankings</h3>
              <p className="stage-description">
                Head-to-head pairwise wins across all peer evaluations:
              </p>
              <div className="aggregate-list">
                {tournamentRankings.map((entry, index) => (
                  <div key={index} className="aggregate-item">
                    <span className="rank-position">#{index + 1}</span>
                    <span className="rank-model">
                      {getModelDisplayName(entry.model)}
                    </span>
                    <span className="rank-score">
                      {Math.round(entry.win_percentage * 100)}% wins
                    </span>
                    <span className="rank-count">
                      ({entry.wins}W–{entry.losses}L{entry.ties ? `–${entry.ties}T` : ''})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {labelToModel && Object.keys(labelToModel).length > 0 && (
            <div className="label-map">
              {Object.entries(labelToModel)
                .sort((a, b) => a[0].localeCompare(b[0]))
                .map(([label, model]) => (
                  <span key={label} className="label-map-item">
                    {label} → {getModelDisplayName(model)}
                  </span>
                ))}
            </div>
          )}

          {activeReview && <details className="raw-output-details">
            <summary>
              Individual reviews ({reviewCount})
            </summary>
            <p className="stage-description">
              Reviewers identify errors, disagreements, gaps, and useful insights using anonymized labels
              (Response A, B, C, etc.) and rank every candidate from best to worst. Below, model names
              are shown in <strong>bold</strong> for readability.
            </p>

            <div className="tabs">
              {displayRankings.map((rank, index) => (
                <button
                  key={index}
                  className={`tab ${activeIndex === index ? 'active' : ''}`}
                  onClick={() => setActiveTab(index)}
                >
                  {getModelDisplayName(rank.model)}
                </button>
              ))}
            </div>

            <div className="tab-content">
              <div className="ranking-model">
                {activeReview.model}
              </div>
              <div className="ranking-content markdown-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {deAnonymizeText(evaluation, labelToModel)}
                </ReactMarkdown>
              </div>

              {activeReview.parsed_ranking &&
                activeReview.parsed_ranking.length > 0 && (
                  <div className="parsed-ranking">
                    <strong>Ranking (best to worst):</strong>
                    <ol>
                      {activeReview.parsed_ranking.map((label, i) => (
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
          </details>}
        </>
      )}
    </div>
  );
}
