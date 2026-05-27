function getProbabilityWidth(probability) {
  if (!Number.isFinite(probability)) {
    return "0%";
  }

  return `${Math.max(0, Math.min(100, probability * 100))}%`;
}

function MethodPredictionDetails({
  methodPrediction,
  loading = false,
  error = "",
}) {
  if (loading) {
    return (
      <div className="method-card">
        <p className="eyebrow">Manner of ending</p>
        <h2>Loading method probabilities...</h2>
      </div>
    );
  }

  if (error) {
    return (
      <div className="method-card">
        <p className="eyebrow">Manner of ending</p>
        <h2>Method prediction unavailable</h2>
        <p className="method-note">{error}</p>
      </div>
    );
  }

  if (!methodPrediction) {
    return null;
  }

  return (
    <div className="method-card">
      <div className="method-header">
        <div>
          <p className="eyebrow">Manner of ending</p>
          <h2>
            Most likely: {methodPrediction.predicted_broad_method}{" "}
            <span>{methodPrediction.predicted_broad_method_percentage}</span>
          </h2>
          <p>
            Detailed lean: {methodPrediction.predicted_detailed_method}{" "}
            {methodPrediction.predicted_detailed_method_percentage}
          </p>
        </div>
      </div>

      <div className="method-grid">
        <div className="method-section">
          <h3>Broad method</h3>

          <div className="method-probability-list">
            {methodPrediction.broad_method_probabilities?.map((row) => (
              <div className="method-probability-row" key={row.label}>
                <div className="method-row-label">
                  <strong>{row.label}</strong>
                  <span>{row.percentage}</span>
                </div>

                <div className="method-bar-track">
                  <div
                    className="method-bar-fill"
                    style={{ width: getProbabilityWidth(row.probability) }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="method-section">
          <h3>Detailed method</h3>

          <div className="method-probability-list detailed">
            {methodPrediction.detailed_method_probabilities?.map((row) => (
              <div className="method-probability-row" key={row.label}>
                <div className="method-row-label">
                  <strong>{row.label}</strong>
                  <span>{row.percentage}</span>
                </div>

                <div className="method-bar-track">
                  <div
                    className="method-bar-fill"
                    style={{ width: getProbabilityWidth(row.probability) }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="method-note">{methodPrediction.model_note}</p>
    </div>
  );
}

export default MethodPredictionDetails;
