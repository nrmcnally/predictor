import { Component } from "react";

/**
 * Per-view crash guard: a render error in one tab shows a styled fallback with
 * a reload action instead of white-screening the whole app for a friend.
 * Keyed by view in App.jsx so switching tabs resets it automatically.
 */
export class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("View crashed:", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="view">
          <div className="empty-state boundary-fallback">
            <span className="empty-icon">✗</span>
            <h3>This corner hit the canvas.</h3>
            <p>
              Something broke rendering this tab. Reload to get back in the
              fight — if it keeps happening, tell the admin what you clicked.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
