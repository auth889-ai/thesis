import {Component, type ReactNode} from "react";

/** A page that throws shows what went wrong and a way back, instead of blanking the whole app. */
export class ErrorBoundary extends Component<{children: ReactNode}, {error: Error | null}> {
  state = {error: null as Error | null};
  static getDerivedStateFromError(error: Error) { return {error}; }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="card" role="alert">
        <h3>This page hit a problem</h3>
        <p className="muted">{this.state.error.message}</p>
        <div className="row"><button className="btn primary" onClick={() => this.setState({error: null})}>Try again</button><a className="btn ghost" href="/today">Back to Today</a></div>
      </div>
    );
  }
}
